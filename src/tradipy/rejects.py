"""Rejection reason codes, and the §4.2 soft flags that are deliberately not rejections.

Normative sources: PRD §3.1.2, §3.1.3, §4.2, §20.9, §20.13, §20.14.

These live in their own module because three layers raise them — :mod:`tradipy.gates` for the
pre-entry gates, :mod:`tradipy.quotes` for §20.14 quote validity, and :mod:`tradipy.scanner`
for the §4.2 hard filters — and a quote is a lower level construct than a gate. Putting the
enum in ``gates`` would have made ``quotes`` depend on ``gates``, inverting the layering for
no reason. :mod:`tradipy.gates` re-exports ``Reject`` so ``from tradipy.gates import Reject``
continues to work.

**Why there are two enums.** PRD §4.2's table has one "Rejection Code" column covering all
fourteen rows, but only seven of those rows are Hard. The other seven are Soft — they
*score or flag*, they do not reject — and one of them (``INST_OWN_HIGH``) is kept
deliberately inert by PLAN **D24**. Round 10's finding **K5** is what a single enum invites:
a reader sizing the scanner from the shared column builds all fourteen as rejection paths,
and the off-by-default hypothesis silently becomes a filter that throws candidates away.

Splitting the namespace makes that mistake a type error rather than a review finding. A soft
code is a :class:`SoftFlag`; nothing in the scanner's rejection path will accept one, because
:class:`~tradipy.scanner.ScanResult.reject` is typed ``Reject | None`` and the two enums are
unrelated types. ``tests/test_enforcement.py`` performs the violation anyway and asserts it
cannot land — convention 6 — because a type annotation is not a runtime guarantee.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Reject", "SoftFlag"]


class Reject(Enum):
    """Why a candidate was declined.

    Each member names the PRD section that defines the rejection, because a reason code
    invented by the implementation is a rule the specification has not agreed to.
    """

    # --- PRD §4.2 hard filters (the scanner, Phase 3) ----------------------
    #: PRD §4.2 — neither the premarket nor the daily gap reached its floor. The two are an
    #: **OR**: a name qualifies on either, which is why one code covers both thresholds.
    GAP_TOO_SMALL = "GAP_TOO_SMALL"

    #: PRD §4.2 / §20.7 — relative volume below ``min_rvol`` against the ``rvol_lookback_days``
    #: average daily volume.
    RVOL_TOO_LOW = "RVOL_TOO_LOW"

    #: PRD §4.2 / D4 — float above ``max_float_shares``. The "20-20 rule": the supply side of
    #: the imbalance Ross Cameron's setups trade.
    FLOAT_TOO_HIGH = "FLOAT_TOO_HIGH"

    #: PRD §4.2 — price outside ``[min_price, max_price]``. One code for both ends, as §4.2
    #: states it; :class:`~tradipy.scanner.HardResult` carries which end bound.
    PRICE_OUT_OF_RANGE = "PRICE_OUT_OF_RANGE"

    #: PRD §4.2 — average daily volume below ``min_adv_shares``. This is the *exit liquidity*
    #: filter, and it is separate from ``max_pct_of_adv`` in §2.2, which caps size once a name
    #: has already passed it.
    ADV_TOO_LOW = "ADV_TOO_LOW"

    #: PRD §4.2 — price is within ``min_luld_distance_pct`` of a LULD band, so a limit-up /
    #: limit-down halt is close enough to be a foreseeable execution risk rather than a tail.
    NEAR_LULD = "NEAR_LULD"

    # --- PRD §3.1.3 / §4.2 spread, and the §3 pre-entry gates --------------
    #: PRD §3.1.3 / §4.2 — spread exceeds the scan-time or signal-time cap, **or** the bid is
    #: thinner than ``min_quote_size``. §4.2's Liquidity/Spread row states both conditions
    #: under this one code; a name nobody is bidding for in size is as unexecutable as one
    #: quoted too wide.
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"

    #: PRD §3.1.1 / §3.1.2 — the proportional term of the unified room requirement binds.
    INSUFFICIENT_ROOM = "INSUFFICIENT_ROOM"

    #: PRD §3.1.2 — the separation term binds; T1 and T2 would collapse together.
    TARGETS_TOO_CLOSE = "TARGETS_TOO_CLOSE"

    #: PRD §2 / §3.2 / §20.13 — stop distance exceeds ``max_stop_pct`` of entry, so the
    #: trade is skipped rather than the stop tightened. The PRD states the rule ("skip the
    #: trade") without naming a code; this name is the implementation's, and PRD §4.2's
    #: rejection-code table should adopt or replace it.
    STOP_TOO_WIDE = "STOP_TOO_WIDE"

    #: PRD §20.14 — the NBBO quote at signal-bar close was older than
    #: ``quote_stale_seconds``.
    QUOTE_STALE = "QUOTE_STALE"

    #: PRD §20.14 — ``ask <= bid``. Never clamped to zero: a zero spread makes the §3.1.2
    #: separation floor trivially satisfiable, which is exactly wrong during the
    #: dislocations that produce crossed quotes.
    QUOTE_CROSSED = "QUOTE_CROSSED"

    #: PRD §20.9 / §20.14 — a one-sided or odd-lot-only quote, or an unadjustable corporate
    #: action. Not a spread, so it is not gated on.
    DATA_QUALITY_DEGRADED = "DATA_QUALITY_DEGRADED"


class SoftFlag(Enum):
    """PRD §4.2's seven Soft rows. **None of these rejects anything.**

    §4.2 lists these in the same "Rejection Code" column as the hard filters, which is the
    naming that produced K5. They are advisory: two of them (``PREMARKET_THIN`` via
    ``norm_premarket_vol`` and ``NO_CATALYST`` via ``catalyst_confirmed``) feed the §20.10
    composite score that ranks survivors, and the rest are context a human reviewing the
    watchlist wants to see. A flag raised on a candidate says something is worth knowing
    about it, never that it should be thrown away.

    The scanner returns them on :class:`~tradipy.scanner.ScanResult.flags` alongside — not
    inside — the rejection path.
    """

    #: PRD §4.2 — premarket volume below ``min_premarket_volume``. Also a §20.10 score input,
    #: so a thin name is ranked down as well as flagged.
    PREMARKET_THIN = "PREMARKET_THIN"

    #: PRD §4.2 — market cap above ``max_market_cap``. Small-cap focus.
    MARKET_CAP_HIGH = "MARKET_CAP_HIGH"

    #: PRD §4.2 — ATR below ``min_atr_multiple`` of its trailing average, i.e. the name is not
    #: moving enough intraday for the §3 setups to reach their targets.
    ATR_LOW = "ATR_LOW"

    #: PRD §4.2 — no headline. §20.10 scores this at zero and §14 requires a catalyst before a
    #: trade, but the scanner does not reject on it: catalyst confirmation is the one manual
    #: step PRD §12.2 keeps in the MVP loop, so the scanner cannot be the thing that decides
    #: it is absent.
    NO_CATALYST = "NO_CATALYST"

    #: PRD §4.2 — halted within ``recent_halt_lookback_days``. §4.2 marks this row
    #: "Soft (flag)" — elevated risk *and* elevated opportunity, so it informs rather than
    #: filters.
    RECENT_HALT = "RECENT_HALT"

    #: PRD §4.2 / **D24** — institutional ownership at or above
    #: ``min_institutional_ownership_pct``. **Disabled by default and unvalidated**: §4.2's
    #: own note calls the premise doubtful, no source in Appendix A states the threshold, and
    #: D24 kept the row off rather than deleting it so the hypothesis can be tested later
    #: instead of being silently lost. With ``institutional_ownership_enabled`` at its default
    #: this flag cannot be raised by any input, which
    #: ``tests/test_enforcement.py`` asserts by attempting it.
    INST_OWN_HIGH = "INST_OWN_HIGH"

    #: PRD §4.2 — short interest at or above ``min_short_interest_pct``. Explicitly
    #: "flag only, not reject": squeeze fuel cuts both ways.
    HIGH_SHORT_INTEREST = "HIGH_SHORT_INTEREST"
