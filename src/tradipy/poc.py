"""Proof-of-concept composition: run one candidate through every Phase 1 gate.

**This is not the strategy engine.** It takes a candidate that has already been found —
entry, stop level, structural target, nearest resistance and an NBBO quote — and applies the
gates in the order PRD §3.1 states them. Finding candidates needs a scanner, a feed and bar
ingestion, none of which exist at this layer and all of which PRD §12.1 scopes to later
phases.

What it is for: making the invariant layer *runnable*, so the rules can be exercised against
arbitrary inputs rather than only against the fixtures. ``python -m tradipy`` is the front
end. The §3.2 fixture in :func:`worked_examples` derives its stop, flag high, flagpole height
and T2 from a bar series via §20.4, which is what PRD §21.1 asks worked-example fixtures to
do; §3.3 and §3.4 take scalars because the PRD states no bar series for them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from tradipy.bars import Bar, flagpole_ending_at, flagpole_height, measured_move, retrace_pct
from tradipy.gates import (
    Ladder,
    apply_stop_floor_and_ceiling,
    check_room,
    check_spread,
    exit_ladder,
    min_separation,
    position_size,
    required_room,
    spread_caps,
)
from tradipy.params import Config
from tradipy.quotes import Quote, spread_at_signal
from tradipy.rejects import Reject
from tradipy.rounding import TICK_SIZE

__all__ = ["Candidate", "GateResult", "Evaluation", "evaluate", "worked_examples"]

D = Decimal


@dataclass(frozen=True)
class Candidate:
    """A formed setup awaiting the pre-entry gates."""

    entry: Decimal
    raw_stop: Decimal
    structural_target: Decimal
    resistance: Decimal
    quote: Quote
    label: str = "candidate"
    section: str = ""
    #: Only for the demo's self-check: values transcribed from the PRD tables. Nothing in
    #: :func:`evaluate` reads these — every number it reports is derived.
    expect: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    """One gate's verdict, with the arithmetic that produced it."""

    gate: str
    section: str
    passed: bool
    detail: str
    reject: Reject | None = None


@dataclass(frozen=True)
class Evaluation:
    candidate: Candidate
    results: list[GateResult]
    spread: Decimal | None = None
    stop: Decimal | None = None
    r: Decimal | None = None
    ladder: Ladder | None = None
    shares: int | None = None

    @property
    def reject(self) -> Reject | None:
        """The first gate to fail, in §3.1 evaluation order."""
        return next((g.reject for g in self.results if not g.passed), None)

    @property
    def accepted(self) -> bool:
        return self.reject is None


def evaluate(candidate: Candidate, cfg: Config) -> Evaluation:
    """Run the full Phase 1 gate chain and report every gate, not only the first failure.

    Order follows PRD §3.1: the quote defines the spread (§20.14), the spread and the stop
    define R, and R is the denominator of both remaining gates. Later gates are still
    evaluated after an earlier one fails wherever their inputs exist, because a PoC whose
    output stops at the first ``REJECT`` tells you less than one that shows which other
    constraints the candidate would also have missed.

    Sizing is the one step that is skipped on failure, and only when the stop itself was
    rejected: :func:`tradipy.gates.position_size` refuses a stop the §20.13 ceiling rejects,
    which is the invariant that replaced a documented convention.
    """
    results: list[GateResult] = []
    entry = candidate.entry

    # --- §20.14 quote validity -> spread ---------------------------------
    spread, quote_reject = spread_at_signal(candidate.quote, cfg)
    q = candidate.quote
    results.append(
        GateResult(
            "quote validity",
            "§20.14",
            quote_reject is None,
            (
                f"bid {q.bid} x{q.bid_size} / ask {q.ask} x{q.ask_size}, age {q.age_seconds}s"
                + (f" -> spread {spread}" if spread is not None else "")
                + (" [ESTIMATED]" if q.estimated else "")
            ),
            quote_reject,
        )
    )
    if spread is None:
        # Every remaining gate consumes the spread. Reporting them against a fabricated
        # value would be worse than not reporting them.
        return Evaluation(candidate, results)

    # --- §20.13 stop construction ----------------------------------------
    stop, stop_reject = apply_stop_floor_and_ceiling(entry, candidate.raw_stop, cfg)
    r = entry - stop
    results.append(
        GateResult(
            "stop construction",
            "§20.13",
            stop_reject is None,
            (
                f"raw {candidate.raw_stop} -> {stop}; R = {r}; "
                f"ceiling = {cfg['max_stop_pct'] * entry} "
                f"({cfg['max_stop_pct']} x {entry})"
            ),
            stop_reject,
        )
    )

    # --- §3.1.3 spread gates ---------------------------------------------
    caps = spread_caps(entry, r, cfg)
    spread_reject = check_spread(spread, entry, r, cfg)
    results.append(
        GateResult(
            "spread gate",
            "§3.1.3",
            spread_reject is None,
            f"observed {spread} vs binding cap {caps.binding} "
            f"(scan {caps.scan}, signal {caps.signal})",
            spread_reject,
        )
    )

    # --- §3.1.2 unified room requirement ---------------------------------
    req = required_room(r, spread, cfg)
    room_reject = check_room(entry, candidate.resistance, r, spread, cfg)
    results.append(
        GateResult(
            "room gate",
            "§3.1.2",
            room_reject is None,
            f"available {candidate.resistance - entry} vs required {req.required} "
            f"(proportional {req.proportional_term}, separation {req.separation_term})",
            room_reject,
        )
    )

    # --- §3.1.1 exit ladder + §3.1.2 separation floor ---------------------
    ladder = exit_ladder(entry, r, candidate.structural_target, cfg)
    floor = min_separation(r, spread, cfg)
    separation = ladder.t2 - ladder.t1
    ordered = ladder.ordered_above(entry)
    results.append(
        GateResult(
            "exit ladder",
            "§3.1.1",
            ordered,
            f"T1 {ladder.t1} ({cfg['t1_r_multiple']}R), T2 {ladder.t2}; "
            f"ordering entry < T1 < T2 {'holds' if ordered else 'VIOLATED'}",
            None if ordered else Reject.TARGETS_TOO_CLOSE,
        )
    )
    results.append(
        GateResult(
            "separation floor",
            "§3.1.2",
            separation >= floor,
            f"T2 - T1 = {separation} vs floor {floor} "
            f"(cost term {cfg['sep_cost_multiple']} x ({spread} + "
            f"{cfg['est_round_trip_cost_per_share']}))",
            None if separation >= floor else Reject.TARGETS_TOO_CLOSE,
        )
    )

    # --- §2.2 sizing -------------------------------------------------------
    shares: int | None = None
    if stop_reject is None:
        shares = position_size(entry, stop, cfg)
        budget = cfg["start_of_day_equity"] * cfg["max_risk_per_trade_pct"]
        results.append(
            GateResult(
                "position size",
                "§2.2",
                True,
                f"{shares:,} sh = floor({budget} / {r}); "
                f"risk at stop {shares * r}, notional {shares * entry}",
            )
        )

    return Evaluation(candidate, results, spread, stop, r, ladder, shares)


# ---------------------------------------------------------------------------
# The three PRD §3 worked examples
# ---------------------------------------------------------------------------
def _quote(price: Decimal, spread: Decimal) -> Quote:
    """A clean two-sided quote at the given spread — the one tick the §3 tables assume.

    ``age_seconds=0`` is the §20.14 ideal: the quote *is* the last one at bar close. The
    worked examples state a spread and say nothing about quote age, so assuming anything
    older would be inventing an input.
    """
    return Quote(
        bid=price - spread, ask=price, bid_size=500, ask_size=500, age_seconds=Decimal(0)
    )


#: PRD §3.2's flagpole and flag, as bars. Reproduces the table's stated geometry: flagpole
#: low $4.80, flagpole high $5.15, height $0.35, flag high $5.12, flag low $5.05, retrace
#: 28.6%, flag/flagpole average volume 0.55.
BULL_FLAG_BARS: list[Bar] = [
    Bar(D("4.82"), D("4.95"), D("4.80"), D("4.93"), 900),  # flagpole
    Bar(D("4.93"), D("5.02"), D("4.91"), D("5.00"), 1100),
    Bar(D("5.00"), D("5.09"), D("4.98"), D("5.07"), 1000),
    Bar(D("5.07"), D("5.15"), D("5.05"), D("5.13"), 1000),
    Bar(D("5.12"), D("5.12"), D("5.08"), D("5.09"), 500),  # flag
    Bar(D("5.09"), D("5.10"), D("5.05"), D("5.06"), 600),
    Bar(D("5.08"), D("5.09"), D("5.06"), D("5.07"), 550),
    Bar(D("5.08"), D("5.17"), D("5.07"), D("5.16"), 1650),  # breakout: closes above flag high
]

#: Index of the first flag bar in :data:`BULL_FLAG_BARS`; §20.4's flagpole is the green run
#: ending immediately before it.
BULL_FLAG_FLAG_START = 4


@dataclass(frozen=True)
class FlagGeometry:
    """What §20.4 derives from :data:`BULL_FLAG_BARS`, kept so the demo can show its work."""

    pole_start: int
    pole_end: int
    pole_low: Decimal
    pole_high: Decimal
    height: Decimal
    flag_high: Decimal
    flag_low: Decimal
    retrace: Decimal
    flag_volume_ratio: Decimal


def bull_flag_geometry(
    bars: list[Bar] = BULL_FLAG_BARS, flag_start: int = BULL_FLAG_FLAG_START
) -> FlagGeometry:
    """Derive PRD §3.2's flagpole and flag numbers from bars, per §20.4.

    The breakout bar is excluded from the flag: §3.2 criterion 6 makes it the *trigger*, and
    including it would put the entry candle inside the pattern it broke out of.
    """
    span = flagpole_ending_at(bars, flag_start - 1)
    if span is None:
        raise ValueError(f"no green run ends at index {flag_start - 1} (PRD §20.4)")
    pole_start, pole_end = span
    pole = bars[pole_start : pole_end + 1]
    flag = bars[flag_start:-1]  # exclude the breakout bar

    height = flagpole_height(pole)
    flag_high = max(b.high for b in flag)
    flag_low = min(b.low for b in flag)
    pole_avg_vol = Decimal(sum(b.volume for b in pole)) / len(pole)
    flag_avg_vol = Decimal(sum(b.volume for b in flag)) / len(flag)

    return FlagGeometry(
        pole_start=pole_start,
        pole_end=pole_end,
        pole_low=pole[0].low,
        pole_high=pole[-1].high,
        height=height,
        flag_high=flag_high,
        flag_low=flag_low,
        retrace=retrace_pct(pole[-1].high, flag_low, height),
        flag_volume_ratio=flag_avg_vol / pole_avg_vol,
    )


def worked_examples() -> list[Candidate]:
    """The three PRD §3 worked examples as evaluable candidates.

    ``expect`` carries the values the PRD tables state, used **only** by the demo's
    self-check. Everything :func:`evaluate` reports is derived from the rules, so a table
    that drifts from its own rules fails rather than passing quietly — the v1.0 defect class.

    **R is written as the subtraction, not as its result.** ``6.48 - 6.33`` rather than
    ``0.15``, because that is what the PRD states (*"R = entry - stop"*) and because two of
    the three results — $0.15 and $0.10 — collide numerically with ``max_spread_r`` and
    ``min_stop_distance``. The registry lint cannot distinguish a worked-example output from
    a restated threshold, and it is right not to try: writing the arithmetic is both more
    faithful to the table and unambiguous to the check.
    """
    geo = bull_flag_geometry()
    bull_entry = BULL_FLAG_BARS[-1].close

    return [
        Candidate(
            label="bull_flag",
            section="§3.2",
            entry=bull_entry,
            # §3.2: hard stop at the low of the flag consolidation, minus one tick — derived
            # from the bars rather than transcribed.
            raw_stop=geo.flag_low - TICK_SIZE,
            # §3.2 T2: the §20.4 measured move.
            structural_target=measured_move(bull_entry, geo.height),
            resistance=measured_move(bull_entry, geo.height),
            quote=_quote(bull_entry, TICK_SIZE),
            expect={
                "stop": D("5.04"),
                "r": D("5.16") - D("5.04"),
                "t1": D("5.40"),
                "t2": D("5.51"),
                "shares": 2500,
            },
        ),
        Candidate(
            label="hod_breakout",
            section="§3.3",
            entry=D("6.48"),
            # min(consolidation low $6.34, breakout low $6.44) - 1 tick.
            raw_stop=min(D("6.34"), D("6.44")) - TICK_SIZE,
            structural_target=D("7.00"),  # next whole dollar above T1
            resistance=D("7.00"),
            quote=_quote(D("6.48"), TICK_SIZE),
            expect={
                "stop": D("6.33"),
                "r": D("6.48") - D("6.33"),
                "t1": D("6.78"),
                "t2": D("7.00"),
                "shares": 2000,
            },
        ),
        Candidate(
            label="vwap_reclaim",
            section="§3.4",
            entry=D("3.83"),
            # §3.4: max(dip_low $3.74, VWAP $3.80 x 0.99 -> $3.76) - 1 tick = $3.75. The
            # minimum-stop floor then widens it to $3.73 inside the gate — which is why the
            # expected stop below is not the raw one, and what makes this row a real check.
            raw_stop=D("3.75"),
            structural_target=D("4.15"),  # HOD retest
            resistance=D("4.15"),
            quote=_quote(D("3.83"), TICK_SIZE),
            expect={
                "stop": D("3.73"),
                "r": D("3.83") - D("3.73"),
                "t1": D("4.03"),
                "t2": D("4.15"),
                "shares": 3000,
            },
        ),
    ]


def check_against_prd(ev: Evaluation) -> list[str]:
    """Mismatches between what the rules derived and what the PRD table states.

    An empty list means the document and the code agree on the five outputs each example
    declares — effective stop, R, T1, T2 and share count.

    **What this does not check, stated because an earlier docstring over-claimed it.** It
    compared these five and asserted that *"the four arithmetic errors in PRD v1.0 would all
    have surfaced here"*, which is not true of at least two of them: §3.2's three different
    entry prices and §3.1.1's inconsistent partial-exit schedule have no representation in
    the compared set, because ``entry`` is an input here and the ladder percentages are not
    modelled at all. The stop/T2 class of error would surface; the input-consistency class
    needs the examples driven from bars, which only §3.2 currently is.
    """
    expect = ev.candidate.expect
    if not expect:
        return []
    got: dict[str, object] = {
        "stop": ev.stop,
        "r": ev.r,
        "t1": ev.ladder.t1 if ev.ladder else None,
        "t2": ev.ladder.t2 if ev.ladder else None,
        "shares": ev.shares,
    }
    return [
        f"{key}: derived {got[key]}, PRD table states {want}"
        for key, want in expect.items()
        if got.get(key) != want
    ]
