"""Engineer 5: exact Nash solver, dominance, dynamics, tournament regressions, stress."""

from __future__ import annotations

from fractions import Fraction as F

import pytest

from courtroom.cases import CASES
from courtroom.contracts import StandardOfProof
from courtroom.engine import run_trial
from courtroom.gametheory import analyze, estimate_payoffs, replicator, stress, support_enumeration, verify_equilibrium
from courtroom.gametheory.bootstrap import DOMINANCE_SOLVABLE, MIXED, PURE, bootstrap_case, equilibrium_label
from courtroom.gametheory.nash import as_fraction_matrix, dominant_strategy, iesds
from courtroom.gametheory.sensitivity import log_odds_for, patched, sweep


def test_matching_pennies_unique_mixed_equilibrium() -> None:
    A = [[1, -1], [-1, 1]]
    B = [[-1, 1], [1, -1]]
    eqs = support_enumeration(as_fraction_matrix(A), as_fraction_matrix(B))
    assert eqs == [([F(1, 2), F(1, 2)], [F(1, 2), F(1, 2)])]


def test_prisoners_dilemma() -> None:
    a = analyze(["C", "D"], ["C", "D"], [[-1, -3], [0, -2]], [[-1, 0], [-3, -2]])
    assert len(a.equilibria) == 1 and a.equilibria[0].pure
    assert a.equilibria[0].row_mix == {"C": 0.0, "D": 1.0}
    assert a.row_dominant == "D" and a.row_dominance == "strict" and a.trivial
    assert any("Pareto-dominates" in n for n in a.notes)


def test_battle_of_the_sexes_three_equilibria() -> None:
    a = analyze(["O", "F"], ["O", "F"], [[2, 0], [0, 1]], [[1, 0], [0, 2]])
    assert len(a.equilibria) == 3
    mixed = next(e for e in a.equilibria if not e.pure)
    assert mixed.row_mix_exact == {"O": "2/3", "F": "1/3"}
    assert mixed.col_mix_exact == {"O": "1/3", "F": "2/3"}


def test_rock_paper_scissors_3x3() -> None:
    A = [[0, -1, 1], [1, 0, -1], [-1, 1, 0]]
    B = [[-x for x in row] for row in A]
    a = analyze(["R", "P", "S"], ["R", "P", "S"], A, B)
    assert len(a.equilibria) == 1
    assert a.equilibria[0].row_mix_exact == {"R": "1/3", "P": "1/3", "S": "1/3"}


def test_verifier_rejects_non_equilibria() -> None:
    A = as_fraction_matrix([[1, -1], [-1, 1]])
    B = as_fraction_matrix([[-1, 1], [1, -1]])
    assert not verify_equilibrium(A, B, [F(1), F(0)], [F(1), F(0)])
    assert not verify_equilibrium(A, B, [F(1, 2), F(1, 3)], [F(1, 2), F(1, 2)])  # not a distribution


def test_iesds_and_weak_dominance() -> None:
    A = as_fraction_matrix([[3, 3], [1, 2], [0, 4]])
    B = as_fraction_matrix([[1, 0], [1, 0], [1, 0]])
    rows, cols = iesds(A, B)
    assert cols == [0] and rows == [0]
    assert dominant_strategy(as_fraction_matrix([[1, 1], [1, 0]]), "row") == (0, "weak")


def test_float_payoffs_are_converted_exactly() -> None:
    a = analyze(["a", "b"], ["x", "y"], [[0.1, 0.2], [0.3, 0.4]], [[0.0, 0.0], [0.0, 0.0]])
    assert all(e.verified for e in a.equilibria)


def test_replicator_converges_to_dominant_strategy() -> None:
    traj = replicator([[3, 0], [5, 1]], [[3, 5], [0, 1]], [0.9, 0.1], [0.9, 0.1], steps=2000)
    x, y = traj[-1]
    assert x[1] > 0.99 and y[1] > 0.99


def test_replicator_stays_on_simplex() -> None:
    for x, y in replicator([[1, -1], [-1, 1]], [[-1, 1], [1, -1]], [0.7, 0.3], [0.2, 0.8]):
        assert sum(x) == pytest.approx(1) and sum(y) == pytest.approx(1)
        assert min(x + y) >= 0


# ----------------------------------------------------------------- regression on the case library


def test_flagship_game_is_not_trivial() -> None:
    """The flagship case must not collapse to a dominant-strategy equilibrium (design goal F1/F2)."""
    table = estimate_payoffs(CASES["helix-espionage"], ("aggressive", "conservative"), seeds=range(20))
    a = table.analysis
    assert not a.trivial
    assert a.row_dominant is None and a.col_dominant is None
    assert not any(e.pure for e in a.equilibria)
    assert all(e.verified for e in a.equilibria)


def test_payoff_estimation_is_deterministic() -> None:
    t1 = estimate_payoffs(CASES["edge-poisoned-tree"], seeds=range(6))
    t2 = estimate_payoffs(CASES["edge-poisoned-tree"], seeds=range(6))
    assert t1 == t2


def test_honest_triviality_report_for_empty_docket() -> None:
    table = estimate_payoffs(CASES["edge-empty-docket"], seeds=range(3))
    assert table.analysis.degenerate  # every profile ties: the analyzer must say so, not invent structure


def test_stress_fuzz_no_crashes_no_invariant_failures() -> None:
    report = stress(n_cases=30, replay_every=7)
    assert report.crashes == 0, report.failures
    assert report.invariant_failures == 0, report.failures
    assert report.trials == 30 * 25
    assert report.deterministic_replays > 0


# ----------------------------------------------------------------- bootstrap stability


def test_equilibrium_label_classifies_known_games() -> None:
    pd = analyze(["C", "D"], ["C", "D"], [[-1, -3], [0, -2]], [[-1, 0], [-3, -2]])
    assert equilibrium_label(pd) == DOMINANCE_SOLVABLE  # IESDS leaves exactly (D, D)
    pennies = analyze(["H", "T"], ["H", "T"], [[1, -1], [-1, 1]], [[-1, 1], [1, -1]])
    assert equilibrium_label(pennies) == MIXED  # no pure equilibrium exists
    bos = analyze(["O", "F"], ["O", "F"], [[2, 0], [0, 1]], [[1, 0], [0, 2]])
    assert equilibrium_label(bos) == PURE  # pure equilibria exist, no dominance


def test_bootstrap_is_deterministic_and_reports_a_fraction() -> None:
    kw = dict(strategies=("aggressive", "conservative"), seeds=range(8), n_resamples=5, rng_seed=7)
    r1 = bootstrap_case(CASES["edge-poisoned-tree"], **kw)
    r2 = bootstrap_case(CASES["edge-poisoned-tree"], **kw)
    assert r1 == r2
    assert sum(r1.label_counts.values()) == 5
    assert 0.0 <= r1.stability <= 1.0
    assert r1.label_counts.get(r1.baseline_label, 0) / 5 == pytest.approx(r1.stability)


# ----------------------------------------------------------------- sensitivity sweep


def _live_scale() -> tuple[F, F]:
    """The LLR_SCALE each module currently sees, as (scoring, rules)."""
    import courtroom.judge.rules as rules
    import courtroom.judge.scoring as scoring

    return scoring.LLR_SCALE, rules.LLR_SCALE


def test_patched_constants_apply_and_restore_exactly() -> None:
    original, doubled = F(3), F(6)
    case = CASES["helix-espionage"]
    before = run_trial(case, "aggressive", "conservative", seed=0)
    assert _live_scale() == (original, original)

    with patched({"LLR_SCALE": doubled}):
        # the by-name binding in scoring.py must move too, not just the one in rules.py
        assert _live_scale() == (doubled, doubled)

    assert _live_scale() == (original, original)
    after = run_trial(case, "aggressive", "conservative", seed=0)
    assert after.digest == before.digest  # restoration is exact: determinism survives


def test_patched_threshold_reaches_the_judge() -> None:
    import courtroom.judge.rules as rules

    base = rules.THRESHOLD_LOG_ODDS[StandardOfProof.BEYOND_REASONABLE_DOUBT]
    with patched(thresholds={StandardOfProof.BEYOND_REASONABLE_DOUBT: log_odds_for(0.80)}):
        assert rules.THRESHOLD_LOG_ODDS[StandardOfProof.BEYOND_REASONABLE_DOUBT] == log_odds_for(0.80)
    assert rules.THRESHOLD_LOG_ODDS[StandardOfProof.BEYOND_REASONABLE_DOUBT] == base


def test_log_odds_for_is_exact_and_monotone() -> None:
    assert log_odds_for(0.5) == F(0)
    assert log_odds_for(0.80) < log_odds_for(0.90) < log_odds_for(0.95)
    assert abs(float(log_odds_for(0.90)) - 2.1972) < 1e-4  # matches the 11/5 constant to 2 dp


def test_sweep_reports_baseline_and_partitions_cases() -> None:
    report = sweep(case_ids=["edge-empty-docket"], strategies=("aggressive", "conservative"), seeds=range(4))
    assert report.baseline["edge-empty-docket"]
    assert set(report.robust_cases) | set(report.fragile_cases) == {"edge-empty-docket"}
    assert not (set(report.robust_cases) & set(report.fragile_cases))
    assert report.variations and all(v.parameter for v in report.variations)


def test_sweep_variations_actually_bite() -> None:
    """A variation must change something.

    Regression guard: when the sweep farmed trials out to a ProcessPoolExecutor the
    children re-imported pristine modules, the patched constants never reached them,
    and every variation silently returned the baseline. Zero movement everywhere is
    indistinguishable from a broken sweep, so assert at least one variation moves.
    """
    report = sweep(case_ids=["helix-espionage"], strategies=("aggressive", "conservative"), seeds=range(12))
    base = report.baseline_win_rate["helix-espionage"]
    moved = [v for v in report.variations if v.prosecution_win_rate["helix-espionage"] != base]
    assert moved, "no variation changed the win rate: the perturbations are not reaching the trials"
