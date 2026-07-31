"""Phase 5 — §6 order construction, §7 pre-order risk, §20.12's state machine.

Fixtures for the worked examples, the §7 rule table, the boundaries and the polarities. The
**guarantee-breaking** fixtures for these modules live in ``test_enforcement.py`` with the rest
of convention 6's block, so that the thing which fails when a guarantee stops holding stays in
one file.

Every assertion here tests a **derivation**, per convention 4: ``assert cap == floor_to_tick(x)
and cap <= x``, never ``assert cap == Decimal("0.01")``. Literals appear freely — ``tests/`` is
deliberately outside the registry lint's scope, because a fixture must state a literal to assert
a derivation against one.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from tradipy.orders import (
    LegPurpose,
    OrderLeg,
    OrderSide,
    OrderType,
    PartialFillAction,
    bracket,
    entry_limit_price,
    idempotency_key,
    partial_fill_action,
    stop_limit_price,
)
from tradipy.params import PARAMS, Config
from tradipy.poc import setup_examples
from tradipy.positions import (
    OPEN_STATES,
    TERMINAL_STATES,
    TRANSITIONS,
    LegQuantities,
    PositionState,
    breakeven_stop,
    leg_quantities,
    position_risk,
    reachable_exit_reasons,
    scale_in_permitted,
    transition,
)
from tradipy.rejects import ExitReason, RiskBlock
from tradipy.risk import (
    EVALUATED_RULES,
    PDT_MAX_DAY_TRADES,
    PDT_MIN_EQUITY,
    OpenPosition,
    OrderIntent,
    RiskState,
    approve,
    approve_all,
    correlation_group,
    daily_loss_breached,
    live_equity,
    max_dollar_risk,
    multi_day_drawdown_breached,
    session_drawdown_breached,
    total_open_risk,
)
from tradipy.rounding import TICK_SIZE, ceil_to_tick, floor_to_tick
from tradipy.setups import SetupSignal, SetupType

D = Decimal
CFG = Config.default(mode="experienced")

SESSION_DATE = "2026-07-31"
ACCOUNT = "SIMULATED-NONE"


def signals_at(cfg: Config) -> dict[SetupType, SetupSignal]:
    """The §3 worked examples that produce a signal under ``cfg``, keyed by setup.

    Parametrised by config rather than fixed, because share count is a function of
    ``start_of_day_equity`` (§2.2) and two fixtures below have to move that figure — a state whose
    equity disagrees with the config that sized the position is not a state the system can reach.
    """
    out: dict[SetupType, SetupSignal] = {}
    for example in setup_examples():
        outcome = example.evaluate(cfg)
        if outcome.signal is not None:
            out[example.setup] = outcome.signal
    return out


def signals() -> dict[SetupType, SetupSignal]:
    """:func:`signals_at` at the §3 tables' own config (``experienced``, D28).

    §3.4 is absent because §3.1.1's room gate rejects it — Phase 4's L2, unresolved. That is
    asserted rather than worked around in
    :func:`test_the_vwap_reclaim_example_never_reaches_the_risk_engine`.
    """
    return signals_at(CFG)


#: The largest ``start_of_day_equity`` at which §7's PDT row can fire at all — see
#: :func:`test_the_pdt_row_is_unreachable_at_the_default_equity`. Derived, not written:
#: ``live_equity`` must fall below FINRA's floor while the §7 daily-loss lockout has not yet
#: fired, so the day's loss must be both ``> equity - floor`` and ``< equity x daily_loss_pct``.
PDT_REACHABLE_EQUITY = PDT_MIN_EQUITY + D("100")


#: A start-of-session state: no positions, no P&L, nothing locked. Built once and reached through
#: :func:`flat_state`, so ``dataclasses.replace`` re-runs ``__post_init__`` on every variant.
_FLAT = RiskState(start_of_day_equity=CFG["start_of_day_equity"])


def flat_state(**overrides: Any) -> RiskState:
    """A start-of-session state, with ``overrides`` applied."""
    return replace(_FLAT, **overrides)


def held(
    signal: SetupSignal,
    *,
    state: PositionState = PositionState.OPEN_FULL,
    group: str = "sector:BIOTECH",
) -> OpenPosition:
    """``signal`` as an already-open position at full risk."""
    return OpenPosition(
        symbol=signal.symbol,
        shares=signal.shares,
        mark=signal.levels.entry_price,
        current_stop=signal.levels.stop_price,
        state=state,
        correlation_group=group,
    )


# ---------------------------------------------------------------------------
# Worked examples: §3 signal -> §7 approval -> §6.1 bracket
# ---------------------------------------------------------------------------
@pytest.mark.spec
@pytest.mark.parametrize("setup", [SetupType.BULL_FLAG, SetupType.HOD_BREAKOUT])
def test_each_accepted_worked_example_is_approved_on_a_flat_account(setup: SetupType) -> None:
    """PRD §7: a §3 signal on an empty, unlocked account passes every pre-order rule.

    Also asserts that **every** rule was evaluated, not merely that none blocked — §9.2's
    ``rules_evaluated`` is *"every rule checked, for audit"*, and a loop that exits early would
    still report ``approved=True``.
    """
    signal = signals()[setup]
    decision = approve(signal, flat_state(), CFG)

    assert decision.approved
    assert decision.reason is None
    assert decision.blocks == ()
    assert decision.approved_shares == signal.shares
    # The exact rule set, in order — not a length. `>= 10` against an actual 12 passes with a
    # rule missing, which is the hole `approve`'s own assertion and
    # `test_approve_evaluates_every_rule_and_cannot_silently_drop_one` now close.
    assert tuple(r.rule for r in decision.rules_evaluated) == EVALUATED_RULES
    assert all(r.detail for r in decision.rules_evaluated), "every rule must show its arithmetic"


@pytest.mark.spec
def test_the_vwap_reclaim_example_never_reaches_the_risk_engine() -> None:
    """§3.4's example is rejected by §3.1.1's room gate, so §7 has nothing to judge.

    Asserted rather than skipped. Phase 4's L2 is open, and if it is ever resolved in the
    direction that admits the example, this fails and the Phase 5 fixtures gain a third case —
    which is the outcome a silent ``skip`` would hide.
    """
    assert SetupType.VWAP_RECLAIM not in signals()


@pytest.mark.spec
@pytest.mark.parametrize("setup", [SetupType.BULL_FLAG, SetupType.HOD_BREAKOUT])
def test_the_bracket_covers_every_share_and_prices_every_leg_on_a_tick(
    setup: SetupType,
) -> None:
    """PRD §6.1 / §3.1.1 / §20.13: four legs, exact ladder, whole ticks, full protection."""
    signal = signals()[setup]
    draft = bracket(signal, signal.levels.entry_price, SESSION_DATE, ACCOUNT, CFG)

    assert [leg.purpose for leg in draft.legs] == [
        LegPurpose.ENTRY,
        LegPurpose.STOP,
        LegPurpose.TARGET_1,
        LegPurpose.TARGET_2,
    ]
    # §21.6: the protective leg covers the whole position, because T3 has no target leg (D18).
    assert draft.protective.quantity == signal.shares
    assert draft.entry.quantity == signal.shares
    q = draft.quantities
    assert q.t1 + q.t2 + q.t3 == signal.shares
    # Every price is a whole tick, and each is the level the gates already rounded.
    for leg in draft.legs:
        for price in (leg.limit_price, leg.stop_price):
            assert price is None or price % TICK_SIZE == 0
    assert draft.protective.stop_price == signal.levels.stop_price
    ladder = signal.levels.ladder
    assert [leg.limit_price for leg in draft.legs[2:]] == [ladder.t1, ladder.t2]
    assert draft.oca_group.endswith(draft.idempotency_key[:16])


@pytest.mark.spec
def test_the_second_signal_is_blocked_by_the_total_open_risk_cap() -> None:
    """PRD §7 row 1 caps **total** open risk at one trade's budget — the Phase 5 finding.

    §2 advertises up to three concurrent positions and §7.1.1 derives the after-T1 constraint
    for scale-ins only. Reproduced here rather than described: the second §3 signal is rejected
    with ``MAX_RISK_EXCEEDED`` while ``max_open_positions`` still reports headroom.

    Raised in docs/CHANGELOG.md and docs/PHASE-5-DESIGN.md §6, **not resolved** — so this
    fixture pins current behaviour, and resolving the question in either direction breaks it
    deliberately.
    """
    ordered = [signals()[SetupType.BULL_FLAG], signals()[SetupType.HOD_BREAKOUT]]
    first, second = approve_all(ordered, flat_state(), CFG)

    assert first.approved
    assert not second.approved
    assert second.reason is RiskBlock.MAX_RISK_EXCEEDED
    # The count rule still has room: it is the risk cap that binds, which is the whole point.
    positions_rule = next(
        r for r in second.rules_evaluated if r.rule.startswith("Max open positions")
    )
    assert positions_rule.passed
    assert CFG["max_open_positions"] > 1
    # And the arithmetic: each position is sized to ~the whole budget, so two exceed it.
    budget = max_dollar_risk(CFG)
    assert second.open_risk_before <= budget
    assert second.open_risk_after > budget


@pytest.mark.spec
def test_the_finding_holds_at_the_beginner_preset_too() -> None:
    """The same block at the declared default, where equity budget and share counts both halve.

    Stated separately because *"at every legal configuration"* is a claim about more than one
    configuration, and the §3 tables are computed at ``experienced`` (D28).
    """
    beginner = Config.default(mode="beginner")
    ordered = [
        outcome.signal
        for example in setup_examples()
        if (outcome := example.evaluate(beginner)).signal is not None
    ]
    assert len(ordered) >= 2
    decisions = approve_all(
        ordered, RiskState(start_of_day_equity=beginner["start_of_day_equity"]), beginner
    )
    assert decisions[0].approved
    assert decisions[1].reason is RiskBlock.MAX_RISK_EXCEEDED


# ---------------------------------------------------------------------------
# §7's rule table, one row at a time
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_a_halted_account_blocks_before_anything_else_is_asked() -> None:
    """PRD §7.2 / §7.1.2: ``trading_halted`` is the first rule, and it names its reason."""
    signal = signals()[SetupType.BULL_FLAG]
    decision = approve(
        signal, flat_state(trading_halted=True, halt_reason="daily_loss"), CFG
    )
    assert decision.reason is RiskBlock.TRADING_HALTED
    assert "daily_loss" in decision.rules_evaluated[0].detail


@pytest.mark.spec
def test_the_daily_loss_limit_blocks_at_the_stated_threshold() -> None:
    """PRD §7 row 2, denominated in the **frozen** start-of-day figure (§7.1).

    Asserts the derivation: the limit is ``start_of_day_equity x daily_loss_pct``, and a P&L
    landing exactly on it has breached (§7 writes ``<=``).
    """
    signal = signals()[SetupType.BULL_FLAG]
    equity = CFG["start_of_day_equity"]
    limit = equity * CFG["daily_loss_pct"]

    at_limit = flat_state(realized_pnl=-limit)
    assert daily_loss_breached(at_limit, CFG)
    assert approve(signal, at_limit, CFG).reason is RiskBlock.DAILY_LOSS_LIMIT

    inside = flat_state(realized_pnl=-limit + TICK_SIZE)
    assert not daily_loss_breached(inside, CFG)

    # §7.1: unrealized P&L counts toward the limit but never toward the denominator.
    split = flat_state(realized_pnl=-limit / 2, unrealized_pnl=-limit / 2)
    assert daily_loss_breached(split, CFG)
    assert live_equity(split) == equity - limit


@pytest.mark.spec
def test_max_open_positions_blocks_when_the_risk_cap_does_not() -> None:
    """PRD §7 row 3, reached only by a position whose live stop is already at breakeven.

    Constructed that way deliberately: at full risk the §7 row 1 cap fires first, so this row is
    otherwise unreachable — which is itself the finding in
    :func:`test_the_second_signal_is_blocked_by_the_total_open_risk_cap`.
    """
    signal = signals()[SetupType.BULL_FLAG]
    breakeven = held(signal, state=PositionState.T1_FILLED)
    breakeven = replace(breakeven, current_stop=breakeven_stop(breakeven.mark))
    assert breakeven.risk == 0

    one = flat_state(positions=(breakeven,))
    assert approve(signal, one, CFG).approved

    capped = Config.default(mode="experienced").with_overrides(max_open_positions=1)
    assert approve(signal, one, capped).reason is RiskBlock.MAX_POSITIONS


@pytest.mark.spec
def test_the_loss_streak_lockout_blocks_entries_and_permits_exits() -> None:
    """PRD §7 row 4: *"Lock new entries; allow exits."*

    The second half is the part a side-derived intent gets wrong, so it is asserted directly.
    """
    signal = signals()[SetupType.BULL_FLAG]
    locked = flat_state(consecutive_losses=int(CFG["max_consecutive_losses"]))

    assert approve(signal, locked, CFG).reason is RiskBlock.LOSS_STREAK_LOCKOUT
    exit_decision = approve(signal, locked, CFG, intent=OrderIntent.REDUCE)
    assert exit_decision.approved
    assert exit_decision.reason is None

    one_short = flat_state(consecutive_losses=int(CFG["max_consecutive_losses"]) - 1)
    assert approve(signal, one_short, CFG).approved


@pytest.mark.spec
def test_buying_power_is_capped_at_the_registered_fraction_and_skipped_when_absent() -> None:
    """PRD §7 row 5 / §2.2, and the reporting of an unsupplied broker figure."""
    signal = signals()[SetupType.BULL_FLAG]
    value = signal.shares * signal.levels.entry_price
    exact = value / CFG["max_bp_usage_pct"]

    assert approve(signal, flat_state(), CFG, buying_power=exact).approved
    tight = approve(signal, flat_state(), CFG, buying_power=exact - D("1"))
    assert tight.reason is RiskBlock.BUYING_POWER

    absent = approve(signal, flat_state(), CFG)
    row = next(r for r in absent.rules_evaluated if r.rule.startswith("Max buying power"))
    assert row.passed
    assert "not evaluated" in row.detail, "a skipped check must not read as a passed one"


def _pdt_setup() -> tuple[Config, SetupSignal, Decimal]:
    """A config, signal and loss at which §7's PDT row can actually fire.

    The default $30,000 account cannot reach it — see
    :func:`test_the_pdt_row_is_unreachable_at_the_default_equity` — so these fixtures move
    ``start_of_day_equity`` down to just above FINRA's floor and re-derive the signal there,
    because §2.2 sizes from that figure and a state whose equity disagrees with the config that
    sized the position is unreachable.
    """
    cfg = CFG.with_overrides(start_of_day_equity=PDT_REACHABLE_EQUITY)
    loss = PDT_REACHABLE_EQUITY - PDT_MIN_EQUITY + D("1")
    assert loss < PDT_REACHABLE_EQUITY * cfg["daily_loss_pct"], (
        "the loss must be small enough that §7's daily-loss row has not fired, or this fixture "
        "is testing that row instead"
    )
    return cfg, signals_at(cfg)[SetupType.BULL_FLAG], loss


@pytest.mark.spec
def test_pdt_needs_both_the_day_trade_count_and_the_equity_floor() -> None:
    """PRD §7 row 6 is a conjunction, and it is tested against **live** equity.

    §7 states *"equity < $25,000"* and §7.1 defines two equity figures without assigning either;
    the reading is ``live_equity``, so a start-of-day figure above the floor with an intraday
    loss below it must still block. Raised in docs/CHANGELOG.md.
    """
    cfg, signal, loss = _pdt_setup()
    equity = cfg["start_of_day_equity"]

    base = RiskState(start_of_day_equity=equity)

    def state(**kw: Any) -> RiskState:
        return replace(base, **kw)

    # Above the floor: the count alone does not block.
    assert approve(signal, state(day_trades_in_window=PDT_MAX_DAY_TRADES), cfg).approved
    # Below the floor but under the count: the equity alone does not block either.
    assert approve(
        signal,
        state(day_trades_in_window=PDT_MAX_DAY_TRADES - 1, realized_pnl=-loss),
        cfg,
    ).approved
    # Both: blocked. And it is the *live* figure that carried it — start-of-day is unchanged.
    both = state(day_trades_in_window=PDT_MAX_DAY_TRADES, realized_pnl=-loss)
    assert live_equity(both) < PDT_MIN_EQUITY <= both.start_of_day_equity
    assert not daily_loss_breached(both, cfg), "the daily-loss row must not be what blocked"
    assert approve(signal, both, cfg).reason is RiskBlock.PDT_VIOLATION


@pytest.mark.spec
def test_the_pdt_row_is_unreachable_at_the_default_equity() -> None:
    """PRD §7 rows 2 and 6 are jointly incoherent at §2.0's default ``start_of_day_equity``.

    **Reproduced, raised, not resolved.** §7's PDT row fires only when ``live_equity`` is below
    FINRA's $25,000 floor. Reaching that from the $30,000 default needs a $5,000 loss, which is
    16.7% of equity — while §7's daily-loss row locks the account at ``daily_loss_pct``, whose
    registered ceiling is 5% ($1,500). So the lockout **always** fires first, and §7's PDT row
    cannot be reached at the shipped default at any legal configuration.

    It is reachable only for an account starting within ``daily_loss_pct`` of the floor, which
    §2.0's own bounds permit (``start_of_day_equity`` has ``lo`` = $25,000). So this is not a dead
    rule — it is a rule whose reachability depends on a parameter nothing relates to it, which is
    the third defect class (joint incoherence) and the same shape as A25.

    Not enforced as a coupling, per convention 5: the incoherent combination *is* the shipped
    default, so raising here would make :meth:`Config.default` throw. Documented instead, and
    pinned in both directions so resolving it breaks this fixture deliberately.
    """
    cfg = CFG
    equity = cfg["start_of_day_equity"]
    signal = signals()[SetupType.BULL_FLAG]

    # The derivation: the drop to the floor exceeds the largest permitted daily loss.
    drop_to_floor = equity - PDT_MIN_EQUITY
    assert drop_to_floor > equity * PARAMS["daily_loss_pct"].hi

    # And by execution: at the count, with equity just under the floor, it is the daily-loss row
    # that reports, not PDT.
    state = RiskState(
        start_of_day_equity=equity,
        realized_pnl=-(drop_to_floor + D("1")),
        day_trades_in_window=PDT_MAX_DAY_TRADES,
    )
    assert live_equity(state) < PDT_MIN_EQUITY
    assert approve(signal, state, cfg).reason is RiskBlock.DAILY_LOSS_LIMIT

    # The reachable window exists, and it is inside §2.0's bounds.
    assert PDT_REACHABLE_EQUITY >= PARAMS["start_of_day_equity"].lo
    reachable = cfg.with_overrides(start_of_day_equity=PDT_REACHABLE_EQUITY)
    assert PDT_REACHABLE_EQUITY - PDT_MIN_EQUITY < (
        PDT_REACHABLE_EQUITY * reachable["daily_loss_pct"]
    )


@pytest.mark.spec
def test_correlated_exposure_counts_positions_sharing_a_group() -> None:
    """PRD §7 row 10 / §7.1.3 / D21, including that §7.1.3's rule 1 dominates rule 2."""
    signal = signals()[SetupType.BULL_FLAG]
    other = replace(
        held(signals()[SetupType.HOD_BREAKOUT], state=PositionState.T1_FILLED),
        current_stop=signals()[SetupType.HOD_BREAKOUT].levels.entry_price,
        correlation_group="catalyst:FDA-APPROVAL",
    )
    state = flat_state(positions=(other,))

    same = approve(signal, state, CFG, correlation="catalyst:FDA-APPROVAL")
    assert same.reason is RiskBlock.CORRELATED_EXPOSURE
    assert approve(signal, state, CFG, correlation="sector:MINING").approved

    # §7.1.3's assignment order: catalyst beats sector beats ungrouped.
    assert correlation_group("ABCD", "FDA", "BIOTECH") == "catalyst:FDA"
    assert correlation_group("ABCD", None, "BIOTECH") == "sector:BIOTECH"
    assert correlation_group("ABCD") == "symbol:ABCD"


@pytest.mark.spec
def test_a_duplicate_idempotency_key_blocks_and_an_absent_one_is_reported() -> None:
    """PRD §6.3 check 8 / §6.7 — against a supplied set, because there is no store."""
    signal = signals()[SetupType.BULL_FLAG]
    key = idempotency_key(
        signal.symbol, signal.setup_type, SESSION_DATE, signal.levels.trigger_minute, ACCOUNT
    )
    seen = flat_state(submitted_keys=frozenset({key}))
    assert approve(signal, seen, CFG, idempotency_key=key).reason is RiskBlock.DUPLICATE_ORDER
    assert approve(signal, flat_state(), CFG, idempotency_key=key).approved

    row = next(
        r
        for r in approve(signal, seen, CFG).rules_evaluated
        if r.rule.startswith("Duplicate order")
    )
    assert "not evaluated" in row.detail


@pytest.mark.spec
def test_the_spread_gate_is_re_applied_against_the_order_time_quote() -> None:
    """PRD §7: the Spread check's enforcement point is *pre-order*, not only signal-time.

    Not redundant, and this is the fixture that shows why: a spread that has widened between
    bar close and submission blocks here on a signal that passed at signal time.
    """
    signal = signals()[SetupType.BULL_FLAG]
    assert approve(signal, flat_state(), CFG).approved
    widened = approve(signal, flat_state(), CFG, spread_now=signal.levels.r_per_share)
    assert widened.reason is not None
    assert widened.reason.value == "SPREAD_TOO_WIDE"


@pytest.mark.spec
def test_the_drawdown_predicates_are_measured_from_a_peak_not_from_start_of_day() -> None:
    """PRD §7 rows 7 and 8. Predicates only — the loop that calls them is Phase 6's."""
    equity = CFG["start_of_day_equity"]
    run_up = equity * D("1.05")
    limit = equity * CFG["session_dd_pct"]

    # Given back more than session_dd_pct from the session peak, while still up on the day.
    state = flat_state(realized_pnl=run_up - equity - limit - D("1"), session_equity_peak=run_up)
    assert live_equity(state) > equity, "still green on the day, and still a breach"
    assert session_drawdown_breached(state, CFG)
    assert not session_drawdown_breached(
        replace(state, session_equity_peak=live_equity(state)), CFG
    )

    # §7 row 8 returns False with no peak: an unmeasured drawdown is not a breach.
    assert not multi_day_drawdown_breached(flat_state(), CFG)
    deep = flat_state(
        realized_pnl=-equity * CFG["multi_day_dd_pct"] - D("1"), multi_day_peak_equity=equity
    )
    assert multi_day_drawdown_breached(deep, CFG)


@pytest.mark.spec
def test_open_risk_is_measured_from_live_stops_and_counts_pending_orders() -> None:
    """PRD §7.1.1 / §7 row 1: *"from current live stops … plus pending orders."*"""
    signal = signals()[SetupType.BULL_FLAG]
    full = held(signal)
    entry_risk = signal.shares * (signal.levels.entry_price - signal.levels.stop_price)
    assert total_open_risk(flat_state(positions=(full,))) == entry_risk

    # A pending entry is counted; a closed position is not.
    pending = replace(full, state=PositionState.PENDING_ENTRY)
    assert total_open_risk(flat_state(positions=(pending,))) == entry_risk
    for done in (PositionState.CLOSED, PositionState.STOPPED_OUT, PositionState.EXPIRED):
        assert total_open_risk(flat_state(positions=(replace(full, state=done),))) == 0

    # Breakeven contributes zero rather than credit — §7.1.1's "~zero", not a negative.
    profitable = replace(full, current_stop=full.mark + D("1"))
    assert position_risk(profitable.shares, profitable.current_stop, profitable.mark) == 0


# ---------------------------------------------------------------------------
# §20.12 state machine
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_every_transition_in_the_table_is_walkable_and_the_table_is_total() -> None:
    """PRD §20.12: every state has a rule, and every listed edge is permitted."""
    assert set(TRANSITIONS) == set(PositionState), "a state with no rule is a missing rule"
    for state, successors in TRANSITIONS.items():
        for successor in successors:
            assert transition(state, successor) is successor
        if not successors:
            assert state in TERMINAL_STATES


@pytest.mark.spec
def test_the_documented_happy_path_walks_end_to_end() -> None:
    """§20.12's main line, walked as one sequence rather than edge by edge."""
    path = [
        PositionState.IDLE,
        PositionState.ARMED,
        PositionState.PENDING_ENTRY,
        PositionState.OPEN_FULL,
        PositionState.T1_FILLED,
        PositionState.T2_FILLED,
        PositionState.TRAILING,
        PositionState.CLOSED,
    ]
    state = path[0]
    for nxt in path[1:]:
        state = transition(state, nxt)
    assert state is PositionState.CLOSED
    assert state in TERMINAL_STATES


@pytest.mark.spec
def test_the_exit_reason_vocabulary_does_not_match_the_state_names() -> None:
    """§9.2 has six ``exit_reason`` values; §20.12 has three matching state names.

    Pinned because it is a documented open finding rather than a bug to fix here — and because
    the specific consequence (§7.2's kill switch cannot be expressed from four open states) is
    the kind of gap a reader assumes is covered.
    """
    state_names = {s.value for s in PositionState}
    shared = {r for r in ExitReason if r.value in state_names}
    assert {r.value for r in shared} == {"STOPPED_OUT", "INVALIDATED", "BAILED_OUT"}
    assert PositionState.EXPIRED.value not in {r.value for r in ExitReason}

    # §7.2's "Any" enforcement point is unreachable from every open state but TRAILING.
    for state in OPEN_STATES - {PositionState.TRAILING}:
        assert ExitReason.KILL_SWITCH not in reachable_exit_reasons(state)
        assert ExitReason.EOD_FLAT not in reachable_exit_reasons(state)
    assert ExitReason.LADDER_COMPLETE in reachable_exit_reasons(PositionState.TRAILING)
    assert reachable_exit_reasons(PositionState.CLOSED) == frozenset()


@pytest.mark.spec
def test_scale_in_is_refused_before_t1_even_when_the_budget_allows_it() -> None:
    """PRD §7.1.1: *"adds are only ever legal after T1, never while … at full risk."*"""
    assert not scale_in_permitted(PositionState.OPEN_FULL, Decimal(0), CFG)
    assert scale_in_permitted(PositionState.T1_FILLED, Decimal(0), CFG)
    assert scale_in_permitted(PositionState.T2_FILLED, max_dollar_risk(CFG), CFG)
    assert not scale_in_permitted(
        PositionState.T1_FILLED, max_dollar_risk(CFG) + TICK_SIZE, CFG
    )
    for state in set(PositionState) - {PositionState.T1_FILLED, PositionState.T2_FILLED}:
        assert not scale_in_permitted(state, Decimal(0), CFG)


# ---------------------------------------------------------------------------
# §6.1 / §6.7 order construction
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_the_idempotency_key_changes_with_every_component_and_repeats_exactly() -> None:
    """PRD §6.7: derived from signal identity — a retry reproduces the key, nothing else does."""
    base = ("ABCD", SetupType.BULL_FLAG, SESSION_DATE, 37, ACCOUNT)
    key = idempotency_key(*base)
    assert idempotency_key(*base) == key, "a retry must reproduce the key (§6.7)"
    assert len(key) == 64 and int(key, 16) >= 0  # sha256 hex

    variants = [
        ("WXYZ", *base[1:]),
        (base[0], SetupType.HOD_BREAKOUT, *base[2:]),
        (*base[:2], "2026-07-30", *base[3:]),
        (*base[:3], 38, base[4]),
        (*base[:4], "OTHER-ACCOUNT"),
    ]
    assert len({idempotency_key(*v) for v in variants} | {key}) == len(variants) + 1


@pytest.mark.spec
def test_the_entry_limit_and_stop_limit_offsets_come_from_the_registry() -> None:
    """PRD §6.1: ``ask + entry_limit_offset_ticks``, ``stop - stop_limit_offset_ticks``.

    Asserted as derivations, and against the registry rather than against 1 and 2 — the
    literals are here to prove the arithmetic, not to define it.
    """
    ask = D("5.163")
    limit = entry_limit_price(ask, CFG)
    assert limit == ceil_to_tick(ask + CFG["entry_limit_offset_ticks"] * TICK_SIZE)
    assert limit >= ask, "ceiling a buy limit must cost money, never save it (§20.13)"
    assert limit % TICK_SIZE == 0

    stop = D("5.04")
    sl = stop_limit_price(stop, CFG)
    assert sl == floor_to_tick(stop - CFG["stop_limit_offset_ticks"] * TICK_SIZE)
    assert sl < stop, "a protective sell limit must sit below its trigger (§6.1)"

    # At a zero offset the entry limit is the ask, rounded up — legal, and fills less often.
    at_ask = CFG.with_overrides(entry_limit_offset_ticks=0)
    assert entry_limit_price(ask, at_ask) == ceil_to_tick(ask)


@pytest.mark.spec
def test_partial_fill_follows_sixty_four_in_all_four_branches() -> None:
    """PRD §6.4's three rules plus the complete case."""
    intended, entry_spread = 1000, TICK_SIZE
    timeout = int(CFG["partial_fill_timeout_seconds"])
    half = int(CFG["min_partial_fill_pct"] * intended)

    assert partial_fill_action(intended, intended, entry_spread, entry_spread, 0, CFG) is (
        PartialFillAction.COMPLETE
    )
    # Below the fraction: wait until the timeout, then cancel.
    assert partial_fill_action(
        intended, half - 1, entry_spread, entry_spread, timeout - 1, CFG
    ) is PartialFillAction.WAIT
    assert partial_fill_action(intended, half - 1, entry_spread, entry_spread, timeout, CFG) is (
        PartialFillAction.CANCEL_REMAINDER
    )
    # At or above the fraction: keep working unless the spread has more than doubled.
    multiple = CFG["partial_fill_spread_widening_multiple"]
    assert partial_fill_action(intended, half, entry_spread, multiple * entry_spread, 0, CFG) is (
        PartialFillAction.KEEP_WORKING
    )
    assert partial_fill_action(
        intended, half, entry_spread, multiple * entry_spread + TICK_SIZE, 0, CFG
    ) is PartialFillAction.CANCEL_REMAINDER


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------
@pytest.mark.boundary
def test_total_open_risk_exactly_at_the_cap_is_permitted() -> None:
    """PRD §7 row 1 rejects when open risk **exceeds** the budget, so equality passes.

    The §3.2 example is sized to the budget almost exactly, which is what makes this boundary
    the shipped default rather than a contrived one.
    """
    signal = signals()[SetupType.BULL_FLAG]
    decision = approve(signal, flat_state(), CFG)
    assert decision.open_risk_after == max_dollar_risk(CFG)
    assert decision.approved


@pytest.mark.boundary
def test_the_day_trade_count_fires_at_the_registered_maximum_not_after_it() -> None:
    """PRD §7: *"``day_trades_in_window >= 3`` when the new one would be the 4th."*"""
    cfg, signal, loss = _pdt_setup()
    for count, blocked in ((PDT_MAX_DAY_TRADES - 1, False), (PDT_MAX_DAY_TRADES, True)):
        state = RiskState(
            start_of_day_equity=cfg["start_of_day_equity"],
            realized_pnl=-loss,
            day_trades_in_window=count,
        )
        assert (approve(signal, state, cfg).reason is RiskBlock.PDT_VIOLATION) is blocked


@pytest.mark.boundary
def test_the_session_window_admits_its_last_minute_and_refuses_the_next() -> None:
    """PRD §7 trading-hours row at exactly ``session_last_entry_minute`` (15:55 ET)."""
    signal = signals()[SetupType.BULL_FLAG]
    last = int(CFG["session_last_entry_minute"])
    for minute, ok in ((last, True), (last + 1, False)):
        late = replace(signal, levels=replace(signal.levels, trigger_minute=minute))
        decision = approve(late, flat_state(), CFG)
        assert decision.approved is ok
        if not ok:
            assert decision.reason is RiskBlock.OUTSIDE_SESSION_WINDOW


@pytest.mark.boundary
def test_the_ladder_is_exact_for_every_share_count_the_fractions_do_not_divide() -> None:
    """PRD §3.1.1 over an integer count — §3.1.1 states no rule, so the invariant carries it.

    Includes the two surprising cases the reading produces: one share exits entirely on the
    trail, and two shares put nothing on T2.
    """
    for shares in range(1, 40):
        q = leg_quantities(shares, CFG)
        assert q.t1 + q.t2 + q.t3 == shares
        assert q.t1 == int(CFG["t1_scale_out_pct"] * shares)
        assert q.t2 == int(CFG["t2_scale_out_pct"] * shares)
        assert q.t3 >= 0
    assert leg_quantities(1, CFG) == LegQuantities(t1=0, t2=0, t3=1, shares=1)
    assert leg_quantities(2, CFG) == LegQuantities(t1=1, t2=0, t3=1, shares=2)
    assert leg_quantities(4, CFG) == LegQuantities(t1=2, t2=1, t3=1, shares=4)


@pytest.mark.boundary
def test_a_partial_fill_of_exactly_the_minimum_fraction_keeps_working() -> None:
    """PRD §6.4: *"If partial fill **>=** 50%"* — the boundary belongs to the keep branch."""
    intended = 1000
    at = int(CFG["min_partial_fill_pct"] * intended)
    assert partial_fill_action(intended, at, TICK_SIZE, TICK_SIZE, 10_000, CFG) is (
        PartialFillAction.KEEP_WORKING
    )
    assert partial_fill_action(intended, at - 1, TICK_SIZE, TICK_SIZE, 10_000, CFG) is (
        PartialFillAction.CANCEL_REMAINDER
    )


# ---------------------------------------------------------------------------
# Polarity
# ---------------------------------------------------------------------------
@pytest.mark.polarity
def test_the_session_window_is_declared_a_maximum_and_compared_as_one() -> None:
    """``session_last_entry_minute`` is a ceiling the trigger minute must stay under.

    Asserted through the registry declaration and the comparison together, so flipping the
    declaration and the comparison independently cannot both pass.
    """
    assert PARAMS["session_last_entry_minute"].polarity is CFG.polarity(
        "session_last_entry_minute"
    )
    assert CFG.polarity("session_last_entry_minute").name == "MAXIMUM"
    signal = signals()[SetupType.BULL_FLAG]
    narrowed = CFG.with_overrides(session_last_entry_minute=signal.levels.trigger_minute - 1)
    assert approve(signal, flat_state(), narrowed).reason is (
        RiskBlock.OUTSIDE_SESSION_WINDOW
    ), "lowering a MAXIMUM must make the gate harder to clear, never easier"


@pytest.mark.polarity
def test_the_partial_fill_fraction_is_declared_a_minimum_and_compared_as_one() -> None:
    """``min_partial_fill_pct`` is a floor the fill must reach; raising it must cut more fills."""
    assert CFG.polarity("min_partial_fill_pct").name == "MINIMUM"
    intended, filled = 1000, 600
    assert partial_fill_action(intended, filled, TICK_SIZE, TICK_SIZE, 10_000, CFG) is (
        PartialFillAction.KEEP_WORKING
    )
    stricter = CFG.with_overrides(min_partial_fill_pct="0.70")
    assert partial_fill_action(intended, filled, TICK_SIZE, TICK_SIZE, 10_000, stricter) is (
        PartialFillAction.CANCEL_REMAINDER
    )


@pytest.mark.polarity
def test_the_breakeven_stop_rounds_the_direction_twenty_thirteen_gives_stops() -> None:
    """§20.13's stop row is unconditional: round **down**, away from the position.

    Exercised on a volume-weighted average cost that is not a whole tick, which is the case
    §6.4's partial fills create and the only case where the direction is observable.
    """
    avg_cost = D("5.1637")
    stop = breakeven_stop(avg_cost)
    assert stop == floor_to_tick(avg_cost)
    assert stop <= avg_cost, "a breakeven stop may widen the position's risk, never tighten it"
    assert stop % TICK_SIZE == 0


# ---------------------------------------------------------------------------
# Rejections of malformed input — the arguments that must not be accepted quietly
# ---------------------------------------------------------------------------
@pytest.mark.spec
@pytest.mark.parametrize(
    ("intended", "filled"),
    [(0, 0), (100, -1), (100, 101)],
)
def test_partial_fill_refuses_impossible_quantities(intended: int, filled: int) -> None:
    """An over-fill is a §21.3 reconciliation fault, not a §6.4 partial fill."""
    with pytest.raises(ValueError, match="intended|filled"):
        partial_fill_action(intended, filled, TICK_SIZE, TICK_SIZE, 0, CFG)


@pytest.mark.spec
def test_a_leg_refuses_a_price_that_is_not_a_whole_tick() -> None:
    """PRD §20.13: an ``OrderDraft`` is the last representation before submission."""
    with pytest.raises(ValueError, match="whole tick"):
        OrderLeg(
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            purpose=LegPurpose.ENTRY,
            limit_price=D("5.163"),
        )


@pytest.mark.spec
def test_the_idempotency_key_refuses_a_field_containing_its_own_separator() -> None:
    """§6.7's key is a ``|``-delimited join, so an embedded delimiter is a collision path."""
    with pytest.raises(ValueError, match="separator"):
        idempotency_key("AB|CD", SetupType.BULL_FLAG, SESSION_DATE, 37, ACCOUNT)
    with pytest.raises(ValueError, match="separator"):
        idempotency_key("ABCD", SetupType.BULL_FLAG, SESSION_DATE, 37, "ACC|OUNT")


@pytest.mark.boundary
def test_correlated_exposure_admits_its_maximum_and_refuses_one_more() -> None:
    """PRD §7 row 10 at exactly ``max_correlated_positions``.

    §7 writes the condition as *"> 1 position sharing a correlation group"*, so the boundary
    belongs to the admit side: the cap is the number that may already be open.
    """
    signal = signals()[SetupType.BULL_FLAG]
    group = "catalyst:SHARED"
    # Held at breakeven so §7 row 1 does not fire first and mask this row.
    def at_breakeven(source: SetupSignal, symbol: str) -> OpenPosition:
        held_position = held(source, state=PositionState.T1_FILLED, group=group)
        return replace(
            held_position, symbol=symbol, current_stop=breakeven_stop(held_position.mark)
        )

    other = signals()[SetupType.HOD_BREAKOUT]
    cap = int(CFG["max_correlated_positions"])
    roomy = CFG.with_overrides(max_correlated_positions=cap + 1, max_open_positions=3)

    one = flat_state(positions=(at_breakeven(other, "HELD1"),))
    # At the cap: one already open against a maximum of one — refused.
    assert approve(signal, one, CFG, correlation=group).reason is RiskBlock.CORRELATED_EXPOSURE
    # Raise the cap by one and the same state admits it.
    assert approve(signal, one, roomy, correlation=group).approved
    # Two open against a cap of two — refused again, one step out.
    two = flat_state(
        positions=(at_breakeven(other, "HELD1"), at_breakeven(other, "HELD2"))
    )
    assert approve(signal, two, roomy, correlation=group).reason is (
        RiskBlock.CORRELATED_EXPOSURE
    )


@pytest.mark.boundary
def test_the_order_price_offsets_hold_at_both_ends_of_their_registered_range() -> None:
    """PRD §6.1's two offsets at their own ``lo`` and ``hi``, asserted as derivations.

    At ``lo`` = 0 both collapse to the unadjusted level, which is the configuration in which an
    offset applied in the wrong direction becomes invisible — so it is the one worth pinning.
    """
    ask, stop = D("5.163"), D("5.04")
    for name, fn, base, expect in (
        ("entry_limit_offset_ticks", entry_limit_price, ask, ceil_to_tick),
        ("stop_limit_offset_ticks", stop_limit_price, stop, floor_to_tick),
    ):
        sign = 1 if name.startswith("entry") else -1
        for edge in (PARAMS[name].lo, PARAMS[name].hi):
            cfg = CFG.with_overrides(**{name: edge})
            got = fn(base, cfg)
            assert got == expect(base + sign * edge * TICK_SIZE)
            assert got % TICK_SIZE == 0
        # At zero the offset must vanish, not flip.
        zeroed = CFG.with_overrides(**{name: 0})
        assert fn(base, zeroed) == expect(base)


@pytest.mark.boundary
def test_the_partial_fill_timeout_and_widening_multiple_bind_at_their_own_values() -> None:
    """PRD §6.4 at exactly ``partial_fill_timeout_seconds`` and exactly 2× the entry spread.

    Both are MAXIMUM-polarity, so the boundary value itself must already have crossed: §6.4 says
    *"within 30 sec"* (so 30 has elapsed) and *"widens **>** 2×"* (so 2× has not).
    """
    intended, entry_spread = 1000, TICK_SIZE
    timeout = int(CFG["partial_fill_timeout_seconds"])
    below = int(CFG["min_partial_fill_pct"] * intended) - 1
    at_or_above = int(CFG["min_partial_fill_pct"] * intended)

    assert partial_fill_action(
        intended, below, entry_spread, entry_spread, timeout - 1, CFG
    ) is PartialFillAction.WAIT
    assert partial_fill_action(
        intended, below, entry_spread, entry_spread, timeout, CFG
    ) is PartialFillAction.CANCEL_REMAINDER

    multiple = CFG["partial_fill_spread_widening_multiple"]
    assert partial_fill_action(
        intended, at_or_above, entry_spread, multiple * entry_spread, 0, CFG
    ) is PartialFillAction.KEEP_WORKING, "§6.4 says '> 2x', so exactly 2x keeps working"
    assert partial_fill_action(
        intended, at_or_above, entry_spread, multiple * entry_spread + TICK_SIZE, 0, CFG
    ) is PartialFillAction.CANCEL_REMAINDER


@pytest.mark.spec
def test_a_trigger_minute_before_the_session_open_is_refused() -> None:
    """PRD §20.1: minute 0 **is** 09:30, so a negative ordinal is not a bar.

    `Levels.trigger_minute` carried a default of ``0`` when Phase 5 added it, and 0 is a
    *legal-looking* value: a hand-built `Levels` would claim the open, clear §7's trading-hours
    check — which only tests the upper edge — and hash into a §6.7 key for the wrong bar. The field
    is now required and floored, and this performs the violation.
    """
    signal = signals()[SetupType.BULL_FLAG]
    with pytest.raises(ValueError, match="before the session open"):
        replace(signal.levels, trigger_minute=-1)


@pytest.mark.spec
def test_the_evaluated_rule_list_matches_prd_section_7s_table() -> None:
    """`EVALUATED_RULES` must name every §7 row this layer owns, and no invented one.

    §7's table has thirteen rows. Two are drawdown rows whose enforcement point is a loop Phase 5
    does not have — asserted unreachable in ``test_enforcement.py`` — and one is §7.2's kill
    switch, which is the halted-account rule. Everything else has a row here, and the count is
    derived from the tuple rather than written down.
    """
    named = set(EVALUATED_RULES)
    assert len(named) == len(EVALUATED_RULES), "a rule name is duplicated"
    for fragment in (
        "§7.2 kill switch",
        "§7 row 1",
        "§7 row 2",
        "§7 row 3",
        "§7 row 4",
        "§7 row 5",
        "§7 row 6",
        "§7 row 9",
        "§7 row 10",
        "§6.3 check 8",
        "§3.1.3",
        "§3.1.2",
    ):
        assert any(fragment in rule for rule in EVALUATED_RULES), f"no rule cites {fragment}"
    # Rows 7 and 8 are absent on purpose: their enforcement point is Phase 6's loop.
    assert not any("row 7" in rule or "row 8" in rule for rule in EVALUATED_RULES)


@pytest.mark.spec
def test_approve_all_folds_an_approved_key_into_the_submitted_set() -> None:
    """PRD §6.7: the key is persisted **before** submission, so a batch must see its own keys.

    Without this, §6.3's eighth check is inert across a batch — every signal would be told its key
    was "not seen" because nothing between them wrote it. That is the closest this layer can come to
    §6.7's *"the DB is the arbiter"* and it is still not that guarantee; what it does close is the
    within-batch case, which is the one a caller can reach with no store at all.

    Driven with **one** key deliberately shared by two signals: distinct signals cannot collide
    (``test_two_different_trigger_bars_cannot_share_an_idempotency_key``), so a shared key is the
    only way to reach the second submission of one signal, which is exactly what §6.7 forbids.

    Asserted against :attr:`RiskDecision.blocks` rather than against ``reason``, and the difference
    matters: the second signal fails §7 row 1 *as well*, because the first is still at full risk —
    which is finding 1 — and row 1 is earlier in §7's table, so it is what ``reason`` reports. A
    fixture demanding ``reason is DUPLICATE_ORDER`` would be asserting a rule *ordering* nobody
    specified while claiming to test key accrual. Evaluating every rule is what makes this
    distinguishable at all.
    """
    first = signals()[SetupType.BULL_FLAG]
    shared = idempotency_key(
        first.symbol, first.setup_type, SESSION_DATE, first.levels.trigger_minute, ACCOUNT
    )
    twin = replace(first, shares=1)
    decisions = approve_all(
        [first, twin], flat_state(), CFG, keys=[(first.symbol, shared)]
    )
    assert decisions[0].approved
    assert not decisions[1].approved
    duplicate = next(
        r for r in decisions[1].rules_evaluated if r.rule.startswith("Duplicate order")
    )
    assert not duplicate.passed, "approve_all did not fold the approved key into the state"
    assert duplicate.block is RiskBlock.DUPLICATE_ORDER
    assert "already submitted" in duplicate.detail
    # The first decision saw the same key as fresh, so the accrual is what changed the verdict.
    assert next(
        r for r in decisions[0].rules_evaluated if r.rule.startswith("Duplicate order")
    ).passed

    # And with no key supplied the rule reports itself unevaluated rather than passing as a check.
    unkeyed = approve_all([first], flat_state(), CFG)
    row = next(
        r for r in unkeyed[0].rules_evaluated if r.rule.startswith("Duplicate order")
    )
    assert row.passed and "not evaluated" in row.detail
