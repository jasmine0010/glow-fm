"""The sealed test's fixed rules (research/SEALED_TEST_PROTOCOL.md): when NISAR should pass again, and how a pass is read.

Pure functions, shared by scripts/seal_next_passes.py and scripts/score_sealed.py and checked in tests/test_sealed.py.
The trust rule, the judgeable bar and the reading are OVERBANK_PROTOCOL.md §4 and §6, unchanged.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

REPEAT = timedelta(days=12)          # NISAR repeats each track every 12 days
HORIZON = timedelta(days=24)         # passes sealed: those falling within 24 days of sealing
MATCH = timedelta(hours=1)           # a found scene begins within this of the predicted time
MISSING_AFTER = timedelta(days=30)   # no scene this long after the predicted time: missing
MIN_BASELINE, MAX_BASELINE, BASELINE_DAYS = 3, 6, 60   # the live protocol's baseline rule
CSI_BAR, MIN_FLOOD_HA, MIN_COVERAGE = 0.60, 500.0, 0.60
RECENT_MM, ANTECEDENT_MM = 5.0, 25.0  # rainy: 24 h and 72 h totals (RAINFALL.md)


def predicted_times(latest: datetime, sealed_at: datetime, horizon: timedelta = HORIZON) -> list[datetime]:
    """Every latest + 12 days x k that falls after the sealing time and within the horizon."""
    out, t = [], latest + REPEAT
    while t <= sealed_at + horizon:
        if t > sealed_at:
            out.append(t)
        t += REPEAT
    return out


def rainy(h24: float | None, h72: float | None) -> bool | None:
    if h24 is None or h72 is None:
        return None
    return h24 >= RECENT_MM or h72 >= ANTECEDENT_MM


def light(confident: bool, is_rainy: bool | None) -> str | None:
    """Green if the confidence label is High and the pass isn't rainy; red otherwise; None if rain is unknown."""
    if is_rainy is None:
        return None
    return "green" if confident and not is_rainy else "red"


def judgeable(estimate_ha: float | None, coverage: float | None) -> bool:
    return estimate_ha is not None and coverage is not None and estimate_ha >= MIN_FLOOD_HA and coverage >= MIN_COVERAGE


def hit(lamp: str, csi: float) -> bool:
    return (csi >= CSI_BAR) == (lamp == "green")


def reading(passes: list[dict]) -> dict:
    """Hits over judgeable passes, against always-green and always-red, with the fixed bars. Each pass: light, csi."""
    n = len(passes)
    hits = sum(hit(p["light"], p["csi"]) for p in passes)
    always_green = sum(p["csi"] >= CSI_BAR for p in passes)
    always_red = n - always_green
    if n < 5:
        verdict = "too few"
    elif hits / n >= 0.8 and hits > always_green and hits > always_red:
        verdict = "held up"
    elif hits / n >= 0.6:
        verdict = "mixed"
    else:
        verdict = "did not hold up"
    green = [p for p in passes if p["light"] == "green"]
    red = [p for p in passes if p["light"] == "red"]
    return {"judgeable": n, "hits": hits, "always_green_hits": always_green, "always_red_hits": always_red,
            "green": {"n": len(green), "hits": sum(hit("green", p["csi"]) for p in green)},
            "red": {"n": len(red), "hits": sum(hit("red", p["csi"]) for p in red)}, "verdict": verdict}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
