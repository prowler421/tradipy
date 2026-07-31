"""Pre-order risk validation — PRD §6.3's checks and §7's rule table.

Normative sources: PRD §6.3 (pre-trade risk validation), §7 (the rule table), §7.1 (equity
definitions), §7.1.1 (scaling in), §7.1.2 (state persistence), §7.1.3 (correlated exposure),
§7.2 (kill switch), §9.2 (the ``RiskDecision`` contract), §2.2 (sizing constraints),
§20.8 (start-of-day equity). §20 governs on any conflict.

**What this module is.** The layer that decides whether the account may take a signal the
strategy engine already approved. §7's table has thirteen rows; two of them — Min R:R and Spread
check — are :func:`tradipy.gates.check_room` and :func:`tradipy.gates.check_spread` and have been
built since v0.0.1. **The other eleven had no enforcement point in code at all**, which for
``daily_loss_pct`` is a NON-BYPASSABLE rule with a legal range, a hard cap and nothing enforcing
it (open question **G2**).

**Every rule is evaluated on every call.** :attr:`RiskDecision.rules_evaluated` is §9.2's own
field — *"every rule checked, for audit"* — and the reason is the one
:class:`tradipy.scanner.HardResult` and :class:`tradipy.setups.Criterion` give: a rejection you
can see one dimension of cannot be recalibrated against measured data. Evaluation does not stop
at the first block.

**What is deliberately not here:**

* **Any broker, feed, clock, file or database.** §7's state arrives as a frozen
  :class:`RiskState`, which is §10's ``daily_state`` row plus the open positions §7.1.1 needs.
  §7.2's kill switch is a *file sentinel* in the PRD; here it is
  :attr:`RiskState.trading_halted`, because no module in this package opens a file (D30).
* **Persistence.** §7.1.2 requires the non-bypassable limits to survive a restart. They do not,
  and docs/PHASE-5-DESIGN.md §1.1 states that rather than implying otherwise.
* **§7's continuous loop.** The daily-loss, session-drawdown and multi-day-drawdown *predicates*
  are here; the 1-second loop that calls them and sets ``trading_halted`` is Phase 6. Same
  treatment §3's post-entry rules got in Phase 4 — rules as predicates, without the state they
  would be evaluated in.
* **Trimming.** §9.2's ``approved_shares`` says it *"may be < TradeSignal.shares after caps"*;
  §7's Violation Action column says *"Reject order"* for every size-related breach. §7 governs.
  Raised in docs/CHANGELOG.md.

This module **does not round.** A risk budget is ``equity × pct`` and open risk is
``shares × (mark − stop)``; neither is a price level compared against a tick, which is the
condition :meth:`tradipy.params.Config.round_for` states for rounding at all. The enforcement
suite derives the set of rounding modules from the source, so this is checked rather than
asserted here.

No numeric threshold appears as a literal, with three stated exceptions that are **law rather
than configuration** — see :data:`PDT_MIN_EQUITY`.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from tradipy.gates import check_room, check_spread
from tradipy.params import Config
from tradipy.positions import OPEN_STATES, PositionState, position_risk
from tradipy.rejects import Reject, RiskBlock
from tradipy.rounding import TICK_SIZE
from tradipy.setups import SetupSignal

__all__ = [
    "PDT_MIN_EQUITY",
    "PDT_MAX_DAY_TRADES",
    "PDT_WINDOW_BUSINESS_DAYS",
    "OrderIntent",
    "OpenPosition",
    "RiskState",
    "RuleOutcome",
    "RiskDecision",
    "correlation_group",
    "total_open_risk",
    "max_dollar_risk",
    "live_equity",
    "daily_loss_breached",
    "session_drawdown_breached",
    "multi_day_drawdown_breached",
    "approve",
    "approve_all",
    "EVALUATED_RULES",
    "UNREACHABLE_BLOCKS",
]

# ---------------------------------------------------------------------------
# FINRA's pattern-day-trader rule: law, not configuration
# ---------------------------------------------------------------------------
#
# These are **not** registry rows, and the omission is deliberate. A `Param` carries a legal
# range, and a regulation does not have one — moving FINRA's threshold is not a configuration
# change, it is a different regulation. `rounding.TICK_SIZE` makes the identical argument from
# SEC Rule 612 ($0.01 at or above $1.00) and `setups._ONE_DOLLAR` makes it about the price grid.
#
# PRD §2.0 does mention the figure, on the `start_of_day_equity` row: bounds "≥ $25,000 for PDT
# mode". That row's `lo` is 25000 for exactly this reason, so the number is not stated twice with
# different meanings — one is the account minimum this system assumes, the other is the statutory
# test, and they coincide.

#: FINRA PDT equity floor (PRD §7 PDT row). Below this, a 4th day trade in the window is illegal.
PDT_MIN_EQUITY = Decimal(25_000)

#: PRD §7: *"``day_trades_in_window >= 3`` when the new one would be the 4th."* So three is the
#: most that may already have been taken, and the rule fires at three, not at four.
PDT_MAX_DAY_TRADES = 3

#: The rolling window PDT counts over. Recorded for completeness: **which** days fall inside it is
#: business-day arithmetic over a calendar, which is §21.4's and ingestion's — this layer receives
#: :attr:`RiskState.day_trades_in_window` already counted.
PDT_WINDOW_BUSINESS_DAYS = 5


class OrderIntent:
    """Whether an order opens exposure or reduces it.

    Not an :class:`~enum.Enum` member of anything in :mod:`tradipy.rejects`, and not derived from
    a side: §7's loss-streak row says *"Lock new entries; **allow exits**"*, and a side cannot
    express that distinction — a long exit and a short entry are both ``SELL``. §6.3's eight
    checks are written as *"before every order submission"* and would therefore block a
    protective exit, which is the opposite of what §7 asks for.

    A two-member namespace rather than a ``bool`` so a call site reads as
    ``OrderIntent.OPEN`` rather than ``True``.
    """

    OPEN = "OPEN"
    REDUCE = "REDUCE"


@dataclass(frozen=True)
class OpenPosition:
    """One position, in the fields §7's rules actually read.

    A narrower type than §9.2's ``Position`` deliberately: this layer needs the live stop, the
    mark it is measured from, the share count, the §20.12 state and the §7.1.3 correlation group,
    and nothing else. Carrying ``position_id``, ``broker_stop_order_id`` or ``opened_at`` here
    would put broker- and clock-shaped fields into a module that must not have either.

    ``mark`` is what the risk is measured *from* — ``avg_cost`` once filled, the entry limit while
    ``PENDING_ENTRY``. §7's first row counts pending orders, so both cases must be representable.
    """

    symbol: str
    shares: int
    mark: Decimal
    current_stop: Decimal
    state: PositionState
    correlation_group: str

    @property
    def risk(self) -> Decimal:
        """Dollars at risk from the **current live stop** (§7.1.1), never from entry risk."""
        if self.state not in OPEN_STATES:
            return Decimal(0)
        return position_risk(self.shares, self.current_stop, self.mark)


@dataclass(frozen=True)
class RiskState:
    """§10's ``daily_state`` row, plus the open positions §7.1.1 needs. Supplied, never sensed.

    Every field here is either a §10 column or a §7 input, and none of them is read from a broker,
    a clock or a file at this layer — which is what makes §7's rules evaluable under D30.

    **There is no ``minute`` field here, deliberately.** §7's trading-hours row is the one
    time-shaped rule in the table, and the time it is evaluated at is the close of the trigger
    bar — which the signal already carries as ``Levels.trigger_minute``, §20.1's ordinal.
    Carrying it here as well would give one fact two sources, which is the v1.2 defect class, and
    the only way they could legitimately differ is §6.6's disconnect queue (*"signals queued
    during a disconnect expire after 60 sec"*) — which is transport, and refused. So
    :func:`approve` reads the minute off the signal.

    ``session_equity_peak`` and ``multi_day_peak_equity`` are **not** §10 columns — §10's
    ``daily_state`` has no drawdown fields at all, which is worth noting because §7 states two
    drawdown rules whose inputs the schema does not persist. They are accepted here so the
    predicates are evaluable; wiring them to a store is Phase 6's along with the loop.
    """

    start_of_day_equity: Decimal
    realized_pnl: Decimal = Decimal(0)
    unrealized_pnl: Decimal = Decimal(0)
    consecutive_losses: int = 0
    day_trades_in_window: int = 0
    trading_halted: bool = False
    halt_reason: str | None = None
    positions: tuple[OpenPosition, ...] = ()
    #: Highest ``live_equity`` seen this session (§7 session-drawdown row). Defaults to
    #: ``start_of_day_equity`` when not supplied, via ``__post_init__``.
    session_equity_peak: Decimal | None = None
    #: Highest equity over the trailing 5 sessions (§7 multi-day row). ``None`` means unknown, and
    #: the predicate returns ``False`` rather than guessing — an unmeasured drawdown is not a
    #: breach, and inventing a peak would make the rule fire or not fire on a fabricated number.
    multi_day_peak_equity: Decimal | None = None
    #: §6.7 idempotency keys already submitted. A supplied set, because §6.7 requires the
    #: *database* to be the arbiter and there is none — see :attr:`RiskBlock.DUPLICATE_ORDER`.
    submitted_keys: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.session_equity_peak is None:
            object.__setattr__(self, "session_equity_peak", self.start_of_day_equity)

    @property
    def open_positions(self) -> tuple[OpenPosition, ...]:
        """Positions holding shares, per :data:`tradipy.positions.OPEN_STATES`."""
        return tuple(p for p in self.positions if p.state in OPEN_STATES)


@dataclass(frozen=True)
class RuleOutcome:
    """One §7 row, evaluated, with the arithmetic that decided it.

    ``block`` is ``None`` when the rule passed. ``detail`` carries the numbers for the same reason
    :attr:`tradipy.setups.Criterion.detail` does: a threshold nobody can see the inputs to cannot
    be recalibrated against measured data.
    """

    rule: str
    passed: bool
    detail: str
    block: RiskBlock | Reject | None = None


#: Every rule :func:`approve` evaluates for an ``OPEN`` order, in §7's table order. Declared
#: rather than left implicit so that a rule dropped from the loop is *detectable*: an assertion
#: on the **length** of ``rules_evaluated`` passes at any length a reader guesses wrong, which is
#: the shape of hole ``tests/test_enforcement.py`` exists for. ``approve`` asserts its own output
#: against this tuple, and a fixture asserts the tuple against §7's table.
EVALUATED_RULES: tuple[str, ...] = (
    "Account not halted (§7.2 kill switch / §7.1.2 lockout)",
    "Max risk per trade (§7 row 1, NON-BYPASSABLE)",
    "Daily loss limit (§7 row 2, NON-BYPASSABLE)",
    "Max open positions (§7 row 3)",
    "Loss-streak lockout (§7 row 4)",
    "Max buying power (§7 row 5)",
    "PDT check (§7 row 6)",
    "Trading-hours lockout (§7 row 9)",
    "Max correlated exposure (§7 row 10 / §7.1.3)",
    "Duplicate order (§6.3 check 8 / §6.7)",
    "Spread check (§7 / §3.1.3, re-applied pre-order)",
    "Min R:R (§7 / §3.1.2, decided at signal)",
)

#: §7 rows this module has a *predicate* for and **no block path**. Rows 7 and 8 are marked
#: *Continuous* and *End of day*, so the loop that would reach them is Phase 6's — and until it
#: exists these two members are produced by nothing. Enumerated here so the unreachability is a
#: fact the tests can assert rather than a sentence in a docstring; see
#: ``test_the_two_drawdown_blocks_are_unreachable_until_phase_6``.
UNREACHABLE_BLOCKS: frozenset[RiskBlock] = frozenset(
    {RiskBlock.SESSION_DRAWDOWN, RiskBlock.MULTI_DAY_DRAWDOWN}
)


@dataclass(frozen=True)
class RiskDecision:
    """PRD §9.2's ``RiskDecision``, minus the two fields this layer cannot honestly fill.

    §9.2 also lists ``signal_id`` and ``evaluated_at``. The first is the caller's join key and is
    carried on the signal; the second is a ``datetime`` from a clock §21.1 forbids here. Both are
    the transport layer's to attach, and inventing either would be this module holding a concern
    D30 keeps out.

    ``reason`` is ``RiskBlock | Reject | None``, which is what §9.2's own
    *"§7 rule name or §4.2 code"* describes. The union is the point: §7's two signal-time rows are
    the gates and return :class:`~tradipy.rejects.Reject` members, and giving them a second
    spelling in :class:`~tradipy.rejects.RiskBlock` would be the v1.2 defect class.
    """

    approved: bool
    reason: RiskBlock | Reject | None
    rules_evaluated: tuple[RuleOutcome, ...]
    open_risk_before: Decimal
    open_risk_after: Decimal
    approved_shares: int

    @property
    def blocks(self) -> tuple[RuleOutcome, ...]:
        """Every rule that failed, not just the one reported as ``reason``."""
        return tuple(r for r in self.rules_evaluated if not r.passed)


# ---------------------------------------------------------------------------
# §7.1 equity definitions, §7.1.1 open risk
# ---------------------------------------------------------------------------
def live_equity(state: RiskState) -> Decimal:
    """PRD §7.1: ``start_of_day_equity + realized P&L + unrealized P&L``.

    Kept strictly separate from ``start_of_day_equity`` because §7.1 is emphatic about why:
    *"denominating the daily-loss threshold in an equity figure that itself includes unrealized
    P&L makes the threshold move as the loss accrues, so the limit can never be reached
    deterministically."* Every threshold in this module is denominated in the frozen figure; this
    one is used for the P&L numerator and for the buying-power and PDT tests.
    """
    return state.start_of_day_equity + state.realized_pnl + state.unrealized_pnl


def max_dollar_risk(cfg: Config) -> Decimal:
    """PRD §2.2 / §7: ``start_of_day_equity × max_risk_per_trade_pct``.

    The same expression :func:`tradipy.gates.position_size` uses to size a trade, and §7's first
    row uses to cap the *total* across all of them. That those are the same number is not an
    implementation detail — it is what makes §7's cap bind on the second position, which is the
    finding in docs/PHASE-5-DESIGN.md §6.
    """
    return cfg["start_of_day_equity"] * cfg["max_risk_per_trade_pct"]


def total_open_risk(state: RiskState) -> Decimal:
    """PRD §7.1.1: total dollars at risk across all positions, from their current live stops.

    *"The cap applies to total open risk, computed from the current live stop of every open
    position — not from the original entry risk."* Pending orders are included because §7's first
    row says *"plus pending orders"* and :data:`tradipy.positions.OPEN_STATES` contains
    ``PENDING_ENTRY``.
    """
    return sum((p.risk for p in state.open_positions), start=Decimal(0))


def correlation_group(
    symbol: str, catalyst_key: str | None = None, sector: str | None = None
) -> str:
    """PRD §7.1.3: the correlation group for a symbol this session, by first matching rule.

    1. **Shared catalyst** — same confirmed headline or event keyword cluster. §7.1.3 puts this
       first deliberately: *"it is the exposure that matters and the one a sector code cannot
       see."*
    2. **Sector** — from the screening vendor, *"not IBKR, which does not reliably supply it."*
    3. **Ungrouped** — the symbol is its own group.

    Both inputs are **supplied**. Rule 1 needs ``news_headlines`` (§10) set at catalyst
    confirmation and rule 2 needs §5.3's vendor, and sourcing either is a feed. What is
    implemented here is the assignment rule, which is first-match-wins over strings; what is
    enforced is the count, in :func:`approve`.

    §7.1.3's *"honest limitation"* stands unchanged: no realized-correlation estimate is computed,
    because *"a spurious estimate would be worse than an admitted proxy"* (A24, D21).
    """
    if catalyst_key:
        return f"catalyst:{catalyst_key}"
    if sector:
        return f"sector:{sector}"
    return f"symbol:{symbol}"


# ---------------------------------------------------------------------------
# §7 continuous rows, as predicates. The loop that calls them is Phase 6's.
# ---------------------------------------------------------------------------
def daily_loss_breached(state: RiskState, cfg: Config) -> bool:
    """PRD §7 row 2: ``realized + unrealized P&L <= -start_of_day_equity × daily_loss_pct``.

    Denominated in the **frozen** equity figure, per §7.1. Non-strict (``<=``) because §7 writes
    the condition as *"P&L ≤ −equity × daily_loss_pct"* — a loss landing exactly on the limit has
    breached it.

    §7 gives this rule *three* enforcement points: *Continuous (1 sec)*, *post-fill*, and §6.3's
    pre-order list. :func:`approve` applies the pre-order one. The other two need a feed and a
    fill, so open question **G2** narrows here rather than closing — which
    docs/PHASE-5-DESIGN.md §6 states rather than claiming a fix.
    """
    return state.realized_pnl + state.unrealized_pnl <= -(
        state.start_of_day_equity * cfg["daily_loss_pct"]
    )


def session_drawdown_breached(state: RiskState, cfg: Config) -> bool:
    """PRD §7 row 7: session peak-to-trough drawdown beyond ``session_dd_pct``.

    Measured against the session peak of ``live_equity``, not against start-of-day: §7 says
    *"peak-to-trough"*, and on a session that ran up before giving back, start-of-day is not the
    peak. Denominated in ``start_of_day_equity`` per §7.1, so the threshold does not move as the
    drawdown accrues.

    §7's enforcement point is *Continuous* and its action is *"Flatten all; lock account"* —
    neither of which is Phase 5's. **Nothing in this module calls this function**; a Phase 6 loop
    would, and would set :attr:`RiskState.trading_halted`, which :func:`approve` does read. Stated
    plainly because a predicate with no caller is the fifth defect class if it goes unrecorded.
    """
    peak = state.session_equity_peak
    assert peak is not None  # set in __post_init__ when not supplied
    drawdown = peak - live_equity(state)
    return drawdown > state.start_of_day_equity * cfg["session_dd_pct"]


def multi_day_drawdown_breached(state: RiskState, cfg: Config) -> bool:
    """PRD §7 row 8: rolling 5-day drawdown beyond ``multi_day_dd_pct``.

    Returns ``False`` when :attr:`RiskState.multi_day_peak_equity` is ``None``. An unmeasured
    drawdown is not a breach, and defaulting the peak to today's equity would make the rule
    unable to fire — which is worse than admitting it has no input, because it would look
    enforced. §10's ``daily_state`` has no column for this, so on the current schema the input
    does not exist; recorded in docs/CHANGELOG.md alongside §7 row 2's three enforcement points.

    Enforcement point *End of day*, action *"Lock account next day"*. Same caveat as
    :func:`session_drawdown_breached`: no caller here, and the loop is Phase 6's.
    """
    peak = state.multi_day_peak_equity
    if peak is None:
        return False
    return peak - live_equity(state) > state.start_of_day_equity * cfg["multi_day_dd_pct"]


# ---------------------------------------------------------------------------
# §6.3 pre-trade risk validation
# ---------------------------------------------------------------------------
def _q(value: Decimal) -> str:
    """Display a dollar figure to the tick, for a ``detail`` string.

    Quantized to :data:`tradipy.rounding.TICK_SIZE` rather than to a ``Decimal("0.01")`` written
    here. That literal is ``max_pct_of_adv``'s registered default and the registry lint says so —
    correctly, even though this use is display: a second spelling of the price grid is exactly
    what convention 1 forbids, and §20.13 already defines the unit once.
    """
    return f"{value.quantize(TICK_SIZE)}"


def approve(
    signal: SetupSignal,
    state: RiskState,
    cfg: Config,
    *,
    intent: str = OrderIntent.OPEN,
    buying_power: Decimal | None = None,
    correlation: str | None = None,
    idempotency_key: str | None = None,
    spread_now: Decimal | None = None,
) -> RiskDecision:
    """Run a signal through PRD §6.3's pre-trade validation and §7's rule table.

    Returns a :class:`RiskDecision` with **every** rule evaluated, per §9.2. The first failing
    rule in §7's table order becomes :attr:`RiskDecision.reason`; the rest are on
    :attr:`RiskDecision.blocks`.

    **The parameter list is long because every fact §7 needs is supplied rather than sensed**, and
    each keyword corresponds to a source §7 names and D30 keeps out of this layer: ``buying_power``
    is the broker's, ``correlation`` is §7.1.3's news/sector join, ``idempotency_key`` is §6.7's
    store, ``spread_now`` is the NBBO at order time rather than at signal time. Omitting one skips
    the rule that reads it — and the skip is *reported* in ``rules_evaluated`` rather than passing
    silently, because a check that is absent and a check that passed are different facts.

    ``intent`` exists because §7's loss-streak row says *"Lock new entries; allow exits"*. A
    ``REDUCE`` order is evaluated against nothing here: §6.3's list would block a protective exit,
    which inverts the rule. Recorded as a reading in docs/PHASE-5-DESIGN.md §5.

    §7's two signal-time rows are re-applied at this point because §7 marks their enforcement
    point *pre-order*:

    * **Spread check** is re-run against ``spread_now`` when supplied, and this is not
      redundant — the spread can widen between the signal bar's close and order submission, which
      is the same concern §6.4's *"spread widens > 2× entry spread"* row addresses on the other
      side of the fill.
    * **Min R:R** is re-run for the audit trail and is **inert by construction**: every input
      (entry, resistance, R, signal-time spread) is frozen on the signal, so the verdict cannot
      differ from the one :mod:`tradipy.setups` already reached. Reported as decided-at-signal
      rather than dropped, because §6.3 lists it and a missing row in an audit trace reads as a
      check nobody ran.
    """
    rules: list[RuleOutcome] = []
    risk_before = total_open_risk(state)
    incoming = position_risk(
        signal.shares, signal.levels.stop_price, signal.levels.entry_price
    )
    risk_after = risk_before + incoming

    if intent == OrderIntent.REDUCE:
        rules.append(
            RuleOutcome(
                "Order intent (§7 loss-streak: 'allow exits')",
                True,
                "REDUCE — §6.3's entry checks do not apply to a protective exit",
            )
        )
        return RiskDecision(
            approved=True,
            reason=None,
            rules_evaluated=tuple(rules),
            open_risk_before=risk_before,
            open_risk_after=risk_before,
            approved_shares=signal.shares,
        )

    budget = max_dollar_risk(cfg)
    open_count = len(state.open_positions)

    # §7 row 11 / §7.2 / §7.1.2 — checked first, because a halted account is not a candidate for
    # any other question. §7.2's enforcement point is "Any".
    rules.append(
        RuleOutcome(
            "Account not halted (§7.2 kill switch / §7.1.2 lockout)",
            not state.trading_halted,
            f"trading_halted={state.trading_halted}"
            + (f" reason={state.halt_reason}" if state.halt_reason else ""),
            None if not state.trading_halted else RiskBlock.TRADING_HALTED,
        )
    )

    # §7 row 1 — NON-BYPASSABLE. Total open risk, from live stops, plus this order.
    within_risk = risk_after <= budget
    rules.append(
        RuleOutcome(
            "Max risk per trade (§7 row 1, NON-BYPASSABLE)",
            within_risk,
            f"total open risk ${_q(risk_before)} + ${_q(incoming)} = ${_q(risk_after)} "
            f"vs budget ${_q(budget)} ({open_count} position(s) open)",
            None if within_risk else RiskBlock.MAX_RISK_EXCEEDED,
        )
    )

    # §7 row 2 — NON-BYPASSABLE, at §6.3's pre-order point only (G2 narrows, not closes).
    loss_ok = not daily_loss_breached(state, cfg)
    limit = state.start_of_day_equity * cfg["daily_loss_pct"]
    rules.append(
        RuleOutcome(
            "Daily loss limit (§7 row 2, NON-BYPASSABLE)",
            loss_ok,
            f"P&L ${_q(state.realized_pnl + state.unrealized_pnl)} vs limit -${_q(limit)}",
            None if loss_ok else RiskBlock.DAILY_LOSS_LIMIT,
        )
    )

    # §7 row 3.
    positions_ok = open_count < cfg["max_open_positions"]
    rules.append(
        RuleOutcome(
            "Max open positions (§7 row 3)",
            positions_ok,
            f"{open_count} open vs max {cfg['max_open_positions']}",
            None if positions_ok else RiskBlock.MAX_POSITIONS,
        )
    )

    # §7 row 4 / §2's Three Strikes Rule.
    streak_ok = state.consecutive_losses < cfg["max_consecutive_losses"]
    rules.append(
        RuleOutcome(
            "Loss-streak lockout (§7 row 4)",
            streak_ok,
            f"{state.consecutive_losses} consecutive vs max {cfg['max_consecutive_losses']}",
            None if streak_ok else RiskBlock.LOSS_STREAK_LOCKOUT,
        )
    )

    # §7 row 5 / §2.2. Skipped, and reported as skipped, when the broker figure is absent.
    if buying_power is None:
        rules.append(
            RuleOutcome(
                "Max buying power (§7 row 5)",
                True,
                "not evaluated — buying_power not supplied (broker figure; D30)",
            )
        )
    else:
        cap = buying_power * cfg["max_bp_usage_pct"]
        value = signal.shares * signal.levels.entry_price
        bp_ok = value <= cap
        rules.append(
            RuleOutcome(
                "Max buying power (§7 row 5)",
                bp_ok,
                f"order value ${_q(value)} vs cap ${_q(cap)} "
                f"({cfg['max_bp_usage_pct']} x ${_q(buying_power)})",
                None if bp_ok else RiskBlock.BUYING_POWER,
            )
        )

    # §7 row 6 — PDT. Against `live_equity`: FINRA tests current account equity, and the frozen
    # figure would let a morning loss below $25,000 pass a check whose purpose is to prevent an
    # illegal trade. §7 states neither basis; raised in docs/CHANGELOG.md.
    equity_now = live_equity(state)
    pdt_ok = not (
        state.day_trades_in_window >= PDT_MAX_DAY_TRADES and equity_now < PDT_MIN_EQUITY
    )
    rules.append(
        RuleOutcome(
            "PDT check (§7 row 6)",
            pdt_ok,
            f"{state.day_trades_in_window} day trade(s) in {PDT_WINDOW_BUSINESS_DAYS} "
            f"business days vs max {PDT_MAX_DAY_TRADES}; live equity ${_q(equity_now)} "
            f"vs FINRA floor ${_q(PDT_MIN_EQUITY)}",
            None if pdt_ok else RiskBlock.PDT_VIOLATION,
        )
    )

    # §7 row 9 — trading hours, in §20.1 ordinal minutes off the signal's own trigger bar. No
    # early edge is needed: minute 0 is 09:30 and a SessionBar admits nothing below it, which is
    # also why §2.0's `premarket_trading_enabled` stays unrepresentable (G9).
    minute = signal.levels.trigger_minute
    window_ok = minute <= cfg["session_last_entry_minute"]
    rules.append(
        RuleOutcome(
            "Trading-hours lockout (§7 row 9)",
            window_ok,
            f"trigger bar at minute {minute} from open vs last entry minute "
            f"{cfg['session_last_entry_minute']} (15:55 ET at the default)",
            None if window_ok else RiskBlock.OUTSIDE_SESSION_WINDOW,
        )
    )

    # §7 row 10 / §7.1.3 / D21. §6.3's eight checks omit this row; §7's enforcement column marks
    # it Pre-order, and §7's column governs — see docs/PHASE-5-DESIGN.md §5.
    group = correlation if correlation is not None else correlation_group(signal.symbol)
    sharing = sum(1 for p in state.open_positions if p.correlation_group == group)
    corr_ok = sharing < cfg["max_correlated_positions"]
    rules.append(
        RuleOutcome(
            "Max correlated exposure (§7 row 10 / §7.1.3)",
            corr_ok,
            f"{sharing} open position(s) in group {group!r} vs max "
            f"{cfg['max_correlated_positions']}",
            None if corr_ok else RiskBlock.CORRELATED_EXPOSURE,
        )
    )

    # §6.3 check 8 / §6.7. The weakest rule here, and it says so: the arbiter should be the
    # database, and there is none.
    if idempotency_key is None:
        rules.append(
            RuleOutcome(
                "Duplicate order (§6.3 check 8 / §6.7)",
                True,
                "not evaluated — no idempotency_key supplied (§6.7 requires a store; D30)",
            )
        )
    else:
        fresh = idempotency_key not in state.submitted_keys
        rules.append(
            RuleOutcome(
                "Duplicate order (§6.3 check 8 / §6.7)",
                fresh,
                f"key {idempotency_key[:12]}... "
                + ("not seen" if fresh else "already submitted"),
                None if fresh else RiskBlock.DUPLICATE_ORDER,
            )
        )

    # §7's two signal-time rows, at the pre-order point §7's enforcement column also names.
    levels = signal.levels
    spread = spread_now if spread_now is not None else levels.spread_at_signal
    spread_reject = check_spread(spread, levels.entry_price, levels.r_per_share, cfg)
    rules.append(
        RuleOutcome(
            "Spread check (§7 / §3.1.3, re-applied pre-order)",
            spread_reject is None,
            f"spread ${_q(spread)} at "
            + ("order time" if spread_now is not None else "signal time (unchanged)")
            + f", R ${_q(levels.r_per_share)}",
            spread_reject,
        )
    )
    room_reject = check_room(
        levels.entry_price,
        levels.resistance.level,
        levels.r_per_share,
        levels.spread_at_signal,
        cfg,
    )
    rules.append(
        RuleOutcome(
            "Min R:R (§7 / §3.1.2, decided at signal)",
            room_reject is None,
            f"resistance ${_q(levels.resistance.level)} - entry "
            f"${_q(levels.entry_price)} vs required ${_q(levels.room.required)} "
            "— inert here: every input is frozen on the signal",
            room_reject,
        )
    )

    # Every §7 row must have been evaluated, in order. Asserted rather than trusted: the loop
    # above is a sequence of appends, and an edit that drops one leaves a decision that still
    # reports `approved=True` and is short by a rule nobody counted (review finding 14).
    evaluated = tuple(r.rule for r in rules)
    if evaluated != EVALUATED_RULES:
        raise AssertionError(
            "approve() did not evaluate §7's rules in full. Missing: "
            f"{[r for r in EVALUATED_RULES if r not in evaluated]}; unexpected: "
            f"{[r for r in evaluated if r not in EVALUATED_RULES]}. §9.2 requires "
            "rules_evaluated to be *every* rule checked."
        )

    first = next((r for r in rules if not r.passed), None)
    approved = first is None
    return RiskDecision(
        approved=approved,
        reason=None if first is None else first.block,
        rules_evaluated=tuple(rules),
        open_risk_before=risk_before,
        # §9.2 asks for the risk this decision *would* produce, so the projected figure stands
        # even on a block — that is the number a reviewer needs to see next to the rejection.
        open_risk_after=risk_after,
        # §7 rejects rather than trims; §9.2's `approved_shares` "may be <" is not applied. See
        # the module docstring and docs/CHANGELOG.md.
        approved_shares=signal.shares if approved else 0,
    )


def approve_all(
    signals: Sequence[SetupSignal],
    state: RiskState,
    cfg: Config,
    *,
    buying_power: Decimal | None = None,
    groups: Collection[tuple[str, str]] = (),
    keys: Collection[tuple[str, str]] = (),
) -> tuple[RiskDecision, ...]:
    """Run several signals through :func:`approve` **sequentially**, accruing open risk.

    Exists because evaluating a watchlist's signals independently against the same
    :class:`RiskState` gets §7's first row wrong in the direction that matters: each would see the
    risk the others have not yet taken, and two orders that are individually inside the cap would
    both be approved. §7's row is a cap on the *total*, so the state has to advance.

    An approved signal is folded in as a ``PENDING_ENTRY`` position at its entry limit and pattern
    stop, which is exactly what §7's *"plus pending orders"* clause describes.

    ``groups`` maps symbol to §7.1.3 correlation group and ``keys`` maps symbol to §6.7
    idempotency key. Both are supplied because neither can be derived here: the group needs
    §10's ``news_headlines`` or §5.3's vendor, and the key is
    :func:`tradipy.orders.idempotency_key`'s — which this module deliberately does not import,
    because §6.2 puts ``PreTradeRiskCheck`` **before** ``OrderDraft`` and a risk engine that
    built orders would invert that.

    **An approved key is folded into ``submitted_keys``**, which is what makes §6.3's eighth
    check mean anything across a batch: §6.7 requires the key to be persisted *before*
    submission, so a second signal resolving to the same key must see the first. That is the
    closest this layer can come to §6.7's guarantee, and it is still not that guarantee — the
    arbiter should be a database and there is none (see :attr:`RiskBlock.DUPLICATE_ORDER`).
    """
    lookup = dict(groups)
    key_for = dict(keys)
    decisions: list[RiskDecision] = []
    current = state
    for signal in signals:
        group = lookup.get(signal.symbol) or correlation_group(signal.symbol)
        key = key_for.get(signal.symbol)
        decision = approve(
            signal,
            current,
            cfg,
            buying_power=buying_power,
            correlation=group,
            idempotency_key=key,
        )
        decisions.append(decision)
        if decision.approved:
            pending = OpenPosition(
                symbol=signal.symbol,
                shares=decision.approved_shares,
                mark=signal.levels.entry_price,
                current_stop=signal.levels.stop_price,
                state=PositionState.PENDING_ENTRY,
                correlation_group=group,
            )
            current = RiskState(
                start_of_day_equity=current.start_of_day_equity,
                realized_pnl=current.realized_pnl,
                unrealized_pnl=current.unrealized_pnl,
                consecutive_losses=current.consecutive_losses,
                day_trades_in_window=current.day_trades_in_window,
                trading_halted=current.trading_halted,
                halt_reason=current.halt_reason,
                positions=(*current.positions, pending),
                session_equity_peak=current.session_equity_peak,
                multi_day_peak_equity=current.multi_day_peak_equity,
                submitted_keys=(
                    current.submitted_keys | {key}
                    if key is not None
                    else current.submitted_keys
                ),
            )
    return tuple(decisions)
