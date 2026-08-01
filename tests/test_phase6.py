"""Phase 6 — §7's non-pre-order enforcement points, §10's ``daily_state``, §20.8, §9.2.

Fixtures for the worked session, §7's enforcement-point coverage, the boundaries and the one
polarity. The **guarantee-breaking** fixtures live in ``test_enforcement.py`` with the rest of
convention 6's block, so that the thing which fails when a guarantee stops holding stays in one
file.

Every assertion here tests a **derivation**, per convention 4: a threshold is recomputed from the
registry and asserted against the direction its polarity requires, never against a value that
happens to agree today. Literals appear freely — ``tests/`` is deliberately outside the registry
lint's scope, because a fixture must state a literal to assert a derivation against one.
"""

from __future__ import annotations

import ast
from dataclasses import fields, replace
from decimal import Decimal
from pathlib import Path

import pytest

from tradipy import daily as tradipy_daily
from tradipy.daily import (
    DAILY_STATE_COLUMNS,
    UNPERSISTED_FIELDS,
    ClosedTrade,
    ConfirmationRequiredError,
    DailyState,
    SessionNotOpenError,
    SessionPhase,
    clear_lock,
    from_row,
    lock,
    mark_to_market,
    open_session,
    record_close,
    record_multi_day_peak,
    record_snapshot,
    risk_state,
    roll_multi_day_peak,
    to_row,
)
from tradipy.monitor import (
    ACTION_FOR,
    RULES_AT,
    EnforcementPoint,
    HaltAction,
    apply,
    eod_flat_due,
    evaluate,
    flatten_all,
    unrepresentable,
    unrepresentable_flatten_states,
)
from tradipy.params import PARAMS, Config, CouplingError
from tradipy.poc import setup_examples
from tradipy.positions import OPEN_STATES, PositionState
from tradipy.rejects import ExitReason, RiskBlock
from tradipy.risk import OpenPosition, RiskState, approve, live_equity
from tradipy.rounding import TICK_SIZE, Polarity
from tradipy.setups import SetupSignal, SetupType

D = Decimal
CFG = Config.default(mode="experienced")
SESSION_DATE = "2026-08-03"
PHRASE = "FLATTEN AND LOCK"


# ---------------------------------------------------------------------------
# Helpers — every figure derived from the §3 worked examples, never restated
# ---------------------------------------------------------------------------
def a_signal(cfg: Config = CFG) -> SetupSignal:
    """The §3.2 worked example's signal, derived from its bar series.

    Sourced from :func:`tradipy.poc.setup_examples` rather than hand-built, for the reason
    ``test_phase5.py`` gives: a second copy of the §3.2 example is the v1.2 defect class in the
    fixtures themselves.
    """
    for example in setup_examples():
        outcome = example.evaluate(cfg)
        if outcome.signal is not None and example.setup is SetupType.BULL_FLAG:
            return outcome.signal
    raise AssertionError("§3.2's worked example no longer produces a signal")


def a_trade(*, winner: bool = False, cfg: Config = CFG) -> ClosedTrade:
    """A §9.2 ``ClosedTrade`` derived from the §3.2 signal: stopped out, or T1 taken."""
    signal = a_signal(cfg)
    levels = signal.levels
    return ClosedTrade(
        symbol=signal.symbol,
        setup_type=signal.setup_type,
        entry_price=levels.entry_price,
        exit_price=levels.ladder.t1 if winner else levels.stop_price,
        shares=signal.shares,
        r_per_share=levels.r_per_share,
        commission=cfg["est_round_trip_cost_per_share"] * signal.shares,
        fees=D(0),
        exit_reason=ExitReason.LADDER_COMPLETE if winner else ExitReason.STOPPED_OUT,
    )


def a_session(cfg: Config = CFG) -> DailyState:
    """An open, unlocked session at the config's own start-of-day equity."""
    return record_snapshot(open_session(SESSION_DATE), cfg["start_of_day_equity"])


def a_position(state: PositionState, cfg: Config = CFG) -> OpenPosition:
    levels = a_signal(cfg).levels
    return OpenPosition(
        symbol=f"X-{state.value}",
        shares=a_signal(cfg).shares,
        mark=levels.entry_price,
        current_stop=levels.stop_price,
        state=state,
        correlation_group="g",
    )


# ---------------------------------------------------------------------------
# The worked session — §3's own example, end to end through §7's other points
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_a_session_runs_from_no_trade_to_a_flatten_directive() -> None:
    """PRD §20.8 -> §9.2 -> §7 row 4 -> §7 row 2 -> §7's *"Flatten all"*, on §3.2's own numbers.

    The Phase 6 analogue of ``demo``'s worked-example replay: nothing here is asserted against a
    figure a reader typed, only against what the §3.2 bar series and the registry produce.
    """
    equity = CFG["start_of_day_equity"]

    opened = open_session(SESSION_DATE)
    assert opened.phase is SessionPhase.NO_TRADE
    assert opened.start_of_day_equity is None
    assert opened.trading_halted, "§20.8: no snapshot means no trading"

    trading = record_snapshot(opened, equity)
    assert trading.phase is SessionPhase.TRADING
    assert trading.session_equity_peak == equity
    assert trading.live_equity == equity

    trade = a_trade()
    # Derivation, not a value: a full-R stop-out loses exactly R x shares gross, and net is
    # worse by the costs. §9.2 computes the multiple on net, so it must be below -1.
    assert trade.gross_pnl == -(trade.r_per_share * trade.shares)
    assert trade.net_pnl == trade.gross_pnl - trade.commission - trade.fees
    assert trade.r_multiple < D(-1)
    assert trade.is_loss

    closed = record_close(trading, trade, unrealized_after=D(0))
    assert closed.realized_pnl == trade.net_pnl
    assert closed.consecutive_losses == 1
    assert closed.day_trades_in_window == 1
    assert closed.live_equity == equity + trade.net_pnl

    # §7 row 2 is not breached by one R, at any legal configuration — that is what
    # `max_risk_per_trade_pct <= daily_loss_pct` buys — so the post-fill point is clear.
    post_fill = evaluate(risk_state(closed), EnforcementPoint.POST_FILL, CFG)
    assert post_fill.action is None and post_fill.reason is None

    # Drive P&L exactly to §7 row 2's limit. §7 writes the condition with `<=`, so landing on it
    # is a breach — asserted through the registry rather than at a typed figure.
    limit = -(equity * CFG["daily_loss_pct"])
    breached = mark_to_market(closed, limit - closed.realized_pnl)
    assert breached.live_equity == equity + limit

    decision = evaluate(risk_state(breached), EnforcementPoint.CONTINUOUS, CFG)
    assert decision.reason is RiskBlock.DAILY_LOSS_LIMIT
    assert decision.action is HaltAction.FLATTEN_AND_LOCK_DAY
    assert decision.flatten and decision.locks

    locked = apply(breached, decision)
    assert locked.phase is SessionPhase.LOCKED
    assert locked.halt_reason is RiskBlock.DAILY_LOSS_LIMIT

    # And the lock reaches §7's pre-order engine through the one bridge, so Phase 5's rules see
    # it without Phase 6 restating any of them.
    verdict = approve(a_signal(), risk_state(locked), CFG)
    assert not verdict.approved
    assert verdict.reason is RiskBlock.TRADING_HALTED

    directives = flatten_all([a_position(s) for s in OPEN_STATES], ExitReason.KILL_SWITCH)
    assert len(directives) == len(OPEN_STATES), "a flatten may not skip a position"
    assert unrepresentable(directives), "finding 2: §20.12 cannot record most of this flatten"


# ---------------------------------------------------------------------------
# §7's enforcement-point coverage — one fixture per (row, point)
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_rules_at_covers_every_section_seven_row_this_module_owns() -> None:
    """Guard on the guard: :data:`RULES_AT` must account for every row it is responsible for.

    Derived from the **enum**, in two steps, because either alone leaves a hole:

    1. :data:`ACTION_FOR` is **total over** :class:`~tradipy.rejects.RiskBlock`. §7's table gives
       every row a Violation Action, so a member added to the enum and given none is a §7 row
       nobody decided the consequence of.
    2. Every row whose action is not ``REJECT_ORDER`` — i.e. every row this module rather than
       ``risk.approve`` owns — appears at exactly the points :data:`RULES_AT` names, and nothing
       else does. A row with an action and no point is unreachable while looking implemented,
       which is the fifth defect class.
    """
    assert set(ACTION_FOR) == set(RiskBlock), (
        "§7 gives every row a Violation Action; these have none: "
        f"{sorted(r.name for r in set(RiskBlock) - set(ACTION_FOR))}"
    )

    placed = {row for rows in RULES_AT.values() for row in rows}
    ours = {row for row, act in ACTION_FOR.items() if act is not HaltAction.REJECT_ORDER}
    assert placed == ours, (
        f"rows with an action but no point: {sorted(r.name for r in ours - placed)}; "
        f"rows at a point but no action of ours: {sorted(r.name for r in placed - ours)}"
    )
    assert EnforcementPoint.PRE_ORDER not in RULES_AT, (
        "§7's Pre-order rows are risk.approve's; a second implementation is the v1.2 class"
    )


@pytest.mark.spec
def test_the_kill_switch_is_evaluated_at_every_point_because_section_seven_says_any() -> None:
    """§7 row 11's enforcement point is *"Any"*, so no point may omit it.

    Asserted over every point in :data:`RULES_AT` rather than over a list written here, so a new
    point cannot be added without inheriting the row §7 marks widest.
    """
    for point in RULES_AT:
        if point is EnforcementPoint.ANY:
            continue
        decision = evaluate(a_session_state(), point, CFG, kill_switch=True)
        assert decision.reason is RiskBlock.TRADING_HALTED, point
        assert decision.action is HaltAction.FLATTEN_AND_HALT, point


def a_session_state(cfg: Config = CFG) -> RiskState:
    return risk_state(a_session(cfg))


@pytest.mark.spec
def test_daily_loss_row_fires_at_both_of_the_points_section_seven_names() -> None:
    """§7 row 2's enforcement point is *"Continuous (1 sec) **+ post-fill**"* — both, not one."""
    equity = CFG["start_of_day_equity"]
    state = mark_to_market(a_session(), -(equity * CFG["daily_loss_pct"]))
    for point in (EnforcementPoint.CONTINUOUS, EnforcementPoint.POST_FILL):
        decision = evaluate(risk_state(state), point, CFG)
        assert decision.reason is RiskBlock.DAILY_LOSS_LIMIT, point
        assert decision.action is HaltAction.FLATTEN_AND_LOCK_DAY, point


@pytest.mark.spec
def test_session_drawdown_fires_only_at_the_continuous_point() -> None:
    """§7 row 7 is *Continuous*, and the peak is the basis — not start-of-day equity.

    Driven from a session that ran **up** before giving back, because that is the only case in
    which peak-to-trough and start-of-day disagree, and it is the case §7's wording chooses.
    """
    equity = CFG["start_of_day_equity"]
    allowed = equity * CFG["session_dd_pct"]
    up = mark_to_market(a_session(), allowed * 2)
    peak = up.session_equity_peak
    assert peak is not None, "§20.8's snapshot sets the peak, so an open session has one"
    assert peak == equity + allowed * 2

    # Give back three quarters of the run-up: below the peak by 1.5x the allowance while still
    # *above* start-of-day equity — so the session is in profit and §7 row 2 cannot be what
    # fires. That combination is only reachable after a run-up, which is exactly why §7 says
    # "peak-to-trough" and not "from start-of-day".
    down = mark_to_market(up, allowed / 2)
    assert down.live_equity > equity
    assert peak - down.live_equity == allowed + allowed / 2
    decision = evaluate(risk_state(down), EnforcementPoint.CONTINUOUS, CFG)
    assert decision.reason is RiskBlock.SESSION_DRAWDOWN, (
        "row 2 must not be what fired: the account is up on the session"
    )
    assert decision.action is HaltAction.FLATTEN_AND_LOCK_DAY

    # And the same state is clear at every other point, because §7 marks this row Continuous.
    for point in (EnforcementPoint.POST_FILL, EnforcementPoint.POST_TRADE_CLOSE):
        assert evaluate(risk_state(down), point, CFG).action is None, point


@pytest.mark.spec
def test_multi_day_drawdown_fires_at_end_of_day_and_locks_tomorrow_not_today() -> None:
    """§7 row 8: enforcement point *End of day*, action *"Lock account **next** day"*.

    The one action that does not bind the session it fires in — which is why
    :func:`tradipy.monitor.apply` sets a carried flag rather than calling
    :func:`tradipy.daily.lock`, and why §10 having no column for that flag is finding 1.
    """
    equity = CFG["start_of_day_equity"]
    over = D(1) + D(2) * CFG["multi_day_dd_pct"]
    state = record_multi_day_peak(a_session(), [equity * over, equity], CFG)

    decision = evaluate(risk_state(state), EnforcementPoint.END_OF_DAY, CFG)
    assert decision.reason is RiskBlock.MULTI_DAY_DRAWDOWN
    assert decision.action is HaltAction.LOCK_ACCOUNT_NEXT_DAY
    assert not decision.flatten and not decision.locks

    carried = apply(state, decision)
    assert carried.phase is SessionPhase.TRADING, "§7 row 8 locks next day, not today"
    assert carried.locks_next_session

    # Tomorrow's session opens locked, once its own §20.8 snapshot succeeds.
    tomorrow = open_session("2026-08-04", carried_lock=decision.reason)
    assert tomorrow.phase is SessionPhase.NO_TRADE and tomorrow.halt_reason is decision.reason
    assert record_snapshot(tomorrow, equity).phase is SessionPhase.LOCKED


@pytest.mark.spec
def test_loss_streak_fires_at_post_trade_close_and_leaves_exits_open() -> None:
    """§7 row 4: *Post-trade close*, action *"Lock new entries; **allow exits**"*.

    The streak is *computed* here, from repeated :func:`record_close` calls, rather than handed
    to :class:`~tradipy.risk.RiskState` as an integer — which is the gap Phase 6 closes.
    """
    state = a_session()
    trade = a_trade()
    limit = int(CFG["max_consecutive_losses"])
    for _ in range(limit):
        state = record_close(state, trade, unrealized_after=D(0))
    assert state.consecutive_losses == limit

    decision = evaluate(risk_state(state), EnforcementPoint.POST_TRADE_CLOSE, CFG)
    assert decision.reason is RiskBlock.LOSS_STREAK_LOCKOUT
    assert decision.action is HaltAction.LOCK_NEW_ENTRIES
    assert not decision.flatten, "§7 row 4 locks entries; it does not flatten"
    assert decision.locks

    # *"Allow exits"* is what `OrderIntent.REDUCE` already means to `approve`, and the lock this
    # sets must not close that door.
    locked = apply(state, decision)
    from tradipy.risk import OrderIntent

    exit_verdict = approve(a_signal(), risk_state(locked), CFG, intent=OrderIntent.REDUCE)
    assert exit_verdict.approved, "§7 row 4 says 'allow exits'"


@pytest.mark.spec
def test_a_win_resets_the_streak_and_a_scratch_does_too() -> None:
    """§7 row 4's *consecutive* — the reading in PHASE-6-DESIGN §5, pinned in both directions."""
    state = record_close(a_session(), a_trade(), unrealized_after=D(0))
    assert state.consecutive_losses == 1

    winner = a_trade(winner=True)
    assert winner.net_pnl > 0
    assert record_close(state, winner, unrealized_after=D(0)).consecutive_losses == 0

    # A scratch: costs exactly offset the gross. Constructed by solving for the exit price
    # rather than typed, so the assertion is about the rule and not about an example.
    signal = a_signal()
    cost = CFG["est_round_trip_cost_per_share"] * signal.shares
    scratch = replace(
        a_trade(),
        exit_price=signal.levels.entry_price + cost / signal.shares,
        commission=cost,
        fees=D(0),
    )
    assert scratch.net_pnl == 0 and not scratch.is_loss
    assert record_close(state, scratch, unrealized_after=D(0)).consecutive_losses == 0


@pytest.mark.spec
def test_the_strictest_action_wins_when_two_rows_breach_together() -> None:
    """The reason is §7's table order; the action is the **strictest** breach. Both, not one.

    A decision that reported the first row's action would under-enforce here: §7 row 4 locks
    entries and §7 row 2 flattens, and reporting the first alone leaves the position open.
    """
    equity = CFG["start_of_day_equity"]
    state = a_session()
    trade = a_trade()
    for _ in range(int(CFG["max_consecutive_losses"])):
        state = record_close(state, trade, unrealized_after=D(0))
    state = mark_to_market(state, -(equity * CFG["daily_loss_pct"]) - state.realized_pnl)

    decision = evaluate(risk_state(state), EnforcementPoint.CONTINUOUS, CFG)
    blocks = {r.block for r in decision.breaches}
    assert RiskBlock.DAILY_LOSS_LIMIT in blocks
    # Row 4 is not evaluated at CONTINUOUS, so drive the point where both are reachable and
    # assert the ranking there instead of asserting a coincidence here.
    assert decision.action is HaltAction.FLATTEN_AND_LOCK_DAY

    both = evaluate(risk_state(state), EnforcementPoint.POST_TRADE_CLOSE, CFG, kill_switch=True)
    breached = [r.block for r in both.breaches]
    assert RiskBlock.LOSS_STREAK_LOCKOUT in breached and RiskBlock.TRADING_HALTED in breached
    assert both.reason is RiskBlock.LOSS_STREAK_LOCKOUT, "reason is §7's table order"
    assert both.action is HaltAction.FLATTEN_AND_HALT, "action is the strictest breach"
    assert ACTION_FOR[both.reason] is not both.action, (
        "this fixture is vacuous unless the two answers actually differ"
    )


# ---------------------------------------------------------------------------
# §20.8 — the snapshot, and the refusal
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_no_trade_has_no_equity_and_cannot_reach_section_seven() -> None:
    """§20.8: *"it does not fall back to a stale or computed value."*"""
    opened = open_session(SESSION_DATE)
    with pytest.raises(SessionNotOpenError):
        risk_state(opened)
    for call in (
        lambda: mark_to_market(opened, D(0)),
        lambda: record_close(opened, a_trade(), unrealized_after=D(0)),
        lambda: record_multi_day_peak(opened, [D(1)], CFG),
        lambda: lock(opened, RiskBlock.DAILY_LOSS_LIMIT),
    ):
        with pytest.raises(SessionNotOpenError):
            call()


@pytest.mark.spec
def test_the_snapshot_is_immutable_for_the_remainder_of_the_session() -> None:
    """§20.8: taken *once*, at the first successful sync, and never updated."""
    state = a_session()
    equity = state.start_of_day_equity
    assert equity is not None, "a_session() has taken §20.8's snapshot"
    with pytest.raises(ValueError, match="immutable"):
        record_snapshot(state, equity + D(1))
    with pytest.raises(ValueError, match="immutable"):
        record_snapshot(state, equity)


@pytest.mark.spec
def test_a_state_cannot_disagree_with_itself_about_whether_it_has_a_snapshot() -> None:
    """``phase`` and ``start_of_day_equity`` are one fact; §20.8 gives them one meaning."""
    with pytest.raises(ValueError, match=r"§20\.8"):
        DailyState(session_date=SESSION_DATE, phase=SessionPhase.TRADING)
    with pytest.raises(ValueError, match=r"§20\.8"):
        DailyState(
            session_date=SESSION_DATE,
            phase=SessionPhase.NO_TRADE,
            start_of_day_equity=D(30_000),
        )


# ---------------------------------------------------------------------------
# §7.1.2 — the round trip, and what §10 cannot hold
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_every_daily_state_column_round_trips_and_the_lock_survives() -> None:
    """§7.1.2: *"the non-bypassable limits are meaningless if they reset on restart."*

    The column set is derived from :data:`DAILY_STATE_COLUMNS`, so a §10 column added to the
    schema and not written fails here rather than being noticed by a reader.
    """
    state = lock(
        record_close(a_session(), a_trade(), unrealized_after=D(0)),
        RiskBlock.DAILY_LOSS_LIMIT,
    )
    row = to_row(state)
    assert set(row) == set(DAILY_STATE_COLUMNS)

    back = from_row(row)
    assert back.phase is SessionPhase.LOCKED
    assert back.halt_reason is RiskBlock.DAILY_LOSS_LIMIT
    assert back.trading_halted
    for field in DAILY_STATE_COLUMNS.values():
        if field == "phase":
            continue
        assert getattr(back, field) == getattr(state, field), field

    # And a NO_TRADE row reloads as NO_TRADE rather than as a zero-equity session.
    reopened = from_row(to_row(open_session(SESSION_DATE)))
    assert reopened.phase is SessionPhase.NO_TRADE
    assert reopened.start_of_day_equity is None


@pytest.mark.spec
def test_the_fields_section_ten_cannot_hold_are_exactly_the_ones_declared() -> None:
    """Finding 1, pinned: §10's ``daily_state`` has no column for four §7 inputs.

    Derived from the dataclass and the column map, so widening either without updating
    :data:`UNPERSISTED_FIELDS` fails — in both directions. A field quietly gaining a column is
    as much a drift as one quietly losing it.
    """
    declared = {f.name for f in fields(DailyState)}
    written = set(DAILY_STATE_COLUMNS.values())
    assert declared - written == UNPERSISTED_FIELDS

    # And the loss is real, not notional: each comes back at its default.
    equity = CFG["start_of_day_equity"]
    over = D(1) + D(2) * CFG["multi_day_dd_pct"]
    rich = replace(
        record_multi_day_peak(mark_to_market(a_session(), D(-100)), [equity * over], CFG),
        locks_next_session=True,
    )
    back = from_row(to_row(rich))
    assert back.unrealized_pnl == 0 != rich.unrealized_pnl
    assert back.multi_day_peak_equity is None is not rich.multi_day_peak_equity
    assert back.session_equity_peak is None is not rich.session_equity_peak
    assert back.locks_next_session is False is not rich.locks_next_session


@pytest.mark.spec
def test_a_reloaded_session_silently_rebases_the_session_peak() -> None:
    """The sharp edge of finding 1: the loss is not an error, it is a **default**.

    ``RiskState.__post_init__`` fills a missing ``session_equity_peak`` with start-of-day
    equity, which is right for a session that has just opened and wrong for one being resumed.
    So §7 row 7 comes back measuring from the wrong basis and reports no breach — asserted here
    so the consequence is a fixture rather than a paragraph.
    """
    equity = CFG["start_of_day_equity"]
    allowed = equity * CFG["session_dd_pct"]
    up = mark_to_market(a_session(), allowed)
    down = mark_to_market(up, -PARAMS["min_stop_distance"].default)
    assert evaluate(risk_state(down), EnforcementPoint.CONTINUOUS, CFG).reason is (
        RiskBlock.SESSION_DRAWDOWN
    )

    resumed = from_row(to_row(down))
    assert risk_state(resumed).session_equity_peak == equity
    assert evaluate(risk_state(resumed), EnforcementPoint.CONTINUOUS, CFG).reason is None


# ---------------------------------------------------------------------------
# §7.2 — the manual reset
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_a_lock_needs_the_confirmation_phrase_and_an_empty_one_does_not_count() -> None:
    """§7.2: *"Requires manual reset with confirmation phrase."*"""
    locked = lock(a_session(), RiskBlock.DAILY_LOSS_LIMIT)
    with pytest.raises(ConfirmationRequiredError):
        clear_lock(locked, "no", PHRASE)
    with pytest.raises(ConfirmationRequiredError):
        clear_lock(locked, "", "")
    assert locked.phase is SessionPhase.LOCKED

    cleared = clear_lock(locked, PHRASE, PHRASE)
    assert cleared.phase is SessionPhase.TRADING and cleared.halt_reason is None

    with pytest.raises(ValueError, match="not LOCKED"):
        clear_lock(cleared, PHRASE, PHRASE)


# ---------------------------------------------------------------------------
# §20.12 — the flatten, and what it cannot record
# ---------------------------------------------------------------------------
@pytest.mark.spec
@pytest.mark.parametrize("reason", [ExitReason.KILL_SWITCH, ExitReason.EOD_FLAT])
def test_the_flatten_is_unrepresentable_from_every_open_state_but_trailing(
    reason: ExitReason,
) -> None:
    """Finding 2 / round 14's H3, pinned so a §20.12 correction fails deliberately.

    The set is derived from :func:`tradipy.positions.reachable_exit_reasons`, so this asserts a
    consequence of §20.12 rather than a list somebody typed. If the PRD gains the missing edges
    the set empties and this fails — which is the point.
    """
    blocked = unrepresentable_flatten_states(reason)
    assert blocked, "§20.12 now records every flatten; PHASE-6-DESIGN §6 finding 2 is stale"
    assert blocked == OPEN_STATES - {PositionState.TRAILING}

    directives = flatten_all([a_position(s) for s in OPEN_STATES], reason)
    assert {d.from_state for d in directives} == OPEN_STATES, "no position may be skipped"
    for directive in directives:
        assert directive.representable is (directive.from_state not in blocked)
        assert directive.to_state in (None, PositionState.CLOSED)


@pytest.mark.spec
def test_a_flatten_ignores_positions_that_are_not_open() -> None:
    """A closed position needs no flatten, and counting one would overstate the exposure."""
    closed = replace(a_position(PositionState.OPEN_FULL), state=PositionState.CLOSED)
    assert flatten_all([closed], ExitReason.KILL_SWITCH) == ()


# ---------------------------------------------------------------------------
# §7 row 8's window
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_the_multi_day_peak_reads_only_the_registered_window() -> None:
    """§7 row 8: *"Rolling 5-day"*, and a sixth session's peak must not reach it."""
    window = int(CFG["multi_day_dd_window_sessions"])
    closes = [D(100 + i) for i in range(window)]
    assert roll_multi_day_peak(closes, CFG) == max(closes)

    # An older, higher close, one session outside the window.
    assert roll_multi_day_peak([D(10_000), *closes], CFG) == max(closes)
    assert roll_multi_day_peak([], CFG) is None


# ---------------------------------------------------------------------------
# Boundary fixtures — every Phase 6 threshold, at its own limit
# ---------------------------------------------------------------------------
@pytest.mark.boundary
def test_session_flat_all_minute_is_inclusive_at_the_cutoff() -> None:
    """§21.4's cutoff is ``session_close - 5 min``: *at* it the flatten is due.

    ``session_flat_all_minute`` at exactly its default, and at the minute before, and at both
    ends of its registered range — the ``hi`` matters because a cutoff one minute before the
    close is the tightest legal configuration.
    """
    cutoff = int(CFG["session_flat_all_minute"])
    assert eod_flat_due(cutoff, CFG)
    assert not eod_flat_due(cutoff - 1, CFG)

    row = PARAMS["session_flat_all_minute"]
    at_hi = CFG.with_overrides(session_flat_all_minute=row.hi)
    assert eod_flat_due(int(row.hi), at_hi)
    assert not eod_flat_due(int(row.hi) - 1, at_hi)

    at_lo = CFG.with_overrides(session_flat_all_minute=row.lo, session_last_entry_minute=row.lo)
    assert eod_flat_due(int(row.lo), at_lo)


@pytest.mark.boundary
def test_the_flat_all_coupling_binds_at_exactly_one_minute_of_disagreement() -> None:
    """§7 / §21.4: the flatten may not precede the last entry. Defaults sit on the boundary."""
    assert CFG["session_flat_all_minute"] == CFG["session_last_entry_minute"], (
        "the defaults are equal, so this coupling is tested exactly at its boundary"
    )
    CFG.with_overrides(session_last_entry_minute=384)  # flatten one minute later: legal
    with pytest.raises(CouplingError, match="before session_last_entry_minute"):
        CFG.with_overrides(session_flat_all_minute=384)


@pytest.mark.boundary
def test_multi_day_dd_window_sessions_at_both_ends_of_its_range() -> None:
    """``multi_day_dd_window_sessions`` at ``lo`` and at ``hi``, and one session past each."""
    row = PARAMS["multi_day_dd_window_sessions"]
    closes = [D(i) for i in range(1, int(row.hi) + 2)]

    at_lo = CFG.with_overrides(multi_day_dd_window_sessions=row.lo)
    assert roll_multi_day_peak(closes, at_lo) == closes[-1]
    assert roll_multi_day_peak(closes[: -int(row.lo)], at_lo) == closes[-int(row.lo) - 1]

    at_hi = CFG.with_overrides(multi_day_dd_window_sessions=row.hi)
    assert roll_multi_day_peak(closes, at_hi) == max(closes[-int(row.hi) :])
    assert roll_multi_day_peak(closes, at_hi) != closes[0], "the oldest close is outside hi"


@pytest.mark.boundary
def test_the_two_drawdown_rows_do_not_fire_at_exactly_their_thresholds() -> None:
    """§7 writes rows 7 and 8 with ``>``, so equality is **not** a breach.

    The opposite of §7 row 2, whose condition is ``<=`` and does fire on the nose. Both
    directions asserted, because the pair is exactly the configuration in which one of them
    silently inherits the other's comparison.
    """
    equity = CFG["start_of_day_equity"]

    # Row 7, exactly on its allowance. Reached by running **up** by the allowance and giving it
    # all back, so P&L is zero and §7 row 2 — whose comparison is the other one — cannot be what
    # answers. Driving the drawdown from start-of-day instead would breach row 2 first at the
    # `experienced` preset, which is what the first draft of this fixture did.
    up = mark_to_market(a_session(), equity * CFG["session_dd_pct"])
    at_session_limit = mark_to_market(up, D(0))
    assert at_session_limit.live_equity == equity
    assert evaluate(risk_state(at_session_limit), EnforcementPoint.CONTINUOUS, CFG).reason is None
    past = mark_to_market(up, -TICK_SIZE)
    assert evaluate(risk_state(past), EnforcementPoint.CONTINUOUS, CFG).reason is (
        RiskBlock.SESSION_DRAWDOWN
    )

    at_multi = record_multi_day_peak(a_session(), [equity * (D(1) + CFG["multi_day_dd_pct"])], CFG)
    assert evaluate(risk_state(at_multi), EnforcementPoint.END_OF_DAY, CFG).reason is None

    # And row 2, for contrast: exactly on the limit *is* a breach.
    at_daily = mark_to_market(a_session(), -(equity * CFG["daily_loss_pct"]))
    assert evaluate(risk_state(at_daily), EnforcementPoint.POST_FILL, CFG).reason is (
        RiskBlock.DAILY_LOSS_LIMIT
    )


@pytest.mark.boundary
def test_the_loss_streak_binds_at_exactly_the_registered_maximum() -> None:
    """§7 row 4 is ``>=``, so the ``max_consecutive_losses``-th loss locks, not the next one."""
    state = a_session()
    trade = a_trade()
    limit = int(CFG["max_consecutive_losses"])
    for i in range(1, limit + 1):
        state = record_close(state, trade, unrealized_after=D(0))
        decision = evaluate(risk_state(state), EnforcementPoint.POST_TRADE_CLOSE, CFG)
        expected = RiskBlock.LOSS_STREAK_LOCKOUT if i >= limit else None
        assert decision.reason is expected, f"after {i} loss(es)"


@pytest.mark.boundary
def test_a_one_share_trade_still_has_an_r_multiple_and_a_zero_share_one_cannot() -> None:
    """The smallest ladder §3.1.1 admits, and the count below it that §9.2 cannot divide by."""
    one = replace(a_trade(), shares=1)
    assert one.r_multiple == one.net_pnl / one.r_per_share
    with pytest.raises(ValueError, match="shares"):
        replace(a_trade(), shares=0)


# ---------------------------------------------------------------------------
# Polarity
# ---------------------------------------------------------------------------
@pytest.mark.polarity
def test_session_flat_all_minute_is_a_maximum_and_the_comparison_reads_that_way() -> None:
    """§21.4's cutoff is a ceiling on how late the session may still hold a position.

    Asserted against the direction the **opposite** polarity would have taken, never against a
    value: under MINIMUM the rule would fire *before* the cutoff and be clear after it, which is
    the reverse of what §21.4 asks for and would leave positions open past the close.
    """
    assert PARAMS["session_flat_all_minute"].polarity is Polarity.MAXIMUM
    cutoff = int(CFG["session_flat_all_minute"])
    before = [m for m in range(cutoff - 3, cutoff) if not eod_flat_due(m, CFG)]
    after = [m for m in range(cutoff, cutoff + 3) if eod_flat_due(m, CFG)]
    assert len(before) == 3 and len(after) == 3, (
        "a MAXIMUM-polarity cutoff is clear below it and due at and above it; the reverse is "
        "what a MINIMUM would produce"
    )


@pytest.mark.polarity
def test_the_window_count_declares_no_polarity_because_it_is_a_window() -> None:
    """A count that is a *window* has no direction; a count that is a *constraint* does.

    The registry already makes this split — ``rvol_lookback_days`` against
    ``max_open_positions`` — and it is asserted rather than described, because a polarity added
    here would mean somebody decided a lookback can be rounded.
    """
    assert PARAMS["multi_day_dd_window_sessions"].polarity is None
    assert PARAMS["max_consecutive_losses"].polarity is Polarity.MAXIMUM
    with pytest.raises(ValueError, match="no declared polarity"):
        CFG.polarity("multi_day_dd_window_sessions")


# ---------------------------------------------------------------------------
# Registry citations
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_both_phase_6_rows_are_marked_code_originated() -> None:
    """Convention 7: §7's multi-day row and §21.4's cutoff have no Bounds column, so say so."""
    for name in ("session_flat_all_minute", "multi_day_dd_window_sessions"):
        assert "(bounds: code)" in PARAMS[name].source, name


@pytest.mark.spec
def test_live_equity_has_exactly_one_implementation() -> None:
    """§7.1's two equity figures must stay distinct, so the live one is defined once.

    :attr:`tradipy.daily.DailyState.live_equity` routes through
    :func:`tradipy.risk.live_equity`; a second expression would be the v1.2 defect class in the
    definition §7.1 spends a paragraph insisting on.

    **Detected by AST, not by substring.** The first version of this searched ``daily.py``'s text
    for ``"live_equity(risk_state(self))"``, which is a formatting-sensitive assertion about a
    correctness property: ``ruff format`` wrapping that call would have failed the test for a
    reason with nothing to do with §7.1. Every other structural check in this suite parses, and
    this one now does too — which is round 15's lesson applied one step early rather than after
    the formatter found it.
    """
    state = mark_to_market(a_session(), D("123.45"))
    assert state.live_equity == live_equity(risk_state(state))

    source = Path(tradipy_daily.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    # Scoped to `DailyState` rather than to the whole module: `daily.py` also *imports* a name
    # `live_equity`, and a module-level function of that name added later would otherwise be
    # what this walks — a guard that silently changes subject is the shape convention 6 is about.
    cls = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "DailyState"
    )
    prop = next(
        node
        for node in ast.walk(cls)
        if isinstance(node, ast.FunctionDef) and node.name == "live_equity"
    )
    called = {
        node.func.id
        for node in ast.walk(prop)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "live_equity" in called, (
        "DailyState.live_equity must delegate to risk.live_equity rather than recompute "
        "§7.1's sum; two expressions for one definition is the v1.2 defect class"
    )
    # And it computes nothing of its own: no arithmetic operator in the property's body.
    assert not [n for n in ast.walk(prop) if isinstance(n, ast.BinOp)], (
        "DailyState.live_equity does arithmetic; §7.1's live figure has one definition"
    )
