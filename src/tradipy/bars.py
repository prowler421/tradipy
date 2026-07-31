"""Flagpole height and measured move (PRD §20.4).

::

    flagpole_low    = LOW of the first candle in the flagpole sequence
    flagpole_high   = HIGH of the last candle before the flag begins
    flagpole_height = flagpole_high - flagpole_low
    measured_move   = entry_price + flagpole_height
    retrace_pct     = (flagpole_high - flag_low) / flagpole_height

Flagpole detection is *"the longest run of consecutive green candles (close > open) ending
immediately before the flag, subject to §3.2 criterion 2. Ties broken by taking the longest
qualifying run; if two runs tie in length, take the one with greater volume."*

**What is deliberately not here.** §3.2 criterion 2 states three thresholds and the window they
are measured over — at least 3 candles, combined move ≥ 2%, total volume ≥ 2× the average
1-minute volume of the prior 30 bars — and none of the four appears in PRD §2 or §2.0.
Registering them here would be this module inventing spec; writing them as literals would break
the project's one-definition rule. So :func:`select_flagpole` takes the qualification test as a
**predicate supplied by the caller**. Phase 4 (**D33**) registered all four with code-originated
bounds and :func:`tradipy.setups.evaluate_bull_flag` supplies the predicate — this module was not
changed to make that possible, which was the point of the arrangement.

§20.1 bar timing (labels, close detection, the 750 ms grace) is a separate subsection and
needs an ingestion layer, so :class:`Bar` carries no timestamp.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

__all__ = [
    "Bar",
    "green_runs",
    "flagpole_ending_at",
    "select_flagpole",
    "flagpole_height",
    "measured_move",
    "retrace_pct",
]


@dataclass(frozen=True)
class Bar:
    """One 1-minute OHLCV bar. All prices are `Decimal`; volume is a share count."""

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    @property
    def is_green(self) -> bool:
        """PRD §20.4: green means ``close > open``. A doji (``close == open``) is not green."""
        return self.close > self.open


def green_runs(bars: Sequence[Bar]) -> list[tuple[int, int]]:
    """Every maximal run of consecutive green bars, as ``(start, end)`` inclusive indices.

    Maximal: a run is not reported if it is a sub-sequence of a longer one, so the result is
    the set of candidate flagpoles before any §3.2 qualification is applied.
    """
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for i, bar in enumerate(bars):
        if bar.is_green:
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(bars) - 1))
    return runs


def flagpole_ending_at(bars: Sequence[Bar], end: int) -> tuple[int, int] | None:
    """The maximal green run ending at index ``end`` inclusive, or None if it is not green.

    §20.4's phrase *"ending immediately before the flag"* pins one end of the run, so given a
    known flag start there is exactly one candidate and no tie is possible. The tie rule
    exists for the search case; see :func:`select_flagpole`.
    """
    if not (0 <= end < len(bars)) or not bars[end].is_green:
        return None
    start = end
    while start > 0 and bars[start - 1].is_green:
        start -= 1
    return start, end


def select_flagpole(
    bars: Sequence[Bar],
    candidates: Sequence[tuple[int, int]],
    qualifies: Callable[[Sequence[Bar]], bool] | None = None,
) -> tuple[int, int] | None:
    """Pick the flagpole from a set of candidate runs, per §20.4's tie rule.

    Longest qualifying run wins; a tie on length is broken by **greater total volume**. If
    two runs tie on both, the earlier one is returned — §20.4 does not say, and picking
    deterministically beats picking arbitrarily.

    ``qualifies`` is §3.2 criterion 2, supplied by the caller because its three thresholds
    have no registry entry (see the module docstring). Passing None applies no qualification
    and selects purely on length and volume.
    """
    scored = [
        (end - start + 1, sum(b.volume for b in bars[start : end + 1]), -start, (start, end))
        for start, end in candidates
        if qualifies is None or qualifies(bars[start : end + 1])
    ]
    if not scored:
        return None
    return max(scored)[3]


def flagpole_height(pole: Sequence[Bar]) -> Decimal:
    """PRD §20.4: ``HIGH of the last candle - LOW of the first candle``.

    Note this is *not* ``max(high) - min(low)`` over the run. The two agree on a
    monotonically rising sequence and diverge on any run containing a bar that dipped below
    its predecessor's low, which a green bar may do. §20.4 names first and last explicitly.
    """
    if not pole:
        raise ValueError("flagpole must contain at least one bar (PRD §20.4)")
    height = pole[-1].high - pole[0].low
    if height <= 0:
        raise ValueError(
            f"flagpole height must be positive, got {height}: the last bar's high "
            f"({pole[-1].high}) is not above the first bar's low ({pole[0].low})"
        )
    return height


def measured_move(entry: Decimal, height: Decimal) -> Decimal:
    """PRD §20.4: ``entry_price + flagpole_height`` — the §3.2 T2 structural target.

    Returned unrounded. §20.13 requires rounding to happen **once, at level computation**,
    and for a target that is :func:`tradipy.gates.exit_ladder`. Both inputs are whole ticks
    whenever they come from real bars, so the sum already is one.
    """
    return entry + height


def retrace_pct(flagpole_high: Decimal, flag_low: Decimal, height: Decimal) -> Decimal:
    """PRD §20.4: ``(flagpole_high - flag_low) / flagpole_height``.

    §3.2 criterion 3 rejects the setup above 50%. Returned as a fraction, not a percentage,
    matching every other ``_pct`` quantity in the registry.
    """
    if height <= 0:
        raise ValueError("flagpole height must be positive to compute a retrace (PRD §20.4)")
    return (flagpole_high - flag_low) / height
