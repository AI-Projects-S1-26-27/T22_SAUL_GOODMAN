"""Command-line interface: ``python -m courtroom <command>``.

Owner: Engineer 6.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console

from courtroom.cases import CASES, generate_case, get_case
from courtroom.contracts import CaseFile
from courtroom.engine import run_trial, verify_chain

# Windows consoles default to cp1252; never let a glyph crash a live demo.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

console = Console()
EXPORT_DIR = Path(__file__).resolve().parent / "viz" / "web" / "data"

# The 4x4 game the proposal analyses (Sec. 7); Chaos is robustness-only and never in the matrix.
ANALYSIS_STRATEGIES = "aggressive,conservative,adaptive,mixed:0.5"


def _case(case_id: str) -> CaseFile:
    return generate_case(int(case_id[4:])) if case_id.startswith("gen-") else get_case(case_id)


def cmd_cases(_: argparse.Namespace) -> int:
    for c in CASES.values():
        console.print(f"[bold]{c.id:24s}[/] {c.case_type.value:8s} {c.standard.value:24s} {c.title}")
        console.print(f"    [grey50]{', '.join(c.tags)}[/]")
    console.print("[grey50]Generated cases: gen-<seed>, e.g. gen-42[/]")
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    from courtroom.viz.terminal import print_summary, replay

    case = _case(a.case)
    result = run_trial(case, a.prosecution, a.defense, a.seed)
    if getattr(a, "narrate", False):
        from courtroom.llm import LLMClient, narrate

        client = LLMClient()
        lines = narrate(result, case, client)
        client.save()
        for ev in result.events:
            if ev.seq in lines:
                colour = "red" if ev.actor and ev.actor.value == "prosecution" else "cyan"
                who = "PROSECUTION" if ev.actor and ev.actor.value == "prosecution" else "DEFENSE"
                console.print(f"  [{colour}]{who:11s}[/] [italic]{lines[ev.seq]}[/]")
        console.print(f"\n[grey50]{client.usage.summary()}[/]")
        if not client.usage.calls and not client.usage.cache_hits:
            console.print("[yellow]No API key and no cache hit: every line above is a template, not model output.[/]")
        return 0
    if a.json:
        Path(a.json).write_text(result.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"wrote {a.json}")
    if a.live:
        replay(result, delay=a.delay, console=console)
    else:
        for ev in result.events:
            actor = ev.actor.value if ev.actor else "court"
            console.print(
                f"[grey50]{ev.seq:3d}[/] [{'red' if actor == 'prosecution' else 'cyan' if actor == 'defense' else 'yellow'}]{actor:11s}[/] {ev.summary}"
            )
        print_summary(result, console)
    return 0


def cmd_game(a: argparse.Namespace) -> int:
    from courtroom.gametheory import estimate_payoffs
    from courtroom.viz.terminal import print_game

    table = estimate_payoffs(_case(a.case), a.strategies.split(","), seeds=range(a.seeds), workers=a.workers)
    print_game(table, console)
    if a.json:
        Path(a.json).write_text(table.model_dump_json(indent=2), encoding="utf-8")
    return 0


def cmd_tournament(a: argparse.Namespace) -> int:
    from courtroom.gametheory import tournament
    from courtroom.viz.terminal import print_game

    for table in tournament(strategies=a.strategies.split(","), seeds=range(a.seeds), workers=a.workers):
        print_game(table, console)
        console.rule()
    return 0


def cmd_llm_models(a: argparse.Namespace) -> int:
    """List the Gemini models this key can actually call. Pricing is not exposed by the API."""
    import os

    if not os.environ.get("GEMINI_API_KEY"):
        console.print("[red]GEMINI_API_KEY is not set.[/] The LLM layer falls back to templates without it.")
        return 2
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    names = sorted(
        m.name for m in client.models.list()
        if not getattr(m, "supported_actions", None) or "generateContent" in m.supported_actions
    )
    for name in names:
        mark = "[green] <- configured[/]" if name.endswith(a.model or "") and a.model else ""
        console.print(f"  {name}{mark}")
    console.print(
        f"\n[grey50]{len(names)} models. The API reports no pricing: check the Gemini pricing page "
        f"for your chosen model and set COURTROOM_LLM_RATES=\"<in>,<out>\" per million tokens.[/]"
    )
    return 0


def cmd_llm_exhibition(a: argparse.Namespace) -> int:
    from courtroom.llm import LLMClient
    from courtroom.llm.exhibition import run_exhibition

    client = LLMClient(cost_ceiling=a.cost_ceiling, max_calls_per_run=a.max_calls)
    done = [0]

    def progress(side, opponent, seed, result, agent, cl):
        done[0] += 1
        console.print(
            f"  [{done[0]:3d}] llm as {side:11s} vs {opponent:14s} seed {seed} -> "
            f"{result.verdict.outcome.value:20s} calls {cl.usage.calls:4d} "
            f"cached {cl.usage.cache_hits:4d} fallback {agent.fallback_rate:5.1%}"
        )

    report = run_exhibition(
        case_id=a.case, seeds=range(a.seeds), client=client,
        max_calls=a.max_calls, out_path=Path(a.out), on_trial=progress,
    )
    console.print(f"[bold]{report['model']}[/]  case {report['case_id']}  seeds {len(report['seeds'])}")
    for cell in report["cells"]:
        console.print(
            f"  llm as {cell['llm_side']:11s} vs {cell['opponent']:14s} "
            f"win {cell['llm_win_rate']:6.1%}  payoff {cell['mean_llm_payoff']:+7.2f}  "
            f"fallback {cell['fallback_rate']:6.1%}"
        )
    console.print(f"\n{client.usage.summary()}")
    console.print(f"overall fallback rate: {report['overall_fallback_rate']:.1%}")
    if report["aborted"]:
        console.print(f"[yellow]ABORTED: {report['aborted']}[/]")
    from courtroom.llm.report import render

    doc = Path("LLM_EXHIBITION.md")
    render(Path(a.out), doc)
    console.print(f"[green]wrote {a.out} and {doc}[/]")
    if report["overall_fallback_rate"] > 0.30:
        console.print(
            f"[red]FALLBACK RATE {report['overall_fallback_rate']:.1%} EXCEEDS 30%[/] - "
            "a large share of these moves are Adaptive's, not Gemini's."
        )
    return 0


def cmd_bootstrap(a: argparse.Namespace) -> int:
    from courtroom.gametheory import bootstrap_library

    reports = bootstrap_library(
        case_ids=a.cases.split(",") if a.cases else None,
        strategies=tuple(a.strategies.split(",")),
        seeds=range(a.seeds),
        n_resamples=a.resamples,
        workers=a.workers,
        rng_seed=a.rng_seed,
    )
    for r in reports:
        colour = "green" if r.stability >= 0.9 else "yellow" if r.stability >= 0.7 else "red"
        console.print(
            f"[bold]{r.case_id:24s}[/] {r.baseline_label:20s} "
            f"stability [{colour}]{r.stability:6.1%}[/]  {dict(sorted(r.label_counts.items()))}"
        )
    if a.json:
        payload = [json.loads(r.model_dump_json()) for r in reports]
        Path(a.json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"wrote {a.json}")
    return 0


def cmd_sensitivity(a: argparse.Namespace) -> int:
    from courtroom.gametheory import sweep

    report = sweep(
        case_ids=a.cases.split(",") if a.cases else None,
        strategies=tuple(a.strategies.split(",")),
        seeds=range(a.seeds),
        delta=a.delta,
    )
    console.print("[bold]baseline labels[/]")
    for cid, label in report.baseline.items():
        console.print(f"  {cid:24s} {label}")
    console.print("\n[bold]variations that moved a label[/]")
    for v in report.variations:
        if v.changed:
            console.print(f"  [yellow]{v.parameter:24s} {v.setting:10s}[/] -> {', '.join(v.changed)}")
    console.print(
        f"\n[green]robust ({len(report.robust_cases)})[/]: {', '.join(report.robust_cases) or '-'}"
        f"\n[red]parameter-dependent ({len(report.fragile_cases)})[/]: {', '.join(report.fragile_cases) or '-'}"
    )
    if a.json:
        Path(a.json).write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"wrote {a.json}")
    return 0


def cmd_analysis(a: argparse.Namespace) -> int:
    """One reproducible command: full matrices, bootstrap stability and the sweep, all to disk."""
    from courtroom.gametheory import bootstrap_library, estimate_payoffs, sweep

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    strategies = tuple(a.strategies.split(","))
    ids = a.cases.split(",") if a.cases else list(CASES)

    console.rule(f"payoff matrices — {len(strategies)} strategies x {a.seeds} common seeds")
    tables = []
    for cid in ids:
        table = estimate_payoffs(get_case(cid), strategies, seeds=range(a.seeds), workers=a.workers)
        tables.append(json.loads(table.model_dump_json()))
        an = table.analysis
        dom = f" row-dominant={an.row_dominant}" if an.row_dominant else ""
        dom += f" col-dominant={an.col_dominant}" if an.col_dominant else ""
        console.print(f"  {cid:24s} equilibria={len(an.equilibria):2d}{dom or ' no dominant strategy'}")
    (out / "payoffs.json").write_text(json.dumps(tables, indent=2), encoding="utf-8")

    console.rule(f"bootstrap — {a.resamples} resamples of {a.seeds} seeds")
    reports = bootstrap_library(
        case_ids=ids, strategies=strategies, seeds=range(a.seeds), n_resamples=a.resamples,
        workers=a.workers, rng_seed=a.rng_seed,
    )
    for r in reports:
        console.print(f"  {r.case_id:24s} {r.baseline_label:20s} stability {r.stability:6.1%}")
    (out / "bootstrap.json").write_text(
        json.dumps([json.loads(r.model_dump_json()) for r in reports], indent=2), encoding="utf-8"
    )

    console.rule(f"sensitivity sweep — +/-{a.delta:.0%} and BRD 80-95%")
    # No workers here: patched constants do not cross a process boundary (see sensitivity._labels).
    report = sweep(case_ids=ids, strategies=strategies, seeds=range(a.sweep_seeds), delta=a.delta)
    (out / "sensitivity.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    console.print(
        f"  robust: {', '.join(report.robust_cases) or '-'}\n"
        f"  parameter-dependent: {', '.join(report.fragile_cases) or '-'}"
    )
    console.print(f"\n[green]wrote {out}/payoffs.json, bootstrap.json, sensitivity.json[/]")
    return 0


def cmd_stress(a: argparse.Namespace) -> int:
    from courtroom.gametheory import stress

    report = stress(n_cases=a.cases)
    console.print_json(report.model_dump_json())
    return 0 if report.crashes == 0 and report.invariant_failures == 0 else 1


def cmd_verify(a: argparse.Namespace) -> int:
    case = _case(a.case)
    first = run_trial(case, a.prosecution, a.defense, a.seed)
    second = run_trial(case, a.prosecution, a.defense, a.seed)
    same = first.digest == second.digest and first.model_dump_json() == second.model_dump_json()
    chain_ok = verify_chain(first.events)
    console.print(f"digest run 1: {first.digest}\ndigest run 2: {second.digest}")
    console.print(
        f"bit-identical results: {'[green]YES' if same else '[red]NO'}[/]   hash chain valid: {'[green]YES' if chain_ok else '[red]NO'}[/]"
    )
    return 0 if same and chain_ok else 1


def cmd_export(a: argparse.Namespace) -> int:
    """Pre-compute a static bundle so the web UI works with no server (demo fallback)."""
    from fastapi.testclient import TestClient

    from courtroom.agents import describe_strategies
    from courtroom.api.server import app as _api
    from courtroom.gametheory import estimate_payoffs, replicator

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, object] = {
        "cases": [json.loads(c.model_dump_json()) for c in CASES.values()],
        "strategies": describe_strategies(),
        # Judge constants + per-ground catch probability, so the judge tab works offline too.
        "rules": TestClient(_api).get("/api/rules").json(),
        "trials": {},
        "games": {},
    }
    pairs = [
        ("aggressive", "conservative"),
        ("aggressive", "aggressive"),
        ("conservative", "aggressive"),
        ("conservative", "conservative"),
        ("adaptive", "adaptive"),
        ("chaos", "aggressive"),
    ]
    for cid, case in CASES.items():
        for p, d in pairs:
            r = run_trial(case, p, d, seed=0)
            bundle["trials"][f"{cid}|{p}|{d}|0"] = json.loads(r.model_dump_json())  # type: ignore[index]
        table = estimate_payoffs(case, ("aggressive", "conservative"), seeds=range(a.seeds), workers=a.workers)
        body = json.loads(table.model_dump_json())
        body["dynamics"] = [
            {"x": x, "y": y} for x, y in replicator(table.analysis.A, table.analysis.B, [0.5, 0.5], [0.5, 0.5], steps=300)[::5]
        ]
        bundle["games"][cid] = body  # type: ignore[index]
        console.print(f"exported {cid}")
    payload = json.dumps(bundle, separators=(",", ":"))
    (out / "bundle.js").write_text(f"window.COURTROOM_BUNDLE = {payload};\n", encoding="utf-8")
    console.print(f"[green]wrote {out / 'bundle.js'} ({len(payload) // 1024} KiB)[/]")
    return 0


def cmd_serve(a: argparse.Namespace) -> int:
    import uvicorn

    console.print(f"Courtroom UI on http://{a.host}:{a.port}/")
    uvicorn.run("courtroom.api.server:app", host=a.host, port=a.port, log_level="warning")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="courtroom", description="Strategic AI agents in a simulated courtroom.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("cases", help="list the synthetic case library").set_defaults(fn=cmd_cases)

    def trial_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--case", default="helix-espionage")
        p.add_argument("-p", "--prosecution", default="aggressive")
        p.add_argument("-d", "--defense", default="conservative")
        p.add_argument("--seed", type=int, default=0)

    p = sub.add_parser("run", help="run one trial")
    trial_args(p)
    p.add_argument("--live", action="store_true", help="animated dashboard replay")
    p.add_argument("--delay", type=float, default=0.35)
    p.add_argument("--json", help="write the TrialResult JSON here")
    p.add_argument("--narrate", action="store_true", help="spoken argument text (exhibition; never affects the verdict)")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("verify", help="prove determinism: run twice, compare digests, check hash chain")
    trial_args(p)
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("game", help="payoff matrix + exact Nash equilibria for one case")
    p.add_argument("--case", default="helix-espionage")
    p.add_argument("--strategies", default="aggressive,conservative")
    p.add_argument("--seeds", type=int, default=200)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--json")
    p.set_defaults(fn=cmd_game)

    p = sub.add_parser("tournament", help="game analysis across the whole library")
    p.add_argument("--strategies", default="aggressive,conservative")
    p.add_argument("--seeds", type=int, default=200)
    p.add_argument("--workers", type=int, default=1)
    p.set_defaults(fn=cmd_tournament)

    p = sub.add_parser("llm-models", help="list Gemini models available on GEMINI_API_KEY")
    p.add_argument("--model", default="", help="highlight this model in the list")
    p.set_defaults(fn=cmd_llm_models)

    p = sub.add_parser("llm-exhibition", help="Gemini policy vs the four deterministic strategies (NOT equilibrium analysis)")
    p.add_argument("--case", default="helix-espionage")
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--max-calls", dest="max_calls", type=int, default=400, help="hard per-run call ceiling")
    p.add_argument("--cost-ceiling", dest="cost_ceiling", type=float, default=None, help="abort above this estimated spend")
    p.add_argument("--out", default="results/llm_exhibition.json")
    p.set_defaults(fn=cmd_llm_exhibition)

    p = sub.add_parser("bootstrap", help="bootstrap stability of each case's equilibrium label")
    p.add_argument("--cases", default="", help="comma-separated ids; default the whole library")
    p.add_argument("--strategies", default=ANALYSIS_STRATEGIES)
    p.add_argument("--seeds", type=int, default=200)
    p.add_argument("--resamples", type=int, default=200)
    p.add_argument("--rng-seed", dest="rng_seed", type=int, default=0)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--json")
    p.set_defaults(fn=cmd_bootstrap)

    p = sub.add_parser("sensitivity", help="sweep costs, sanctions, scale and standards; report what survives")
    p.add_argument("--cases", default="")
    p.add_argument("--strategies", default=ANALYSIS_STRATEGIES)
    p.add_argument("--seeds", type=int, default=60)
    p.add_argument("--delta", type=float, default=0.25)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--json")
    p.set_defaults(fn=cmd_sensitivity)

    p = sub.add_parser("analysis", help="full analysis in one command: matrices + bootstrap + sweep, written to disk")
    p.add_argument("--out", default="results")
    p.add_argument("--cases", default="")
    p.add_argument("--strategies", default=ANALYSIS_STRATEGIES)
    p.add_argument("--seeds", type=int, default=200, help="common random seeds per cell")
    p.add_argument("--resamples", type=int, default=200)
    p.add_argument("--sweep-seeds", dest="sweep_seeds", type=int, default=60)
    p.add_argument("--delta", type=float, default=0.25)
    p.add_argument("--rng-seed", dest="rng_seed", type=int, default=0)
    p.add_argument("--workers", type=int, default=1)
    p.set_defaults(fn=cmd_analysis)

    p = sub.add_parser("stress", help="fuzz generated cases x all strategies (incl. chaos); exit 1 on any failure")
    p.add_argument("--cases", type=int, default=100)
    p.set_defaults(fn=cmd_stress)

    p = sub.add_parser("export", help="write the static web bundle (offline demo fallback)")
    p.add_argument("--out", default=str(EXPORT_DIR))
    p.add_argument("--seeds", type=int, default=200)
    p.add_argument("--workers", type=int, default=1)
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("serve", help="start the web UI + API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(fn=cmd_serve)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.fn(args))
    except (KeyError, ValueError) as exc:
        console.print(f"[red]error:[/] {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
