"""NBBO quote validity and ``spread_at_signal`` (PRD §20.14).

``spread_at_signal`` is the binding input to the §3.1.2 separation floor and the §3.1.3
spread gate, both of which reject entries. §20.14 opens by noting it *"was previously used in
three places and defined in none"* — this module is that definition.

Until v0.1.0 ``Reject.QUOTE_STALE`` and ``Reject.QUOTE_CROSSED`` were declared and returned by
nothing, and ``quote_stale_seconds`` and ``min_quote_size`` were registered and read by
nothing. The rule was fully specified and entirely absent from the code.

**Out of scope here.** §20.14's sampling rule — *"the last NBBO quote at or before the close
of the signal bar"* — is a feed concern: this module validates whatever quote it is handed and
takes the caller's word that it was sampled correctly. There is no feed at this layer to check
against.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tradipy.params import Config
from tradipy.rejects import Reject
from tradipy.rounding import TICK_SIZE, ceil_to_tick

__all__ = ["Quote", "check_quote", "spread_at_signal", "estimated_spread"]


@dataclass(frozen=True)
class Quote:
    """One consolidated NBBO quote, as of the close of a signal bar.

    ``age_seconds`` is the quote's age **at bar close**, not at the time of evaluation —
    §20.14 measures staleness against the as-of point, matching §20.7's discipline, so that
    a backtest and a live session reach the same verdict.

    ``estimated`` marks the §20.14 backtest substitute. Estimated-spread trades are reported
    separately in §8.3 and excluded from the §18.7 viability gate, so the flag has to travel
    with the quote rather than being inferred later.
    """

    bid: Decimal
    ask: Decimal
    bid_size: int
    ask_size: int
    age_seconds: Decimal
    estimated: bool = False

    @property
    def spread(self) -> Decimal:
        """PRD §20.14: ``spread = NBBO_ask - NBBO_bid``.

        Never last-trade-derived and never a single-venue book. Negative for a crossed
        quote, deliberately — :func:`check_quote` rejects those rather than clamping, and a
        property that quietly returned zero would defeat it.
        """
        return self.ask - self.bid


def check_quote(quote: Quote, cfg: Config) -> Reject | None:
    """None if the quote is a usable spread, else the §20.14 reason it is not.

    Three tests, applied in this order:

    1. **Validity** — *"Both sides must be present with ``bid_size >= 100`` and
       ``ask_size >= 100``. A one-sided or odd-lot-only quote is not a spread."* Presence is
       checked as a positive price, because a missing side arrives from a feed as a zero or a
       sentinel rather than as an absent field, and a $0.00 bid against a $5.16 ask would
       otherwise pass as a $5.16 "spread".
    2. **Crossed** — ``ask <= bid`` is ``QUOTE_CROSSED``, *"never clamped to zero"*.
    3. **Staleness** — older than ``quote_stale_seconds`` at bar close is ``QUOTE_STALE``.
       §5.2's ≤ 5 s forward-fill allowance governs *display*, not risk gates.

    Only the first failure is returned, matching the ``Reject | None`` convention the gates
    use — so the order matters, and **§20.14 does not state one.** It is chosen here, and the
    reasoning is: validity first because tests 2 and 3 ask questions about a spread and there
    is not one yet; crossed before stale because a crossed market is a fact about the market
    that a fresh timestamp does not cure, and because a clamped zero spread would make the
    §3.1.2 separation floor trivially satisfiable during exactly the dislocations that produce
    it. Recorded explicitly rather than left implicit: this package marks code-originated
    *bounds* as such, and a code-originated *rule* deserves the same treatment.
    """
    if quote.bid <= 0 or quote.ask <= 0:
        return Reject.DATA_QUALITY_DEGRADED
    if quote.bid_size < cfg["min_quote_size"] or quote.ask_size < cfg["min_quote_size"]:
        return Reject.DATA_QUALITY_DEGRADED
    if quote.ask <= quote.bid:
        return Reject.QUOTE_CROSSED
    if quote.age_seconds > cfg["quote_stale_seconds"]:
        return Reject.QUOTE_STALE
    return None


def spread_at_signal(quote: Quote, cfg: Config) -> tuple[Decimal | None, Reject | None]:
    """The §20.14 spread, or the reason there isn't one.

    Returns ``(spread, None)`` on success and ``(None, reject)`` on failure. The spread is
    deliberately **not** returned alongside a rejection: an invalid quote's arithmetic
    difference is not a spread, and returning it invites a caller to gate on it. That is the
    same information-loss shape as the ``vwap_reclaim_stop`` verdict bug, approached from the
    other side.
    """
    verdict = check_quote(quote, cfg)
    if verdict is not None:
        return None, verdict
    return quote.spread, None


def estimated_spread(price: Decimal, spread_pct_median: Decimal, cfg: Config) -> Decimal:
    """PRD §20.14 backtest substitute: ``max(1 tick, spread_pct_median * price)``.

    Used only when NBBO history is unavailable for a session. Any :class:`Quote` built from
    this must set ``estimated=True``: §8.3 reports these trades separately and §18.7 excludes
    them from the viability gate, *"because the gate's whole purpose is to measure
    net-of-cost expectancy."*

    §20.14 states no rounding. Rounding **up** is applied here because a spread is an input
    to two constraints and understating it weakens both — it lowers the §3.1.2 separation
    floor and makes the §3.1.3 gate easier to pass. That is the same "rounding must never
    weaken a constraint" principle as §20.13, applied to an input rather than a threshold.
    ``cfg`` is taken so the tick and the rule stay together as this grows a per-symbol tick.
    """
    del cfg  # no per-symbol tick yet; see PRD §20.13 (SEC Rule 612, $0.01 at/above $1.00)
    return max(TICK_SIZE, ceil_to_tick(spread_pct_median * price))
