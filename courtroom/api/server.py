"""HTTP API + static web UI.

Owner: Engineer 6. Endpoints return the same Pydantic contracts the CLI uses.
Input sizes are bounded so a demo audience can't hang the server.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from courtroom import __version__
from courtroom.agents import describe_strategies, make_agent
from courtroom.api import analyst
from courtroom.cases import CASES, generate_case, get_case
from courtroom.contracts import CaseFile, Surprises, TrialResult
from courtroom.engine import run_trial, run_with_agents, verify_chain
from courtroom.gametheory import PayoffTable, estimate_payoffs, replicator
from courtroom.gametheory.bootstrap import STYLES as STYLES4
from courtroom.gametheory.bootstrap import bootstrap_case, collect_samples
from courtroom.gametheory.classic import LABELS as CLASSIC_LABELS
from courtroom.gametheory.classic import classify_case
from courtroom.gametheory.efficiency import constant_sum_check, efficiency
from courtroom.gametheory.finder import find_classic, find_contested
from courtroom.gametheory.lookahead_eval import compare_lookahead
from courtroom.gametheory.matters import measure
from courtroom.gametheory.oracle import run_oracle
from courtroom.gametheory.search import solve_case, trace
from courtroom.judge.explain import build_facts, template_text
from courtroom.judge.tipping import tipping_points
from courtroom.llm import default_client
from courtroom.llm import register as _register_ai  # noqa: F401  (registers the 'llm' strategy; the core never imports this)
from courtroom.llm.draft import MAX_TEXT, draft_case
from courtroom.llm.explainer import explain_in_words
from courtroom.llm.narrator import narrate_case
from courtroom.llm.policy import LLMAgent

WEB_DIR = Path(__file__).resolve().parent.parent / "viz" / "web"
RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "results"


# An inline case (the what-if editor, a drafted case) is bounded so a visitor cannot hang the server with a huge one.
MAX_INLINE_EVIDENCE = 30
MAX_INLINE_WITNESSES = 15
MAX_INLINE_ELEMENTS = 8
MAX_INLINE_CHARS = 60_000
MAX_BODY_BYTES = 1_000_000
MAX_HEAVY_JOBS = 2  # CPU-heavy requests running at once; a third gets a 503 instead of starving /api/health
_HEAVY = threading.BoundedSemaphore(MAX_HEAVY_JOBS)


def heavy() -> Iterator[None]:
    """Dependency for the endpoints that can run for seconds: at most MAX_HEAVY_JOBS at a time, the rest are told to retry."""
    if not _HEAVY.acquire(blocking=False):
        raise HTTPException(503, "the server is busy with other heavy requests; try again in a few seconds")
    try:
        yield
    finally:
        _HEAVY.release()


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


def _known_strategies(names: list[str]) -> list[str]:
    import random

    for v in names:
        if v == "lookahead":
            raise ValueError("lookahead is an exhibition style, not one of the certified styles; it cannot enter a payoff table")
        make_agent(v, random.Random(0))  # raises ValueError on unknown or malformed names
    return names


class ExplainRequest(TrialRequest):
    words: bool = False  # ask the model to word the explanation (checked against the judge's figures)


class DraftRequest(BaseModel):
    text: str = Field(min_length=10, max_length=MAX_TEXT)


class NarrateRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None


class BootstrapRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    seeds: int = Field(default=20, ge=5, le=40)
    resamples: int = Field(default=200, ge=20, le=400)
    surprises: Surprises | bool | None = None


class OracleRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    budget: int = Field(default=12, ge=2, le=30)
    rounds: int = Field(default=2, ge=1, le=4)
    surprises: Surprises | bool | None = None


class GameRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    strategies: list[str] = Field(default_factory=lambda: ["aggressive", "conservative"], min_length=2, max_length=4)
    seeds: int = Field(default=20, ge=1, le=100)
    surprises: Surprises | bool | None = None

    @field_validator("strategies")
    @classmethod
    def _known(cls, v: list[str]) -> list[str]:
        return _known_strategies(v)


class MattersRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    seeds: int = Field(default=8, ge=1, le=8)
    surprises: Surprises | bool | None = None


class ClassicRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    seeds: int = Field(default=20, ge=5, le=30)
    resamples: int = Field(default=60, ge=10, le=100)
    surprises: Surprises | bool | None = None


class ClassicFindRequest(BaseModel):
    start: int = Field(default=0, ge=0, le=100_000)
    count: int = Field(default=12, ge=1, le=30)
    targets: list[str] = Field(default_factory=lambda: ["prisoners-dilemma", "stag-hunt", "battle-of-the-sexes"], max_length=7)
    surprises: Surprises | bool | None = None


class EfficiencyRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    seeds: int = Field(default=20, ge=5, le=30)
    surprises: Surprises | bool | None = None


class TreeRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    max_nodes: int = Field(default=15_000, ge=100, le=15_000)
    picture: bool = False  # also return the nested record of the ordered alpha-beta search, for drawing


class LookaheadRequest(BaseModel):
    case_id: str = ""
    case: CaseFile | None = None
    seeds: int = Field(default=8, ge=4, le=12)
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


def _run(req: TrialRequest, case: CaseFile | None = None) -> TrialResult:
    """Run a trial. A language-model lawyer goes through its own path so its fallback counts can be reported."""
    case = case or _pick_case(req.case_id, req.case)
    sur = _surprises(req.surprises)
    if "llm" not in (req.prosecution, req.defense):
        return run_trial(case, req.prosecution, req.defense, req.seed, sur)
    import random

    client = default_client()
    client.start_trial()
    agents: dict[str, LLMAgent] = {}
    built = {}
    for side, name in (("prosecution", req.prosecution), ("defense", req.defense)):
        if name == "llm":
            agents[side] = built[side] = LLMAgent(client, random.Random(f"{req.seed}:agent:{side}"))
        else:
            built[side] = make_agent(name, random.Random(f"{req.seed}:agent:{side}"))
    result = run_with_agents(case, built["prosecution"], built["defense"], req.seed, sur, req.prosecution, req.defense)
    client.save()
    reports = {side: a.report() for side, a in agents.items()}
    return result.model_copy(update={"certified": False, "ai": {"sides": reports, "fallback_rate": max(r["fallback_rate"] for r in reports.values())}})


def create_app() -> FastAPI:
    app = FastAPI(title="Saul Goodman Courtroom", version=__version__)
    # the server is for this computer only: a request that names another host (DNS rebinding) is refused
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def limit_body(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # a case is at most MAX_INLINE_CHARS; nothing legitimate is anywhere near this, so refuse before reading
        n = request.headers.get("content-length")
        if n is not None and n.isdigit() and int(n) > MAX_BODY_BYTES:
            return JSONResponse({"detail": f"request body too large (over {MAX_BODY_BYTES} bytes)"}, status_code=413)
        try:
            return await call_next(request)
        except RecursionError:
            return JSONResponse({"detail": "request body too deeply nested"}, status_code=422)

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
        return _run(req)

    @app.get("/api/ai")
    def ai_status() -> dict[str, object]:
        """Does a language-model backend answer right now? The page offers the AI lawyer and case drafting only if so."""
        return default_client().status()

    @app.post("/api/verify")
    def verify(req: TrialRequest) -> dict[str, object]:
        """Run the same trial twice and compare: the digests must match and the hash chain must hold."""
        case = _pick_case(req.case_id, req.case)
        first, second = _run(req, case), _run(req, case)
        return {
            "digest_first": first.digest,
            "digest_second": second.digest,
            "identical": first.digest == second.digest and first.model_dump_json(exclude={"ai"}) == second.model_dump_json(exclude={"ai"}),
            "chain_valid": verify_chain(first.events) and verify_chain(second.events),
            "events": len(first.events),
        }

    @app.post("/api/matters")
    def matters(req: MattersRequest) -> JSONResponse:
        """Does strategy matter in this case? Measured from fresh runs of every pairing of the three styles."""
        case = _pick_case(req.case_id, req.case)
        return JSONResponse(measure(case, seeds=tuple(range(req.seeds)), surprises=_surprises(req.surprises)).model_dump(mode="json"))

    @app.post("/api/find")
    def find(req: FindRequest, _: None = Depends(heavy)) -> JSONResponse:
        """Search generated cases for contested ones (bounded: at most 60 candidates and about 25 seconds)."""
        report = find_contested(req.start, req.count, req.top, surprises=_surprises(req.surprises), time_budget=25.0)
        return JSONResponse(report.model_dump(mode="json"))

    @app.post("/api/classic")
    def classic(req: ClassicRequest, _: None = Depends(heavy)) -> JSONResponse:
        """Which classic game does each two-by-two corner of this case's measured table resemble? (bounded: 30 seeds at most)"""
        case = _pick_case(req.case_id, req.case)
        sur = _surprises(req.surprises)
        samples = collect_samples(case, STYLES4, tuple(range(req.seeds)), surprises=sur)
        res = classify_case(case.id, samples, STYLES4, STYLES4, n_resamples=req.resamples, surprises=sur is not None)
        return JSONResponse(res.model_dump(mode="json"))

    @app.post("/api/classic/find")
    def classic_find(req: ClassicFindRequest, _: None = Depends(heavy)) -> JSONResponse:
        """Search generated cases for a prisoner's dilemma, stag hunt or battle of the sexes (bounded: about 25 seconds)."""
        bad = [t for t in req.targets if t not in CLASSIC_LABELS]
        if bad:
            raise HTTPException(422, f"unknown classic game {bad[0]}")
        rep = find_classic(tuple(req.targets), req.start, req.count, surprises=_surprises(req.surprises), time_budget=25.0, n_resamples=40, confirm_seeds=tuple(range(1000, 1020)))
        return JSONResponse(rep.model_dump(mode="json"))

    @app.post("/api/efficiency")
    def efficiency_route(req: EfficiencyRequest, _: None = Depends(heavy)) -> JSONResponse:
        """Pareto-efficient cells, whether each equilibrium is efficient, and the security values (bounded: 30 seeds at most)."""
        case = _pick_case(req.case_id, req.case)
        t = estimate_payoffs(case, STYLES4, seeds=range(req.seeds), surprises=_surprises(req.surprises))
        win = {(c.row, c.col): c.prosecution_win_rate for c in t.cells}
        W = [[win[(r, c)] for c in t.col_strategies] for r in t.row_strategies]
        return JSONResponse(
            {
                "case_id": case.id,
                "row_strategies": t.row_strategies,
                "col_strategies": t.col_strategies,
                "A": t.analysis.A,
                "B": t.analysis.B,
                "accuser_win_rate": W,
                "efficiency": efficiency(t.analysis).model_dump(mode="json"),
                "constant_sum": constant_sum_check(W).model_dump(mode="json"),
            }
        )

    @app.post("/api/tree")
    def tree(req: TreeRequest, _: None = Depends(heavy)) -> JSONResponse:
        """The trial as a game tree on the open-file relaxation (bounded: 15,000 nodes, so only small cases are solved exactly)."""
        case = _pick_case(req.case_id, req.case)
        rep = solve_case(case, max_nodes=req.max_nodes, with_line=True)
        body = rep.model_dump(mode="json")
        if req.picture and rep.alphabeta_ordered_nodes is not None and rep.alphabeta_ordered_nodes <= 300:
            body["picture"] = trace(case, max_nodes=2000)
        return JSONResponse(body)

    @app.post("/api/lookahead")
    def lookahead_route(req: LookaheadRequest, _: None = Depends(heavy)) -> JSONResponse:
        """Does the lookahead lawyer beat the four hand-written styles? Exhibition, not certified (bounded: 12 seeds)."""
        case = _pick_case(req.case_id, req.case)
        rep = compare_lookahead(case, tuple(range(req.seeds)), _surprises(req.surprises), workers=1)
        return JSONResponse(rep.model_dump(mode="json"))

    @app.post("/api/explain")
    def explain(req: ExplainRequest) -> JSONResponse:
        """Why this verdict (the judge's own numbers in plain words) and the smallest single change that would flip it."""
        case = _pick_case(req.case_id, req.case)
        result = _run(req, case)
        facts = build_facts(result, case)
        said = explain_in_words(facts, default_client()) if req.words and default_client().available() else None
        return JSONResponse(
            {
                "digest": result.digest,
                "text": said["text"] if said else template_text(facts),
                "text_source": said["source"] if said else "template",
                "text_note": said["note"] if said else None,
                "facts": facts.model_dump(mode="json"),
                "tipping": [t.model_dump(mode="json") for t in tipping_points(case, result)],
            }
        )

    @app.post("/api/case/draft")
    def draft(req: DraftRequest) -> JSONResponse:
        """A case written from plain English by the model, validated by the contracts. The page puts it in the editor."""
        client = default_client()
        if not client.available():
            return JSONResponse({"detail": "no language model answers", "reason": client.last_error}, status_code=503)
        result = draft_case(req.text, client)
        client.save()
        if result.case is None:
            return JSONResponse({"detail": result.error, "problems": result.problems, "repairs": result.repairs}, status_code=422)
        return JSONResponse(
            {"case": result.case.model_dump(mode="json"), "repairs": result.repairs, "notes": result.notes, "model": client.last_model, "backend": client.last_source}
        )

    @app.post("/api/narrate")
    def narrate(req: NarrateRequest) -> JSONResponse:
        """Model-worded spoken lines for a case with no script. Lines that add any fact are refused."""
        client = default_client()
        if not client.available():
            return JSONResponse({"detail": "no language model answers", "reason": client.last_error}, status_code=503)
        return JSONResponse(narrate_case(_pick_case(req.case_id, req.case), client))

    @app.post("/api/bootstrap")
    def bootstrap(req: BootstrapRequest, _: None = Depends(heavy)) -> JSONResponse:
        """How often the equilibrium label survives resampling the seeds (bounded: 40 seeds at most)."""
        case = _pick_case(req.case_id, req.case)
        res = bootstrap_case(case, seeds=tuple(range(req.seeds)), n_resamples=req.resamples, workers=1, surprises=_surprises(req.surprises))
        return JSONResponse(res.model_dump(mode="json"))

    @app.post("/api/oracle")
    def oracle(req: OracleRequest, _: None = Depends(heavy)) -> JSONResponse:
        """A small, bounded best-response search run live. The committed results use a larger budget (see /api/results)."""
        case = _pick_case(req.case_id, req.case)
        rep = run_oracle(case, budget=req.budget, surprises=_surprises(req.surprises), train=tuple(range(4)), heldout=tuple(range(100, 108)), workers=4, max_rounds=req.rounds)
        return JSONResponse(rep.model_dump(mode="json"))

    @app.get("/api/results")
    def results() -> dict[str, object]:
        """The certified results committed under results/ (bootstrap, sensitivity, best-response), for the lab."""
        out: dict[str, object] = {}
        for path in sorted(RESULTS_DIR.glob("*.json")):
            out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        oracle_dir = RESULTS_DIR / "oracle"
        if oracle_dir.is_dir():
            out["oracle"] = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(oracle_dir.glob("*.json"))}
        return out

    @app.post("/api/game")
    def game(req: GameRequest, _: None = Depends(heavy)) -> JSONResponse:
        if "llm" in req.strategies:
            raise HTTPException(422, "the AI lawyer is an exhibition, not a certified strategy; it cannot enter a payoff table")
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
