"""Small statistics helpers for honest accuracy figures."""

from __future__ import annotations

import math
from typing import Optional, Tuple

# Below this many scored forecasts a hit rate is shown, but marked as not yet reliable.
RELIABLE_SAMPLE = 30


def wilson_interval(hits: int, n: int, z: float = 1.959964) -> Optional[Tuple[float, float]]:
    """95 % Wilson score interval of a hit rate, in percent (None without data).

    With few forecasts the interval is wide: 3 hits out of 5 is anything from about 23 % to 88 %."""
    if n <= 0:
        return None
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, centre - half) * 100, 1), round(min(1.0, centre + half) * 100, 1)


def normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))
