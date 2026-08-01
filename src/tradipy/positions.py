"""The §20.12 position state machine, §3.1.1 stop management, and §7.1.1 scale-in legality.

Normative sources: PRD §20.12 (the state machine), §3.1.1 (the exit ladder and the
stop-to-breakeven move), §7.1.1 (scaling in against the non-bypassable risk cap), §9.2 (the
``Position`` contract), §20.13 (rounding). §20 governs on any conflict.

**What this module is.** The lifecycle of a *position*, as distinct from the lifecycle of an
*order*. ``OrderEvent.status`` covers the latter and §20.12 opens by saying so: it *"covers
order state but not position lifecycle, which is what the multi-target ladder and partial-fill
quantity adjustments actually require."* Everything here is a pure function of a state and some
arithmetic; nothing reads a clock, a feed or a database.

**What is deliberately not here:**

* **Persistence.** §20.12 requires *"every transition is persisted (``positions.state``) and
  emitted to the audit log, so a restart can resume mid-position."* This module transitions;
  §10's table and §21.3's reconciliation are the transport half, and D30 refuses transport. The
  consequence is that §7.1.2's *"the non-bypassable limits are meaningless if they reset on
  restart"* is **unclosed**, and docs/PHASE-5-DESIGN.md §1.1 says so rather than implying
  otherwise.
* **T3's ratcheting 9 EMA trail.** The ``TRAILING`` state is modelled and
  :meth:`tradipy.session.Session.ema_at` computes §20.5's level, but **D18** requires the
  ratcheted level to rest as a broker-side stop amended each bar close. A local-only trail would
  silently void §21.2's guarantee at exactly the state where a position is least attended.

**Where §20.12 contradicts itself.** Its diagram and its table do not agree on the permitted
transitions, and neither is complete on its own. The reading is recorded on
:data:`TRANSITIONS` and raised in docs/CHANGELOG.md rather than settled here.

No numeric threshold appears as a literal and no rounding direction is named — the same two rules
``gates``, ``scanner`` and ``setups`` are held to.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType

from tradipy.params import Config
from tradipy.rejects import ExitReason
from tradipy.rounding import floor_to_tick

__all__ = [
    "PositionState",
    "TERMINAL_STATES",
    "OPEN_STATES",
    "TRANSITIONS",
    "IllegalTransitionError",
    "transition",
    "reachable_exit_reasons",
    "breakeven_stop",
    "LegQuantities",
    "leg_quantities",
    "position_risk",
    "scale_in_permitted",
]


class PositionState(Enum):
    """PRD §20.12's twelve position states, spelled as that section spells them.

    The strings are persisted in ``positions.state`` (§10) and read back by §21.3's
    reconciliation, so inventing a spelling here would make a position irreconcilable across a
    restart — the same argument :class:`tradipy.setups.SetupType` makes about §9.2's
    ``signals.setup_type``.
    """

    #: No setup recognised. §20.12's diagram names it; its table gives it no row.
    IDLE = "IDLE"
    #: Setup recognised, awaiting the trigger bar.
    ARMED = "ARMED"
    #: Entry order live, unfilled or partially filled.
    PENDING_ENTRY = "PENDING_ENTRY"
    #: Position open, stop at the pattern level, full R at risk.
    OPEN_FULL = "OPEN_FULL"
    #: ``t1_scale_out_pct`` out; stop moved to breakeven; scale-in now arithmetically possible.
    T1_FILLED = "T1_FILLED"
    #: T1 plus ``t2_scale_out_pct`` out.
    T2_FILLED = "T2_FILLED"
    #: Final tranche on the ratcheting 9 EMA stop (§20.5, §21.2 — the level is D18's, not here).
    TRAILING = "TRAILING"
    #: Ladder complete, or flattened. Terminal.
    CLOSED = "CLOSED"
    #: The trigger never came, or the entry order never filled. Terminal, and the one state with
    #: no §9.2 ``exit_reason``: a position that expired never opened, so there is no closed trade.
    EXPIRED = "EXPIRED"
    #: A protective stop filled.
    STOPPED_OUT = "STOPPED_OUT"
    #: A §3 post-entry invalidation fired (:func:`tradipy.setups.bull_flag_exit` and friends).
    INVALIDATED = "INVALIDATED"
    #: The §3.2/§3.3 breakout-or-bailout timer expired.
    BAILED_OUT = "BAILED_OUT"


#: States from which nothing further happens. ``CLOSED`` and ``EXPIRED`` only: §20.12's diagram
#: routes the three exit states onward to ``CLOSED``, so they are *not* terminal even though a
#: reader skimming the table — which gives them no row at all — would take them to be.
TERMINAL_STATES: frozenset[PositionState] = frozenset({PositionState.CLOSED, PositionState.EXPIRED})

#: States in which shares are held and therefore at risk. Read by :func:`position_risk` and by
#: :mod:`tradipy.risk`'s §7.1.1 total-open-risk sum, so that a ``PENDING_ENTRY`` order counts —
#: §7's first row says *"all positions … **plus pending orders**"* in terms.
OPEN_STATES: frozenset[PositionState] = frozenset(
    {
        PositionState.PENDING_ENTRY,
        PositionState.OPEN_FULL,
        PositionState.T1_FILLED,
        PositionState.T2_FILLED,
        PositionState.TRAILING,
    }
)


def _transitions() -> Mapping[PositionState, frozenset[PositionState]]:
    """PRD §20.12's permitted transitions, and the reading needed to have any.

    **§20.12's diagram and its table disagree, and neither is complete.** The table's
    "Permitted transitions" column gives six rows — ``ARMED``, ``PENDING_ENTRY``,
    ``OPEN_FULL``, ``T1_FILLED``, ``T2_FILLED``, ``TRAILING`` — and no row for ``IDLE``,
    ``CLOSED``, ``EXPIRED`` or the three exit states. The diagram adds ``IDLE → ARMED`` and
    routes ``STOPPED_OUT / INVALIDATED / BAILED_OUT → CLOSED``, and it also draws a ``↓`` under
    ``T1_FILLED`` and ``T2_FILLED`` into all three exit states where the table permits only
    ``STOPPED_OUT`` from the first and only ``TRAILING`` from the second.

    **The reading: the table where it has a row, the diagram where it has none.** The table's
    column is an explicit enumeration and is the stricter of the two, which is the choice this
    package takes wherever §20 admits two readings. But the table alone yields a machine that
    can neither start (nothing reaches ``ARMED``) nor finish (nothing reaches ``CLOSED`` from an
    exit state), so the diagram has to supply those two edge sets and nothing else.

    Raised in docs/CHANGELOG.md, not settled here. What it costs, stated because it is a
    behaviour difference rather than a documentation one: under this reading a position that has
    taken T1 profit **cannot** be recorded as ``INVALIDATED`` or ``BAILED_OUT`` — only as
    ``STOPPED_OUT`` — so a §3 post-entry invalidation firing after T1 has no state to move to.
    :func:`tradipy.setups.bull_flag_exit` will still return ``INVALIDATED`` for those bars, and
    :func:`transition` will refuse it. That is a real gap and it is the strongest argument for
    the diagram's reading; it is not taken unilaterally because widening a state machine to
    admit a transition the normative table omits is a spec change.
    """
    t: dict[PositionState, frozenset[PositionState]] = {
        # Diagram only — the table has no `IDLE` row, and without this nothing can start.
        PositionState.IDLE: frozenset({PositionState.ARMED}),
        # Table rows, transcribed.
        PositionState.ARMED: frozenset({PositionState.PENDING_ENTRY, PositionState.EXPIRED}),
        PositionState.PENDING_ENTRY: frozenset({PositionState.OPEN_FULL, PositionState.EXPIRED}),
        PositionState.OPEN_FULL: frozenset(
            {
                PositionState.T1_FILLED,
                PositionState.STOPPED_OUT,
                PositionState.INVALIDATED,
                PositionState.BAILED_OUT,
            }
        ),
        PositionState.T1_FILLED: frozenset({PositionState.T2_FILLED, PositionState.STOPPED_OUT}),
        PositionState.T2_FILLED: frozenset({PositionState.TRAILING}),
        PositionState.TRAILING: frozenset({PositionState.CLOSED, PositionState.STOPPED_OUT}),
        # Diagram only — the table has no rows for these, and without them nothing can finish.
        PositionState.STOPPED_OUT: frozenset({PositionState.CLOSED}),
        PositionState.INVALIDATED: frozenset({PositionState.CLOSED}),
        PositionState.BAILED_OUT: frozenset({PositionState.CLOSED}),
        # Terminal in both the table and the diagram.
        PositionState.CLOSED: frozenset(),
        PositionState.EXPIRED: frozenset(),
    }
    return MappingProxyType(t)


#: The §20.12 transition table. Read-only, and **total**: every state has an entry, so a
#: ``KeyError`` from :func:`transition` would be a missing enum member rather than a missing rule.
#: ``tests/test_enforcement.py`` walks every edge in it and asserts every edge outside it raises.
TRANSITIONS: Mapping[PositionState, frozenset[PositionState]] = _transitions()


class IllegalTransitionError(ValueError):
    """Raised when a transition §20.12 does not permit is attempted.

    A distinct type rather than a bare ``ValueError`` because §20.12's whole purpose is that a
    restart can resume mid-position rather than *"discovering an untracked broker position"*, and
    a caller reconciling against a broker needs to tell "the broker says something §20.12
    forbids" apart from "this argument was the wrong shape."
    """


def transition(state: PositionState, to: PositionState) -> PositionState:
    """Move ``state`` to ``to`` if §20.12 permits it, else raise :class:`IllegalTransitionError`.

    Returns the new state rather than mutating anything: §9.2's ``Position`` is the only
    non-frozen contract in that section, and the transition itself is a function.

    A self-transition is refused. §20.12 lists no state as its own successor, and permitting one
    would make the audit log §20.12 requires unable to distinguish "no event" from "an event that
    changed nothing" — which is the same information-loss shape as
    :func:`tradipy.gates.position_size` returning ``0`` for both "no budget" and "skip".
    """
    permitted = TRANSITIONS[state]
    if to not in permitted:
        allowed = ", ".join(sorted(s.value for s in permitted)) or "(terminal)"
        raise IllegalTransitionError(
            f"PRD §20.12 does not permit {state.value} -> {to.value}; "
            f"from {state.value} the permitted transitions are: {allowed}"
        )
    return to


def reachable_exit_reasons(state: PositionState) -> frozenset[ExitReason]:
    """Which §9.2 ``exit_reason`` values §20.12 permits a position in ``state`` to close with.

    Exists because §9.2 enumerates **six** exit reasons and §20.12 has state names matching only
    three of them, so the mapping between the two vocabularies is not the identity. Derived from
    :data:`TRANSITIONS` rather than written out, so it cannot disagree with the machine.

    **What this function makes visible, and it is the point of it.** §7.2's kill switch has
    enforcement point *"Any"* and action *"Cancel all open orders → market-close all
    positions"*; §7's trading-hours row implies the same flattening at the close. Both need an
    edge to ``CLOSED`` from **every** open state, and §20.12 provides one only from ``TRAILING``.
    So ``EOD_FLAT`` and ``KILL_SWITCH`` are *unreachable* from ``PENDING_ENTRY``, ``OPEN_FULL``,
    ``T1_FILLED`` and ``T2_FILLED`` under §20.12 as written.

    That is reported rather than patched. Adding the edges would make the kill switch work and
    would also widen a normative table on this module's own authority, which is a spec change;
    raised in docs/CHANGELOG.md. ``tests/test_enforcement.py`` asserts the emptiness, so if
    §20.12 is later corrected the assertion fails and this docstring gets revisited.
    """
    if state not in OPEN_STATES:
        return frozenset()
    successors = TRANSITIONS[state]
    reasons = {
        ExitReason(s.value)
        for s in successors
        if s in {PositionState.STOPPED_OUT, PositionState.INVALIDATED, PositionState.BAILED_OUT}
    }
    if PositionState.CLOSED in successors:
        # §20.12's one non-failure path to CLOSED, and therefore the only state from which the
        # three flattening reasons are expressible at all.
        reasons |= {ExitReason.LADDER_COMPLETE, ExitReason.EOD_FLAT, ExitReason.KILL_SWITCH}
    return frozenset(reasons)


def breakeven_stop(avg_cost: Decimal) -> Decimal:
    """PRD §3.1.1: on T1 fill, move the stop on the remainder to breakeven.

    Rounded **down** to a tick, because it is a stop and §20.13's stop row is unconditional —
    *"round down (away from the position)"* — not conditional on how the level was derived. At a
    tick-aligned ``avg_cost`` this is a no-op; a volume-weighted average across partial fills is
    the case where it is not, and that is precisely the case §6.4 creates.

    One line, and it is the line that makes §7.1.1's reconciliation of scale-ins with the
    non-bypassable cap true: *"because the stop moves to breakeven when T1 fills, the original
    tranche contributes ~zero risk at that point, which is precisely what creates headroom."*
    """
    return floor_to_tick(avg_cost)


@dataclass(frozen=True)
class LegQuantities:
    """The §3.1.1 ladder split over an integer share count.

    ``t1 + t2 + t3 == shares`` is an invariant, not a coincidence — see :func:`leg_quantities`.
    """

    t1: int
    t2: int
    t3: int
    shares: int

    def __post_init__(self) -> None:
        if self.t1 + self.t2 + self.t3 != self.shares:
            raise ValueError(
                f"leg quantities {self.t1}/{self.t2}/{self.t3} sum to "
                f"{self.t1 + self.t2 + self.t3}, not {self.shares}. Every share must be covered "
                "by an exit leg: PRD §21.6 makes an unprotected position a Sev-1."
            )


def leg_quantities(shares: int, cfg: Config) -> LegQuantities:
    """Split ``shares`` across §3.1.1's three exit legs.

    §3.1.1's ladder is T1 50%, T2 25%, T3 25%, and §20.12 corroborates it (``T1_FILLED`` is
    *"50% out"*, ``T2_FILLED`` *"75% out"*). **§3.1.1 states no rule for a share count those
    fractions do not divide**, and §2.2 floors the count, so indivisible is the normal case.

    The reading: **floor T1 and T2, and give T3 the remainder.** The binding requirement is that
    the three legs sum *exactly* to ``shares`` — §21.6 makes a share with no protective leg a
    Sev-1 alert, so an allocation that can drop one is not merely imprecise. Flooring the two
    profit legs is the only one of the three roundings that cannot leave a share uncovered, and
    the remainder lands on the tranche §3.1.1 already trails rather than targets.

    **Consequence, stated because it is surprising and is tested:** a 1-share position has
    ``t1 == t2 == 0`` and exits entirely on the trail. Two shares put one on T1 and one on the
    trail with nothing on T2. Neither is wrong under §3.1.1 as written, and both are what a
    $0.10-minimum stop on a small account produces.

    Raises on a non-positive count: ``leg_quantities(0)`` would return three zeros that satisfy
    the sum invariant while protecting nothing, which is the shape of bug the invariant exists to
    catch.
    """
    if shares <= 0:
        raise ValueError(
            f"shares must be positive to build an exit ladder, got {shares}. "
            "A zero-share ladder satisfies the sum invariant and protects nothing; see "
            "tradipy.gates.position_size, which returns 0 for 'no budget' as well as 'skip'."
        )
    t1 = int(cfg["t1_scale_out_pct"] * shares)
    t2 = int(cfg["t2_scale_out_pct"] * shares)
    return LegQuantities(t1=t1, t2=t2, t3=shares - t1 - t2, shares=shares)


def position_risk(shares: int, current_stop: Decimal, mark: Decimal) -> Decimal:
    """Dollars at risk on one position, measured from its **current live stop** (§7.1.1).

    ``mark`` is the price the risk is measured from — ``avg_cost`` for an open position, the
    entry limit for a ``PENDING_ENTRY`` order. §7's first row requires both to be counted:
    *"all positions … measured from current live stops, **plus pending orders**."*

    Clamped at zero rather than returning a negative. Once the stop is at or above the mark —
    which is exactly what :func:`breakeven_stop` does at T1 — the position cannot lose, and a
    negative contribution would let one profitable position *fund* risk on another. §7.1.1's
    headroom argument is that the tranche contributes *"~zero"*, not that it contributes credit.
    """
    return max(Decimal(0), (mark - current_stop) * shares)


def scale_in_permitted(
    state: PositionState,
    open_risk_after: Decimal,
    cfg: Config,
) -> bool:
    """PRD §7.1.1: may shares be added to an existing position?

    §7.1.1 reconciles §3.5's *"add to winners"* with the non-bypassable per-trade cap, and the
    rule it lands on is a **consequence** rather than an independent threshold: an add is
    permitted only if total open risk still satisfies
    ``<= start_of_day_equity × max_risk_per_trade_pct`` *after* the add.

    So the arithmetic is the whole rule and the state is a filter on it. Both are checked here,
    deliberately, because §7.1.1's own conclusion — *"adds are only ever legal after T1, never
    while the initial position is still at full risk"* — is a claim about states, and asserting
    it in code makes it fail loudly if the arithmetic ever stops implying it. A position at
    ``OPEN_FULL`` is refused even when the budget appears to allow it, which can only happen at a
    configuration where the position was sized below the cap.
    """
    if state not in {PositionState.T1_FILLED, PositionState.T2_FILLED}:
        return False
    budget = cfg["start_of_day_equity"] * cfg["max_risk_per_trade_pct"]
    return open_risk_after <= budget
