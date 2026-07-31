"""The three MVP setups — PRD §3.2 Bull Flag, §3.3 HOD Breakout, §3.4 VWAP Reclaim.

Normative sources: PRD §3.2, §3.3, §3.4 (the setups), §3.1.1–§3.1.3 (the shared ladder and
pre-entry gates), §9.2 (the ``TradeSignal`` contract), §20.1–§20.6 and §20.11 (computation
semantics and signal arbitration), §8.1 (no look-ahead). §20 governs on any conflict.

**What this module is.** The layer that turns a *bar series* into a signal. Every pre-entry
gate in :mod:`tradipy.gates` takes ``resistance``, ``structural_target``, ``raw_stop``,
``effective_stop`` and ``spread_at_signal`` as inputs, and until Phase 4 nothing in the package
computed any of them — ``poc.evaluate`` supplied them by hand from the §3 tables, which is why
``python -m tradipy demo`` replays arithmetic rather than setups. It also answers §21.1's
worked-example row on the side it actually names: *"input **bar series** -> asserted entry,
stop, R, targets, share count."*

**What is deliberately not here**, because an omission nobody wrote down cannot be told apart
from an oversight:

* **§20.12's position state machine, and everything that needs it** — the T1 stop-to-breakeven
  move, §7.1.1 scale-ins, and T3's ratcheting 9 EMA trail. D18 requires the ratcheted level to
  rest as a broker-side stop amended each bar close, so a local-only trail would silently void
  §21.2's guarantee at exactly the state where a position is least attended.
  :meth:`tradipy.session.Session.ema_at` computes §20.5; the protection is Phase 5/6's.
* **The §3 post-entry rules are here, but as predicates** — :func:`bull_flag_exit`,
  :func:`hod_breakout_exit` and :func:`vwap_reclaim_exit` are pure functions of the bars after
  entry. They are §3's rules; the state they would be evaluated *in* is not.
* **Order routing, sizing against live equity, §7's pre-order rules.** §7 states its own
  enforcement point as *pre-order* for all but two rows, and the two that are signal-time —
  Min R:R and Spread check — are :func:`tradipy.gates.check_room` and
  :func:`tradipy.gates.check_spread`, already built.
* **Any feed.** PLAN **D30**: the ladder is at ``SIMULATED``, so a :class:`~tradipy.session.Session`
  is handed to this layer exactly as a ``ScanCandidate`` is handed to the scanner.

**Where §3 admits more than one reading — and where it defines nothing at all.** §20 defines
flagpole geometry (§20.4) and stops: *flag*, *consolidation candle*, *dip*, *leg* and *leg
height* have no normative definition anywhere in the PRD. Each reading this module had to take
is stated on the function that takes it and raised in docs/CHANGELOG.md's spec-question table;
docs/PHASE-4-DESIGN.md §5 is the list. None is resolved here. Two are worth knowing before
reading any output:

* **The room gate's ``resistance`` is measured against the HOD established *before* the trigger
  bar** — see :func:`nearest_resistance`, which explains why the alternative makes §3.1.1
  unsatisfiable for every breakout.
* **§3.1.1 enumerates ``next whole dollar`` in the resistance set, and §3.4's worked example
  does not apply it.** Applying §3.1.1 as written rejects that example. The disagreement is
  reproduced by ``tests/test_setups.py`` rather than smoothed over, because §3.4's is the
  example the PRD calls *"the reason §3.1.2 exists."*

**No threshold appears here as a literal and no rounding direction is named**, the same two
rules `gates` and `scanner` are held to.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import Enum
from typing import ClassVar

from tradipy.bars import (
    Bar,
    flagpole_ending_at,
    flagpole_height,
    measured_move,
    retrace_pct,
    select_flagpole,
)
from tradipy.gates import (
    Ladder,
    RoomRequirement,
    apply_stop_floor_and_ceiling,
    check_room,
    check_spread,
    exit_ladder,
    min_separation,
    position_size,
    required_room,
    spread_caps,
    t1_level,
    vwap_reclaim_stop,
)
from tradipy.params import Config
from tradipy.rejects import ExitReason, Reject
from tradipy.rounding import TICK_SIZE, floor_to_tick
from tradipy.session import Session, tighter, wider

__all__ = [
    "SetupType",
    "Criterion",
    "Resistance",
    "Levels",
    "SetupSignal",
    "SetupOutcome",
    "nearest_resistance",
    "whole_dollar_above",
    "evaluate_bull_flag",
    "evaluate_hod_breakout",
    "evaluate_vwap_reclaim",
    "EVALUATORS",
    "evaluate_all",
    "arbitrate",
    "bull_flag_exit",
    "hod_breakout_exit",
    "vwap_reclaim_exit",
]

#: One dollar, for §3.1.1's "next whole dollar" resistance level. A unit of the price grid
#: like ``TICK_SIZE``, not a tunable threshold, so it is named here rather than registered.
_ONE_DOLLAR = Decimal(1)


class SetupType(Enum):
    """The three MVP setups, with PRD §9.2's ``signals.setup_type`` values.

    The strings are §9.2's, not this module's: they are persisted in ``signals`` and are half of
    §6.7's idempotency key, so inventing a spelling here would make a signal irreconcilable
    across a restart.

    Declaration order is §20.11's **priority order** — *"Bull Flag -> HOD Breakout -> VWAP
    Reclaim (descending source confidence, §16)"* — and :func:`arbitrate` reads it from the
    enum rather than restating it. The §3.1 inventory's confidence column agrees: High, High,
    Medium-High.
    """

    BULL_FLAG = "BULL_FLAG"
    HOD_BREAKOUT = "HOD_BREAKOUT"
    VWAP_RECLAIM = "VWAP_RECLAIM"

    @property
    def priority(self) -> int:
        """§20.11 rule 2: lower wins. Derived from declaration order, not restated."""
        return list(SetupType).index(self)


@dataclass(frozen=True)
class Criterion:
    """One §3 entry criterion or §3.1 gate, with the arithmetic that decided it.

    Field order mirrors :class:`tradipy.scanner.HardResult` deliberately: the two are read the
    same way, and ``detail`` exists for the same reason — a rejection you have to re-derive to
    understand cannot be recalibrated against measured data.

    ``code`` is the rejection this criterion raises when it fails. Pattern criteria all carry
    :attr:`~tradipy.rejects.Reject.SETUP_NOT_PRESENT`; the gate criteria carry the code the gate
    itself defines, so no rejection code is invented at this layer.
    """

    name: str
    code: Reject
    passed: bool
    detail: str


@dataclass(frozen=True)
class Resistance:
    """The §3.1.1 room gate's nearest overhead level, and every candidate considered."""

    level: Decimal
    source: str
    #: Every candidate above entry, nearest first. Exposed so *why* the gate bound is readable
    #: without re-deriving the set — which is the whole finding in §3.4's worked example.
    candidates: tuple[tuple[str, Decimal], ...]


@dataclass(frozen=True)
class Levels:
    """Every price PRD §9.2's ``TradeSignal`` carries, derived once the pattern is recognised.

    Separate from :class:`SetupSignal` so a **rejected** setup can still report them.
    :class:`tradipy.scanner.ScanResult` reports all seven §4.2 filters' arithmetic on a rejected
    candidate for the same reason: a rejection whose numbers you cannot see is not a rejection
    anyone can recalibrate against. What is withheld from a reject is the *share count*, which
    is this layer's analogue of the composite score §4.1 withholds — the rejection is the
    answer, and a size sitting on it is an invitation to use it.
    """

    entry_price: Decimal
    #: The pattern level before A14's selection and before the $0.10 floor. Kept because the
    #: difference between this and :attr:`stop_price` is exactly what A14 is about, and a signal
    #: reporting only the effective stop cannot show that nominal and realised R differ.
    pattern_stop: Decimal
    #: The **effective** stop — §20.6's selection and A14's ``max()`` applied, then §20.13's
    #: floor and ceiling. This is what sizing uses and what §9.2 calls ``stop_price``.
    stop_price: Decimal
    r_per_share: Decimal
    ladder: Ladder
    resistance: Resistance
    room: RoomRequirement
    min_separation: Decimal
    spread_at_signal: Decimal
    #: §3.2 / §3.3's breakout-or-bailout compares against the trigger bar's high.
    breakout_high: Decimal
    #: The HOD established *before* the trigger bar (§20.3).
    prior_hod: Decimal

    @property
    def target_prices(self) -> tuple[Decimal, Decimal]:
        """§9.2: ``[T1, T2]``, ordered. T3 is trailed, so it is not a price."""
        return (self.ladder.t1, self.ladder.t2)

    @property
    def required_room(self) -> Decimal:
        """§3.1.2's unified requirement, as §9.2 records it."""
        return self.room.required


@dataclass(frozen=True)
class SetupSignal:
    """PRD §9.2's ``TradeSignal``: the :class:`Levels` plus what acceptance adds.

    ``signal_id``, ``created_at`` and ``status`` are §10.1's columns and belong to whatever
    persists this. ``confidence`` is §9.2's and is the §20.10 composite score, which is the
    scanner's output rather than the setup's — a signal does not recompute its own name's rank.
    """

    symbol: str
    setup_type: SetupType
    levels: Levels
    shares: int

    #: §9.2: every MVP setup is long-only. §3.5's short setups are post-MVP and §7's rules are
    #: written for longs throughout (§20.6 defines "tighter" for a long only).
    direction: ClassVar[str] = "LONG"


@dataclass(frozen=True)
class SetupOutcome:
    """One setup's full evaluation at one bar: every criterion, its levels, and the signal.

    **Pattern criteria short-circuit; gate criteria do not.** :class:`tradipy.scanner.ScanResult`
    evaluates all seven §4.2 filters even after one fails, because a rejection you can only see
    one dimension of is not readable. That is possible there and impossible here for the pattern
    half: a flag's retrace is undefined without a flag, so the criteria stop at the first
    *structural* absence. Once the pattern exists, all of the §3.1 gates are evaluated and
    reported together, and :attr:`levels` is populated whether they passed or not — that half
    keeps the scanner's property.
    """

    symbol: str
    setup_type: SetupType
    criteria: tuple[Criterion, ...]
    levels: Levels | None = None
    signal: SetupSignal | None = None

    def __post_init__(self) -> None:
        if self.signal is not None and self.failures:
            raise ValueError(
                f"{self.symbol} {self.setup_type.value}: a signal cannot coexist with a failed "
                f"criterion ({', '.join(c.name for c in self.failures)}). PRD §3.x states its "
                "criteria as 'all required'."
            )

    @property
    def failures(self) -> tuple[Criterion, ...]:
        """Every failed criterion, in evaluation order."""
        return tuple(c for c in self.criteria if not c.passed)

    @property
    def reject(self) -> Reject | None:
        """The first failure's code, or ``None`` if every criterion passed."""
        failures = self.failures
        return failures[0].code if failures else None

    @property
    def accepted(self) -> bool:
        return self.signal is not None


# ---------------------------------------------------------------------------
# §3.1.1 resistance
# ---------------------------------------------------------------------------
def whole_dollar_above(price: Decimal) -> Decimal:
    """The next whole-dollar level strictly above ``price`` (PRD §3.1.1, §3.3's T2).

    Strictly above: at exactly $6.00 the next whole dollar is $7.00, because a level price has
    already reached is not overhead. Whole dollars are whole ticks, so nothing is rounded here.
    """
    return price.to_integral_value(rounding=ROUND_FLOOR) + _ONE_DOLLAR


def nearest_resistance(
    entry: Decimal,
    *,
    prior_hod: Decimal,
    structural_target: Decimal,
    premarket_high: Decimal | None = None,
) -> Resistance:
    """§3.1.1's *nearest overhead level above entry*, over the set §3.1.1 and §20.3 define.

    §3.1.1: *"let ``resistance`` be the nearest overhead level above entry among {HOD, next
    whole dollar, prior leg high, measured-move projection}."* §20.3 adds one from outside that
    enumeration: *"Premarket high is tracked separately as ``PMH`` and used as an additional
    resistance level in the room gate."* §20 governs, so ``PMH`` is in the set when supplied.

    **Two departures, both stated rather than silent.**

    *"Prior leg high"* is **omitted**, because *leg* and *leg height* are undefined in §20 and
    everywhere else. Inventing a definition would put a fabricated level into a gate §7 marks
    non-bypassable, which is worse than a gate that is missing one candidate — and the omission
    can only make the gate *more* permissive, which is the direction that must be visible.

    **HOD means the HOD established before the trigger bar.** §20.3 updates HOD *"on every
    completed bar"* and the trigger bar is completed, so the literal reading puts the trigger
    bar's own high in the set. Every breakout bar that closes below its high would then have
    overhead resistance a few ticks above entry, and §3.1.1 would reject every §3.2 and §3.3
    setup — a rule that rejects its own two flagship patterns unconditionally is not the rule.
    A level the trigger bar has already traded through is not overhead.

    Note what this function makes visible about §3.4's worked example: at entry $3.83 with HOD
    $4.15, the next whole dollar is $4.00 and is nearer. §3.4's table names HOD as *"nearest
    overhead resistance"* and computes a passing room test from it; §3.1.1's set as written
    rejects it. Raised in docs/CHANGELOG.md — not resolved here, and not smoothed over by
    dropping the whole-dollar candidate.
    """
    candidates: list[tuple[str, Decimal]] = [
        ("HOD", prior_hod),
        ("next whole dollar", whole_dollar_above(entry)),
        ("structural target", structural_target),
    ]
    if premarket_high is not None:
        candidates.append(("PMH", premarket_high))

    overhead = sorted(((n, lv) for n, lv in candidates if lv > entry), key=lambda c: c[1])
    if not overhead:
        # Unreachable: `whole_dollar_above` is strictly above entry by construction. Kept
        # because "unreachable" is a claim about today's candidate set, and a future one that
        # drops it should fail loudly rather than index into an empty list.
        raise ValueError(
            f"no overhead level above entry {entry}; the §3.1.1 candidate set has lost its "
            "whole-dollar term, which is the one that cannot be below entry"
        )
    source, level = overhead[0]
    return Resistance(level, source, tuple(overhead))


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _mean_volume(bars: Sequence[Bar]) -> Decimal:
    if not bars:
        raise ValueError("mean volume of an empty run is undefined")
    return Decimal(sum(b.volume for b in bars)) / Decimal(len(bars))


def _run_ending_before(
    session: Session, i: int, is_member: Callable[[int], bool]
) -> tuple[int, int] | None:
    """The maximal run of bars ending at ``i - 1`` whose every member satisfies ``is_member``.

    The one shape all three patterns share: a flag, a consolidation and a dip are each *the run
    of bars immediately before the trigger* that qualify. Written once so the three cannot
    disagree about what "immediately before" means, and it means index ``i - 1``: §20.1's gap
    rule is checked separately, on minutes, by
    :meth:`tradipy.session.Session.pattern_intact`.
    """
    end = i - 1
    if end < 0 or not is_member(end):
        return None
    start = end
    while start - 1 >= 0 and is_member(start - 1):
        start -= 1
    return start, end


def _flagpole_qualifies(
    pole: Sequence[Bar], baseline: Sequence[Bar], cfg: Config
) -> tuple[bool, str]:
    """PRD §3.2 criterion 2 — the predicate :func:`tradipy.bars.select_flagpole` asks for.

    *"Flagpole: >= 3 consecutive green 1-min candles with combined move >= 2% and total volume
    >= 2x average 1-min volume of prior 30 bars."*

    Two readings, both recorded in docs/CHANGELOG.md:

    * **The denominator of "combined move"** is unstated. Taken as ``flagpole_height /
      flagpole_low``, which reproduces §3.2's worked example (+7.29% = $0.35 / $4.80) exactly;
      neither the first candle's open nor the prior close does.
    * **"Total volume >= 2x average 1-min volume"** compares a sum against a per-bar mean, which
      any three-bar pole at ordinary volume satisfies — the criterion would be inert. Taken as
      the **per-bar** comparison, ``mean(pole) >= multiple x mean(prior bars)``, which is the
      stricter reading and the same shape as criterion 7 (*"breakout candle volume >= 2x average
      flag candle volume"*). This is a reading, not a correction: A13 shows §3.2's volume rows
      have needed one reversal already.

    A short baseline is a **refusal, not a pass.** If fewer than ``flagpole_vol_lookback_bars``
    bars precede the pole the criterion cannot be evaluated, and the alternative — comparing
    against whatever bars happen to exist — reports a verdict it did not earn.
    """
    min_candles = cfg["flagpole_min_candles"]
    min_move = cfg["flagpole_min_move_pct"]
    multiple = cfg["flagpole_vol_multiple"]
    lookback = int(cfg["flagpole_vol_lookback_bars"])

    if len(baseline) < lookback:
        return False, (
            f"volume baseline needs {lookback} prior bars, {len(baseline)} available — "
            "not evaluable"
        )

    height = flagpole_height(pole)
    move = height / pole[0].low
    pole_volume = _mean_volume(pole)
    baseline_volume = _mean_volume(baseline)
    required_volume = multiple * baseline_volume

    ok = Decimal(len(pole)) >= min_candles and move >= min_move and pole_volume >= required_volume
    return ok, (
        f"{len(pole)} green candle(s) vs {min_candles}, move {move:.4f} vs {min_move}, "
        f"mean volume {pole_volume:.0f} vs {required_volume:.0f} "
        f"({multiple} x {lookback}-bar mean {baseline_volume:.0f})"
    )


def _trigger_bar_eligible(session: Session, i: int) -> Criterion:
    """PRD §20.1 and §20.2: is bar ``i`` one a VWAP-dependent setup may fire on?

    §20.1 evaluates signals *"only on closed bars"*, which a :class:`~tradipy.session.Session`
    guarantees by construction — there is no representation of a partial bar. What is not
    structural is §20.2's other half: *"VWAP is undefined until the 09:30 bar closes; no
    VWAP-dependent setup can fire before 09:31."* All three MVP setups are VWAP-dependent, so
    all three refuse the session's opening minute — and every §20.3 quantity this layer uses is
    *prior* HOD, so a pattern needs a prior bar too.

    **The check is ``i > 0`` alone, not ``minute > 0 and i > 0``.** A ``minute > 0`` conjunct
    looks like it does independent work — a session whose first available bar is minute 3 (no
    trades in the first three minutes) has a legal trigger minute at index 0 and still no pattern
    behind it — but :class:`~tradipy.session.Session` already guarantees minutes are strictly
    increasing, non-negative integers, so ``session.minute(i) >= i`` for every valid ``i``:
    ``minute > 0`` is true whenever ``i > 0`` and the conjunction can never differ from ``i > 0``
    alone. The example above is the reason ``i > 0`` is required, not a reason ``minute > 0`` is
    also required. (Round 13, M3: an earlier version of this function carried the redundant
    conjunct; removing it changes no test outcome.)
    """
    return Criterion(
        "Bar timing (§20.1, §20.2)",
        Reject.SETUP_NOT_PRESENT,
        i > 0,
        f"trigger at session minute {session.minute(i)}, bar index {i}: VWAP-dependent setups "
        "cannot fire in the opening minute, and a pattern needs a prior bar",
    )


def _gate_criteria(
    *,
    entry: Decimal,
    stop: Decimal,
    stop_reject: Reject | None,
    r: Decimal,
    spread: Decimal,
    ladder: Ladder,
    room: RoomRequirement,
    separation: Decimal,
    resistance: Resistance,
    cfg: Config,
) -> list[Criterion]:
    """The §3.1 gates every setup shares, evaluated together and reported together.

    Order is §3.x's own: stop construction (§2, §20.13), then the spread gate (§3.1.3), then the
    room gate and separation floor (§3.1.2), then §3.1.1's ordering constraint. Each verdict
    comes from the function in :mod:`tradipy.gates` that owns it — this assembles, it does not
    re-derive. The one comparison made here is the ladder's, and only because
    :class:`~tradipy.gates.Ladder` owns it as a method.

    **§3.1.1's ordering constraint is checked rather than assumed, and it does currently hold.**
    §3.1.1 says ``entry < T1 < T2`` is *"guaranteed by the pre-entry room gate below rather than
    checked afterwards"*, and the reason it is guaranteed is a step §3.1.1 does not spell out: the
    measured-move projection is one of its own resistance candidates, so ``resistance <=
    structural_target`` and the room gate's ``resistance - entry >= t1_r_multiple × R +
    min_separation`` forces T2 above T1. Each setup satisfies the premise differently — §3.2's T2
    *is* the projection, §3.4's is the HOD that criterion 6 puts above entry, and §3.3's is the
    whole dollar above **T1**, which is above T1 by construction and is *not* always the
    whole-dollar candidate §3.1.1 measures from entry.

    So the check below is unreachable through the three MVP evaluators today, and it is retained
    because the premise is a property of the *candidate set* rather than of the gate: a fourth
    setup whose structural target is not among §3.1.1's candidates would lose the guarantee with
    nothing to notice. ``tests/test_enforcement.py`` asserts both halves — that the implication
    holds for every accepted setup, and that the check fires when handed a ladder that violates it.
    """
    room_verdict = check_room(entry, resistance.level, r, spread, cfg)
    caps = spread_caps(entry, r, cfg)
    gap = resistance.level - entry
    return [
        Criterion(
            "Stop construction (§2, §20.13)",
            Reject.STOP_TOO_WIDE,
            stop_reject is None,
            f"stop {stop}, distance {entry - stop} vs floor {cfg['min_stop_distance']} and "
            f"ceiling {cfg['max_stop_pct'] * entry} ({cfg['max_stop_pct']} x {entry})",
        ),
        Criterion(
            "Spread gate (§3.1.3, §20.14)",
            Reject.SPREAD_TOO_WIDE,
            check_spread(spread, entry, r, cfg) is None,
            f"spread {spread} vs binding cap {caps.binding} "
            f"(scan {caps.scan}, signal {caps.signal})",
        ),
        Criterion(
            # `room.binding` on both branches, not just the failing one — round 13, M4:
            # `room_verdict`, whenever it is a `Reject`, is `check_room`'s own `req.binding` for
            # `req = required_room(r, spread, cfg)`, the identical pure call the caller already
            # made to produce `room` above. A ternary reading the two apart implied they could
            # disagree; they cannot, so this is the one value rather than a choice between two.
            "Room gate (§3.1.2 unified)",
            room.binding,
            room_verdict is None,
            f"{resistance.source} at {resistance.level}, gap {gap} vs required "
            f"{room.required} (proportional {room.proportional_term}, separation "
            f"{room.separation_term})",
        ),
        Criterion(
            "Separation floor (§3.1.2)",
            Reject.TARGETS_TOO_CLOSE,
            (ladder.t2 - ladder.t1) >= separation,
            f"T2 - T1 = {ladder.t2 - ladder.t1} vs floor {separation}",
        ),
        Criterion(
            "Target ordering (§3.1.1)",
            Reject.TARGETS_TOO_CLOSE,
            ladder.ordered_above(entry),
            f"entry {entry} < T1 {ladder.t1} < T2 {ladder.t2}",
        ),
    ]


def _assemble(
    *,
    symbol: str,
    setup_type: SetupType,
    criteria: list[Criterion],
    entry: Decimal,
    stop: Decimal,
    pattern_stop: Decimal,
    r: Decimal,
    ladder: Ladder,
    resistance: Resistance,
    room: RoomRequirement,
    separation: Decimal,
    spread: Decimal,
    breakout_high: Decimal,
    prior_hod: Decimal,
    cfg: Config,
    buying_power: Decimal | None,
    adv_shares: Decimal | None,
) -> SetupOutcome:
    """Build the outcome, sizing only if every criterion passed.

    Sizing is withheld from a rejected setup for the reason
    :class:`tradipy.scanner.ScanResult` withholds the composite score from a rejected candidate:
    the rejection is the answer, and a share count sitting on it is an invitation to use it.
    :func:`tradipy.gates.position_size` would also *raise* on a stop the §20.13 ceiling rejects,
    which is the behaviour that closed F-round finding — so calling it here unconditionally
    would turn a reportable rejection into an exception.
    """
    levels = Levels(
        entry_price=entry,
        pattern_stop=pattern_stop,
        stop_price=stop,
        r_per_share=r,
        ladder=ladder,
        resistance=resistance,
        room=room,
        min_separation=separation,
        spread_at_signal=spread,
        breakout_high=breakout_high,
        prior_hod=prior_hod,
    )
    outcome = SetupOutcome(symbol, setup_type, tuple(criteria), levels)
    if outcome.failures:
        return outcome
    shares = position_size(entry, stop, cfg, buying_power=buying_power, adv_shares=adv_shares)
    return SetupOutcome(
        symbol,
        setup_type,
        tuple(criteria),
        levels,
        SetupSignal(symbol=symbol, setup_type=setup_type, levels=levels, shares=shares),
    )


# ---------------------------------------------------------------------------
# §3.2 Bull Flag
# ---------------------------------------------------------------------------
def evaluate_bull_flag(
    symbol: str,
    session: Session,
    i: int,
    spread: Decimal,
    cfg: Config,
    *,
    premarket_high: Decimal | None = None,
    buying_power: Decimal | None = None,
    adv_shares: Decimal | None = None,
) -> SetupOutcome:
    """PRD §3.2 at bar ``i``, which is the candidate breakout bar.

    Criterion 1 (*"stock passes scanner hard filters"*) is :mod:`tradipy.scanner`'s and is not
    re-evaluated here: §4.1 runs over a universe and this runs over a symbol's bars. A caller
    that skips the scanner has skipped §3.2 criterion 1, and no arrangement of this signature
    prevents that — stated because a criterion silently absent is worse than one delegated.

    **The flag is the maximal run of not-green bars immediately before the trigger.** §3.2
    criterion 3 says *"2-5 red/consolidation candles"*, and a consolidation candle may close up
    — but §20.4 terminates the flagpole at *"the longest run of consecutive green candles ending
    immediately before the flag"*, so a flag that admits green bars needs the flagpole to locate
    its own start while §20.4 needs the flag's start to locate the flagpole. The not-green
    reading is what breaks that circle. Raised in docs/CHANGELOG.md.

    Criterion 4 is read as *"remains"* states it: each flag bar's **low** against VWAP as of
    **that** bar, not one VWAP value at the trigger. It is the same test as the invalidation
    rule *"price breaks below VWAP during flag formation"*, and it is wick-based because §3.2
    says *low*.
    """
    criteria: list[Criterion] = [_trigger_bar_eligible(session, i)]
    if not criteria[0].passed:
        return SetupOutcome(symbol, SetupType.BULL_FLAG, tuple(criteria))

    plain = session.ohlcv()
    trigger = session.bar(i)
    absent = Reject.SETUP_NOT_PRESENT

    flag_span = _run_ending_before(session, i, lambda k: not plain[k].is_green)
    flag_low_bound = cfg["flag_min_candles"]
    flag_high_bound = cfg["flag_max_candles"]
    if flag_span is None:
        criteria.append(
            Criterion(
                "Flag (§3.2 crit 3)",
                absent,
                False,
                f"bar {i - 1} is green, so no flag ends immediately before the trigger "
                f"(need {flag_low_bound}-{flag_high_bound} not-green candles)",
            )
        )
        return SetupOutcome(symbol, SetupType.BULL_FLAG, tuple(criteria))

    flag_start, flag_end = flag_span
    flag = plain[flag_start : flag_end + 1]
    flag_count = Decimal(len(flag))

    pole_span = flagpole_ending_at(plain, flag_start - 1)
    if pole_span is None:
        criteria.append(
            Criterion(
                "Flagpole (§3.2 crit 2, §20.4)",
                absent,
                False,
                f"no green run ends at bar {flag_start - 1}, so §20.4 has no flagpole",
            )
        )
        return SetupOutcome(symbol, SetupType.BULL_FLAG, tuple(criteria))

    pole_start, pole_end = pole_span
    pole = plain[pole_start : pole_end + 1]
    lookback = int(cfg["flagpole_vol_lookback_bars"])
    baseline = plain[max(0, pole_start - lookback) : pole_start]

    # §20.4's qualification predicate, supplied to `select_flagpole` exactly as `bars.py` asks:
    # the three thresholds it refused to invent are now registry rows, and this is their reader.
    _, pole_detail = _flagpole_qualifies(pole, baseline, cfg)
    chosen = select_flagpole(
        plain, [pole_span], lambda run: _flagpole_qualifies(run, baseline, cfg)[0]
    )
    criteria.append(
        Criterion("Flagpole (§3.2 crit 2, §20.4)", absent, chosen is not None, pole_detail)
    )
    if chosen is None:
        # Not `chosen is None or not qualified` — round 13, M5: `select_flagpole` is given the
        # single candidate `pole_span` with the identical qualifying predicate just evaluated
        # above, so `chosen is None` and `not qualified` are the same fact read twice.
        return SetupOutcome(symbol, SetupType.BULL_FLAG, tuple(criteria))

    height = flagpole_height(pole)
    pole_high = pole[-1].high
    flag_high = max(b.high for b in flag)
    flag_low = min(b.low for b in flag)
    retrace = retrace_pct(pole_high, flag_low, height)
    vwap = session.vwap_at(i)
    entry = trigger.close

    breaches = [k for k in range(flag_start, flag_end + 1) if plain[k].low <= session.vwap_at(k)]
    flag_volume = _mean_volume(flag)
    pole_volume = _mean_volume(pole)
    volume_ratio = flag_volume / pole_volume
    breakout_required = cfg["breakout_vol_multiple"] * flag_volume

    criteria.extend(
        [
            Criterion(
                "Flag (§3.2 crit 3)",
                absent,
                flag_low_bound <= flag_count <= flag_high_bound
                and retrace <= cfg["max_flag_retrace_pct"],
                f"{len(flag)} candle(s) vs [{flag_low_bound}, {flag_high_bound}], retrace "
                f"{retrace:.4f} vs {cfg['max_flag_retrace_pct']} "
                f"(({pole_high} - {flag_low}) / {height})",
            ),
            Criterion(
                "Flag low above VWAP (§3.2 crit 4, §20.2)",
                absent,
                not breaches,
                f"flag low {flag_low} vs VWAP per bar; {len(breaches)} bar(s) at or below "
                f"(VWAP at trigger {vwap:.4f})",
            ),
            Criterion(
                "Flag volume contraction (§3.2 crit 5, A13)",
                absent,
                volume_ratio <= cfg["max_flag_volume_ratio"],
                f"flag/flagpole mean volume {volume_ratio:.4f} vs "
                f"{cfg['max_flag_volume_ratio']} ({flag_volume:.0f} / {pole_volume:.0f})",
            ),
            Criterion(
                "Trigger closes above flag high (§3.2 crit 6)",
                absent,
                entry > flag_high,
                f"close {entry} vs flag high {flag_high}",
            ),
            Criterion(
                "Breakout volume (§3.2 crit 7)",
                absent,
                Decimal(trigger.volume) >= breakout_required,
                f"volume {trigger.volume} vs {breakout_required:.0f} "
                f"({cfg['breakout_vol_multiple']} x flag mean {flag_volume:.0f})",
            ),
            Criterion(
                "Pattern not broken by a gap (§20.1)",
                absent,
                session.pattern_intact(pole_start, i, cfg),
                f"bars {pole_start}..{i} span minutes {session.minute(pole_start)}.."
                f"{session.minute(i)} vs max gap {cfg['max_pattern_gap_minutes']}",
            ),
        ]
    )
    if any(not c.passed for c in criteria):
        return SetupOutcome(symbol, SetupType.BULL_FLAG, tuple(criteria))

    # §3.2: hard stop at the flag low, minus one tick. **No VWAP branch**: criterion 4 puts the
    # flag low above VWAP, so §20.6's tighter() could never select the VWAP level — which is
    # true at the signal bar and is the whole of §3.2's claim. The post-entry VWAP invalidation
    # stays armed regardless; see `bull_flag_exit`.
    pattern_stop = flag_low - TICK_SIZE
    stop, stop_reject = apply_stop_floor_and_ceiling(entry, pattern_stop, cfg)
    r = entry - stop
    structural = measured_move(entry, height)
    prior_hod = session.hod_through(i - 1)
    resistance = nearest_resistance(
        entry,
        prior_hod=prior_hod,
        structural_target=structural,
        premarket_high=premarket_high,
    )
    ladder = exit_ladder(entry, r, structural, cfg)
    room = required_room(r, spread, cfg)
    separation = min_separation(r, spread, cfg)

    criteria.extend(
        _gate_criteria(
            entry=entry,
            stop=stop,
            stop_reject=stop_reject,
            r=r,
            spread=spread,
            ladder=ladder,
            room=room,
            separation=separation,
            resistance=resistance,
            cfg=cfg,
        )
    )
    return _assemble(
        symbol=symbol,
        setup_type=SetupType.BULL_FLAG,
        criteria=criteria,
        entry=entry,
        stop=stop,
        pattern_stop=pattern_stop,
        r=r,
        ladder=ladder,
        resistance=resistance,
        room=room,
        separation=separation,
        spread=spread,
        breakout_high=trigger.high,
        prior_hod=prior_hod,
        cfg=cfg,
        buying_power=buying_power,
        adv_shares=adv_shares,
    )


# ---------------------------------------------------------------------------
# §3.3 High-of-Day Breakout
# ---------------------------------------------------------------------------
def evaluate_hod_breakout(
    symbol: str,
    session: Session,
    i: int,
    spread: Decimal,
    cfg: Config,
    *,
    premarket_high: Decimal | None = None,
    buying_power: Decimal | None = None,
    adv_shares: Decimal | None = None,
) -> SetupOutcome:
    """PRD §3.3 at bar ``i``, the candidate breakout bar.

    **A consolidation bar is one that set no new high and held above VWAP.** §3.3 criterion 3
    says *">= 2 candles where high <= prior HOD and low >= VWAP"*, which is circular as stated:
    the run's extent depends on *prior HOD* and *prior HOD* depends on where the run starts. Read
    per bar — ``high <= hod_through(k-1)`` and ``low >= vwap_at(k)`` — the circle closes, and it
    closes on the same number either way: no bar in the run made a new high, so the HOD as of the
    bar before the trigger equals the HOD as of the bar before the run. Raised in
    docs/CHANGELOG.md.

    The stop is §20.6 twice over: :func:`~tradipy.session.wider` selects the lower of the
    consolidation low and the breakout bar's low, per §3.3, and :func:`~tradipy.session.tighter`
    then applies A14's ``max()`` against ``VWAP - 1 tick``. A14's note observes that the second
    is inert while criterion 3 holds, and that is exactly right at the signal bar — it binds only
    when the *breakout* bar's low is the lower candidate and sits below VWAP, a case A14 does not
    mention. Applied as A14 states it, with the observation raised rather than acted on.
    """
    criteria: list[Criterion] = [_trigger_bar_eligible(session, i)]
    if not criteria[0].passed:
        return SetupOutcome(symbol, SetupType.HOD_BREAKOUT, tuple(criteria))

    plain = session.ohlcv()
    trigger = session.bar(i)
    absent = Reject.SETUP_NOT_PRESENT
    prior_hod = session.hod_through(i - 1)
    vwap = session.vwap_at(i)
    entry = trigger.close

    def is_consolidation(k: int) -> bool:
        if k == 0:
            return False  # the opening bar sets the first high; it cannot be "below prior HOD"
        return plain[k].high <= session.hod_through(k - 1) and plain[k].low >= session.vwap_at(k)

    span = _run_ending_before(session, i, is_consolidation)
    min_candles = cfg["consolidation_min_candles"]
    criteria.append(
        Criterion(
            "Prior HOD established (§3.3 crit 2, §20.3)",
            absent,
            session.hod_established_by(i - 1),
            f"prior HOD {prior_hod}; a bar after the session's first must have set a higher "
            "high for the HOD to be tradeable",
        )
    )
    if span is None:
        criteria.append(
            Criterion(
                "Consolidation (§3.3 crit 3)",
                absent,
                False,
                f"bar {i - 1} set a new high or closed its low below VWAP, so no "
                f"consolidation run of >= {min_candles} candle(s) ends before the trigger",
            )
        )
        return SetupOutcome(symbol, SetupType.HOD_BREAKOUT, tuple(criteria))

    start, end = span
    consolidation = plain[start : end + 1]
    consolidation_low = min(b.low for b in consolidation)
    consolidation_volume = _mean_volume(consolidation)
    required_volume = cfg["hod_breakout_vol_multiple"] * consolidation_volume
    extension = entry / vwap - Decimal(1)

    criteria.extend(
        [
            Criterion(
                "Consolidation (§3.3 crit 3)",
                absent,
                Decimal(len(consolidation)) >= min_candles,
                f"{len(consolidation)} candle(s) vs {min_candles}, low {consolidation_low}, "
                f"high {max(b.high for b in consolidation)} vs prior HOD {prior_hod}",
            ),
            Criterion(
                "Trigger closes above prior HOD (§3.3 crit 4, §20.3)",
                absent,
                entry > prior_hod,
                f"close {entry} vs prior HOD {prior_hod} (close-based, not wick)",
            ),
            Criterion(
                "Breakout volume (§3.3 crit 5)",
                absent,
                Decimal(trigger.volume) >= required_volume,
                f"volume {trigger.volume} vs {required_volume:.0f} "
                f"({cfg['hod_breakout_vol_multiple']} x consolidation mean "
                f"{consolidation_volume:.0f})",
            ),
            Criterion(
                "VWAP extension (§3.3 crit 6, §2)",
                absent,
                extension <= cfg["max_vwap_extension_pct"],
                f"extension {extension:.4f} vs {cfg['max_vwap_extension_pct']} "
                f"({entry} / {vwap:.4f} - 1)",
            ),
            Criterion(
                "Pattern not broken by a gap (§20.1)",
                absent,
                session.pattern_intact(start, i, cfg),
                f"bars {start}..{i} span minutes {session.minute(start)}.."
                f"{session.minute(i)} vs max gap {cfg['max_pattern_gap_minutes']}",
            ),
        ]
    )
    if any(not c.passed for c in criteria):
        return SetupOutcome(symbol, SetupType.HOD_BREAKOUT, tuple(criteria))

    pattern_stop = wider(consolidation_low, trigger.low) - TICK_SIZE
    # A14: size against whichever level triggers first. `floor_to_tick` before the subtraction
    # for the same reason `gates.vwap_reclaim_stop` does it — the band must be a whole tick
    # before it is compared, and §20.13 puts the rounding at level computation.
    vwap_stop = floor_to_tick(vwap) - TICK_SIZE
    stop, stop_reject = apply_stop_floor_and_ceiling(entry, tighter(pattern_stop, vwap_stop), cfg)
    r = entry - stop
    # §3.3 T2: "next whole-dollar level above T1, or prior leg extension (1x leg height),
    # whichever is nearer and above T1". Only the whole-dollar branch is implementable: *leg
    # height* is undefined in §20 and everywhere else, and §3.3's own worked example uses the
    # whole dollar. The omission can only make T2 further away, never nearer — stated because
    # that is the direction a reader needs to know, and raised in docs/CHANGELOG.md.
    structural = whole_dollar_above(t1_level(entry, r, cfg))
    resistance = nearest_resistance(
        entry,
        prior_hod=prior_hod,
        structural_target=structural,
        premarket_high=premarket_high,
    )
    ladder = exit_ladder(entry, r, structural, cfg)
    room = required_room(r, spread, cfg)
    separation = min_separation(r, spread, cfg)

    criteria.extend(
        _gate_criteria(
            entry=entry,
            stop=stop,
            stop_reject=stop_reject,
            r=r,
            spread=spread,
            ladder=ladder,
            room=room,
            separation=separation,
            resistance=resistance,
            cfg=cfg,
        )
    )
    return _assemble(
        symbol=symbol,
        setup_type=SetupType.HOD_BREAKOUT,
        criteria=criteria,
        entry=entry,
        stop=stop,
        pattern_stop=pattern_stop,
        r=r,
        ladder=ladder,
        resistance=resistance,
        room=room,
        separation=separation,
        spread=spread,
        breakout_high=trigger.high,
        prior_hod=prior_hod,
        cfg=cfg,
        buying_power=buying_power,
        adv_shares=adv_shares,
    )


# ---------------------------------------------------------------------------
# §3.4 VWAP Reclaim
# ---------------------------------------------------------------------------
def evaluate_vwap_reclaim(
    symbol: str,
    session: Session,
    i: int,
    spread: Decimal,
    cfg: Config,
    *,
    premarket_high: Decimal | None = None,
    buying_power: Decimal | None = None,
    adv_shares: Decimal | None = None,
) -> SetupOutcome:
    """PRD §3.4 at bar ``i``, the candidate reclaim bar.

    **The dip is close-based.** §3.4 criterion 3 counts *"consecutive candles below VWAP"* and
    criterion 4 triggers on a candle that *"closes above VWAP"*. A reclaim defined by closes has
    to have a dip defined by closes, or the two tests disagree about the same bar. Depth is
    measured against VWAP as of the bar that set the dip low, matching the per-bar reading; the
    worked example has one VWAP value and cannot distinguish them.

    **"Still below HOD" means below the prior HOD.** Criterion 6's alternative — HOD including the
    trigger bar's own high — lets a reclaim bar satisfy the criterion with its own wick.

    The stop is :func:`tradipy.gates.vwap_reclaim_stop`, which is §20.13's own worked reference
    and returns the ceiling verdict as well as the level.
    """
    criteria: list[Criterion] = [_trigger_bar_eligible(session, i)]
    if not criteria[0].passed:
        return SetupOutcome(symbol, SetupType.VWAP_RECLAIM, tuple(criteria))

    plain = session.ohlcv()
    trigger = session.bar(i)
    absent = Reject.SETUP_NOT_PRESENT
    vwap = session.vwap_at(i)
    entry = trigger.close
    prior_hod = session.hod_through(i - 1)

    dip_span = _run_ending_before(session, i, lambda k: plain[k].close < session.vwap_at(k))
    max_candles = cfg["max_dip_candles"]
    if dip_span is None:
        criteria.append(
            Criterion(
                "Dip below VWAP (§3.4 crit 3)",
                absent,
                False,
                f"bar {i - 1} did not close below its VWAP, so there is no dip to reclaim",
            )
        )
        return SetupOutcome(symbol, SetupType.VWAP_RECLAIM, tuple(criteria))

    dip_start, dip_end = dip_span
    dip = plain[dip_start : dip_end + 1]
    dip_low = min(b.low for b in dip)
    low_index = next(k for k in range(dip_start, dip_end + 1) if plain[k].low == dip_low)
    vwap_at_low = session.vwap_at(low_index)
    depth = (vwap_at_low - dip_low) / vwap_at_low
    dip_volume = _mean_volume(dip)
    required_volume = cfg["reclaim_vol_multiple"] * dip_volume

    above = _run_ending_before(session, dip_start, lambda k: plain[k].close > session.vwap_at(k))
    bars_above = Decimal(above[1] - above[0] + 1) if above is not None else Decimal(0)

    # §3.4 crit 9: within `hod_proximity_pct` of HOD, require `hod_proximity_min_candles` since
    # the dip low with high <= HOD. Measured against HOD, not entry — §2's row is "Max Extension
    # **from** HOD", and an extension is measured from the level it is named for.
    proximity = (prior_hod - entry) / prior_hod
    near_hod = proximity <= cfg["hod_proximity_pct"]
    since_low = [k for k in range(low_index + 1, i + 1) if plain[k].high <= prior_hod]
    proximity_ok = not near_hod or Decimal(len(since_low)) >= cfg["hod_proximity_min_candles"]

    criteria.extend(
        [
            Criterion(
                "Above VWAP before the dip (§3.4 crit 2, §20.1)",
                absent,
                bars_above >= cfg["min_bars_above_vwap"],
                f"{bars_above} bar(s) closing above VWAP immediately before the dip vs "
                f"{cfg['min_bars_above_vwap']} (§3.4 states minutes; §20.1 counts bars)",
            ),
            Criterion(
                "Dip below VWAP (§3.4 crit 3)",
                absent,
                Decimal(len(dip)) <= max_candles and depth <= cfg["max_dip_depth_pct"],
                f"{len(dip)} candle(s) vs {max_candles}, depth {depth:.4f} vs "
                f"{cfg['max_dip_depth_pct']} (({vwap_at_low:.4f} - {dip_low}) / "
                f"{vwap_at_low:.4f})",
            ),
            Criterion(
                "Trigger closes above VWAP (§3.4 crit 4, §20.2)",
                absent,
                entry > vwap,
                f"close {entry} vs VWAP {vwap:.4f}",
            ),
            Criterion(
                "Reclaim volume (§3.4 crit 5)",
                absent,
                Decimal(trigger.volume) >= required_volume,
                f"volume {trigger.volume} vs {required_volume:.0f} "
                f"({cfg['reclaim_vol_multiple']} x dip mean {dip_volume:.0f})",
            ),
            Criterion(
                "Still below HOD (§3.4 crit 6, §20.3)",
                absent,
                entry < prior_hod,
                f"entry {entry} vs prior HOD {prior_hod}",
            ),
            Criterion(
                "HOD proximity consolidation (§3.4 crit 9, §2)",
                absent,
                proximity_ok,
                f"proximity {proximity:.4f} vs {cfg['hod_proximity_pct']}; "
                f"{len(since_low)} bar(s) since the dip low with high <= {prior_hod} vs "
                f"{cfg['hod_proximity_min_candles']} required when near",
            ),
            Criterion(
                "Pattern not broken by a gap (§20.1)",
                absent,
                session.pattern_intact(dip_start, i, cfg),
                f"bars {dip_start}..{i} span minutes {session.minute(dip_start)}.."
                f"{session.minute(i)} vs max gap {cfg['max_pattern_gap_minutes']}",
            ),
        ]
    )
    if any(not c.passed for c in criteria):
        return SetupOutcome(symbol, SetupType.VWAP_RECLAIM, tuple(criteria))

    stop, stop_reject = vwap_reclaim_stop(entry, dip_low, vwap, cfg)
    r = entry - stop
    # §3.4 T2: the HOD retest. §3.4 calls it "guaranteed above T1 by the room gate", which is
    # the conditional guarantee `_gate_criteria` checks rather than assumes.
    structural = prior_hod
    resistance = nearest_resistance(
        entry,
        prior_hod=prior_hod,
        structural_target=structural,
        premarket_high=premarket_high,
    )
    ladder = exit_ladder(entry, r, structural, cfg)
    room = required_room(r, spread, cfg)
    separation = min_separation(r, spread, cfg)

    criteria.extend(
        _gate_criteria(
            entry=entry,
            stop=stop,
            stop_reject=stop_reject,
            r=r,
            spread=spread,
            ladder=ladder,
            room=room,
            separation=separation,
            resistance=resistance,
            cfg=cfg,
        )
    )
    return _assemble(
        symbol=symbol,
        setup_type=SetupType.VWAP_RECLAIM,
        criteria=criteria,
        entry=entry,
        stop=stop,
        pattern_stop=dip_low - TICK_SIZE,
        r=r,
        ladder=ladder,
        resistance=resistance,
        room=room,
        separation=separation,
        spread=spread,
        breakout_high=trigger.high,
        prior_hod=prior_hod,
        cfg=cfg,
        buying_power=buying_power,
        adv_shares=adv_shares,
    )


#: The three evaluators, keyed by setup. Iteration order is §20.11's priority order, inherited
#: from :class:`SetupType` rather than restated — a second ordering is the v1.2 defect class.
EVALUATORS: dict[SetupType, Callable[..., SetupOutcome]] = {
    SetupType.BULL_FLAG: evaluate_bull_flag,
    SetupType.HOD_BREAKOUT: evaluate_hod_breakout,
    SetupType.VWAP_RECLAIM: evaluate_vwap_reclaim,
}


def evaluate_all(
    symbol: str,
    session: Session,
    i: int,
    spread: Decimal,
    cfg: Config,
    **kwargs: Decimal | None,
) -> tuple[SetupOutcome, ...]:
    """Every setup's outcome at bar ``i``, in §20.11 priority order.

    All three are evaluated, including after one accepts: §20.11 exists because *"a bull-flag
    breakout is frequently also a HOD breakout"*, and rule 3 requires the losers be recorded
    with the winner's id. A pipeline that stopped at the first acceptance would have nothing to
    record.
    """
    return tuple(
        EVALUATORS[setup](symbol, session, i, spread, cfg, **kwargs) for setup in SetupType
    )


def arbitrate(
    outcomes: Iterable[SetupOutcome],
) -> tuple[SetupSignal | None, tuple[SetupOutcome, ...]]:
    """PRD §20.11 rules 1 and 2: one signal per symbol, highest-priority setup wins.

    Returns the winner and every superseded *accepted* outcome, so rule 3 — *"losing signals are
    recorded with status ``SUPERSEDED`` and the winning ``signal_id`` referenced"* — is possible
    for a caller that has somewhere to write them. Writing them is not this layer's: `signals`
    is a table (§10.1) and a `signal_id` needs an ID generator.

    Rule 4 — *"while a position is open in a symbol, further signals are ``SUPERSEDED``, except
    an explicit scale-in add permitted under §7.1.1"* — is **not** here, because it is a
    predicate over open positions and this layer has none. Named because rule 4 sits in the same
    numbered list and its absence would otherwise look like an oversight.

    Raises if handed outcomes for more than one symbol: rule 1 deduplicates *by symbol*, and
    silently arbitrating across two of them would suppress a signal §20.11 never asked to
    suppress.
    """
    accepted = [o for o in outcomes if o.accepted and o.signal is not None]
    if not accepted:
        return None, ()
    symbols = {o.symbol for o in accepted}
    if len(symbols) > 1:
        raise ValueError(
            f"arbitrate() is per-symbol (PRD §20.11 rule 1) but was given {sorted(symbols)}"
        )
    ranked = sorted(accepted, key=lambda o: o.setup_type.priority)
    winner = ranked[0].signal
    return winner, tuple(ranked[1:])


# ---------------------------------------------------------------------------
# §3 post-entry rules (predicates — the state they run in is Phase 5/6's)
# ---------------------------------------------------------------------------
def _closed_below_vwap(session: Session, after: Sequence[int]) -> int | None:
    """The first index in ``after`` whose close is below its own VWAP, or ``None``."""
    return next((k for k in after if session.bar(k).close < session.vwap_at(k)), None)


def bull_flag_exit(
    session: Session, signal: SetupSignal, after: Sequence[int], cfg: Config
) -> ExitReason | None:
    """PRD §3.2's post-entry rules over the bars after entry, by index.

    Two rules, in the order §3.2 lists them:

    * **Invalidation** — *"close below VWAP after entry -> exit immediately."* Checked first
      because it can fire on the very next bar, while the bailout cannot fire before the timer
      expires.
    * **Breakout or bailout** — *"exit full position if, within 3 candles (3 min) of entry,
      price has not closed above the entry price **and** has not made a new high above the
      breakout candle high."* A **conjunction**: one of the two suffices to stay in. §3.3 states
      only the second half and §3.4 states no bailout at all, which is raised in
      docs/CHANGELOG.md as one rule with three spellings rather than unified here.

    *"3 candles (3 min)"* is read as three **available bars**, per §20.1's *"pattern counts count
    available bars, not wall-clock minutes"* — the parenthetical equates them and §20 governs.
    Returns ``None`` while fewer than ``bailout_candles`` bars have closed: undecided is not the
    same as passed.
    """
    invalidated = _closed_below_vwap(session, after)
    if invalidated is not None:
        return ExitReason.INVALIDATED
    window = int(cfg["bailout_candles"])
    if len(after) < window:
        return None
    bars = [session.bar(k) for k in after[:window]]
    moved = any(b.close > signal.levels.entry_price for b in bars) or any(
        b.high > signal.levels.breakout_high for b in bars
    )
    return None if moved else ExitReason.BAILED_OUT


def hod_breakout_exit(
    session: Session, signal: SetupSignal, after: Sequence[int], cfg: Config
) -> ExitReason | None:
    """PRD §3.3's post-entry rules: two invalidations, then the bailout.

    * *"Close back below prior HOD within 2 candles of breakout"* —
      ``hod_reclaim_invalidation_candles``, and only within that window: a close below the old
      HOD on the tenth bar is not this rule.
    * *"Close below VWAP."*
    * *"3 candles after entry with no new high above the breakout candle high -> exit."* One
      condition, where §3.2 states two.
    """
    window = int(cfg["hod_reclaim_invalidation_candles"])
    if any(session.bar(k).close < signal.levels.prior_hod for k in after[:window]):
        return ExitReason.INVALIDATED
    if _closed_below_vwap(session, after) is not None:
        return ExitReason.INVALIDATED
    window = int(cfg["bailout_candles"])
    if len(after) < window:
        return None
    made_high = any(session.bar(k).high > signal.levels.breakout_high for k in after[:window])
    return None if made_high else ExitReason.BAILED_OUT


def vwap_reclaim_exit(
    session: Session, _signal: SetupSignal, after: Sequence[int], _cfg: Config
) -> ExitReason | None:
    """PRD §3.4's post-entry rule, which is one rule: *"close back below VWAP -> exit remainder."*

    **§3.4 states no breakout-or-bailout rule**, and none is applied. The signature keeps the
    other two's shape so a caller can dispatch on setup type without special-casing, and the
    unused parameters are named with a leading underscore rather than dropped — a signature that
    silently differs is how a caller comes to believe the timer is running.
    """
    return ExitReason.INVALIDATED if _closed_below_vwap(session, after) is not None else None
