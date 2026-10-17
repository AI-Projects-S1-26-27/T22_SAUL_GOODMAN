"""HTTP API + static web UI.

Owner: Engineer 6. Endpoints return the same Pydantic contracts the CLI uses.
Input sizes are bounded so a demo audience can't hang the server.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

from courtroom import __version__
from courtroom.agents import describe_strategies, make_agent
from courtroom.cases import CASES, generate_case, get_case
from courtroom.contracts import CaseFile, TrialResult
from courtroom.engine import run_trial
from courtroom.gametheory import PayoffTable, estimate_payoffs, replicator

WEB_DIR = Path(__file__).resolve().parent.parent / "viz" / "web"


class TrialRequest(BaseModel):
    case_id: str | None = None
    case: CaseFile | None = None  # an examiner's own case file, instead of a library id
    prosecution: str = "aggressive"
    defense: str = "conservative"
    seed: int = Field(default=0, ge=0, le=2**31)

    @field_validator("prosecution", "defense")
    @classmethod
    def _known_strategy(cls, v: str) -> str:
        import random

        make_agent(v, random.Random(0))  # raises ValueError on unknown names
        return v


class GameRequest(BaseModel):
    case_id: str
    strategies: list[str] = Field(default_factory=lambda: ["aggressive", "conservative"], min_length=2, max_length=4)
    seeds: int = Field(default=20, ge=1, le=100)


def _resolve_case(case_id: str) -> CaseFile:
    if case_id.startswith("gen-"):
        try:
            return generate_case(int(case_id[4:]))
        except ValueError:
            raise HTTPException(404, f"bad generated case id {case_id}") from None
    try:
        return get_case(case_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from None


def create_app() -> FastAPI:
    app = FastAPI(title="Saul Goodman Courtroom", version=__version__)

    @app.middleware("http")
    async def no_stale_ui(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Always revalidate UI assets so an edited app.js can't be masked by the browser cache mid-demo.
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-cache")
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/cases")
    def cases() -> list[dict[str, object]]:
        return [
            {
                "id": c.id,
                "title": c.title,
                "synopsis": c.synopsis,
                "case_type": c.case_type,
                "standard": c.standard,
                "tags": c.tags,
            }
            for c in CASES.values()
        ]

    @app.get("/api/cases/{case_id}", response_model=CaseFile)
    def case(case_id: str) -> CaseFile:
        return _resolve_case(case_id)

    @app.get("/api/strategies")
    def strategies() -> list[dict[str, str]]:
        return describe_strategies()

    @app.get("/api/rules")
    def rules_info() -> dict[str, object]:
        """Judge constants and, per objection ground, the chance a flaw is actually caught."""
        from courtroom.agents.base import OBSERVABLE_GROUNDS, PRIOR_DEFECT_RATE, defect_posteriors
        from courtroom.agents.policies import PROFILES
        from courtroom.contracts import ObjectionGround
        from courtroom.judge.rules import PRIOR_LOG_ODDS, THRESHOLD_LOG_ODDS, fmt, sigmoid

        accuracies = sorted({round(c.perception_accuracy, 4) for c in CASES.values()})
        catch: dict[str, list[dict[str, object]]] = {}
        for acc in accuracies:
            posterior_yes, _ = defect_posteriors(acc)
            rows: list[dict[str, object]] = []
            for ground in ObjectionGround:
                observable = ground in OBSERVABLE_GROUNDS
                rows.append(
                    {
                        "ground": ground.value,
                        "observable": observable,
                        "belief_if_flagged": 1.0 if observable else round(posterior_yes, 4),
                        # A flaw is caught when the signal fires AND the belief clears the
                        # profile's objection threshold. Observable grounds always do both.
                        "caught_by": {
                            name: round(1.0 if observable else (acc if posterior_yes >= p.objection_belief else 0.0), 4)
                            for name, p in PROFILES.items()
                        },
                    }
                )
            catch[str(acc)] = rows
        return {
            "prior_defect_rate": PRIOR_DEFECT_RATE,
            "priors": {k.value: {"log_odds": fmt(v), "probability": round(sigmoid(float(v)), 4)} for k, v in PRIOR_LOG_ODDS.items()},
            "standards": {
                k.value: {"log_odds": fmt(v), "probability": round(sigmoid(float(v)), 4)} for k, v in THRESHOLD_LOG_ODDS.items()
            },
            "catch_probability": catch,
        }

    @app.post("/api/validate")
    def validate(payload: dict) -> JSONResponse:
        """Check an examiner's case file through the same validator the library uses."""
        try:
            case = CaseFile.model_validate(payload)
        except ValidationError as exc:
            return JSONResponse(
                status_code=422,
                content={
                    "ok": False,
                    "errors": [
                        {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()
                    ],
                },
            )
        return JSONResponse(
            {
                "ok": True,
                "case_id": case.id,
                "title": case.title,
                "elements": len(case.elements),
                "witnesses": len(case.witnesses),
                "evidence": len(case.evidence),
            }
        )

    @app.post("/api/narrate")
    def narrate_trial(req: TrialRequest) -> JSONResponse:
        """Spoken argument text for a trial, generated after it has already been decided.

        Exhibition only. The trial is run and scored first; this adds words to a finished
        record and can never change a verdict. Falls back to templates with no API key.
        """
        from courtroom.llm import LLMClient, narrate

        case = req.case if req.case is not None else _resolve_case(req.case_id or "")
        result = run_trial(case, req.prosecution, req.defense, req.seed)
        client = LLMClient()
        lines = narrate(result, case, client)
        client.save()
        return JSONResponse(
            {
                "digest": result.digest,
                "narration": {str(k): v for k, v in lines.items()},
                "source": "llm" if client.usage.calls or client.usage.cache_hits else "template",
                "usage": {
                    "calls": client.usage.calls,
                    "cache_hits": client.usage.cache_hits,
                    "unavailable": client.usage.refusals,
                    "cost_estimate_usd": client.usage.cost_estimate(),
                },
            }
        )

    @app.post("/api/trial", response_model=TrialResult)
    def trial(req: TrialRequest) -> TrialResult:
        if req.case is not None:
            return run_trial(req.case, req.prosecution, req.defense, req.seed)
        if not req.case_id:
            raise HTTPException(422, "give either case_id or an inline case")
        return run_trial(_resolve_case(req.case_id), req.prosecution, req.defense, req.seed)

    @app.post("/api/game")
    def game(req: GameRequest) -> JSONResponse:
        if "chaos" in req.strategies:
            raise HTTPException(422, "chaos is a fuzzing agent, not a strategy for equilibrium analysis")
        table: PayoffTable = estimate_payoffs(_resolve_case(req.case_id), req.strategies, seeds=range(req.seeds))
        k = len(req.strategies)
        start = [1.0 / k] * k
        traj = replicator(table.analysis.A, table.analysis.B, start, start, steps=300)
        body = table.model_dump(mode="json")
        body["dynamics"] = [{"x": x, "y": y} for x, y in traj[::5]]
        return JSONResponse(body)

    if WEB_DIR.exists():  # mounted last so /api/* routes take precedence
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="ui")

    return app


app = create_app()
