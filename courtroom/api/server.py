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
from pydantic import BaseModel, Field, field_validator

from courtroom import __version__
from courtroom.agents import describe_strategies, make_agent
from courtroom.api import analyst
from courtroom.cases import CASES, generate_case, get_case
from courtroom.contracts import CaseFile, Surprises, TrialResult
from courtroom.engine import run_trial, verify_chain
from courtroom.gametheory import PayoffTable, estimate_payoffs, replicator
from courtroom.gametheory.finder import find_contested
from courtroom.gametheory.matters import measure
from courtroom.judge.explain import build_facts, template_text
from courtroom.judge.tipping import tipping_points

WEB_DIR = Path(__file__).resolve().parent.parent / "viz" / "web"


# An inline case (the what-if editor, a drafted case) is bounded so a visitor cannot hang the server with a huge one.
MAX_INLINE_EVIDENCE = 30
MAX_INLINE_WITNESSES = 15
MAX_INLINE_ELEMENTS = 8
MAX_INLINE_CHARS = 60_000


class TrialRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None  # an inline case replaces case_id; validated by the contracts like any other
    prosecution: str = "aggressive"
    defense: str = "conservative"
    seed: int = Field(default=0, ge=0, le=2**31)
    surprises: Surprises | bool | None = None  # True: the default chances; None/False: the plain rulebook

    @field_validator("prosecution", "defense")
    @classmethod
    def _known_strategy(cls, v: str) -> str:
        import random

        make_agent(v, random.Random(0))  # raises ValueError on unknown names
        return v


class GameRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    strategies: list[str] = Field(default_factory=lambda: ["aggressive", "conservative"], min_length=2, max_length=4)
    seeds: int = Field(default=20, ge=1, le=100)
    surprises: Surprises | bool | None = None


class MattersRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    seeds: int = Field(default=5, ge=1, le=8)
    surprises: Surprises | bool | None = None


class FindRequest(BaseModel):
    start: int = Field(default=0, ge=0, le=100_000)
    count: int = Field(default=30, ge=1, le=60)
    top: int = Field(default=5, ge=1, le=8)
    surprises: Surprises | bool | None = None


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


def _surprises(value: Surprises | bool | None) -> Surprises | None:
    if value is True:
        return Surprises()
    return value if isinstance(value, Surprises) else None


def _pick_case(case_id: str, inline: CaseFile | None) -> CaseFile:
    """The case a request is about: the inline one if given (size-bounded), else the library or generated one."""
    if inline is None:
        if not case_id:
            raise HTTPException(422, "give a case_id or an inline case")
        return _resolve_case(case_id)
    if len(inline.evidence) > MAX_INLINE_EVIDENCE or len(inline.witnesses) > MAX_INLINE_WITNESSES or len(inline.elements) > MAX_INLINE_ELEMENTS:
        raise HTTPException(422, f"inline case too large (at most {MAX_INLINE_EVIDENCE} exhibits, {MAX_INLINE_WITNESSES} witnesses, {MAX_INLINE_ELEMENTS} points)")
    if len(inline.model_dump_json()) > MAX_INLINE_CHARS:
        raise HTTPException(422, f"inline case too large (over {MAX_INLINE_CHARS} characters)")
    return inline


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

    @app.post("/api/trial", response_model=TrialResult)
    def trial(req: TrialRequest) -> TrialResult:
        return run_trial(_pick_case(req.case_id, req.case), req.prosecution, req.defense, req.seed, _surprises(req.surprises))

    @app.post("/api/verify")
    def verify(req: TrialRequest) -> dict[str, object]:
        """Run the same trial twice and compare: the digests must match and the hash chain must hold."""
        case, sur = _pick_case(req.case_id, req.case), _surprises(req.surprises)
        first = run_trial(case, req.prosecution, req.defense, req.seed, sur)
        second = run_trial(case, req.prosecution, req.defense, req.seed, sur)
        return {
            "digest_first": first.digest,
            "digest_second": second.digest,
            "identical": first.digest == second.digest and first.model_dump_json() == second.model_dump_json(),
            "chain_valid": verify_chain(first.events) and verify_chain(second.events),
            "events": len(first.events),
        }

    @app.post("/api/matters")
    def matters(req: MattersRequest) -> JSONResponse:
        """Does strategy matter in this case? Measured from fresh runs of every pairing of the three styles."""
        case = _pick_case(req.case_id, req.case)
        return JSONResponse(measure(case, seeds=tuple(range(req.seeds)), surprises=_surprises(req.surprises)).model_dump(mode="json"))

    @app.post("/api/find")
    def find(req: FindRequest) -> JSONResponse:
        """Search generated cases for contested ones (bounded: at most 60 candidates and about 25 seconds)."""
        report = find_contested(req.start, req.count, req.top, surprises=_surprises(req.surprises), time_budget=25.0)
        return JSONResponse(report.model_dump(mode="json"))

    @app.post("/api/explain")
    def explain(req: TrialRequest) -> JSONResponse:
        """Why this verdict (the judge's own numbers in plain words) and the smallest single change that would flip it."""
        case = _pick_case(req.case_id, req.case)
        result = run_trial(case, req.prosecution, req.defense, req.seed, _surprises(req.surprises))
        facts = build_facts(result, case)
        return JSONResponse(
            {
                "digest": result.digest,
                "text": template_text(facts),
                "facts": facts.model_dump(mode="json"),
                "tipping": [t.model_dump(mode="json") for t in tipping_points(case, result)],
            }
        )

    @app.post("/api/game")
    def game(req: GameRequest) -> JSONResponse:
        if "chaos" in req.strategies:
            raise HTTPException(422, "chaos is a fuzzing agent, not a strategy for equilibrium analysis")
        table: PayoffTable = estimate_payoffs(
            _pick_case(req.case_id, req.case), req.strategies, seeds=range(req.seeds), surprises=_surprises(req.surprises)
        )
        k = len(req.strategies)
        start = [1.0 / k] * k
        traj = replicator(table.analysis.A, table.analysis.B, start, start, steps=300)
        body = table.model_dump(mode="json")
        body["dynamics"] = [{"x": x, "y": y} for x, y in traj[::5]]
        return JSONResponse(body)

    @app.post("/api/analyst")
    def ask_analyst(req: analyst.AnalystRequest) -> JSONResponse:
        # The strategy lab's chat box. A 503 tells the page to fall back to its built-in analyst.
        try:
            return JSONResponse(analyst.ask(req))
        except analyst.AnalystUnavailable as exc:
            return JSONResponse({"detail": "analyst unavailable", "reasons": exc.reasons}, status_code=503)

    if WEB_DIR.exists():  # mounted last so /api/* routes take precedence
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="ui")

    return app


app = create_app()
