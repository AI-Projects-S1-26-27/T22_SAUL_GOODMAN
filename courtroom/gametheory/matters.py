"""Does the lawyers' strategy matter in this case?  Measured, never assumed.

For a case we run every pairing of the three styles (Bold, Careful, Smart) over several seeds and look at how the
verdict moves. Two things can move it: *who the lawyers are* (the pairing) and *the seed* (luck of the draw). If neither
does, the evidence decided the case and the lawyers were scenery. The measure is a plain function of fresh runs, so
the same call gives the same answer on any machine.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from courtroom.contracts import CaseFile, Side, Surprises
from courtroom.engine import run_trial

STYLES: tuple[str, ...] = ("aggressive", "conservative", "adaptive")
LABEL = {"aggressive": "Bold", "conservative": "Careful", "adaptive": "Smart"}

# Thresholds for the plain-language rating. They are rules of thumb for a label, not part of the judge.
LAWYERS_SPREAD = 0.5  # the best pairing and the worst differ by at least half the seeds
SOME_SPREAD = 0.2
COIN_NOISE = 0.3  # in the average pairing, at least 30% of the way to a coin flip between seeds


class Mattering(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    styles: list[str]
    seeds: list[int]
    surprises: bool
    trials: int
    win_rate: list[list[float]]  # [prosecution style][defense style] -> share of seeds the Accuser wins
    pairing_spread: float  # best pairing minus worst pairing, in win rate
    seed_noise: float  # 0 = a pairing always ends the same way, 1 = every pairing is a coin flip
    overall_win_rate: float
    verdict: str  # evidence | lawyers | partly_lawyers | seeds
    label: str
    explanation: str


def rate(spread: float, noise: float) -> str:
    if spread >= LAWYERS_SPREAD:
        return "lawyers"
    if noise >= COIN_NOISE:
        return "seeds"
    if spread >= SOME_SPREAD:
        return "partly_lawyers"
    return "evidence"


_TEXT = {
    "evidence": ("Decided by the evidence", "Whoever the lawyers are and whatever the seed, the verdict comes out the same. The exhibits decide this one."),
    "lawyers": ("Decided by the lawyers", "Changing the lawyers' styles flips the verdict. This is a case where strategy matters."),
    "partly_lawyers": ("Partly the lawyers", "Some pairings tip the result, but most do not. Style matters a little here."),
    "seeds": ("A coin-flip between seeds", "The same lawyers get different verdicts on different seeds. Luck of the draw moves this one more than style does."),
}


def measure(
    case: CaseFile,
    seeds: Sequence[int] = tuple(range(8)),
    styles: Sequence[str] = STYLES,
    surprises: Surprises | None = None,
) -> Mattering:
    n = len(seeds)
    grid: list[list[float]] = []
    for p in styles:
        row = []
        for d in styles:
            wins = sum(run_trial(case, p, d, s, surprises).verdict.outcome.favours is Side.PROSECUTION for s in seeds)
            row.append(wins / n)
        grid.append(row)
    flat = [w for r in grid for w in r]
    spread = max(flat) - min(flat)
    noise = sum(2 * min(w, 1 - w) for w in flat) / len(flat)
    key = rate(spread, noise)
    label, why = _TEXT[key]
    return Mattering(
        case_id=case.id,
        styles=list(styles),
        seeds=list(seeds),
        surprises=surprises is not None,
        trials=len(styles) ** 2 * n,
        win_rate=[[round(w, 4) for w in r] for r in grid],
        pairing_spread=round(spread, 4),
        seed_noise=round(noise, 4),
        overall_win_rate=round(sum(flat) / len(flat), 4),
        verdict=key,
        label=label,
        explanation=why,
    )
