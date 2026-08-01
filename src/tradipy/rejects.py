"""Rejection reason codes, the §4.2 soft flags, and the §3 post-entry exit reasons.

Normative sources: PRD §3.1.2, §3.1.3, §4.2, §20.9, §20.12, §20.13, §20.14.

These live in their own module because three layers raise them — :mod:`tradipy.gates` for the
pre-entry gates, :mod:`tradipy.quotes` for §20.14 quote validity, and :mod:`tradipy.scanner`
for the §4.2 hard filters — and a quote is a lower level construct than a gate. Putting the
enum in ``gates`` would have made ``quotes`` depend on ``gates``, inverting the layering for
no reason. :mod:`tradipy.gates` re-exports ``Reject`` so ``from tradipy.gates import Reject``
continues to work.

**Why there is more than one enum.** PRD §4.2's table has one "Rejection Code" column covering
all fourteen rows, but only seven of those rows are Hard. The other seven are Soft — they
*score or flag*, they do not reject — and one of them (``INST_OWN_HIGH``) is kept
deliberately inert by PLAN **D24**. Round 10's finding **K5** is what a single enum invites:
a reader sizing the scanner from the shared column builds all fourteen as rejection paths,
and the off-by-default hypothesis silently becomes a filter that throws candidates away.

Splitting the namespace makes that mistake a type error rather than a review finding. A soft
code is a :class:`SoftFlag`; nothing in the scanner's rejection path will accept one, because
:class:`~tradipy.scanner.ScanResult.reject` is typed ``Reject | None`` and the two enums are
unrelated types. ``tests/test_enforcement.py`` performs the violation anyway and asserts it
cannot land — convention 6 — because a type annotation is not a runtime guarantee.

:class:`ExitReason` is the third, added with Phase 4 on the same argument one step further out:
a *rejection* declines a trade that was never taken and an *exit* closes one that was, so a
pre-entry gate returning ``BAILED_OUT`` and an exit rule returning ``SPREAD_TOO_WIDE`` are both
nonsense that a shared namespace would permit. Its members are transcribed from §20.12's state
names and §9.2's ``ClosedTrade.exit_reason`` values rather than named here.

:class:`RiskBlock` is the fourth, added with Phase 5 (**D34**) for §7's rule table. A
:class:`Reject` says *this candidate is not tradeable*; a ``RiskBlock`` says *this account may
not take this trade right now*, and the same candidate is fine tomorrow. Mixing them would let
:mod:`tradipy.scanner` filter a universe on ``LOSS_STREAK_LOCKOUT``, which is K5's shape exactly.
There is also a concrete asymmetry that no shared enum can express: two §7 rows' Violation Action
is *"Flatten all; lock account"*, which is not a rejection of anything.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Reject", "SoftFlag", "ExitReason", "RiskBlock"]


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

    # --- PRD §3.2 / §3.3 / §3.4 setup recognition (Phase 4) ----------------
    #: PRD §3.2 / §3.3 / §3.4 — the setup's pattern is not present at the bar being evaluated:
    #: no flag, no consolidation, no dip, or a criterion the pattern itself fails. The **only**
    #: rejection code Phase 4 adds. Every other way a setup can be declined already had one,
    #: which is the argument for the code namespace being small: a new code is a new rule, and
    #: the pre-entry gates are §3.1's rules rather than each setup's.
    #:
    #: :class:`~tradipy.setups.SetupOutcome` carries every criterion and its arithmetic, so
    #: *which* part of the pattern is absent is readable without re-deriving it. §4.2's table
    #: names a code per row; §3 names none at all, so this name is the implementation's and PRD
    #: §4.2's rejection-code table should adopt or replace it — the same standing request
    #: ``STOP_TOO_WIDE`` carries.
    SETUP_NOT_PRESENT = "SETUP_NOT_PRESENT"


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


class ExitReason(Enum):
    """Why an **open** position is exited, for the §3 post-entry rules.

    A third namespace rather than more :class:`Reject` members, for the reason the second one
    exists: a rejection declines a trade that was never taken, and an exit closes one that
    was. Mixing them would let a pre-entry gate return ``BAILED_OUT`` — meaningless — and let
    an exit rule return ``SPREAD_TOO_WIDE``, which reads as a rejection of something already
    filled. ``tests/test_enforcement.py`` performs both.

    **Both names are transcribed from PRD §20.12's state machine, not invented here.** That
    matters because §20.12 itself is Phase 5/6's — the states, their transitions and their
    persistence need a position — while the *rules* that reach two of those states are §3's and
    are pure functions of the bars after entry. Taking the names from §20.12 is what keeps the
    two halves able to meet: a Phase 5 state machine consuming these does not have to reconcile
    a second vocabulary.
    """

    #: PRD §20.12 / §3.2 / §3.3 — the breakout-or-bailout timer expired without the move the
    #: entry was predicated on. §3.2 requires a conjunction (no close above entry **and** no new
    #: high above the breakout candle's), §3.3 states only the second condition, and §3.4 states
    #: no bailout rule at all — so this code is reached by three different tests, which is
    #: raised as a spec question in docs/CHANGELOG.md rather than unified here.
    BAILED_OUT = "BAILED_OUT"

    #: PRD §20.12 / §3.2 / §3.3 / §3.4 — a post-entry invalidation fired: a close back below
    #: VWAP (all three setups) or, for §3.3, a close back below the prior HOD within
    #: ``hod_reclaim_invalidation_candles``.
    INVALIDATED = "INVALIDATED"

    # --- PRD §9.2 `ClosedTrade.exit_reason`, the remaining four (Phase 5) --
    # §9.2 enumerates six exit reasons; §20.12 has state names matching only three of them
    # (`STOPPED_OUT`, `INVALIDATED`, `BAILED_OUT`). The three below have no §20.12 state, and
    # §20.12's `EXPIRED` has no exit reason — consistently, because a position that expired
    # never opened and so produces no `ClosedTrade`. Both halves of that asymmetry are raised in
    # docs/CHANGELOG.md rather than reconciled here.

    #: PRD §9.2 / §20.12 / §3.1.1 — the full ladder ran: T1, T2, then the trail closed the
    #: final tranche. The `TRAILING -> CLOSED` edge, and the only exit that is not a failure.
    LADDER_COMPLETE = "LADDER_COMPLETE"

    #: PRD §9.2 / §20.12 — a protective stop filled. A §20.12 *state* as well as an exit reason,
    #: reachable from `OPEN_FULL`, `T1_FILLED` and `TRAILING` per that section's table.
    STOPPED_OUT = "STOPPED_OUT"

    #: PRD §9.2 / §7 — flattened at the end of the enabled session window. §7's trading-hours
    #: row rejects new *entries* outside the window; closing what is already open is this.
    EOD_FLAT = "EOD_FLAT"

    #: PRD §9.2 / §7.2 — the emergency kill switch flattened everything. Distinct from
    #: :attr:`RiskBlock.TRADING_HALTED`, which declines an entry: this closes a position.
    KILL_SWITCH = "KILL_SWITCH"


class RiskBlock(Enum):
    """Why the **account** may not take a trade right now — PRD §7's rule table.

    One member per §7 row that is not already a :class:`Reject`, named for the rule rather than
    for the condition, because §9.2's ``RiskDecision.reject_reason`` is *"§7 rule name or §4.2
    code"* and §7 is the table those names come from.

    §7's two signal-time rows are **deliberately absent**: Min R:R and Spread check are
    :func:`tradipy.gates.check_room` and :func:`tradipy.gates.check_spread`, they already return
    :class:`Reject` members, and giving them a second spelling here would be the v1.2 defect
    class. :class:`~tradipy.risk.RiskDecision` carries ``RiskBlock | Reject | None`` for exactly
    that reason.
    """

    #: PRD §7 row 1 — **NON-BYPASSABLE.** Total open risk across all positions, measured from
    #: their *current live stops* plus the pending order (§7.1.1), would exceed
    #: ``start_of_day_equity × max_risk_per_trade_pct``. Note this is a cap on the **total**,
    #: not per position, which is what makes ``max_open_positions`` > 1 unreachable at full size
    #: — raised in docs/CHANGELOG.md and pinned by ``tests/test_enforcement.py``.
    MAX_RISK_EXCEEDED = "MAX_RISK_EXCEEDED"

    #: PRD §7 row 2 — **NON-BYPASSABLE.** Realized + unrealized P&L at or below
    #: ``-start_of_day_equity × daily_loss_pct``. §7 gives this rule three enforcement points
    #: (continuous at 1 s, post-fill, and §6.3's pre-order list); only the pre-order one is
    #: implemented, which narrows open question **G2** rather than closing it.
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"

    #: PRD §7 row 3 — open positions already at ``max_open_positions``.
    MAX_POSITIONS = "MAX_POSITIONS"

    #: PRD §7 row 4 / §2 "Three Strikes Rule" — ``consecutive_losses >=
    #: max_consecutive_losses``. §7's action is *"Lock new entries; **allow exits**"*, which is
    #: why :func:`tradipy.risk.approve` takes the order's intent explicitly rather than inferring
    #: it from a side.
    LOSS_STREAK_LOCKOUT = "LOSS_STREAK_LOCKOUT"

    #: PRD §7 row 5 / §2.2 — ``shares × entry > buying_power × max_bp_usage_pct``. §2.2 states
    #: the same constraint as a *sizing* cap, where :func:`tradipy.gates.position_size` applies
    #: it; §7 states it as a pre-order *rejection*. Both are implemented, at their own points.
    BUYING_POWER = "BUYING_POWER"

    #: PRD §7 row 6 — the order would open the **4th** day trade in a rolling 5-business-day
    #: window while equity is below FINRA's $25,000 threshold. Not bypassable per §7.
    PDT_VIOLATION = "PDT_VIOLATION"

    #: PRD §7 row 7 — session peak-to-trough drawdown beyond ``session_dd_pct``. Enforcement
    #: point *Continuous*, so through Phase 5 this was produced by a predicate no loop called;
    #: :func:`tradipy.monitor.evaluate` is that caller as of Phase 6, and the action it produces
    #: is §7's *"Flatten all; lock account"*.
    SESSION_DRAWDOWN = "SESSION_DRAWDOWN"

    #: PRD §7 row 8 — rolling 5-day drawdown beyond ``multi_day_dd_pct``. Enforcement point
    #: *End of day*, action *"Lock account next day"* — which §10's ``daily_state`` has no column
    #: for, so the lock is carried by :attr:`tradipy.daily.DailyState.locks_next_session` and the
    #: gap is recorded in :data:`tradipy.daily.UNPERSISTED_FIELDS`.
    MULTI_DAY_DRAWDOWN = "MULTI_DAY_DRAWDOWN"

    #: PRD §7 row 9 — outside the enabled session window. Evaluated against §20.1's ordinal
    #: minute from the open, not a wall clock (§21.1).
    OUTSIDE_SESSION_WINDOW = "OUTSIDE_SESSION_WINDOW"

    #: PRD §7 row 10 / §7.1.3 / **D21** — more than ``max_correlated_positions`` sharing a
    #: correlation group. The group is *assigned* from a supplied catalyst key or sector, because
    #: sourcing either is a feed; the rule enforced here is the count.
    CORRELATED_EXPOSURE = "CORRELATED_EXPOSURE"

    #: PRD §7 row 11 / §7.2 / §7.1.2 — the account is locked: kill switch, daily-loss lockout or
    #: a drawdown lock carried over. This is §10's ``daily_state.trading_halted``, supplied
    #: rather than sensed, because §7.2's trigger is a file sentinel and no module here reads a
    #: file (D30).
    TRADING_HALTED = "TRADING_HALTED"

    #: PRD §6.7 — an order already exists for this ``idempotency_key``. §6.3's eighth check.
    #: **The weakest member of this enum, and it says so:** §6.7 requires the *database* to be
    #: the arbiter so protection survives a crash mid-submission, and Phase 5 has no store — so
    #: this is raised against a set of keys the caller hands in. See docs/PHASE-5-DESIGN.md §1.1.
    DUPLICATE_ORDER = "DUPLICATE_ORDER"
