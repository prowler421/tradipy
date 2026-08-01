"""PRD §10's ``daily_state``, §20.8's snapshot, §9.2's ``ClosedTrade``, and §7 row 4.

Normative sources: PRD §10.1 (the ``daily_state`` and ``closed_trades`` schemas), §20.8
(start-of-day equity), §7 (the rule table's *Post-trade close* row), §7.1 (equity definitions),
§7.1.2 (state persistence), §7.2 (the kill switch's manual reset), §9.2 (the ``ClosedTrade``
contract), §18.7 (the figure the viability gate is judged on). §20 governs on any conflict.

**What this module is.** The account's own history, as a value. :mod:`tradipy.risk` answers
*may this account take this trade* against a :class:`~tradipy.risk.RiskState` it is **handed**;
every field of that state — realized P&L, the consecutive-loss count, the day-trade count, the
session peak — is a fact about trades that already closed, and nothing in the package produced
one. This module does: :class:`DailyState` is §10's row, :class:`ClosedTrade` is §9.2's, and
:func:`record_close` is §7 row 4's *Post-trade close* enforcement point.

**Why there is not a second state type.** :class:`DailyState` and
:class:`~tradipy.risk.RiskState` share eight fields, which is the exact configuration the v1.2
defect class arises in. They are not independent: ``DailyState`` is §10's **persisted row** and
``RiskState`` is §7's **evaluation input**, and :func:`risk_state` is the only function that
turns one into the other. ``tests/test_enforcement.py`` derives both field sets from the
dataclasses and asserts the bridge carries every shared one, so a field added to either and
forgotten on the bridge fails rather than silently defaulting.

**What is deliberately not here:**

* **Any store.** §7.1.2 requires the non-bypassable limits to survive a restart.
  :func:`to_row` and :func:`from_row` map §10's columns to and from a plain ``dict``; there is
  no file, no driver and no ``sqlite3``. So §7.1.2's *arithmetic* is testable — a reloaded row
  reproduces the same lockout — and its *durability* is not, which is D30 and is stated rather
  than implied.
* **The columns §10 does not have.** Four facts §7's rules read have no ``daily_state`` column:
  see :data:`UNPERSISTED_FIELDS`, which is the finding rather than an implementation note.
* **A clock.** ``session_date`` is a supplied ISO string and §10's ``updated_at`` is not
  written — the same treatment :class:`~tradipy.risk.RiskDecision` gives ``evaluated_at``.
* **§9.2's ``JournalEntry`` and §8.3's metrics.** §12.1 puts the CLI journal in the **MVP Gate**
  row and the metrics in Phase 4b. ``ClosedTrade`` is here because §7 row 4 needs one.

This module **does not round.** A P&L is money accumulated rather than a price level compared
against a tick, and an exit price is an *observed* fill rather than a level submitted to a
broker, so §20.13 does not reach either. Same posture as :mod:`tradipy.risk`, and the
enforcement suite derives the set of rounding modules from the source rather than trusting this
paragraph.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from decimal import Decimal
from enum import Enum

from tradipy.params import Config
from tradipy.rejects import ExitReason, RiskBlock
from tradipy.risk import OpenPosition, RiskState, live_equity
from tradipy.setups import SetupType

__all__ = [
    "SessionPhase",
    "ClosedTrade",
    "DailyState",
    "DAILY_STATE_COLUMNS",
    "CLOCK_COLUMNS",
    "UNPERSISTED_FIELDS",
    "SessionNotOpenError",
    "ConfirmationRequiredError",
    "open_session",
    "record_snapshot",
    "mark_to_market",
    "record_close",
    "roll_multi_day_peak",
    "record_multi_day_peak",
    "lock",
    "clear_lock",
    "to_row",
    "from_row",
    "risk_state",
    "BRIDGE_EXCEPTIONS",
    "bridge_fields",
]


class SessionPhase(Enum):
    """Where a session is, in the three states PRD §20.8 and §7 between them describe.

    §20.8 names ``NO_TRADE`` and defines it nowhere else; §7's Violation Action column says
    *"lock account"* in three places and names no state at all. These are the three, and the
    reading is recorded in docs/PHASE-6-DESIGN.md §5.
    """

    #: PRD §20.8 — no start-of-day equity snapshot yet. **Not** an equity of zero: every
    #: non-bypassable limit is denominated in the snapshot, so a placeholder would satisfy the
    #: type and defeat the sentence. :func:`risk_state` refuses this phase.
    NO_TRADE = "NO_TRADE"
    #: Snapshot taken, no lock in force.
    TRADING = "TRADING"
    #: PRD §7 — the account is locked. §7.2's reset is :func:`clear_lock`.
    LOCKED = "LOCKED"


@dataclass(frozen=True)
class ClosedTrade:
    """PRD §9.2's ``ClosedTrade``, minus the four fields this layer cannot honestly fill.

    §9.2 also lists ``trade_id``, ``signal_id``, ``opened_at`` and ``closed_at``. The first two
    are join keys the caller owns and the last two are ``datetime``\\ s from a clock §21.1
    forbids here — the same split :class:`~tradipy.risk.RiskDecision` makes for ``signal_id``
    and ``evaluated_at``.

    **The three money figures are derived, not stored.** §9.2 marks ``net_pnl`` *"the figure
    §18.7 is judged on"* and requires ``r_multiple`` to be *"computed on NET P&L, not gross"*, so
    the two comments together are what the viability gate turns on. A stored field can be
    computed once, wrongly, and agree with itself forever; a property cannot disagree with its
    inputs.

    ``entry_price`` and ``exit_price`` are §9.2's volume-weighted averages **across fills** and
    are supplied. Nothing here rounds them: they are observed prices rather than levels
    submitted to a broker, so §20.13's requirement does not reach them.
    """

    symbol: str
    setup_type: SetupType
    #: §9.2: volume-weighted across entry fills.
    entry_price: Decimal
    #: §9.2: volume-weighted across all exit legs.
    exit_price: Decimal
    shares: int
    #: The signal's R. §9.2 does not carry it on ``ClosedTrade`` and ``r_multiple`` cannot be
    #: computed without it — the initial dollar risk is the denominator, and reconstructing it
    #: from ``entry_price - stop`` would need a stop this contract does not have either.
    r_per_share: Decimal
    commission: Decimal
    fees: Decimal
    exit_reason: ExitReason
    #: §20.14 / §9.2 — excluded from the §18.7 gate when ``True``.
    spread_estimated: bool = False

    def __post_init__(self) -> None:
        if self.shares <= 0:
            raise ValueError(
                f"a closed trade must have shares, got {self.shares}. PRD §9.2's r_multiple "
                "divides by shares x R, and a zero-share trade has no multiple to report."
            )
        if self.r_per_share <= 0:
            raise ValueError(
                f"r_per_share must be positive, got {self.r_per_share}. It is the denominator "
                "of PRD §9.2's r_multiple and PRD §2.2's sizing already refuses a zero R."
            )
        if self.entry_price <= 0 or self.exit_price <= 0:
            raise ValueError(
                f"entry_price={self.entry_price} and exit_price={self.exit_price} must both be "
                "positive; PRD §4.2's price floor is $1.00 and a non-positive fill is not a fill."
            )
        if self.commission < 0 or self.fees < 0:
            raise ValueError(
                f"commission={self.commission} and fees={self.fees} are costs and cannot be "
                "negative; a rebate is not modelled and inventing one would flatter §18.7."
            )

    @property
    def gross_pnl(self) -> Decimal:
        """§9.2: ``(exit - entry) x shares``. Long-only, per §9.2's ``direction``."""
        return (self.exit_price - self.entry_price) * self.shares

    @property
    def net_pnl(self) -> Decimal:
        """§9.2: *"the figure §18.7 is judged on"* — gross less commission and fees."""
        return self.gross_pnl - self.commission - self.fees

    @property
    def r_multiple(self) -> Decimal:
        """§9.2: *"computed on NET P&L, not gross"*, over the initial dollar risk.

        The denominator is ``r_per_share x shares``, which is what §2.2 sized the position
        against — so ``1.0`` here means the trade made back exactly the amount §7's first row
        had at stake, **after** costs. Computing it on gross is the version that makes a
        cost-negative strategy look breakeven, which is the bias §18.2 names.
        """
        return self.net_pnl / (self.r_per_share * self.shares)

    @property
    def is_loss(self) -> bool:
        """Whether §7 row 4's consecutive-loss count should advance.

        **Net, and strictly negative.** §7 never says which; §9.2 fixes the other half of the
        question by computing ``r_multiple`` on net, and §18.7 is judged net — so a trade that
        clears gross and pays it back in commission cost the account money, and a streak rule
        calling that a win counts something the account did not experience.

        A **scratch** (``net_pnl == 0``) is not a loss and therefore resets the streak.
        *Consecutive* means unbroken, and a trade that was not a loss breaks a run of them. Both
        readings are recorded in docs/PHASE-6-DESIGN.md §5 and raised in docs/CHANGELOG.md.
        """
        return self.net_pnl < 0


#: PRD §10's ``daily_state`` columns, mapped to the :class:`DailyState` field each is written
#: from. ``trading_halted`` has no field of its own — it is derived from :attr:`DailyState.phase`,
#: because a phase and a boolean saying the same thing is the v1.2 defect class.
DAILY_STATE_COLUMNS: Mapping[str, str] = {
    "session_date": "session_date",
    "start_of_day_equity": "start_of_day_equity",
    "realized_pnl": "realized_pnl",
    "consecutive_losses": "consecutive_losses",
    "day_trades_in_window": "day_trades_in_window",
    "trading_halted": "phase",
    "halt_reason": "halt_reason",
}

#: §10 columns this layer deliberately does not write. ``updated_at`` is a ``TIMESTAMPTZ`` and
#: §21.1 forbids a clock here, so a store supplies it — the same treatment
#: :class:`~tradipy.risk.RiskDecision` gives ``evaluated_at``.
CLOCK_COLUMNS: tuple[str, ...] = ("updated_at",)

#: **§7 inputs that §10's ``daily_state`` has no column for.** Enumerated rather than left to be
#: discovered, exactly as :data:`tradipy.risk.UNREACHABLE_BLOCKS` was: a field that silently
#: fails to round-trip is worse than one documented as not round-tripping, and the difference is
#: a named set with a test on it.
#:
#: The consequence, which is finding 1 in docs/PHASE-6-DESIGN.md §6: on §10's schema as written,
#: a restart mid-session restores the daily-loss lockout (§7 row 2) and **silently resets both
#: drawdown rules** (rows 7 and 8), and a restart overnight loses row 8's *"Lock account next
#: day"* entirely — the one action whose whole purpose is to survive to the next session. Raised
#: in docs/CHANGELOG.md; not resolved, because adding four columns to §10 is a spec change.
UNPERSISTED_FIELDS: frozenset[str] = frozenset(
    {
        "unrealized_pnl",
        "session_equity_peak",
        "multi_day_peak_equity",
        "locks_next_session",
    }
)


class SessionNotOpenError(ValueError):
    """Raised when a rule is applied to a session PRD §20.8 has not opened.

    A distinct type rather than a bare ``ValueError`` for :class:`IllegalTransitionError`'s reason:
    *"the snapshot has not happened"* and *"this argument was the wrong shape"* are different
    facts to a caller, and §20.8's whole point is that the first one must stop the system rather
    than be worked around.
    """


class ConfirmationRequiredError(ValueError):
    """Raised when PRD §7.2's manual reset is attempted without the confirmation phrase."""


@dataclass(frozen=True)
class DailyState:
    """PRD §10's ``daily_state`` row, plus the four §7 inputs §10 has no column for.

    Keyed by ``session_date``, as §10's primary key is. Every mutation is a pure function
    returning a new value — :func:`record_snapshot`, :func:`mark_to_market`,
    :func:`record_close`, :func:`lock`, :func:`clear_lock` — so a caller cannot advance the
    session by assignment, which is the property `Config` needed four separate fixes to get.
    """

    session_date: str
    phase: SessionPhase = SessionPhase.NO_TRADE
    #: §20.8's snapshot. ``None`` **iff** the phase is ``NO_TRADE``; see :func:`risk_state`.
    start_of_day_equity: Decimal | None = None
    realized_pnl: Decimal = Decimal(0)
    unrealized_pnl: Decimal = Decimal(0)
    consecutive_losses: int = 0
    day_trades_in_window: int = 0
    #: Which §7 row locked the account. A :class:`~tradipy.rejects.RiskBlock` rather than a
    #: fifth enum: §7's table is where these names come from and ``RiskBlock`` is already one
    #: member per §7 row. §10's column is a ``VARCHAR(48)``, so :func:`risk_state` and
    #: :func:`to_row` write ``.value``.
    halt_reason: RiskBlock | None = None
    #: §7 row 7's peak-to-trough basis. Set to the snapshot when one is taken.
    session_equity_peak: Decimal | None = None
    #: §7 row 8's trailing peak, from :func:`roll_multi_day_peak`. ``None`` means unknown, and
    #: :func:`tradipy.risk.multi_day_drawdown_breached` returns ``False`` rather than guessing.
    multi_day_peak_equity: Decimal | None = None
    #: §7 row 8's Violation Action — *"Lock account next day"*. §10 has no column for it and
    #: this layer holds one session, so the lock is carried out of the session that earned it
    #: and into the next by :func:`open_session`'s ``carried_lock``.
    locks_next_session: bool = False

    def __post_init__(self) -> None:
        has_equity = self.start_of_day_equity is not None
        if (self.phase is SessionPhase.NO_TRADE) == has_equity:
            raise ValueError(
                f"phase={self.phase.value} and start_of_day_equity={self.start_of_day_equity} "
                "disagree. PRD §20.8: the session is NO_TRADE until the snapshot succeeds and "
                "carries a snapshot after — it never falls back to a stale or computed value."
            )
        if self.phase is SessionPhase.LOCKED and self.halt_reason is None:
            raise ValueError(
                "a LOCKED session must name the §7 row that locked it; halt_reason is §10's "
                "own column and an unexplained lock cannot be reset under §7.2."
            )

    @property
    def trading_halted(self) -> bool:
        """§10's ``trading_halted`` column, and §7's *"may this account act"*.

        **Anything but ``TRADING``**, which includes ``NO_TRADE``: §20.8 blocks trading until the
        snapshot succeeds just as firmly as §7's lockout blocks it afterwards, and
        :func:`tradipy.risk.approve` reads exactly this field. Derived rather than stored,
        because a phase and a boolean asserting the same thing is the v1.2 defect class.
        """
        return self.phase is not SessionPhase.TRADING

    @property
    def live_equity(self) -> Decimal:
        """PRD §7.1: ``start_of_day_equity + realized + unrealized``.

        Routed through :func:`tradipy.risk.live_equity` rather than restated, because §7.1 is
        emphatic that the two equity figures must stay distinct and one definition is how that
        stays true. Raises in ``NO_TRADE``: without §20.8's snapshot there is no equity, which
        is the whole of that section.
        """
        return live_equity(risk_state(self))


def open_session(session_date: str, *, carried_lock: RiskBlock | None = None) -> DailyState:
    """Open a session in PRD §20.8's ``NO_TRADE`` phase, optionally already locked.

    §20.8: *"If the broker is unreachable at 09:30, the system remains in ``NO_TRADE`` state
    until a snapshot succeeds — it does not fall back to a stale or computed value, because
    every non-bypassable risk limit is denominated in it."* So a session begins with **no**
    equity, and :func:`risk_state` refuses to evaluate §7 against it.

    ``carried_lock`` is §7 row 8's *"Lock account next day"* arriving. That action cannot be a
    mutation of the session that earned it, and §10 has no column for a pending lock, so the
    previous session's :attr:`DailyState.locks_next_session` is the caller's input here. The
    reason is preserved through the ``NO_TRADE`` phase and applied by :func:`record_snapshot`.
    """
    return DailyState(session_date=session_date, halt_reason=carried_lock)


def record_snapshot(state: DailyState, equity: Decimal) -> DailyState:
    """PRD §20.8: take the start-of-day equity snapshot, **once**.

    *"Snapshot of broker net liquidation value taken at the first successful broker sync at or
    after 09:30:00 ET … and immutable for the remainder of the session."* Immutable is enforced
    here rather than assumed: a second call raises, whatever value it carries.

    The session becomes ``TRADING``, or ``LOCKED`` when :func:`open_session` carried §7 row 8's
    next-day lock in — which is the one path by which a session can be locked before it has
    taken a trade.
    """
    if state.phase is not SessionPhase.NO_TRADE:
        raise ValueError(
            f"session {state.session_date} already has a start-of-day equity snapshot "
            f"(${state.start_of_day_equity}). PRD §20.8 makes it immutable for the remainder "
            "of the session; every non-bypassable limit is denominated in it."
        )
    if equity <= 0:
        raise ValueError(
            f"start-of-day equity must be positive, got {equity}. PRD §2.0 bounds it at "
            "$25,000 and up; a non-positive snapshot makes every §7 threshold zero."
        )
    locked = state.halt_reason is not None
    return replace(
        state,
        phase=SessionPhase.LOCKED if locked else SessionPhase.TRADING,
        start_of_day_equity=equity,
        session_equity_peak=equity,
    )


def _require_open(state: DailyState, what: str) -> Decimal:
    if state.start_of_day_equity is None:
        raise SessionNotOpenError(
            f"cannot {what} for session {state.session_date}: PRD §20.8's start-of-day equity "
            "snapshot has not been taken, so the session is NO_TRADE and every §7 threshold "
            "denominated in that figure is undefined."
        )
    return state.start_of_day_equity


def mark_to_market(state: DailyState, unrealized_pnl: Decimal) -> DailyState:
    """Update unrealized P&L and PRD §7 row 7's session peak.

    §7 row 2's condition is *"Realized + unrealized P&L"* and its enforcement points are
    *Continuous (1 sec)* and *post-fill*, so both need a current mark; §7 row 7 is
    *"peak-to-trough"*, so the peak has to be maintained as the session runs rather than
    recomputed from a history nothing keeps.

    The mark itself is **supplied**. Deriving it would need live prices for every open position,
    which is a feed, and D30 keeps feeds out of this layer — the same split
    ``spread_at_signal`` and ``buying_power`` already take.
    """
    _require_open(state, "mark to market")
    marked = replace(state, unrealized_pnl=unrealized_pnl)
    peak = state.session_equity_peak
    live = marked.live_equity
    return replace(marked, session_equity_peak=live if peak is None or live > peak else peak)


def record_close(
    state: DailyState,
    trade: ClosedTrade,
    *,
    unrealized_after: Decimal,
    day_trade: bool = True,
) -> DailyState:
    """PRD §7 row 4's *Post-trade close* enforcement point: accrue one closed trade.

    Four §7 inputs move, and none of them was computed anywhere before this function:

    * ``realized_pnl`` gains :attr:`ClosedTrade.net_pnl` — §7 row 2's numerator, and §18.7's.
    * ``consecutive_losses`` advances on a loss and **resets to zero otherwise**, which is §7
      row 4 and §2's Three Strikes Rule. See :attr:`ClosedTrade.is_loss` for what counts.
    * ``day_trades_in_window`` advances when ``day_trade`` — §7's PDT row counts day trades
      specifically, and while every MVP setup is intraday (§3, §12.2) an exit that is not a day
      trade must be expressible or the count becomes an assumption.
    * ``session_equity_peak`` re-marks, because closing a trade moves ``live_equity``.

    ``unrealized_after`` is required and has no default: after a close the remaining open
    positions are worth something different, and a default of the previous value would double-
    count the closed one into §7 row 2's numerator. §2.2's sizing has the same shape of
    argument — a default that lies is worse than a required argument.

    **Allowed while ``LOCKED``**, and that is not an oversight: §7 row 4's action is *"Lock new
    entries; **allow exits**"*, and a flatten under rows 2, 7 or 11 closes trades by definition.
    Refused only in ``NO_TRADE``, where there is no equity to denominate anything in.
    """
    _require_open(state, "record a closed trade")
    streak = state.consecutive_losses + 1 if trade.is_loss else 0
    accrued = replace(
        state,
        realized_pnl=state.realized_pnl + trade.net_pnl,
        consecutive_losses=streak,
        day_trades_in_window=state.day_trades_in_window + (1 if day_trade else 0),
    )
    return mark_to_market(accrued, unrealized_after)


def roll_multi_day_peak(session_closes: Sequence[Decimal], cfg: Config) -> Decimal | None:
    """PRD §7 row 8: the peak equity over the trailing ``multi_day_dd_window_sessions``.

    Returns ``None`` for an empty history, which is the value
    :func:`tradipy.risk.multi_day_drawdown_breached` reads as *"unmeasured"* and declines to
    treat as a breach. Inventing a peak would make the rule fire or not fire on a fabricated
    number, which is the objection D30 makes to undeclared data one layer out.

    **Which sessions are in the window is not decided here.** §7 says *"Rolling 5-day"* and §21.4
    owns the trading calendar — holidays and half-days included — so this takes the closes it is
    given, most recent last, and reads only how many of them count. A risk engine that parsed a
    calendar would be holding a concern §21.1 and D30 both keep out.
    """
    window = int(cfg["multi_day_dd_window_sessions"])
    recent = list(session_closes)[-window:]
    return max(recent) if recent else None


def record_multi_day_peak(
    state: DailyState, session_closes: Sequence[Decimal], cfg: Config
) -> DailyState:
    """Set PRD §7 row 8's trailing peak from the closes of the sessions before this one.

    Split from :func:`roll_multi_day_peak` so that the *window arithmetic* and the *state
    transition* are separately testable, and because the peak is the one §7 input that comes
    from outside the session rather than from anything that happened inside it.

    Refused in ``NO_TRADE`` like every other mutation: §7 row 8's threshold is
    ``start_of_day_equity x multi_day_dd_pct``, so a peak set before the snapshot would be
    compared against a denominator that does not exist yet.
    """
    _require_open(state, "record a multi-day peak")
    return replace(state, multi_day_peak_equity=roll_multi_day_peak(session_closes, cfg))


def lock(state: DailyState, reason: RiskBlock) -> DailyState:
    """Apply PRD §7's *"lock account"* to an open session, naming the row that did it.

    Refused in ``NO_TRADE``: a session with no snapshot is already halted — see
    :attr:`DailyState.trading_halted` — and giving it a §7 reason would claim a rule fired that
    could not have been evaluated, since every §7 threshold is denominated in the snapshot.
    :func:`open_session`'s ``carried_lock`` is the one way a reason reaches an unopened session,
    and it comes from the previous one.

    Re-locking an already-locked session with a **different** reason is permitted and keeps the
    new one: §7's rows are not exclusive, and the row a reviewer needs to see is the last one
    that bound. Re-locking with the same reason is a no-op by construction.
    """
    _require_open(state, "lock")
    return replace(state, phase=SessionPhase.LOCKED, halt_reason=reason)


def clear_lock(state: DailyState, confirmation: str, expected: str) -> DailyState:
    """PRD §7.2: *"Requires manual reset with confirmation phrase."*

    Both sides are **supplied**. The rule this enforces is that a lock cannot be cleared
    implicitly — which is arithmetic — while sourcing the phrase is §21.5's OS keyring, and
    §21.5 is explicit that credentials never live in configuration or in the repository. So
    there is no registry row and no constant here; a caller passes what the operator typed and
    what the keyring holds.

    This is the mechanism behind §11.1's *"lock persists across restart … and cannot be cleared
    by relaunching"*: :func:`from_row` reloads a locked session locked, and the only exit is this
    function.

    An **empty** ``expected`` is refused rather than matched. A guard whose expected value is the
    empty string accepts the empty string, which is what a caller with no keyring would pass —
    a check that passes when its configuration is missing is the fifth defect class.
    """
    if not expected:
        raise ConfirmationRequiredError(
            "PRD §7.2's reset needs a confirmation phrase to compare against, and an empty "
            "expected value would accept an empty confirmation. §21.5 puts the phrase in the "
            "OS keyring; a missing one must block the reset, not wave it through."
        )
    if state.phase is not SessionPhase.LOCKED:
        raise ValueError(
            f"session {state.session_date} is {state.phase.value}, not LOCKED; there is no §7 "
            "lock to reset. Clearing a lock that is not there cannot be distinguished from "
            "clearing one that is, which is why tradipy.positions.transition refuses a "
            "self-transition for the same reason."
        )
    if confirmation != expected:
        raise ConfirmationRequiredError(
            f"confirmation phrase does not match; the §7 lock on {state.session_date} "
            f"({state.halt_reason.value if state.halt_reason else '?'}) stands. PRD §7.2 "
            "requires a manual reset with the phrase, and §21.5 requires the same phrase for "
            "the API and UI triggers."
        )
    return replace(state, phase=SessionPhase.TRADING, halt_reason=None)


def to_row(state: DailyState) -> dict[str, str | int | bool | None]:
    """Serialise the §10 ``daily_state`` columns. **No store; a plain ``dict``.**

    §7.1.2's requirement is that the non-bypassable limits survive a restart. This is the half
    of that which is arithmetic — the row a store would write, and the row :func:`from_row`
    reads back with the lockout intact. The other half is a database, and D30 admits none, so
    §7.1.2 stays open; ``tests/test_enforcement.py`` pins the absence rather than implying it
    closed.

    ``Decimal`` values are written as **strings**, not floats: §10 declares them ``DECIMAL`` and
    §9.2 requires ``Decimal`` wherever a value is accumulated into P&L, so a float round trip
    would lose exactly the precision the type was chosen for.

    Scope, stated because an unqualified claim about a serialiser is what F8 was about: this
    covers :data:`DAILY_STATE_COLUMNS` and nothing else. §10's ``updated_at`` is in
    :data:`CLOCK_COLUMNS` and is a store's to supply; the four fields in
    :data:`UNPERSISTED_FIELDS` have no column at all, which is a finding rather than an
    omission; and §10's ``closed_trades`` table is **not** written here, because its single
    ``pnl`` column cannot express the gross/net distinction §18.7 is judged on.
    """
    equity = state.start_of_day_equity
    return {
        "session_date": state.session_date,
        "start_of_day_equity": None if equity is None else str(equity),
        "realized_pnl": str(state.realized_pnl),
        "consecutive_losses": state.consecutive_losses,
        "day_trades_in_window": state.day_trades_in_window,
        "trading_halted": state.trading_halted,
        "halt_reason": None if state.halt_reason is None else state.halt_reason.value,
    }


def from_row(row: Mapping[str, str | int | bool | None]) -> DailyState:
    """Rebuild a :class:`DailyState` from a §10 ``daily_state`` row.

    The phase is **reconstructed**, because §10 has no column for it and inventing one would be
    a schema change: no snapshot means ``NO_TRADE`` (§20.8), a halted session with a snapshot
    means ``LOCKED``, and anything else is ``TRADING``. That reconstruction is exactly why
    :attr:`DailyState.trading_halted` is derived from the phase rather than stored beside it —
    with two stored fields the round trip could disagree with itself.

    The four fields in :data:`UNPERSISTED_FIELDS` come back at their defaults, which is finding
    1 in docs/PHASE-6-DESIGN.md §6 rather than a quirk of this function: §7 rows 7 and 8 lose
    their inputs across a restart on §10's schema as written.
    """
    equity_raw = row["start_of_day_equity"]
    equity = None if equity_raw is None else Decimal(str(equity_raw))
    reason_raw = row["halt_reason"]
    reason = None if reason_raw is None else RiskBlock(str(reason_raw))

    if equity is None:
        phase = SessionPhase.NO_TRADE
    elif bool(row["trading_halted"]):
        phase = SessionPhase.LOCKED
    else:
        phase = SessionPhase.TRADING

    return DailyState(
        session_date=str(row["session_date"]),
        phase=phase,
        start_of_day_equity=equity,
        realized_pnl=Decimal(str(row["realized_pnl"])),
        consecutive_losses=int(row["consecutive_losses"]),  # type: ignore[arg-type]
        day_trades_in_window=int(row["day_trades_in_window"]),  # type: ignore[arg-type]
        halt_reason=reason,
    )


def risk_state(
    state: DailyState,
    positions: Sequence[OpenPosition] = (),
    submitted_keys: frozenset[str] = frozenset(),
) -> RiskState:
    """Build the §7 evaluation input from §10's row. **The only bridge between the two.**

    ``positions`` and ``submitted_keys`` are arguments rather than fields of
    :class:`DailyState` because neither is a ``daily_state`` column: §10 puts them in
    ``positions`` and ``idempotency_keys``, which are separate tables with separate lifetimes.
    Every other field of :class:`~tradipy.risk.RiskState` comes from this state, and
    ``tests/test_enforcement.py`` derives that correspondence from the two dataclasses so a new
    field on either cannot be quietly dropped here.

    **Raises in ``NO_TRADE``.** PRD §20.8: *"it does not fall back to a stale or computed
    value, because every non-bypassable risk limit is denominated in it."* The only way to make
    that sentence enforceable is for the fallback not to exist, so
    :attr:`DailyState.start_of_day_equity` is ``None`` and this refuses rather than defaulting
    to zero — which would give every §7 threshold a denominator of zero and pass every check.
    """
    equity = _require_open(state, "evaluate §7's rules")
    return RiskState(
        start_of_day_equity=equity,
        realized_pnl=state.realized_pnl,
        unrealized_pnl=state.unrealized_pnl,
        consecutive_losses=state.consecutive_losses,
        day_trades_in_window=state.day_trades_in_window,
        trading_halted=state.trading_halted,
        halt_reason=None if state.halt_reason is None else state.halt_reason.value,
        # Passed through whole. `RiskState.open_positions` applies `OPEN_STATES`, and filtering
        # here as well would be two definitions of which positions carry risk — the v1.2 shape,
        # in the function whose entire job is to have one definition of this mapping.
        positions=tuple(positions),
        session_equity_peak=state.session_equity_peak,
        multi_day_peak_equity=state.multi_day_peak_equity,
        submitted_keys=submitted_keys,
    )


#: :class:`~tradipy.risk.RiskState` field names :func:`risk_state` does **not** copy verbatim
#: from a same-named :class:`DailyState` attribute. ``positions`` and ``submitted_keys`` are
#: arguments — §10 puts them in different tables — and ``halt_reason`` changes type across the
#: bridge, because §10's column is a ``VARCHAR(48)`` and this layer holds the typed §7 row.
#:
#: Declared so the enforcement suite can assert that *everything else* is carried straight
#: across, which is checkable, rather than restating the exception list in the test, which is
#: two spellings of one thing — the v1.2 defect class in the constant written to prevent it.
#: ``test_the_daily_state_bridge_cannot_silently_drop_a_field`` reads this and nothing else.
BRIDGE_EXCEPTIONS: frozenset[str] = frozenset({"positions", "submitted_keys", "halt_reason"})


def bridge_fields() -> tuple[frozenset[str], frozenset[str]]:
    """The two dataclasses' field names, for the enforcement suite's derived bridge check.

    Exposed here rather than recomputed in the test so that the *definition* of "a field of
    each" lives beside the bridge it constrains, and a reader changing either dataclass sees
    it. The assertion itself belongs in the test, not here.
    """
    return (
        frozenset(f.name for f in fields(DailyState)),
        frozenset(f.name for f in fields(RiskState)),
    )
