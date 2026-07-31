"""Order construction — PRD §6.1, §6.2, §6.4 and §6.7. Nothing that sends anything.

Normative sources: PRD §6.1 (order types), §6.2 (lifecycle), §6.4 (partial fills), §6.7
(duplicate-order protection), §3.1.1 (the exit ladder), §9.2 (the ``OrderEvent`` contract),
§20.13 (tick rounding), §21.2 (bracket/OCA protection). §20 governs on any conflict.

**Where this module stops.** §6.2's lifecycle is::

    Signal -> PreTradeRiskCheck -> OrderDraft -> Submit -> Acknowledged -> ... -> Filled

:mod:`tradipy.risk` is the second arrow and this module is the third. **The fourth is refused,
not deferred** — PLAN **D30** admits no broker SDK, vendor client or network module anywhere in
``src/``, and §12.1's Phase 5 dependency column names *"IBKR paper"*. So this layer builds the
draft, guarantees that every price on it is submittable, and hands it back.

**Two guarantees §6 asks for that this module cannot make**, both stated rather than implied:

* §6.7 requires the *database* to be the arbiter of duplication, *"so protection survives a crash
  mid-submission"*. :func:`idempotency_key` derives the key correctly and there is no store; the
  duplicate check is :attr:`tradipy.rejects.RiskBlock.DUPLICATE_ORDER` against a supplied set.
* §21.2 requires the stop and targets to *rest at the broker* as native OCA orders from the moment
  of entry fill. :class:`OrderDraft` describes that group; nothing places it.

**What is not here.** §6.6's connection recovery, §6.8's retry, backoff and rate limit, and
§21.3's reconciliation all require a connection to have existed. §6.5's slippage model is §8.2's
consumer and therefore Phase 4b's — see docs/PHASE-5-DESIGN.md §1.1, which also records that this
puts a §6 rule outside the phase that owns §6.

No numeric threshold appears here as a literal and no rounding direction is named, the same two
rules ``gates``, ``scanner``, ``setups`` and ``positions`` are held to.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from tradipy.params import Config
from tradipy.positions import LegQuantities, leg_quantities
from tradipy.rounding import TICK_SIZE, ceil_to_tick, floor_to_tick
from tradipy.setups import SetupSignal, SetupType

__all__ = [
    "OrderSide",
    "OrderType",
    "LegPurpose",
    "OrderLeg",
    "OrderDraft",
    "PartialFillAction",
    "idempotency_key",
    "entry_limit_price",
    "stop_limit_price",
    "bracket",
    "partial_fill_action",
]


class OrderSide(Enum):
    """PRD §9.2's ``OrderEvent.side`` values. MVP is long-only (§9.2's ``direction``)."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """PRD §6.1's five order types, spelled as §9.2's ``OrderEvent.order_type`` persists them."""

    #: §6.1 — *"Emergency exit, halt resumption (with slippage cap)"*. No leg below uses it: the
    #: cases that need it are §7.2's kill switch and §6.1's halt resumption, both of which are
    #: post-fill actions on an open position rather than parts of an entry bracket.
    MARKET = "MARKET"
    #: §6.1 — *"Primary entry/exit; price = ask + 1 tick (buy) or bid − 1 tick (sell)"*.
    LIMIT = "LIMIT"
    #: §6.1 — *"Hard stop placement immediately after fill"*.
    STOP = "STOP"
    #: §6.1 — *"Stop with limit offset (default: stop − 2 ticks for sells)"*.
    STOP_LIMIT = "STOP_LIMIT"
    #: §6.1 — *"Entry + stop + target as atomic group"*. The group, not a leg; carried on
    #: :attr:`OrderDraft.oca_group`, which is §9.2's ``bracket_group_id``.
    BRACKET = "BRACKET"


class LegPurpose(Enum):
    """Which §3.1.1 role a leg plays. Not a PRD enum — §9.2 has no field for it.

    Named because the alternative is inferring a leg's role from its side and type, and that is
    ambiguous in exactly the case that matters: the stop and both targets are all ``SELL``, and the
    stop and the stop-limit are both protective. A reviewer reading a draft needs to see which leg
    is the protection without reconstructing it.
    """

    ENTRY = "ENTRY"
    STOP = "STOP"
    TARGET_1 = "TARGET_1"
    TARGET_2 = "TARGET_2"


@dataclass(frozen=True)
class OrderLeg:
    """One leg of a bracket, in §9.2's ``OrderEvent`` fields that exist before submission.

    §9.2's ``OrderEvent`` also carries ``order_id``, ``status``, ``filled_qty``,
    ``avg_fill_price`` and ``timestamp``. None of those exists before a broker has seen the order,
    which is why this is a *draft* leg and not an ``OrderEvent``: a type carrying a ``status``
    field that is always ``PENDING`` invites a caller to believe something was submitted.

    Every price is validated to be a whole tick on construction. §20.13's universal requirement is
    *"every price submitted to the broker or compared against a bar must be a whole tick"*, and a
    draft leg is the last representation before submission — so this is where that binds, and it
    binds as an exception rather than a rounding, because silently rounding here would put a
    second rounding point after §20.13's *"rounding happens once, at level computation"*.
    """

    side: OrderSide
    order_type: OrderType
    quantity: int
    purpose: LegPurpose
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError(f"leg quantity may not be negative, got {self.quantity}")
        for name, price in (("limit_price", self.limit_price), ("stop_price", self.stop_price)):
            if price is not None and price % TICK_SIZE != 0:
                raise ValueError(
                    f"{self.purpose.value} {name}={price} is not a whole tick. PRD §20.13: every "
                    "price submitted to the broker must be a whole tick, and rounding happens "
                    "once at level computation — not here."
                )


@dataclass(frozen=True)
class OrderDraft:
    """A §6.1 bracket: entry, stop and the two §3.1.1 targets, as one OCA group.

    **Four legs, not five.** §3.1.1's ladder has three exit tranches, and T3 has no leg here:
    that tranche trails the 9 EMA, and **D18** requires the ratcheted level to rest as a
    broker-side stop *amended each bar close*, which is an amendment stream rather than a leg of
    the opening bracket. :data:`tradipy.positions.PositionState.TRAILING` is the state; the
    amendments are transport's.

    ``oca_group`` is §9.2's ``bracket_group_id``. It is derived from the idempotency key rather
    than generated, for §6.7's reason: a value that is unique by construction cannot be
    reconciled after a restart.
    """

    symbol: str
    setup_type: SetupType
    idempotency_key: str
    oca_group: str
    legs: tuple[OrderLeg, ...]
    quantities: LegQuantities

    @property
    def entry(self) -> OrderLeg:
        return next(leg for leg in self.legs if leg.purpose is LegPurpose.ENTRY)

    @property
    def protective(self) -> OrderLeg:
        """The stop leg — §21.6 makes the absence of one a Sev-1, so it is named, not searched."""
        return next(leg for leg in self.legs if leg.purpose is LegPurpose.STOP)

    @property
    def exit_quantity(self) -> int:
        """Shares covered by exit legs. Equals the entry quantity minus T3's trailed remainder."""
        return sum(
            leg.quantity for leg in self.legs if leg.purpose is not LegPurpose.ENTRY
        ) - self.protective.quantity


class PartialFillAction(Enum):
    """What §6.4 says to do about an incomplete entry fill."""

    #: Keep waiting: the timeout has not elapsed.
    WAIT = "WAIT"
    #: §6.4 — *"cancel remainder and size stop to filled amount"*.
    CANCEL_REMAINDER = "CANCEL_REMAINDER"
    #: §6.4 — a fill at or above ``min_partial_fill_pct`` with the spread still tight. Keep the
    #: remainder working.
    KEEP_WORKING = "KEEP_WORKING"
    #: The fill completed.
    COMPLETE = "COMPLETE"


def idempotency_key(
    symbol: str,
    setup_type: SetupType,
    session_date: str,
    trigger_minute: int,
    account_id: str,
) -> str:
    """PRD §6.7's deduplication key: ``sha256(symbol|setup_type|trigger_bar|account_id)``.

    §6.7 is emphatic about what this is *not*: *"A UUID cannot serve this purpose: a freshly
    generated one is unique by construction, so a duplicate check against it can never fire."*
    Every input below is therefore a fact about the signal, and nothing here is random.

    **The reading on §6.7's ``trigger_bar_timestamp``.** §21.1 forbids ``datetime.now()`` in
    strategy code and :class:`tradipy.session.SessionBar` carries an ``int`` minute rather than a
    timestamp for that reason, so the bar is identified by ``session_date`` — an ISO string the
    caller supplies — plus ``trigger_minute``, §20.1's ordinal. That keeps §6.7's derivation
    *here* (the same setup on the same bar produces the same key on a retry, a restart or a
    duplicate event delivery) while the only imported fact is which session it is, and a ``str``
    cannot be read from a clock. Raised in docs/CHANGELOG.md.

    ``setup_type.value`` is §9.2's spelling, which is what makes the key reconcilable: §6.7 says
    the key is *"sent to IBKR as the order reference for cross-system tracing"*, so a local
    spelling would be untraceable in the one place it needs to be traced.

    Separator is ``|``, as §6.7 writes it. Any field containing a ``|`` would make the encoding
    ambiguous, so this raises rather than producing a key two different signals could share — the
    collision §6.7 exists to prevent, arriving through the encoding instead of through the inputs.
    """
    fields = (symbol, setup_type.value, session_date, str(trigger_minute), account_id)
    offending = [f for f in fields if "|" in f]
    if offending:
        raise ValueError(
            f"idempotency key fields may not contain the '|' separator: {offending}. "
            "PRD §6.7's key is a delimited join, so an embedded delimiter lets two distinct "
            "signals produce one key — the collision the key exists to prevent."
        )
    return hashlib.sha256("|".join(fields).encode("utf-8")).hexdigest()


def entry_limit_price(ask: Decimal, cfg: Config) -> Decimal:
    """PRD §6.1: a buy entry limit at ``ask + entry_limit_offset_ticks``.

    **§20.13 states no rounding direction for an entry limit price.** Its table covers stops
    (down), targets (up), gate minima (up) and gate maxima (down); the price §6.1 actually submits
    is not among them. The reading taken is ``ceil_to_tick``, from §20.13's *governing principle*
    rather than its table: *"no rounding decision anywhere in the system can make a trade look
    better than it is."* Ceiling a **buy** limit pays more, so any rounding here costs money
    rather than saves it. Raised in docs/CHANGELOG.md.

    The offset is registered rather than written as ``+ TICK_SIZE`` because §6.1 states it as a
    default, which makes it configuration; at ``0`` this is a limit at the ask, which is legal and
    fills less often.
    """
    return ceil_to_tick(ask + cfg["entry_limit_offset_ticks"] * TICK_SIZE)


def stop_limit_price(stop: Decimal, cfg: Config) -> Decimal:
    """PRD §6.1: the limit on a protective sell stop, ``stop - stop_limit_offset_ticks``.

    ``floor_to_tick``, which is §20.13's own direction for a stop — *"round down (away from the
    position)"* — applied to the limit that rides with it. Lower is the safe direction for a
    protective sell: it is the worst price the exit will accept, so a lower limit is more likely to
    fill in the fast market a stop trigger implies. A stop-limit that will not fill is a stop that
    does not protect, which §21.6 grades a Sev-1.
    """
    return floor_to_tick(stop - cfg["stop_limit_offset_ticks"] * TICK_SIZE)


def bracket(
    signal: SetupSignal,
    ask: Decimal,
    session_date: str,
    account_id: str,
    cfg: Config,
) -> OrderDraft:
    """Build the §6.1 bracket for an approved signal. Constructs; does not submit.

    Leg layout, and where each price comes from:

    ==========  ======  ============  ===================================================
    Purpose     Side    Type          Price
    ==========  ======  ============  ===================================================
    ENTRY       BUY     LIMIT         :func:`entry_limit_price` on ``ask`` (§6.1)
    STOP        SELL    STOP_LIMIT    ``signal.levels.stop_price``, limit from
                                      :func:`stop_limit_price` (§6.1, §20.13)
    TARGET_1    SELL    LIMIT         ``signal.levels.ladder.t1`` (§3.1.1, 2R)
    TARGET_2    SELL    LIMIT         ``signal.levels.ladder.t2`` (§3.1.1, structural)
    ==========  ======  ============  ===================================================

    **The stop leg covers the whole position and the targets cover their tranches.** That is not
    an arbitrary allocation: §21.6 makes an unprotected share a Sev-1, and the ladder's T3 tranche
    has no target leg (D18), so the only leg that can cover every share is the stop.
    :func:`tradipy.positions.leg_quantities` guarantees the three tranches sum to the share count,
    and ``T1 + T2 <= shares`` follows from it.

    The stop and target prices are **already** whole ticks — :mod:`tradipy.gates` rounds them at
    level computation, which is where §20.13 puts rounding — so they are passed through and
    :class:`OrderLeg` raises if that ever stops being true. Only the entry limit is rounded here,
    because ``ask`` is an input from a feed and nothing upstream has rounded it.

    Raises on a zero-share signal — and does so **through**
    :func:`tradipy.positions.leg_quantities` rather than by checking here first. A bracket with no
    shares is four legs of nothing, and :func:`tradipy.gates.position_size` returns ``0`` for both
    *"no budget"* and *"skip"*, so the case has to fail; but stating the condition in two places
    would be the v1.2 defect class, and the ladder is where "no shares" is already meaningless.
    Same delegation shape as :func:`tradipy.gates.exit_ladder` to
    :func:`tradipy.gates.t1_level`.
    """
    levels = signal.levels
    quantities = leg_quantities(signal.shares, cfg)
    key = idempotency_key(
        signal.symbol, signal.setup_type, session_date, levels.trigger_minute, account_id
    )
    legs = (
        OrderLeg(
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=signal.shares,
            purpose=LegPurpose.ENTRY,
            limit_price=entry_limit_price(ask, cfg),
        ),
        OrderLeg(
            side=OrderSide.SELL,
            order_type=OrderType.STOP_LIMIT,
            quantity=signal.shares,
            purpose=LegPurpose.STOP,
            limit_price=stop_limit_price(levels.stop_price, cfg),
            stop_price=levels.stop_price,
        ),
        OrderLeg(
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=quantities.t1,
            purpose=LegPurpose.TARGET_1,
            limit_price=levels.ladder.t1,
        ),
        OrderLeg(
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=quantities.t2,
            purpose=LegPurpose.TARGET_2,
            limit_price=levels.ladder.t2,
        ),
    )
    return OrderDraft(
        symbol=signal.symbol,
        setup_type=signal.setup_type,
        idempotency_key=key,
        # §9.2's `bracket_group_id`, derived rather than generated — §6.7's argument about UUIDs
        # applies to the group id too, because §21.3 reconciles a bracket by it after a restart.
        oca_group=f"OCA-{key[:16]}",
        legs=legs,
        quantities=quantities,
    )


def partial_fill_action(
    intended: int,
    filled: int,
    entry_spread: Decimal,
    spread_now: Decimal,
    seconds_since_submit: int,
    cfg: Config,
) -> PartialFillAction:
    """PRD §6.4's partial-fill decision. A decision, not a wait.

    §6.4 states three rules:

    1. *"Track cumulative filled quantity vs intended quantity"* — the caller's, and the two
       counts are arguments here.
    2. *"If partial fill < 50% of intended within 30 sec, cancel remainder and size stop to filled
       amount."*
    3. *"If partial fill >= 50%, cancel remainder only if spread widens > 2× entry spread."*

    **The clock stays outside.** ``seconds_since_submit`` is a supplied fact and
    ``partial_fill_timeout_seconds`` is applied here, which is the shape
    :attr:`tradipy.quotes.Quote.age_seconds` already uses to carry §20.14's staleness rule into a
    clockless module. §21.1 forbids ``datetime.now()``; it does not forbid comparing an elapsed
    count against a threshold.

    Rule 3 is evaluated **before** the timeout, deliberately: §6.4 attaches no time bound to the
    spread-widening condition, so a fill that has crossed the 50% line and then seen the spread
    double should be cut immediately rather than at 30 seconds. §6.4 does not state the ordering;
    this is the reading, and it is the stricter of the two.

    Raises on ``filled > intended``: an over-fill is a broker- or reconciliation-level fault
    (§21.3), and returning a plausible action for it would let a caller size a stop to a quantity
    it does not hold.
    """
    if intended <= 0:
        raise ValueError(f"intended quantity must be positive, got {intended}")
    if filled < 0 or filled > intended:
        raise ValueError(
            f"filled={filled} is not in [0, {intended}]. An over-fill is a §21.3 reconciliation "
            "fault, not a §6.4 partial fill; sizing a stop from it would protect shares that "
            "are not held."
        )
    if filled == intended:
        return PartialFillAction.COMPLETE

    fraction = Decimal(filled) / Decimal(intended)
    if fraction >= cfg["min_partial_fill_pct"]:
        widened = spread_now > cfg["partial_fill_spread_widening_multiple"] * entry_spread
        return PartialFillAction.CANCEL_REMAINDER if widened else PartialFillAction.KEEP_WORKING
    if seconds_since_submit >= cfg["partial_fill_timeout_seconds"]:
        return PartialFillAction.CANCEL_REMAINDER
    return PartialFillAction.WAIT
