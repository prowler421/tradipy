"""PRD §7's non-pre-order enforcement points, and the flatten §7's Violation Action requires.

Normative sources: PRD §7 (the rule table — read by its **Enforcement Point** and **Violation
Action** columns), §7.1.2 (lockouts), §7.2 (the kill switch), §9.2 (``RiskDecision``'s audit
contract), §20.12 (the position state machine), §21.4 (the flat-all cutoff). §20 governs on any
conflict.

**What this module is.** §7's table has thirteen rows and its Enforcement Point column names six
distinct points. :func:`tradipy.risk.approve` is the *Pre-order* one, and until this module the
other five had no code at all — which is why :mod:`tradipy.risk` ships
``session_drawdown_breached`` and ``multi_day_drawdown_breached`` with no caller and
``UNREACHABLE_BLOCKS`` to say so. This is the caller.

It also reads the column nothing had read: **Violation Action.** *"Reject order"* is
``approve``'s, and the other four — *"Flatten all; lock account for day"*, *"Lock new entries;
allow exits"*, *"Lock account next day"* and *"Flatten all; halt all trading"* — are
:class:`HaltAction`, produced here and applied to §10's row by :func:`apply`.

**Every applicable rule is evaluated on every call**, and :func:`evaluate` asserts its own
output against :data:`RULES_AT` — the same discipline ``approve`` applies against
``EVALUATED_RULES``, and for §9.2's reason: *"every rule checked, for audit."*

**What is deliberately not here:**

* **The 1-second timer.** §7 row 2 says *"Continuous (1 sec)"*. A timer is a clock and §21.1
  forbids one in risk code, so :func:`evaluate` is a pure function of the state it is handed and
  the cadence is ingestion's. The figure is therefore **not registered**: a threshold whose only
  reader would be a loop this package refuses to write is the fifth defect class.
* **The kill-switch file sentinel** at ``$XDG_STATE_HOME/tradipy/kill`` (§7.2, §21.5). No module
  here opens a file (D30); the trigger is a ``kill_switch`` argument.
* **Sending anything.** :func:`flatten_all` computes a directive per open position. Turning one
  into a cancel and a market order is §6.2's ``OrderDraft -> Submit`` arrow, which Phase 5
  refused and this phase refuses again.
* **§21.6's ``Alert``.** A :class:`MonitorDecision` already carries the reason, the action and
  the arithmetic; a notification layer built before anything emits into it is a mechanism wired
  to nothing.

This module **does not round**, for :mod:`tradipy.daily`'s reason: an equity threshold is
``equity x pct`` and a minute is an ordinal, and neither is a price level compared against a
tick.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from tradipy.daily import DailyState, lock
from tradipy.params import Config
from tradipy.positions import (
    OPEN_STATES,
    PositionState,
    reachable_exit_reasons,
    transition,
)
from tradipy.rejects import ExitReason, RiskBlock
from tradipy.risk import (
    OpenPosition,
    RiskState,
    RuleOutcome,
    daily_loss_breached,
    live_equity,
    multi_day_drawdown_breached,
    session_drawdown_breached,
)
from tradipy.rounding import TICK_SIZE

__all__ = [
    "EnforcementPoint",
    "HaltAction",
    "RULES_AT",
    "ACTION_FOR",
    "MonitorDecision",
    "evaluate",
    "apply",
    "eod_flat_due",
    "FlattenDirective",
    "flatten_all",
    "unrepresentable",
    "unrepresentable_flatten_states",
]


class EnforcementPoint(Enum):
    """PRD §7's **Enforcement Point** column, transcribed as that column spells it.

    Six values for thirteen rows. :func:`tradipy.risk.approve` owns :attr:`PRE_ORDER`; this
    module owns the rest. The strings are the column's own text rather than a code-style name,
    because a §7 audit row naming *"post-fill"* and a §7 table saying *"post-fill"* should be
    greppable as the same thing.
    """

    #: ``risk.approve``'s. Present so the enum covers §7's column, absent from :data:`RULES_AT`.
    PRE_ORDER = "Pre-order"
    #: §7 rows 2 and 7. The cadence is the caller's — see the module docstring.
    CONTINUOUS = "Continuous"
    #: §7 row 2, whose enforcement point is *"Continuous (1 sec) **+ post-fill**"*.
    POST_FILL = "post-fill"
    #: §7 row 4, and the point :func:`tradipy.daily.record_close` produces the state for.
    POST_TRADE_CLOSE = "Post-trade close"
    #: §7 row 8.
    END_OF_DAY = "End of day"
    #: §7 row 11, the kill switch. Unioned into every point above — see :data:`RULES_AT`.
    ANY = "Any"


class HaltAction(Enum):
    """PRD §7's **Violation Action** column, for the rows that are not *"Reject order"*.

    Transcribed from §7, including the wording difference between rows 2 and 7 — which is a
    reading rather than a transcription and is recorded on :data:`ACTION_FOR`.
    """

    #: §7 rows 1, 3, 5, 6, 9, 10 and 13, plus §6.3's eighth check. ``risk.approve``'s, present so
    #: the enum covers §7's column and every :class:`~tradipy.rejects.RiskBlock` maps to
    #: something. **Row 12 is deliberately not in that list:** its Violation Action is *"Reject
    #: **signal**"*, not *"Reject order"*, and both rows 12 and 13 return
    #: :class:`~tradipy.rejects.Reject` members rather than ``RiskBlock`` ones anyway.
    REJECT_ORDER = "Reject order"
    #: §7 rows 2 and 7 — *"Flatten all; lock account for day"*.
    FLATTEN_AND_LOCK_DAY = "Flatten all; lock account for day"
    #: §7 row 4 — *"Lock new entries; allow exits"*.
    LOCK_NEW_ENTRIES = "Lock new entries; allow exits"
    #: §7 row 8 — *"Lock account next day"*. The only action that does **not** bind today.
    LOCK_ACCOUNT_NEXT_DAY = "Lock account next day"
    #: §7 row 11 / §7.2 — *"Flatten all; halt all trading"*.
    FLATTEN_AND_HALT = "Flatten all; halt all trading"


#: Which §7 rows this module evaluates at which enforcement point, transcribed from §7's third
#: column. :attr:`EnforcementPoint.PRE_ORDER` is deliberately **absent**: those rows are
#: :func:`tradipy.risk.approve`'s and restating them here would be the v1.2 defect class.
#:
#: :attr:`EnforcementPoint.ANY` is unioned into every other point by :func:`_rules_at` rather
#: than repeated in each entry. *Any* is the widest word in §7's column and the row it marks is
#: the kill switch, so the reading that costs something if it is wrong is the narrow one —
#: deriving the union means a rule marked *Any* cannot be present at four points and missing
#: from the fifth.
RULES_AT: Mapping[EnforcementPoint, tuple[RiskBlock, ...]] = MappingProxyType(
    {
        EnforcementPoint.CONTINUOUS: (RiskBlock.DAILY_LOSS_LIMIT, RiskBlock.SESSION_DRAWDOWN),
        EnforcementPoint.POST_FILL: (RiskBlock.DAILY_LOSS_LIMIT,),
        EnforcementPoint.POST_TRADE_CLOSE: (RiskBlock.LOSS_STREAK_LOCKOUT,),
        EnforcementPoint.END_OF_DAY: (RiskBlock.MULTI_DAY_DRAWDOWN,),
        EnforcementPoint.ANY: (RiskBlock.TRADING_HALTED,),
    }
)

#: PRD §7's **Violation Action** per row, and **total over**
#: :class:`~tradipy.rejects.RiskBlock` — every member maps to something, including the seven
#: whose action is ``REJECT_ORDER`` and therefore :func:`tradipy.risk.approve`'s. Total on
#: purpose: it is what lets ``test_rules_at_covers_every_section_seven_row_this_module_owns``
#: derive its coverage claim from the **enum**, so a §7 row added to ``RiskBlock`` and given no
#: action fails rather than being invisible to the check written to catch exactly that.
#:
#: **One reading.** §7 row 2 says *"Flatten all; lock account **for day**"* and row 7 says
#: *"Flatten all; lock account"* with no duration. They share
#: :attr:`HaltAction.FLATTEN_AND_LOCK_DAY` here: the rule is a *session* drawdown and §10 keys
#: ``daily_state`` by session date, so the day is the only scope row 7's own inputs have. The
#: stricter reading — an indefinite lock — is rejected because §7 states durations where it
#: means them, row 8 being *"next day"* in terms. Raised in docs/CHANGELOG.md.
ACTION_FOR: Mapping[RiskBlock, HaltAction] = MappingProxyType(
    {
        # §7 rows this module owns.
        RiskBlock.DAILY_LOSS_LIMIT: HaltAction.FLATTEN_AND_LOCK_DAY,
        RiskBlock.SESSION_DRAWDOWN: HaltAction.FLATTEN_AND_LOCK_DAY,
        RiskBlock.LOSS_STREAK_LOCKOUT: HaltAction.LOCK_NEW_ENTRIES,
        RiskBlock.MULTI_DAY_DRAWDOWN: HaltAction.LOCK_ACCOUNT_NEXT_DAY,
        RiskBlock.TRADING_HALTED: HaltAction.FLATTEN_AND_HALT,
        # §7 rows `risk.approve` owns — rows 1, 3, 5, 6, 9 and 10, plus §6.3's eighth check.
        RiskBlock.MAX_RISK_EXCEEDED: HaltAction.REJECT_ORDER,
        RiskBlock.MAX_POSITIONS: HaltAction.REJECT_ORDER,
        RiskBlock.BUYING_POWER: HaltAction.REJECT_ORDER,
        RiskBlock.PDT_VIOLATION: HaltAction.REJECT_ORDER,
        RiskBlock.OUTSIDE_SESSION_WINDOW: HaltAction.REJECT_ORDER,
        RiskBlock.CORRELATED_EXPOSURE: HaltAction.REJECT_ORDER,
        RiskBlock.DUPLICATE_ORDER: HaltAction.REJECT_ORDER,
    }
)

#: How the actions rank when several rows breach at once, weakest first. Declared rather than
#: inferred from the enum's definition order, because a member reordered for readability must
#: not change what a risk engine does.
#:
#: The ranking is by what the action **removes**: locking new entries leaves exits and tomorrow;
#: locking tomorrow leaves today; flattening removes today's exposure; halting removes both.
#: :attr:`HaltAction.LOCK_ACCOUNT_NEXT_DAY` ranks above :attr:`HaltAction.LOCK_NEW_ENTRIES`
#: because a lock that outlives the session is the larger consequence, and it ranks below the
#: two flattens because it takes no position off.
_SEVERITY: tuple[HaltAction, ...] = (
    HaltAction.REJECT_ORDER,
    HaltAction.LOCK_NEW_ENTRIES,
    HaltAction.LOCK_ACCOUNT_NEXT_DAY,
    HaltAction.FLATTEN_AND_LOCK_DAY,
    HaltAction.FLATTEN_AND_HALT,
)

#: The actions that close open exposure, and therefore produce :func:`flatten_all` directives.
_FLATTENING: frozenset[HaltAction] = frozenset(
    {HaltAction.FLATTEN_AND_LOCK_DAY, HaltAction.FLATTEN_AND_HALT}
)


def _rules_at(point: EnforcementPoint) -> tuple[RiskBlock, ...]:
    """The rows evaluated at ``point``: its own, plus every row §7 marks *Any*.

    Derived rather than written into each entry of :data:`RULES_AT`, so a row marked *Any*
    cannot be present at four points and missing from the fifth. ``ANY`` itself resolves to just
    its own rows, so ``evaluate(state, EnforcementPoint.ANY, cfg)`` is the kill-switch check on
    its own and is not silently widened into a full sweep.
    """
    if point is EnforcementPoint.PRE_ORDER:
        raise ValueError(
            "PRD §7's Pre-order rows are tradipy.risk.approve's, not this module's. Evaluating "
            "them here would give §7's table two implementations, which is the v1.2 defect "
            "class; call approve() with the signal instead."
        )
    own = RULES_AT.get(point, ())
    if point is EnforcementPoint.ANY:
        return own
    return (*own, *RULES_AT[EnforcementPoint.ANY])


@dataclass(frozen=True)
class MonitorDecision:
    """One evaluation of §7's rules at one enforcement point, with the arithmetic that decided it.

    ``rules_evaluated`` is §9.2's *"every rule checked, for audit"* applied to the points
    :class:`~tradipy.risk.RiskDecision` does not cover, and it reuses
    :class:`tradipy.risk.RuleOutcome` rather than defining a second audit row.
    """

    point: EnforcementPoint
    rules_evaluated: tuple[RuleOutcome, ...]
    #: The **first** breaching row in §7's table order, which is ``approve``'s convention.
    reason: RiskBlock | None
    #: The **strictest** breaching action, which is not always ``ACTION_FOR[reason]``. Those are
    #: two different questions and answering both with one value under-enforces: if row 4
    #: (*lock entries*) and row 2 (*flatten*) breach together, the reason is the earlier row and
    #: the action is the flatten.
    action: HaltAction | None

    @property
    def breaches(self) -> tuple[RuleOutcome, ...]:
        """Every rule that fired, not only the one reported as :attr:`reason`."""
        return tuple(r for r in self.rules_evaluated if not r.passed)

    @property
    def flatten(self) -> bool:
        """Whether §7's action requires open exposure to be closed."""
        return self.action in _FLATTENING

    @property
    def locks(self) -> bool:
        """Whether §7's action locks the account **today**.

        ``LOCK_ACCOUNT_NEXT_DAY`` is deliberately excluded: §7 row 8 says *next* day, and
        :func:`apply` carries it forward rather than locking the session that earned it.
        """
        return self.action is not None and self.action not in {
            HaltAction.REJECT_ORDER,
            HaltAction.LOCK_ACCOUNT_NEXT_DAY,
        }


#: §7's rule names as an audit trail spells them, one per row this module evaluates. Kept beside
#: :data:`ACTION_FOR` so that adding a row to one and not the other raises rather than producing
#: an unlabelled audit entry — ``evaluate`` indexes both.
_ROW_LABELS: Mapping[RiskBlock, str] = MappingProxyType(
    {
        RiskBlock.DAILY_LOSS_LIMIT: "Daily loss limit (§7 row 2, NON-BYPASSABLE)",
        RiskBlock.SESSION_DRAWDOWN: "Max drawdown, session (§7 row 7)",
        RiskBlock.MULTI_DAY_DRAWDOWN: "Max drawdown, multi-day (§7 row 8)",
        RiskBlock.LOSS_STREAK_LOCKOUT: "Loss-streak lockout (§7 row 4)",
        RiskBlock.TRADING_HALTED: "Emergency kill switch (§7 row 11 / §7.2)",
    }
)


def _q(value: Decimal) -> str:
    """Display a dollar figure to the tick, for a ``detail`` string.

    Quantized to :data:`tradipy.rounding.TICK_SIZE` rather than to a ``Decimal("0.01")`` written
    here, for the reason :func:`tradipy.risk._q` gives: that literal is ``max_pct_of_adv``'s
    registered default, and a second spelling of the price grid is what convention 1 forbids
    whatever it is used for. Importing ``TICK_SIZE`` does **not** make this a rounding module —
    ``quantize`` is not one of the four functions the enforcement suite derives that list from,
    which is also why ``risk.py`` is outside it.
    """
    return f"{value.quantize(TICK_SIZE)}"


def evaluate(
    state: RiskState,
    point: EnforcementPoint,
    cfg: Config,
    *,
    kill_switch: bool = False,
) -> MonitorDecision:
    """Run PRD §7's rules for ``point`` against ``state``.

    Returns a :class:`MonitorDecision` with **every** applicable rule evaluated. The first
    breaching row in §7's table order becomes :attr:`MonitorDecision.reason`; the strictest
    breaching action becomes :attr:`MonitorDecision.action`; every failure is on
    :attr:`MonitorDecision.breaches`.

    ``kill_switch`` is §7 row 11's trigger. §7.2 sources it from a UI button, an API endpoint or
    a file sentinel; all three are outside this package (D30), so it arrives as an argument. It
    is **or**-ed with :attr:`~tradipy.risk.RiskState.trading_halted`, because §7 row 11's
    enforcement point is *"Any"* and an account already halted is still halted — the row reports
    the same block from either source, which is what its
    :class:`~tradipy.rejects.RiskBlock` docstring already says.

    Raises for :attr:`EnforcementPoint.PRE_ORDER`: those rows are
    :func:`tradipy.risk.approve`'s.
    """
    expected = _rules_at(point)
    rules: list[RuleOutcome] = []

    for row in expected:
        rules.append(_evaluate_row(row, state, cfg, kill_switch=kill_switch))

    # Every §7 row for this point must have been evaluated, in order. Asserted rather than
    # trusted: the loop above is a sequence of appends and a dispatch table, and an edit that
    # drops a row leaves a decision reporting no breach and short by a rule nobody counted —
    # which is the shape `approve` guards against for the same reason.
    evaluated = tuple(r.rule for r in rules)
    names = tuple(_ROW_LABELS[row] for row in expected)
    if evaluated != names:
        raise AssertionError(
            f"evaluate() did not apply PRD §7's rules for {point.value} in full. Missing: "
            f"{[n for n in names if n not in evaluated]}; unexpected: "
            f"{[n for n in evaluated if n not in names]}. §9.2 requires rules_evaluated to be "
            "*every* rule checked."
        )

    breaches = [r for r in rules if not r.passed]
    reason = breaches[0].block if breaches else None
    actions = [ACTION_FOR[r.block] for r in breaches if isinstance(r.block, RiskBlock)]
    action = max(actions, key=_SEVERITY.index) if actions else None
    return MonitorDecision(
        point=point,
        rules_evaluated=tuple(rules),
        reason=reason if isinstance(reason, RiskBlock) else None,
        action=action,
    )


def _evaluate_row(
    row: RiskBlock, state: RiskState, cfg: Config, *, kill_switch: bool
) -> RuleOutcome:
    """One §7 row, evaluated, with its arithmetic in the ``detail`` string.

    The three drawdown-shaped rows call :mod:`tradipy.risk`'s predicates rather than restating
    the comparison. Those predicates were written in Phase 5 with the note that *"a Phase 6 loop
    needs to call them without building a decision"*; this is that loop, and a second
    implementation of any of them would be the v1.2 defect class in the module written to close
    the gap they were left for.
    """
    label = _ROW_LABELS[row]

    if row is RiskBlock.DAILY_LOSS_LIMIT:
        breached = daily_loss_breached(state, cfg)
        limit = state.start_of_day_equity * cfg["daily_loss_pct"]
        return RuleOutcome(
            label,
            not breached,
            f"P&L ${_q(state.realized_pnl + state.unrealized_pnl)} vs limit -${_q(limit)}",
            row if breached else None,
        )

    if row is RiskBlock.SESSION_DRAWDOWN:
        breached = session_drawdown_breached(state, cfg)
        peak = state.session_equity_peak
        assert peak is not None  # RiskState.__post_init__ defaults it to the snapshot
        allowed = state.start_of_day_equity * cfg["session_dd_pct"]
        return RuleOutcome(
            label,
            not breached,
            f"peak ${_q(peak)} - live ${_q(live_equity(state))} = "
            f"${_q(peak - live_equity(state))} vs allowed ${_q(allowed)}",
            row if breached else None,
        )

    if row is RiskBlock.MULTI_DAY_DRAWDOWN:
        breached = multi_day_drawdown_breached(state, cfg)
        peak = state.multi_day_peak_equity
        allowed = state.start_of_day_equity * cfg["multi_day_dd_pct"]
        measured = (
            "no multi-day peak supplied — unmeasured, not a breach"
            if peak is None
            else f"peak ${_q(peak)} - live ${_q(live_equity(state))} = "
            f"${_q(peak - live_equity(state))} vs allowed ${_q(allowed)}"
        )
        return RuleOutcome(label, not breached, measured, row if breached else None)

    if row is RiskBlock.LOSS_STREAK_LOCKOUT:
        breached = state.consecutive_losses >= cfg["max_consecutive_losses"]
        return RuleOutcome(
            label,
            not breached,
            f"{state.consecutive_losses} consecutive vs max "
            f"{cfg['max_consecutive_losses']} (§2 Three Strikes Rule)",
            row if breached else None,
        )

    # RiskBlock.TRADING_HALTED — §7 row 11, enforcement point "Any".
    breached = kill_switch or state.trading_halted
    source = "trigger" if kill_switch else ("state" if state.trading_halted else "none")
    return RuleOutcome(
        label,
        not breached,
        f"kill_switch={kill_switch} trading_halted={state.trading_halted} (source: {source})"
        + (f" reason={state.halt_reason}" if state.halt_reason else ""),
        row if breached else None,
    )


def apply(state: DailyState, decision: MonitorDecision) -> DailyState:
    """Fold §7's Violation Action into §10's ``daily_state`` row.

    Three outcomes, and the middle one is the reason this is a function rather than a field
    assignment:

    * **No breach** — the state is returned unchanged.
    * **:attr:`HaltAction.LOCK_ACCOUNT_NEXT_DAY`** — §7 row 8 locks *next* day, so today's phase
      is untouched and :attr:`tradipy.daily.DailyState.locks_next_session` is set. §10 has no
      column for that, which is finding 1 in docs/PHASE-6-DESIGN.md §6; the carrier is
      :func:`tradipy.daily.open_session`'s ``carried_lock``.
    * **Anything else that locks** — :func:`tradipy.daily.lock` with the §7 row that bound.

    Note what this does **not** do: flatten. :attr:`MonitorDecision.flatten` says whether §7
    requires it and :func:`flatten_all` says what that means per position, but nothing here
    closes anything — §6.2's ``OrderDraft -> Submit`` arrow is refused (D30).
    """
    if decision.action is None or decision.reason is None:
        return state
    if decision.action is HaltAction.LOCK_ACCOUNT_NEXT_DAY:
        return replace(state, locks_next_session=True)
    if decision.locks:
        return lock(state, decision.reason)
    return state


def eod_flat_due(minute: int, cfg: Config) -> bool:
    """PRD §21.4's flat-all cutoff: is the session at or past ``session_flat_all_minute``?

    **Not a §7 row, and deliberately not filed as one.** §7's trading-hours row is marked
    *Pre-order* and rejects an *entry* outside the window; §21.4's *"15:55 flat-all cutoff"*
    closes what is already open. Folding the second into :data:`RULES_AT` would let a caller
    reading that table believe §7 states a flatten time, which it does not.

    Inclusive at the cutoff — *at* 15:55 the flatten is due, not one minute after — because
    §21.4 defines the cutoff as ``session_close - 5 min`` and a position still open at the
    cutoff is the thing the five minutes exist to close.

    ``session_flat_all_minute`` is a **separate registry row** from
    ``session_last_entry_minute`` even though both default to 385. They are two rules about two
    different actions, equal only on a regular session: §21.4 defines this one relative to
    ``session_close``, so on a 13:00 half-day it is minute 205 while §7's prose still says
    15:55. That contradiction is raised in docs/CHANGELOG.md and not resolved here, because
    resolving it needs a trading calendar. ``validate_couplings`` enforces the part that *is*
    invariant: the flatten may not precede the last entry.
    """
    return minute >= cfg["session_flat_all_minute"]


@dataclass(frozen=True)
class FlattenDirective:
    """What §7's *"Flatten all"* means for one position — including when §20.12 cannot say.

    ``to_state`` is ``None`` when PRD §20.12 provides no edge for this exit from
    :attr:`from_state`. That is not an error path and it is not rare: §20.12 has four edges into
    ``CLOSED`` and only one of them starts at an **open** state, so **four of the five open
    states** cannot record a kill-switch or end-of-day flatten at all. See
    :func:`unrepresentable_flatten_states`, review round 14's **H3**, and finding 2 in
    docs/PHASE-6-DESIGN.md §6.
    """

    symbol: str
    shares: int
    from_state: PositionState
    exit_reason: ExitReason
    to_state: PositionState | None

    @property
    def representable(self) -> bool:
        """Whether §20.12 has a state for this exit. ``False`` is the finding, not a bug."""
        return self.to_state is not None

    def commit(self) -> PositionState:
        """Perform the §20.12 transition, or raise
        :class:`~tradipy.positions.IllegalTransitionError`.

        Deliberately **not** guarded by :attr:`representable`. A caller that ignores the flag
        must hit §20.12's own refusal rather than a silently different failure, and the
        enforcement suite performs exactly that violation.
        """
        return transition(self.from_state, PositionState.CLOSED)


def unrepresentable_flatten_states(reason: ExitReason) -> frozenset[PositionState]:
    """Open states from which PRD §20.12 cannot record a flatten with ``reason``.

    **Derived from :func:`tradipy.positions.reachable_exit_reasons`**, never re-walked here.
    That function already encodes §20.12's *table-where-it-has-a-row, diagram-where-it-has-none*
    reading and already carries the test asserting the gap; a second walk of ``TRANSITIONS`` in
    this module would be two definitions of which flatten is legal — in the module whose job is
    to discover that the first one is nearly empty.

    At §20.12 as written this returns four of the five members of
    :data:`tradipy.positions.OPEN_STATES` for ``KILL_SWITCH`` and ``EOD_FLAT`` — every one but
    ``TRAILING``, which is the only *open* state with an edge into ``CLOSED`` — and a test asserts
    it is **non-empty** so that a later correction to §20.12 fails deliberately rather than
    quietly making this function pointless.
    """
    return frozenset(s for s in OPEN_STATES if reason not in reachable_exit_reasons(s))


def flatten_all(
    positions: Sequence[OpenPosition], reason: ExitReason
) -> tuple[FlattenDirective, ...]:
    """PRD §7's *"Flatten all"* / §7.2's *"market-close all positions"*, as directives.

    One directive per **open** position, and the count is the point: nothing is filtered out for
    being awkward. A position §20.12 cannot express the exit for gets a directive with
    ``to_state=None`` rather than being dropped, because a flatten that silently skips a
    position is the failure §21.6 makes a Sev-1 — *"zero unprotected open positions"* — arriving
    as an omission instead of an alert.

    ``reason`` is §9.2's ``ClosedTrade.exit_reason``: ``KILL_SWITCH`` for §7.2, ``EOD_FLAT`` for
    §21.4's cutoff. Both are :class:`~tradipy.rejects.ExitReason` members transcribed from §9.2
    in Phase 5 precisely so this layer would not need a second vocabulary.

    Nothing is sent. §6.2's ``OrderDraft -> Submit`` arrow is refused (D30), so this produces the
    decision and stops — the same boundary :mod:`tradipy.orders` stops at.

    **Why so few are representable.** §20.12 has four edges into ``CLOSED`` — from ``TRAILING``
    and from the three exit states — but only one of them starts at an *open* state, so a flatten
    that must reach ``CLOSED`` directly can be recorded from ``TRAILING`` alone.
    """
    return tuple(
        FlattenDirective(
            symbol=p.symbol,
            shares=p.shares,
            from_state=p.state,
            exit_reason=reason,
            to_state=(PositionState.CLOSED if reason in reachable_exit_reasons(p.state) else None),
        )
        for p in positions
        if p.state in OPEN_STATES
    )


def unrepresentable(
    directives: Sequence[FlattenDirective],
) -> tuple[FlattenDirective, ...]:
    """The directives §20.12 has no target state for — finding 2, as a value a caller can print.

    Separate from :func:`flatten_all` so that the *count* of positions requiring a flatten and
    the *count* that can be recorded are two readable numbers rather than one number and a
    caveat. ``python -m tradipy monitor`` prints both.
    """
    return tuple(d for d in directives if not d.representable)
