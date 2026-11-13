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
from courtroom.contracts import CaseFile, Surprises
from courtroom.engine import run_trial, verify_chain

# Windows consoles default to cp1252; never let a glyph crash a live demo.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

console = Console()
EXPORT_DIR = Path(__file__).resolve().parent / "viz" / "web" / "data"


def _case(case_id: str) -> CaseFile:
    return generate_case(int(case_id[4:])) if case_id.startswith("gen-") else get_case(case_id)


def _surprises(a: argparse.Namespace) -> Surprises | None:
    return Surprises() if getattr(a, "surprises", False) else None


def cmd_cases(_: argparse.Namespace) -> int:
    for c in CASES.values():
        console.print(f"[bold]{c.id:24s}[/] {c.case_type.value:8s} {c.standard.value:24s} {c.title}")
        console.print(f"    [grey50]{', '.join(c.tags)}[/]")
    console.print("[grey50]Generated cases: gen-<seed>, e.g. gen-42[/]")
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    from courtroom.viz.terminal import print_summary, replay

    result = run_trial(_case(a.case), a.prosecution, a.defense, a.seed, _surprises(a))
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

    table = estimate_payoffs(_case(a.case), a.strategies.split(","), seeds=range(a.seeds), workers=a.workers, surprises=_surprises(a))
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


def cmd_stress(a: argparse.Namespace) -> int:
    from courtroom.gametheory import stress

    report = stress(n_cases=a.cases)
    console.print_json(report.model_dump_json())
    return 0 if report.crashes == 0 and report.invariant_failures == 0 else 1


def cmd_verify(a: argparse.Namespace) -> int:
    case = _case(a.case)
    first = run_trial(case, a.prosecution, a.defense, a.seed, _surprises(a))
    second = run_trial(case, a.prosecution, a.defense, a.seed, _surprises(a))
    same = first.digest == second.digest and first.model_dump_json() == second.model_dump_json()
    chain_ok = verify_chain(first.events)
    console.print(f"digest run 1: {first.digest}\ndigest run 2: {second.digest}")
    console.print(
        f"bit-identical results: {'[green]YES' if same else '[red]NO'}[/]   hash chain valid: {'[green]YES' if chain_ok else '[red]NO'}[/]"
    )
    return 0 if same and chain_ok else 1


def cmd_matters(a: argparse.Namespace) -> int:
    """Does strategy matter in this case? Measured from fresh runs of every pairing of Bold, Careful and Smart."""
    from courtroom.gametheory.matters import measure

    ids = [a.case] if a.case else list(CASES)
    for cid in ids:
        m = measure(_case(cid), seeds=tuple(range(a.seeds)), surprises=_surprises(a))
        console.print(f"[bold]{cid:24s}[/] {m.label:28s} spread {m.pairing_spread:4.0%}  seed noise {m.seed_noise:4.0%}  accuser wins {m.overall_win_rate:4.0%}")
    return 0


def cmd_find(a: argparse.Namespace) -> int:
    """Search generated cases (gen-<seed>) for contested ones: the lawyers or the seed really move the verdict."""
    from courtroom.gametheory.finder import find_contested

    report = find_contested(a.start, a.count, a.top, surprises=_surprises(a))
    console.print(f"[grey50]{report.note} ({report.seconds}s)[/]")
    for f in report.found:
        dom = {True: "no dominant strategy", False: "one style simply wins", None: "game not solved"}[f.no_dominant_strategy]
        console.print(f"[bold]{f.case_id:10s}[/] score {f.score:5.2f}  {f.mattering.label:26s} {dom} ({f.equilibrium_kind})")
    if a.json:
        Path(a.json).write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return 0


def cmd_classic(a: argparse.Namespace) -> int:
    """Which classic game (prisoner's dilemma, stag hunt, ...) does each 2x2 corner of a case's measured table resemble?"""
    from courtroom.gametheory.bootstrap import STYLES, collect_samples
    from courtroom.gametheory.classic import LABELS, PLAIN, classify_case
    from courtroom.gametheory.finder import find_classic

    sur = _surprises(a)
    if a.find:
        rep = find_classic(tuple(a.find.split(",")), a.start, a.count, surprises=sur)
        console.print(f"[grey50]{rep.note} ({rep.seconds}s)[/]")
        console.print("labels over every 2x2 corner tried: " + ", ".join(f"{k} {v}" for k, v in rep.label_counts.items()))
        console.print("same, reading the means as exact (no tolerance): " + ", ".join(f"{k} {v}" for k, v in rep.label_counts_no_tolerance.items()))
        for f in rep.found:
            console.print(f"[bold]{f.case_id:10s}[/] {PLAIN[f.label]}: {f.rows} vs {f.cols}  survives {f.stability:.0%} of resamples")
        if not rep.found:
            console.print("[yellow]None found: no generated case in this range has a stable two-by-two game of that kind.[/]")
        if a.json:
            Path(a.json).write_text(rep.model_dump_json(indent=2), encoding="utf-8")
        return 0
    ids = [a.case] if a.case else list(CASES)
    for cid in ids:
        samples = collect_samples(_case(cid), STYLES, tuple(range(a.seeds)), workers=a.workers, surprises=sur)
        res = classify_case(cid, samples, STYLES, STYLES, n_resamples=a.resamples, surprises=sur is not None)
        shown = ", ".join(f"{PLAIN[k]} {res.label_counts[k]}" for k in LABELS if res.label_counts[k])
        console.print(f"[bold]{cid:24s}[/] {shown}  (labels survive {res.mean_stability:.0%} of resamples on average)")
    return 0


def cmd_efficiency(a: argparse.Namespace) -> int:
    """Pareto-efficient cells, equilibrium efficiency and security (maximin) values of a case's measured 4x4 game."""
    from courtroom.gametheory.bootstrap import STYLES
    from courtroom.gametheory.efficiency import constant_sum_check, efficiency
    from courtroom.gametheory.payoff import estimate_payoffs

    t = estimate_payoffs(_case(a.case), STYLES, seeds=tuple(range(a.seeds)), workers=a.workers, surprises=_surprises(a))
    e = efficiency(t.analysis)
    win = {(c.row, c.col): c.prosecution_win_rate for c in t.cells}
    cs = constant_sum_check([[win[(r, c)] for c in t.col_strategies] for r in t.row_strategies])
    console.print(f"[bold]{a.case}[/]  Pareto-efficient cells: {', '.join(f'{r}/{c}' for r, c in e.pareto_cells)}")
    for q in e.equilibria:
        tag = "Pareto-efficient" if q.pareto_efficient else ("dominated for both sides (a dilemma)" if q.strictly_dominated else "weakly Pareto-dominated (a cell helps one side and hurts nobody)")
        console.print(f"  equilibrium payoffs ({q.row_payoff:.2f}, {q.col_payoff:.2f}): {tag}; above the security floor by {q.security_gap_row:.2f} (Accuser), {q.security_gap_col:.2f} (Defender)")
    console.print(f"  security values (mixed): Accuser {e.row_security.mixed_value:.3f}, Defender {e.col_security.mixed_value:.3f}")
    console.print(f"  win-probability game (constant-sum): maximin {cs.maximin:.4f}, minimax {cs.minimax:.4f}, Nash value {cs.nash_value}; theorem holds: {cs.theorem_holds}")
    return 0


def cmd_tree(a: argparse.Namespace) -> int:
    """Solve the trial as a game tree (open-file relaxation): plain minimax, alpha-beta, and alpha-beta with move ordering."""
    from courtroom.gametheory.search import solve_case

    case = _case(a.case)
    r = solve_case(case, max_nodes=a.max_nodes, with_minimax=not a.skip_minimax, with_unordered=not a.skip_minimax)
    console.print(f"[bold]{r.case_id}[/]  {r.title}  ({r.evidence[0]} Accuser exhibits, {r.evidence[1]} Defender exhibits)")
    console.print(f"[grey50]{r.note}[/]")
    show = lambda n: "more than the node limit" if n is None else f"{n:,}"  # noqa: E731
    console.print(f"  value (Accuser advantage with best play): {r.value}")
    console.print(f"  nodes visited: minimax {show(r.minimax_nodes)}; alpha-beta {show(r.alphabeta_nodes)}; alpha-beta with ordering {show(r.alphabeta_ordered_nodes)}")
    if r.pruned_share is not None:
        console.print(f"  pruned away: {r.pruned_share:.1%} of minimax's nodes; ordering saved {r.ordering_saving:.1%} over unordered alpha-beta")
    console.print(f"  the three values agree: {r.values_agree}")
    for step in r.best_play:
        console.print(f"    - {step}")
    return 0 if r.values_agree in (True, None) else 1


def cmd_lookahead(a: argparse.Namespace) -> int:
    """Does the lookahead lawyer (depth-limited alpha-beta) beat the four hand-written styles? Exhibition, not certified."""
    from courtroom.gametheory.lookahead_eval import compare_lookahead

    ids = [a.case] if a.case else list(CASES)
    for cid in ids:
        r = compare_lookahead(_case(cid), tuple(range(a.seeds)), _surprises(a), a.workers)
        console.print(f"[bold]{cid:24s}[/] Accuser z {r.prosecution.z:+.1f}, Defender z {r.defense.z:+.1f}: {r.verdict}")
    console.print("[grey50]Exhibition, not certified: lookahead is not one of the four certified styles.[/]")
    return 0


def cmd_oracle(a: argparse.Namespace) -> int:
    """Can the four hand-written lawyer styles be beaten? A double-oracle search over lawyer profiles."""
    from courtroom.gametheory.oracle import run_oracle

    r = run_oracle(_case(a.case), budget=a.budget, surprises=_surprises(a), workers=a.workers, rng_seed=a.rng_seed, max_rounds=a.rounds)
    console.print(f"[bold]{r.case_id}[/]  surprises {'on' if r.surprises else 'off'}  {r.trials} trials in {r.seconds}s")
    console.print(r.headline)
    for c in r.candidates:
        verdict = "[green]kept[/]" if c.accepted else "[grey50]dropped[/]"
        console.print(f"  {c.name:14s} {verdict}  beats the equilibrium by {c.difference:+.2f} (z {c.z:+.1f})  {c.plain}")
    console.print(f"  stopped: {r.stopped}")
    console.print(f"  final equilibrium: Accuser {r.final_equilibrium.get('prosecution_mix')}  Defender {r.final_equilibrium.get('defense_mix')}")
    if a.json:
        Path(a.json).write_text(r.model_dump_json(indent=1), encoding="utf-8")
        console.print(f"wrote {a.json}")
    return 0


def cmd_exhibition(a: argparse.Namespace) -> int:
    """The AI lawyer against the four styles: an exhibition, never certified. Runs only if a model backend answers."""
    from courtroom.llm import default_client
    from courtroom.llm.exhibition import run_exhibition

    client = default_client()
    if not client.available():
        console.print("[red]no language model answers[/] (set OLLAMA_API_KEY or GEMINI_API_KEY in .env, or start `ollama serve`). Nothing was run.")
        return 3
    table = run_exhibition([_case(c) for c in a.cases.split(",")], client, seeds=range(a.seeds), surprises=_surprises(a))
    console.print(f"[bold]{table.label}[/]  model {table.model} via {table.provider}")
    for c in table.cells:
        console.print(f"  {c.case_id:18s} AI as {c.ai_side:11s} v {c.style:12s} wins {c.ai_win_rate:4.0%} (Smart in its seat {c.smart_reference_win_rate:4.0%})  fell back {c.fallback_rate:4.0%}")
    if a.json:
        Path(a.json).write_text(table.model_dump_json(indent=1), encoding="utf-8")
        console.print(f"wrote {a.json}")
    return 0


def cmd_export(a: argparse.Namespace) -> int:
    """Pre-compute a static bundle so the web UI works with no server (demo fallback)."""
    from courtroom.agents import describe_strategies
    from courtroom.gametheory import estimate_payoffs, replicator

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, object] = {
        "cases": [json.loads(c.model_dump_json()) for c in CASES.values()],
        "strategies": describe_strategies(),
        "trials": {},
        "games": {},
    }
    ui_styles = ("aggressive", "conservative", "adaptive", "reckless")
    pairs = [(p, d) for p in ui_styles for d in ui_styles]  # every pairing the web UI offers
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

    def surprise_arg(p: argparse.ArgumentParser) -> None:
        p.add_argument("--surprises", action="store_true", help="switch on courtroom surprises (no-show, missing certificate, hostile witness)")

    def trial_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--case", default="helix-espionage")
        p.add_argument("-p", "--prosecution", default="aggressive")
        p.add_argument("-d", "--defense", default="conservative")
        p.add_argument("--seed", type=int, default=0)
        surprise_arg(p)

    p = sub.add_parser("run", help="run one trial")
    trial_args(p)
    p.add_argument("--live", action="store_true", help="animated dashboard replay")
    p.add_argument("--delay", type=float, default=0.35)
    p.add_argument("--json", help="write the TrialResult JSON here")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("verify", help="prove determinism: run twice, compare digests, check hash chain")
    trial_args(p)
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("game", help="payoff matrix + exact Nash equilibria for one case")
    p.add_argument("--case", default="helix-espionage")
    p.add_argument("--strategies", default="aggressive,conservative")
    p.add_argument("--seeds", type=int, default=40)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--json")
    surprise_arg(p)
    p.set_defaults(fn=cmd_game)

    p = sub.add_parser("matters", help="does strategy matter? measured from fresh runs of every pairing")
    p.add_argument("--case", help="one case id (default: the whole library)")
    p.add_argument("--seeds", type=int, default=8)
    surprise_arg(p)
    p.set_defaults(fn=cmd_matters)

    p = sub.add_parser("classic", help="which classic game does each 2x2 corner of the measured table resemble?")
    p.add_argument("--case", help="one case id (default: the whole library)")
    p.add_argument("--seeds", type=int, default=30)
    p.add_argument("--resamples", type=int, default=100)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--find", help="search generated cases instead, e.g. prisoners-dilemma,stag-hunt,battle-of-the-sexes")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--count", type=int, default=30)
    p.add_argument("--json")
    surprise_arg(p)
    p.set_defaults(fn=cmd_classic)

    p = sub.add_parser("efficiency", help="Pareto efficiency, security values and the minimax theorem on a case's measured game")
    p.add_argument("--case", default="helix-espionage")
    p.add_argument("--seeds", type=int, default=30)
    p.add_argument("--workers", type=int, default=1)
    surprise_arg(p)
    p.set_defaults(fn=cmd_efficiency)

    p = sub.add_parser("tree", help="the trial as a game tree: exact minimax and alpha-beta (open-file relaxation)")
    p.add_argument("--case", default="cookie-jar", help="a library case or gen-<n>")
    p.add_argument("--max-nodes", type=int, default=1_000_000)
    p.add_argument("--skip-minimax", action="store_true", help="only the ordered alpha-beta (for cases too big for plain minimax)")
    p.set_defaults(fn=cmd_tree)

    p = sub.add_parser("lookahead", help="does the lookahead lawyer beat the four styles? (exhibition, not certified)")
    p.add_argument("--case", help="one case id (default: the whole library)")
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--workers", type=int, default=1)
    surprise_arg(p)
    p.set_defaults(fn=cmd_lookahead)

    p = sub.add_parser("oracle", help="best-response search: can the four hand-written styles be beaten?")
    p.add_argument("--case", default="helix-espionage")
    p.add_argument("--budget", type=int, default=40, help="candidate profiles tried per side per round")
    p.add_argument("--rounds", type=int, default=4)
    p.add_argument("--rng-seed", type=int, default=0)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--json")
    surprise_arg(p)
    p.set_defaults(fn=cmd_oracle)

    p = sub.add_parser("exhibition", help="the AI lawyer against the four styles (needs a model backend; never certified)")
    p.add_argument("--cases", default="helix-espionage,kestrel-av")
    p.add_argument("--seeds", type=int, default=3)
    p.add_argument("--json")
    surprise_arg(p)
    p.set_defaults(fn=cmd_exhibition)

    p = sub.add_parser("find", help="search generated cases for contested ones")
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--count", type=int, default=40)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--json")
    surprise_arg(p)
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("tournament", help="game analysis across the whole library")
    p.add_argument("--strategies", default="aggressive,conservative")
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--workers", type=int, default=1)
    p.set_defaults(fn=cmd_tournament)

    p = sub.add_parser("stress", help="fuzz generated cases x all strategies (incl. chaos); exit 1 on any failure")
    p.add_argument("--cases", type=int, default=100)
    p.set_defaults(fn=cmd_stress)

    p = sub.add_parser("export", help="write the static web bundle (offline demo fallback)")
    p.add_argument("--out", default=str(EXPORT_DIR))
    p.add_argument("--seeds", type=int, default=30)
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
