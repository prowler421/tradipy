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
from tradipy.scanner import ScanCandidate
from tradipy.score import Catalyst
from tradipy.session import Session, bar_sequence
from tradipy.setups import EVALUATORS, SetupOutcome, SetupType

__all__ = [
    "Candidate",
    "GateResult",
    "Evaluation",
    "evaluate",
    "worked_examples",
    "simulated_universe",
    "SetupExample",
    "setup_examples",
]

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
    return Quote(bid=price - spread, ask=price, bid_size=500, ask_size=500, age_seconds=Decimal(0))


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


# ---------------------------------------------------------------------------
# A simulated universe for the §4 scanner
# ---------------------------------------------------------------------------
#: How far the simulated LULD bands sit from the reference price, as a fraction. Comfortably
#: outside ``min_luld_distance_pct`` so a fixture only fails §4.2's Circuit Breakers row when
#: it says it does.
_SIM_LULD_BAND = D("0.35")


#: The clean baseline every simulated candidate starts from: passes all seven §4.2 hard
#: filters and raises **no** soft flag, so each fixture below raises exactly the flags it asks
#: for. Hoisted to module constants rather than written into ``_sim``'s signature because
#: ``Decimal("0.18")`` in a default is a call, which ruff's ``B008`` forbids — and because
#: reading the baseline in one block is easier than reading it down a parameter list.
_SIM_PRICE = D("4.25")
_SIM_PREMARKET_GAP_PCT = D("0.18")
_SIM_DAILY_GAP_PCT = D("0.22")
_SIM_RVOL = D("12")
_SIM_FLOAT_SHARES = D("6200000")
_SIM_ADV_SHARES = D("1400000")
_SIM_BID_SIZE = 800
_SIM_PREMARKET_VOLUME = D("450000")
_SIM_MARKET_CAP = D("180000000")
_SIM_ATR = D("0.42")
_SIM_AVG_ATR = D("0.19")
#: Below ``min_short_interest_pct``. It was above it, which made ``HIGH_SHORT_INTEREST`` fire
#: on all fourteen candidates and drowned out every other flag in the demo output — a
#: fixture that says nothing because it says the same thing everywhere. Not ``0.01``, which
#: the registry lint reads as a restatement of ``max_pct_of_adv``.
_SIM_SHORT_INTEREST_PCT = D("0.012")


def _sim(
    symbol: str,
    *,
    price: Decimal = _SIM_PRICE,
    premarket_gap_pct: Decimal = _SIM_PREMARKET_GAP_PCT,
    daily_gap_pct: Decimal = _SIM_DAILY_GAP_PCT,
    rvol: Decimal = _SIM_RVOL,
    float_shares: Decimal = _SIM_FLOAT_SHARES,
    adv_shares: Decimal = _SIM_ADV_SHARES,
    luld_upper: Decimal | None = None,
    spread: Decimal = TICK_SIZE,
    bid_size: int = _SIM_BID_SIZE,
    premarket_volume: Decimal = _SIM_PREMARKET_VOLUME,
    catalyst: Catalyst = Catalyst.CONFIRMED,
    market_cap: Decimal | None = _SIM_MARKET_CAP,
    atr: Decimal | None = _SIM_ATR,
    avg_atr: Decimal | None = _SIM_AVG_ATR,
    sessions_since_halt: int | None = None,
    short_interest_pct: Decimal | None = _SIM_SHORT_INTEREST_PCT,
) -> ScanCandidate:
    """A candidate that passes all seven §4.2 hard filters, with named defects applied.

    Every field starts from a clean value and each fixture states only what it changes, so a
    rejection in the demo output is attributable to the argument that caused it.

    The LULD bands **follow the price** unless ``luld_upper`` is given explicitly. Without
    that, moving a fixture's price out of §4.2's range would also move it inside the band and
    the demo would report two rejections where one is the point.
    """
    return ScanCandidate(
        symbol=symbol,
        price=price,
        premarket_gap_pct=premarket_gap_pct,
        daily_gap_pct=daily_gap_pct,
        rvol=rvol,
        float_shares=float_shares,
        adv_shares=adv_shares,
        luld_upper=luld_upper if luld_upper is not None else price * (Decimal(1) + _SIM_LULD_BAND),
        luld_lower=price * (Decimal(1) - _SIM_LULD_BAND),
        spread=spread,
        bid_size=bid_size,
        premarket_volume=premarket_volume,
        catalyst=catalyst,
        market_cap=market_cap,
        atr=atr,
        avg_atr=avg_atr,
        sessions_since_halt=sessions_since_halt,
        short_interest_pct=short_interest_pct,
    )


def simulated_universe(cfg: Config) -> list[ScanCandidate]:
    """Fourteen synthetic candidates: seven that survive §4.2, seven that each fail one row.

    **Simulated, and that is a policy position rather than a convenience.** PLAN **D30** puts
    the project on the ``SIMULATED`` rung of the data ladder, and D32 opened Phase 3 without
    advancing it, so this universe is *constructed* rather than read. It touches no file,
    which is why it needs no ``PROVENANCE.txt``: the provenance gate constrains what may be
    read, and nothing here reads anything.

    What it demonstrates is that the pipeline runs end to end and that each of §4.2's seven
    hard filters is reachable. What it cannot demonstrate is that any threshold is calibrated
    — that is Phase 2a Q1, on measured data, and it is still unanswered.

    The seven survivors differ in the §20.10 inputs so the watchlist ordering is a real
    ranking rather than input order, and there are seven of them against a
    ``watchlist_size`` of five so the truncation is visible. They also raise **one soft flag
    each**, so the demo shows what a flag looks like on an accepted name without any one flag
    firing everywhere. The baseline raises none — see ``_SIM_SHORT_INTEREST_PCT``.

    **Boundary values are derived from the registry, not written.** ``cfg["min_rvol"] - 1``
    rather than ``4``: a demo is not a test, so it should follow the configuration rather than
    silently stop exercising a filter when a threshold moves. Tests do the opposite — they
    state literals, because asserting a derivation against a value the registry supplied
    proves nothing (convention 4).
    """
    return [
        # --- seven that survive; each raises one soft flag, or none -------
        _sim("SYNA", rvol=D("31"), float_shares=D("2100000"), short_interest_pct=D("0.31")),
        _sim("SYNB", rvol=D("18"), daily_gap_pct=D("0.41"), premarket_volume=D("620000")),
        _sim("SYNC", rvol=D("8"), catalyst=Catalyst.HEADLINE_ONLY, atr=D("0.21")),
        _sim("SYND", rvol=D("22"), float_shares=D("3800000"), sessions_since_halt=1),
        _sim("SYNE", rvol=D("7"), daily_gap_pct=D("0.13"), catalyst=Catalyst.NONE),
        _sim("SYNF", rvol=D("11"), market_cap=D("4300000000")),
        _sim("SYNG", rvol=D("6"), premarket_volume=D("38000"), short_interest_pct=None),
        # --- seven that each fail exactly one hard row --------------------
        # SYNGAP carries a soft flag as well as its rejection, deliberately: the demo should
        # show at least one line where a flag sits beside a REJECT and changes nothing.
        _sim(
            "SYNGAP",
            premarket_gap_pct=cfg["min_gap_premarket_pct"] / Decimal(2),
            daily_gap_pct=cfg["min_gap_daily_pct"] / Decimal(2),
            short_interest_pct=D("0.44"),
        ),
        _sim("SYNRVL", rvol=cfg["min_rvol"] - Decimal(1)),
        _sim("SYNFLT", float_shares=cfg["max_float_shares"] * Decimal(3)),
        _sim("SYNPRC", price=cfg["max_price"] + Decimal(5)),
        _sim("SYNADV", adv_shares=cfg["min_adv_shares"] / Decimal(5)),
        _sim("SYNLLD", luld_upper=_SIM_PRICE + TICK_SIZE),
        _sim("SYNSPR", spread=cfg["max_spread_abs"] * Decimal(4)),
    ]


# ---------------------------------------------------------------------------
# Phase 4 — the three §3 setups, driven from bar series
# ---------------------------------------------------------------------------
#: §3.2's flagpole/flag bars need a volume history behind them: criterion 2 compares the pole's
#: volume against the mean of the ``flagpole_vol_lookback_bars`` bars *before* it, and a short
#: baseline is a refusal rather than a pass. These are that history — quiet, below the flag low,
#: and ending on a red bar so §20.4's green run cannot extend into them.
BULL_FLAG_WARMUP: list[Bar] = [Bar(D("4.78"), D("4.80"), D("4.74"), D("4.75"), 400)] * 30

#: PRD §3.3's worked example as bars. Volumes are chosen so that §20.2's VWAP at the trigger is
#: **exactly** the table's $6.32 — the opening bar's 52,700 shares is the one solved figure, and
#: ``tests/test_setups.py`` asserts the library agrees rather than trusting the arithmetic here.
#: Bars 2–3 are the pullback that separates the HOD from the consolidation: their lows sit below
#: the VWAP *as of those bars*, which is what keeps §3.3's consolidation run at the table's three
#: candles. That the run's extent turns on the per-bar VWAP rather than the trigger's is the
#: reading recorded on :func:`tradipy.setups.evaluate_hod_breakout`.
HOD_BREAKOUT_BARS: list[Bar] = [
    Bar(D("6.10"), D("6.20"), D("6.08"), D("6.18"), 52700),  # 09:30 open
    Bar(D("6.18"), D("6.45"), D("6.15"), D("6.38"), 30000),  # sets the prior HOD, $6.45
    Bar(D("6.38"), D("6.44"), D("6.20"), D("6.24"), 15000),  # pullback below VWAP
    Bar(D("6.24"), D("6.39"), D("6.22"), D("6.30"), 15000),
    Bar(D("6.36"), D("6.42"), D("6.36"), D("6.38"), 20000),  # consolidation, $6.34-$6.42
    Bar(D("6.38"), D("6.41"), D("6.34"), D("6.36"), 20000),
    Bar(D("6.36"), D("6.40"), D("6.35"), D("6.39"), 20000),
    Bar(D("6.44"), D("6.49"), D("6.44"), D("6.48"), 38000),  # breakout: closes above the HOD
]

#: PRD §3.4's worked example as bars. Every bar has ``high + low + close = $11.40``, so its
#: §20.2 typical price is exactly $3.80 and the VWAP is $3.80 at *every* bar regardless of
#: volume — which is what lets the dip depth (1.58%) and the stop chain ($3.762 -> $3.76 -> $3.75
#: -> $3.73) reproduce the table without a solved volume. The opening bar carries the $4.15 HOD.
VWAP_RECLAIM_BARS: list[Bar] = [
    Bar(D("3.45"), D("4.15"), D("3.40"), D("3.85"), 40000),  # opening drive, HOD $4.15
    *([Bar(D("3.79"), D("3.83"), D("3.75"), D("3.82"), 8000)] * 17),  # 17 more above VWAP
    Bar(D("3.80"), D("3.86"), D("3.77"), D("3.77"), 10000),  # dip, 4 candles
    Bar(D("3.77"), D("3.88"), D("3.74"), D("3.78"), 10000),  # dip low $3.74
    Bar(D("3.78"), D("3.85"), D("3.77"), D("3.78"), 10000),
    Bar(D("3.78"), D("3.84"), D("3.77"), D("3.79"), 10000),
    Bar(D("3.78"), D("3.83"), D("3.74"), D("3.83"), 24000),  # reclaim: closes above VWAP
]


@dataclass(frozen=True)
class SetupExample:
    """One §3 worked example as PRD §21.1 asks for it: a bar series and the table's outputs.

    ``expect`` carries what the §3 table states. It is compared against what the rules derive,
    never substituted for it — so a table that has drifted from its own rules fails rather than
    passing quietly, which is the v1.0 defect class and the reason §21.1 asks for this row.

    ``expect_reject`` is not a convenience. §3.4's example is **rejected** by §3.1.1's resistance
    set as that section enumerates it, because the next whole dollar ($4.00) is nearer than the
    HOD ($4.15) the table names — so this field is how a divergence between the document and its
    own rules is recorded rather than smoothed over. See
    :func:`tradipy.setups.nearest_resistance`.
    """

    label: str
    section: str
    bars: list[Bar]
    spread: Decimal
    setup: SetupType
    expect: dict[str, object]
    expect_reject: Reject | None = None

    @property
    def session(self) -> Session:
        """The bars as a contiguous §20.1 session starting at the 09:30 bar."""
        return bar_sequence(self.bars)

    @property
    def trigger(self) -> int:
        """The trigger bar's index — the last bar, in every §3 example."""
        return len(self.bars) - 1

    def evaluate(self, cfg: Config) -> SetupOutcome:
        """Run the setup this example belongs to at its trigger bar."""
        return EVALUATORS[self.setup](
            self.label.upper(), self.session, self.trigger, self.spread, cfg
        )


def setup_examples() -> list[SetupExample]:
    """The three PRD §3 worked examples, each driven from a bar series.

    The §3.2 series is :data:`BULL_FLAG_WARMUP` plus :data:`BULL_FLAG_BARS` — the *same* bars
    :func:`worked_examples` uses, extended with the volume history §3.2 criterion 2 needs. A
    second copy of the §3.2 example would be the v1.2 defect class in the fixtures themselves.
    """
    return [
        SetupExample(
            label="bull_flag",
            section="§3.2",
            bars=BULL_FLAG_WARMUP + BULL_FLAG_BARS,
            spread=TICK_SIZE,
            setup=SetupType.BULL_FLAG,
            expect={
                "entry": D("5.16"),
                "stop": D("5.04"),
                "r": D("5.16") - D("5.04"),
                "t1": D("5.40"),
                "t2": D("5.51"),
                "shares": 2500,
            },
        ),
        SetupExample(
            label="hod_breakout",
            section="§3.3",
            bars=HOD_BREAKOUT_BARS,
            spread=TICK_SIZE,
            setup=SetupType.HOD_BREAKOUT,
            expect={
                "entry": D("6.48"),
                "stop": D("6.33"),
                "r": D("6.48") - D("6.33"),
                "t1": D("6.78"),
                "t2": D("7.00"),
                "shares": 2000,
            },
        ),
        SetupExample(
            label="vwap_reclaim",
            section="§3.4",
            bars=VWAP_RECLAIM_BARS,
            spread=TICK_SIZE,
            setup=SetupType.VWAP_RECLAIM,
            # Every line of §3.4's table up to the room gate reproduces; the room gate does not,
            # and the entry/stop/R/T1/T2 below are asserted anyway because they are derived
            # before it. `shares` is absent deliberately: a rejected setup is not sized.
            expect={
                "entry": D("3.83"),
                "stop": D("3.73"),
                "r": D("3.83") - D("3.73"),
                "t1": D("4.03"),
                "t2": D("4.15"),
            },
            expect_reject=Reject.TARGETS_TOO_CLOSE,
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
