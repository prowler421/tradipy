"""Tick arithmetic and polarity-aware threshold rounding.

Normative source: PRD §20.13 (Tick Size and Price Rounding), decided as PLAN D19
and amended by D25 (the polarity split).

The governing principle is *"rounding must never weaken a constraint."* `ceil` and
`floor` are consequences of it; which one applies depends on the **polarity** of the
constraint being rounded. Getting this backwards is not cosmetic — an earlier draft of
PRD §3.1.3 applied `ceil_to_tick` to a maximum by analogy with the minimum-gate rule,
which made the spread gate *more permissive* while the surrounding prose claimed
conservatism. That defect survived a full review round because every number in the
tables that applied it was individually correct.

All money is `Decimal`. Prices are compared against tick boundaries, and binary float
cannot represent $0.01 exactly, so float here would produce comparison errors that look
like logic bugs. PRD §9.2 requires `Decimal` wherever a value is compared against a tick
boundary or accumulated into P&L.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from enum import Enum

__all__ = [
    "TICK_SIZE",
    "Polarity",
    "floor_to_tick",
    "ceil_to_tick",
    "round_threshold",
    "is_whole_tick",
]


# PRD §20.13: $0.01 for all tradeable symbols. SEC Rule 612 mandates $0.01 increments
# at or above $1.00, and the §2 price filter floors the universe at $1.00, so sub-penny
# increments never arise.
TICK_SIZE = Decimal("0.01")


class Polarity(Enum):
    """Which direction a threshold must be rounded so the constraint is never weakened.

    PRD §20.13 requires every threshold to be classified **before** a rounding function
    is chosen. There is deliberately no default: an unclassified threshold is a bug, not
    something to guess at.
    """

    #: Value must **exceed** the threshold (room gate, separation floor, min stop
    #: distance). Rounding **up** raises the bar, so the requirement is never weakened.
    MINIMUM = "minimum"

    #: Value must **stay under** the threshold (spread caps, max stop distance).
    #: Rounding **down** lowers the ceiling, so the requirement is never weakened.
    MAXIMUM = "maximum"


def floor_to_tick(value: Decimal) -> Decimal:
    """Round down to the nearest whole tick."""
    return (value / TICK_SIZE).to_integral_value(rounding=ROUND_FLOOR) * TICK_SIZE


def ceil_to_tick(value: Decimal) -> Decimal:
    """Round up to the nearest whole tick."""
    return (value / TICK_SIZE).to_integral_value(rounding=ROUND_CEILING) * TICK_SIZE


def is_whole_tick(value: Decimal) -> bool:
    """True if `value` is an exact multiple of the tick size.

    PRD §20.13: every price submitted to the broker or compared against a bar must be a
    whole tick, and rounding happens **once**, at level computation, never at comparison
    time.
    """
    return value == value.quantize(TICK_SIZE)


def round_threshold(value: Decimal, polarity: Polarity) -> Decimal:
    """Round a gate threshold in the direction its polarity requires.

    MINIMUM -> ceil (raise the floor).
    MAXIMUM -> floor, then clamp to >= 1 tick.

    The clamp on maxima is load-bearing, not defensive. PRD §20.13 and A25: a maximum
    that floors to $0.00 rejects every possible value, which is a silent kill switch
    rather than a filter. In §3.1.3 the signal-time spread cap is
    ``floor_to_tick(max_spread_r * R)``, which reaches $0.00 whenever
    ``R < TICK_SIZE / max_spread_r`` — $0.067 at the default 0.15. Today's
    ``min_stop_distance`` of $0.10 keeps R above that, but §2.0 permits $0.01, so the
    outage is reachable by a legal configuration change rather than by a bug.

    Note the clamp *contains* that failure without making such trades sound: a one-tick
    spread against a sub-$0.07 R is still ~30% of R round-trip. The proper fix is the
    cross-parameter validator in :func:`tradipy.params.validate_couplings`.
    """
    if polarity is Polarity.MINIMUM:
        return ceil_to_tick(value)
    if polarity is Polarity.MAXIMUM:
        return max(TICK_SIZE, floor_to_tick(value))
    raise ValueError(f"unclassified threshold polarity: {polarity!r}")
