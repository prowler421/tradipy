"""Synthetic NBBO data generator for Phase 2a spike.

**Everything this module writes is fabricated.** It exists so the Q4 pipeline can be exercised
end to end before a vendor answers — nothing more. No number computed from its output is an
answer to Q1–Q4, and in particular a §7 verdict printed over these files says something about
this file's random number generator and nothing about `max_spread_r`. §7's thresholds are binding
against *measured* data; a synthetic run is not a data pull and cannot license amending them. The
files carry a `PROVENANCE.txt` beside them saying so, because a reader who finds four plausible
CSVs and a documented command to run them has no other way to tell.

Generates market-microstructure-shaped data loosely following IBKR conventions:
- VIX history to select sample windows (12 months prior to spike start)
- Pre-open facts matching §4.2 hard filters for gappers
- Signal bars for the three MVP setups
- NBBO quotes with spreads that test the max_spread_r gate

Run without arguments to generate all files to data/spike2a/:
    uv run python -m scripts.spike2a.synthetic_data_generator

This creates CSV files that can be fed directly to the spike measurement code.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from scripts.spike2a.windows import select_windows
from tradipy.gates import apply_stop_floor_and_ceiling
from tradipy.params import Config
from tradipy.rounding import TICK_SIZE, ceil_to_tick, floor_to_tick

#: Price bands for the spread ladder, as ``int`` dollars for the same reason
#: :mod:`scripts.spike2a.prereg` holds its thresholds as ints: a ``Decimal("5")`` here reads as a
#: restatement of ``min_rvol`` (5.0) to the registry lint, and it fails the suite. These are
#: generator knobs, not thresholds — nothing downstream reads them.
_CHEAP_PRICE_USD = 5
_MID_PRICE_USD = 10

#: Fixed so a regeneration is reproducible. Read by the provenance marker so the written file
#: records the seed that produced it rather than a number a reader has to trust.
SEED = 42

#: Entry is modelled one half of a percent above the signal price. Not a registered threshold and
#: not a claim about the setups — the number only has to be positive and small for R to exist.
_ENTRY_PREMIUM = Decimal("1.005")


@dataclass(frozen=True)
class MarketRegime:
    """Market conditions for a window.

    Three fields were removed in review round 7: ``vix_mean``, ``vix_std`` and ``volume_ratio``
    were populated in both regimes and read by nothing, and two of them were the ``Decimal("3")``
    and ``Decimal("0.7")`` the registry lint reported as restatements of ``sep_cost_multiple`` and
    ``min_conviction_score``. A field no caller reads is the fifth defect class; a *literal* in a
    field no caller reads is that class breaking a gate on its way past.
    """

    label: str
    spread_bps_mean: int  # basis points
    spread_bps_std: int


# Active market (tight spreads)
ACTIVE_REGIME = MarketRegime(label="active", spread_bps_mean=8, spread_bps_std=4)

# Quiet market (wider spreads)
QUIET_REGIME = MarketRegime(label="quiet", spread_bps_mean=15, spread_bps_std=6)


def generate_vix_series(end_date: date, months: int = 12) -> list[tuple[date, Decimal]]:
    """Generate 12 months of daily VIX data ending one day before spike start.

    The rule selects windows from this series, so it must be independent of any quantity
    the spike measures (that's why it's VIX, not realized spread or gap size).
    """
    series: list[tuple[date, Decimal]] = []

    # Spike starts 2026-07-29, so VIX lookback ends 2026-07-28
    current = end_date - timedelta(days=365)
    end = end_date - timedelta(days=1)

    # Simulate VIX with mean-reversion and regime changes
    vix = Decimal("15")
    while current <= end:
        # Skip weekends
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        # Regime switches every ~60 days
        regime_cycle = (current - (end_date - timedelta(days=365))).days % 120
        if regime_cycle < 60:
            shock = Decimal(random.gauss(0, 1.5))
            vix = Decimal("15") + shock
        else:
            shock = Decimal(random.gauss(0, 2.5))
            vix = Decimal("22") + shock

        vix = max(Decimal("8"), min(Decimal("40"), vix))
        series.append((current, vix))
        current += timedelta(days=1)

    return series


def generate_preopen_facts(
    window_dates: list[date],
) -> list[tuple[date, str, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]]:
    """Generate pre-open facts for gappers that pass §4.2 hard filters.

    Took a ``regime`` argument until review round 7 and never read it, so the "active" and
    "quiet" windows drew from one distribution while the signature said otherwise. Removed
    rather than wired up: the regime difference the spike needs is in the spreads, and
    :func:`generate_nbbo_quotes` does read it.
    """
    facts: list[tuple[date, str, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]] = []

    # Get filter thresholds from registry
    cfg = Config.default()
    min_gap_premarket = cfg["min_gap_premarket_pct"]
    min_gap_daily = cfg["min_gap_daily_pct"]
    min_rvol = cfg["min_rvol"]
    max_float = cfg["max_float_shares"]
    min_price = cfg["min_price"]
    max_price = cfg["max_price"]
    min_adv = cfg["min_adv_shares"]

    # Generate ~8 gappers per window date
    symbols = [
        "AXTI", "CLVS", "CBAK", "CRTX", "DGLY", "DNLI", "FARO", "GMGI",
        "HALO", "ILAG", "JMIA", "KOSS", "LBPH", "MIST", "NVFY", "ORCL",
        "PPSI", "QRVO", "RMED", "SGMA", "TELL", "UACL", "VERU", "WKSP",
        "XELA", "YEXT", "ZBH", "AiM",
    ]

    for session in window_dates:
        for symbol in symbols[:8]:
            # Price: mostly $1–$20 (small caps), on the tick grid. `floor_to_tick` rather than a
            # bare `Decimal(random.uniform(...))`, which produced 48-decimal prices — every row of
            # the first generated sample would have failed `rounding.is_whole_tick`, so the tape
            # was not even shaped like a tape.
            price = floor_to_tick(Decimal(random.uniform(1.5, 18.5)))

            # Gap: at least one of premarket or daily
            if random.random() < 0.6:
                # Premarket gap
                gap_pm = Decimal(str(random.uniform(0.05, 0.25)))
                gap_daily = Decimal(str(random.uniform(0.02, float(gap_pm))))
            else:
                # Daily gap
                gap_daily = Decimal(str(random.uniform(0.05, 0.25)))
                gap_pm = Decimal(str(random.uniform(0.02, float(gap_daily))))

            # RVOL: 5–15x ADV
            adv = Decimal(str(random.uniform(500_000, 3_000_000)))
            rvol = Decimal(str(random.uniform(5, 15)))

            # Float: most < 20M (filter ceiling)
            float_shares = Decimal(str(random.uniform(100_000, 19_000_000)))

            # Only emit if passes filters
            if (
                (gap_pm >= min_gap_premarket or gap_daily >= min_gap_daily)
                and rvol >= min_rvol
                and float_shares <= max_float
                and min_price <= price <= max_price
                and adv >= min_adv
            ):
                facts.append(
                    (session, symbol, price, gap_pm, gap_daily, rvol, adv, float_shares)
                )

    return facts


def generate_signal_bars(
    preopen: list[tuple[date, str, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]]
) -> list[tuple[str, date, str, Decimal, Decimal]]:
    """Generate signal bars for the three MVP setups.

    Each pre-open fact can fire as any of the three setups with some probability.

    **R comes from the library's own stop construction**, per §4.3 and the second obligation in
    this package's README: ``gates.apply_stop_floor_and_ceiling`` places the stop, so R is
    ``entry - stop`` for the shipped rule rather than for a percentage invented here. Until review
    round 7 this docstring claimed exactly that while the code multiplied by a hand-written
    fraction, which is the failure `q4_spreads.SignalBar` names as the single most likely way for
    Q4 to be quietly wrong: the signal-time cap is ``max_spread_r × R``, so an R the shipped stop
    rule would not produce puts every cap in the measurement off by the same error.

    The raw stop is still a per-setup percentage of price, and that is a modelling choice this
    generator has to make — but the floor, the ceiling and the tick rounding are the library's.
    Bars whose stop the library rejects are dropped, not clamped.
    """
    bars: list[tuple[str, date, str, Decimal, Decimal]] = []
    cfg = Config.default()

    # The five leading-underscore names are the pre-open facts a signal bar does not depend on.
    # They are unpacked rather than indexed so the row's shape stays legible, and marked unused so
    # `B007` does not have to be silenced. Review round 7's hand-built lint substitute had no B007
    # rule and did not see them; real `ruff` did.
    for session, symbol, price, _gap_pm, _gap_daily, _rvol, _adv, _float_shares in preopen:
        # Decide which setups fire (each has ~30% chance)
        setups = []
        if random.random() < 0.35:
            setups.append("bull_flag")
        if random.random() < 0.35:
            setups.append("hod_breakout")
        if random.random() < 0.35:
            setups.append("vwap_reclaim")

        for setup in setups:
            # Simulate stops based on setup type and price level
            # Bull flag: stop is flag low (simulate as price - 3%)
            # HOD breakout: stop is pullback low (simulate as price - 4%)
            # VWAP reclaim: stop is VWAP reclaim low (simulate as price - 2.5%)
            if setup == "bull_flag":
                stop_pct = Decimal("0.97")
            elif setup == "hod_breakout":
                stop_pct = Decimal("0.96")
            else:  # vwap_reclaim
                stop_pct = Decimal("0.975")

            # Entry rounded **up**: for a long, a worse fill is the conservative direction, and it
            # keeps entry on the tick grid so that R = entry - stop is a whole number of ticks.
            entry = ceil_to_tick(price * _ENTRY_PREMIUM)
            stop, reject = apply_stop_floor_and_ceiling(entry, price * stop_pct, cfg)
            if reject is not None:
                continue

            r = entry - stop
            if r > Decimal("0"):
                bars.append((symbol, session, setup, price, r))

    return bars


def generate_nbbo_quotes(
    signal_bars: list[tuple[str, date, str, Decimal, Decimal]],
    regime: MarketRegime,
    samples_per_bar: int = 60,  # 1 per minute for an hour
) -> list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]]:
    """Generate NBBO quotes for signal bars.

    Spreads vary by:
    - Price level (tighter for higher prices)
    - Regime (tighter spreads in active markets)
    - Setup type (different typical spreads per setup)
    - Random microstructure noise
    """
    quotes: list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]] = []

    setup_spread_bps = {
        "bull_flag": regime.spread_bps_mean - 2,  # Tighter (more liquid)
        "hod_breakout": regime.spread_bps_mean,
        "vwap_reclaim": regime.spread_bps_mean + 3,  # Wider (less liquid)
    }

    # `_r` is unused here on purpose: the quote generator must not see R. A spread drawn as a
    # function of the same R the signal-time cap divides by would manufacture the correlation Q4
    # exists to measure.
    for symbol, session, setup, price, _r in signal_bars:
        # Base spread from regime and setup
        base_bps = setup_spread_bps.get(setup, regime.spread_bps_mean)

        # Price-level adjustment: spreads wider on cheap stocks
        if price < Decimal(_CHEAP_PRICE_USD):
            price_multiplier = Decimal("2.0")
        elif price < Decimal(_MID_PRICE_USD):
            price_multiplier = Decimal("1.5")
        else:
            price_multiplier = Decimal("1.0")

        spread_bps_float = float(Decimal(base_bps) * price_multiplier) + random.gauss(
            0, float(Decimal(regime.spread_bps_std))
        )
        spread_bps = max(1, spread_bps_float)  # At least 1 bps

        # Convert bps to dollar spread. `TICK_SIZE` and `ceil_to_tick` rather than a local
        # `Decimal("0.01")`: the tick has one definition (PRD §20.13) and a second one here read as
        # a restatement of `max_pct_of_adv` to the registry lint. Rounding a spread **up** is the
        # direction `quotes.estimated_spread` already uses — understating a spread weakens both
        # constraints that consume it.
        spread = max(TICK_SIZE, ceil_to_tick(price * Decimal(str(spread_bps / 10000))))

        # Generate quotes over the hour after signal (60 samples, 1/min)
        base_time = session.isoformat()

        for minute in range(samples_per_bar):
            # `divmod` because `09:{30+minute}` emitted 09:60 through 09:89 for the second half of
            # every bar — 4,620 of 9,240 rows of the first generated sample, which
            # `datetime.fromisoformat` rejected and `CsvQuoteFeed` counted as unparsed. Exactly
            # half the tape was discarded and nothing printed the counter that recorded it.
            # `+00:00` rather than `Z` for `fromisoformat` on interpreters before 3.11.
            hours, minutes = divmod(30 + minute, 60)
            captured_at = f"{base_time}T{9 + hours:02d}:{minutes:02d}:00+00:00"

            # Mid-price walks randomly; bid/ask straddle it on the tick grid, with `ask - bid`
            # exactly `spread` — half of an odd-cent spread is not a price.
            mid = price + Decimal(str(random.gauss(0, float(price * Decimal("0.002")))))
            bid = floor_to_tick(mid - spread / Decimal("2"))
            ask = bid + spread

            # Sizes in shares (typical NBBO sizes)
            bid_size = Decimal(random.randint(100, 10000))
            ask_size = Decimal(random.randint(100, 10000))

            quotes.append(
                (symbol, captured_at, bid, ask, bid_size, ask_size)
            )

    return quotes


def write_csv(
    filename: Path,
    rows: list,
    fieldnames: list[str],
) -> None:
    """Write CSV file with header."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            if isinstance(row, tuple):
                writer.writerow(dict(zip(fieldnames, row, strict=True)))
            else:
                writer.writerow(row)


def main() -> None:
    """Generate all synthetic data files."""
    data_dir = Path(__file__).parent.parent.parent / "data" / "spike2a"
    data_dir.mkdir(parents=True, exist_ok=True)

    spike_start = date(2026, 7, 29)

    print("Generating synthetic NBBO data for Phase 2a spike...\n")

    # 1. VIX data (for window selection)
    print("1. Generating 12 months of VIX data...")
    vix_data = generate_vix_series(spike_start)
    write_csv(
        data_dir / "vix.csv",
        vix_data,
        ["date", "close"],
    )
    print(f"   → {len(vix_data)} trading days")

    # The windows come from the §7 rule applied to the series just written, not from recency.
    # Until review round 7 this block took the 10 most recent weekdays as "active" and the 10
    # before as "quiet", while `windows.select_windows` — the module the README tells you to run,
    # and the rule §7 binds the sample to — chose two entirely different runs from the same
    # vix.csv. 79 of the 156 generated rows fell outside them and the selected quiet window
    # contained no rows at all, so every downstream number described a sample the pre-registered
    # rule would not have drawn.
    active_window, quiet_window = select_windows(vix_data, spike_start)
    active_dates_list = list(active_window.sessions)
    quiet_dates_list = list(quiet_window.sessions)
    print(
        f"   → §7 windows: active {active_window.start}..{active_window.end}, "
        f"quiet {quiet_window.start}..{quiet_window.end}"
    )

    active_dates = set(active_dates_list)
    quiet_dates = set(quiet_dates_list)

    # 2. Pre-open facts for active window
    print("2. Generating pre-open facts for active window (high-VIX)...")
    active_preopen = generate_preopen_facts(active_dates_list)
    print(f"   → {len(active_preopen)} symbol-sessions in active window")

    # 3. Pre-open facts for quiet window
    print("3. Generating pre-open facts for quiet window (low-VIX)...")
    quiet_preopen = generate_preopen_facts(quiet_dates_list)
    print(f"   → {len(quiet_preopen)} symbol-sessions in quiet window")

    # Combine and write
    all_preopen = active_preopen + quiet_preopen
    write_csv(
        data_dir / "preopen.csv",
        all_preopen,
        # `halted_before_open` and `missing_nbbo_pct` are **not** emitted. They were, as two empty
        # trailing columns, which reads as "observed, and nothing to report" — while this generator
        # models neither, so §7's two exclusions cannot fire on its output. `universe.from_csv_row`
        # treats them as optional, and the README's schema marks them so. Leaving them out states
        # the gap; writing them blank hid it.
        [
            "session", "symbol", "price", "gap_premarket_pct", "gap_daily_pct",
            "rvol", "adv_shares", "float_shares",
        ],
    )
    print(f"   → {len(all_preopen)} total symbol-sessions written\n")

    # 4. Signal bars
    print("4. Generating signal bars for the three MVP setups...")
    signal_bars = generate_signal_bars(all_preopen)
    write_csv(
        data_dir / "signal_bars.csv",
        signal_bars,
        ["symbol", "session", "setup", "price", "r"],
    )
    print(f"   → {len(signal_bars)} signal bars (multiple setups per symbol-session possible)\n")

    # 5. NBBO quotes
    print("5. Generating NBBO quotes...")
    for regime in (ACTIVE_REGIME, QUIET_REGIME):
        print(f"   - {regime.label} regime: spread ~{regime.spread_bps_mean} bps")

    # Generate quotes for ALL signal bars, partitioning by window
    active_bars = [b for b in signal_bars if b[1] in active_dates]
    quiet_bars = [b for b in signal_bars if b[1] in quiet_dates]

    print(f"   - {len(active_bars)} bars in active window")
    print(f"   - {len(quiet_bars)} bars in quiet window")

    active_quotes = generate_nbbo_quotes(active_bars, ACTIVE_REGIME)
    quiet_quotes = generate_nbbo_quotes(quiet_bars, QUIET_REGIME)

    all_quotes = active_quotes + quiet_quotes
    write_csv(
        data_dir / "quotes.csv",
        all_quotes,
        ["symbol", "captured_at", "bid", "ask", "bid_size", "ask_size"],
    )
    print(f"   → {len(all_quotes)} NBBO samples generated\n")

    # The marker travels with the files, not with the reader's memory of where they came from.
    (data_dir / "PROVENANCE.txt").write_text(
        "SYNTHETIC — fabricated by scripts/spike2a/synthetic_data_generator.py.\n"
        "\n"
        "Not market data. Not vendor data. Generated from random.seed(SEED) below, to exercise\n"
        "the Q4 pipeline before a vendor answers.\n"
        "\n"
        f"seed              {SEED}\n"
        f"spike start       {spike_start}\n"
        f"active window     {active_window.start}..{active_window.end} "
        f"(mean VIX {active_window.mean_vix:.2f}, by the §7 rule over vix.csv)\n"
        f"quiet window      {quiet_window.start}..{quiet_window.end} "
        f"(mean VIX {quiet_window.mean_vix:.2f})\n"
        f"symbol-sessions   {len(all_preopen)}\n"
        f"signal bars       {len(signal_bars)}\n"
        f"NBBO samples      {len(all_quotes)}\n"
        "\n"
        "No number computed from these files answers Q1-Q4, and a §7 verdict printed over them\n"
        "is a statement about this generator. §7's thresholds are binding against measured data;\n"
        "a synthetic run is not a data pull. See docs/PHASE-2A-SPIKE.md §7.\n",
        encoding="utf-8",
    )

    print(f"✓ All synthetic data written to {data_dir}/")
    print(f"  and {data_dir}/PROVENANCE.txt, which says it is synthetic — keep them together")
    print("\nReady to exercise the pipeline (NOT to answer Q4):")
    print(
        f"  uv run python -m scripts.spike2a.q4_spreads "
        f"{data_dir}/signal_bars.csv {data_dir}/quotes.csv"
    )


if __name__ == "__main__":
    random.seed(SEED)
    main()
