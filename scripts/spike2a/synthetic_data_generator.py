"""Synthetic NBBO data generator for Phase 2a spike.

Generates realistic market microstructure data based on IBKR conventions:
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

from tradipy.params import Config


@dataclass(frozen=True)
class MarketRegime:
    """Market conditions for a window."""

    label: str
    vix_mean: Decimal
    vix_std: Decimal
    spread_bps_mean: int  # basis points
    spread_bps_std: int
    volume_ratio: Decimal  # how active relative to baseline


# Active market (high VIX, tight spreads, high volume)
ACTIVE_REGIME = MarketRegime(
    label="active",
    vix_mean=Decimal("25"),
    vix_std=Decimal("3"),
    spread_bps_mean=8,
    spread_bps_std=4,
    volume_ratio=Decimal("1.5"),
)

# Quiet market (low VIX, wider spreads, lower volume)
QUIET_REGIME = MarketRegime(
    label="quiet",
    vix_mean=Decimal("12"),
    vix_std=Decimal("2"),
    spread_bps_mean=15,
    spread_bps_std=6,
    volume_ratio=Decimal("0.7"),
)


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
    window_dates: list[date], regime: MarketRegime
) -> list[tuple[date, str, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]]:
    """Generate pre-open facts for gappers that pass §4.2 hard filters."""
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
        "AXTI",
        "CLVS",
        "CBAK",
        "CRTX",
        "DGLY",
        "DNLI",
        "FARO",
        "GMGI",
        "HALO",
        "ILAG",
        "JMIA",
        "KOSS",
        "LBPH",
        "MIST",
        "NVFY",
        "ORCL",
        "PPSI",
        "QRVO",
        "RMED",
        "SGMA",
        "TELL",
        "UACL",
        "VERU",
        "WKSP",
        "XELA",
        "YEXT",
        "ZBH",
        "AiM",
    ]

    for session in window_dates:
        for _i, symbol in enumerate(symbols[:8]):
            # Price: mostly $1–$20 (small caps)
            price = Decimal(random.uniform(1.5, 18.5))

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
                facts.append((session, symbol, price, gap_pm, gap_daily, rvol, adv, float_shares))

    return facts


def generate_signal_bars(
    preopen: list[tuple[date, str, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]],
) -> list[tuple[str, date, str, Decimal, Decimal]]:
    """Generate signal bars for the three MVP setups.

    Each pre-open fact can fire as any of the three setups with some probability.
    The R value is computed using the library's own stop functions, per §4.3.
    """
    bars: list[tuple[str, date, str, Decimal, Decimal]] = []

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

            stop = price * stop_pct

            # R = entry - stop (simulate entry as price + 0.5%)
            entry = price * Decimal("1.005")
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

    for symbol, session, setup, price, _r in signal_bars:
        # Base spread from regime and setup
        base_bps = setup_spread_bps.get(setup, regime.spread_bps_mean)

        # Price-level adjustment: spreads wider on cheap stocks
        if price < Decimal("5"):
            price_multiplier = Decimal("2.0")
        elif price < Decimal("10"):
            price_multiplier = Decimal("1.5")
        else:
            price_multiplier = Decimal("1.0")

        spread_bps_float = float(Decimal(base_bps) * price_multiplier) + random.gauss(
            0, float(Decimal(regime.spread_bps_std))
        )
        spread_bps = max(1, spread_bps_float)  # At least 1 bps

        # Convert bps to dollar spread
        spread = price * Decimal(str(spread_bps / 10000))
        spread = max(Decimal("0.01"), spread.quantize(Decimal("0.01")))

        # Generate quotes over the hour after signal (60 samples, 1/min)
        session_dt = session
        base_time = session_dt.isoformat()

        for minute in range(samples_per_bar):
            # Use +00:00 instead of Z for Python 3.10 fromisoformat compatibility
            captured_at = f"{base_time}T09:{30 + minute:02d}:00+00:00"

            # Mid-price walks randomly; bid/ask around it
            mid = price + Decimal(str(random.gauss(0, float(price * Decimal("0.002")))))
            bid = mid - spread / Decimal("2")
            ask = mid + spread / Decimal("2")

            # Sizes in shares (typical NBBO sizes)
            bid_size = Decimal(random.randint(100, 10000))
            ask_size = Decimal(random.randint(100, 10000))

            quotes.append((symbol, captured_at, bid, ask, bid_size, ask_size))

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

    # Define windows explicitly to match later
    # Active window: 10 most recent trading days (including spike start date)
    # Quiet window: 10 trading days before that
    recent_days = [spike_start - timedelta(days=x) for x in range(40)]

    # Filter to weekdays only for simplicity
    weekdays = [d for d in recent_days if d.weekday() < 5]

    active_dates_list = sorted(weekdays[:10], reverse=True)  # Most recent 10 weekdays
    quiet_dates_list = sorted(weekdays[10:20], reverse=True)  # Next 10 weekdays

    active_dates = set(active_dates_list)
    quiet_dates = set(quiet_dates_list)

    # 2. Pre-open facts for active window
    print("2. Generating pre-open facts for active window (high-VIX)...")
    active_preopen = generate_preopen_facts(active_dates_list, ACTIVE_REGIME)
    print(f"   → {len(active_preopen)} symbol-sessions in active window")

    # 3. Pre-open facts for quiet window
    print("3. Generating pre-open facts for quiet window (low-VIX)...")
    quiet_preopen = generate_preopen_facts(quiet_dates_list, QUIET_REGIME)
    print(f"   → {len(quiet_preopen)} symbol-sessions in quiet window")

    # Combine and write
    all_preopen = active_preopen + quiet_preopen
    write_csv(
        data_dir / "preopen.csv",
        all_preopen,
        [
            "session",
            "symbol",
            "price",
            "gap_premarket_pct",
            "gap_daily_pct",
            "rvol",
            "adv_shares",
            "float_shares",
            "halted_before_open",
            "missing_nbbo_pct",
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
    print(
        f"   - Active regime: {ACTIVE_REGIME.label} (spread ~{ACTIVE_REGIME.spread_bps_mean} bps)"
    )
    print(f"   - Quiet regime: {QUIET_REGIME.label} (spread ~{QUIET_REGIME.spread_bps_mean} bps)")

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

    print(f"✓ All synthetic data written to {data_dir}/")
    print("\nReady to run spike measurement code:")
    print(
        f"  uv run python -m scripts.spike2a.q4_spreads {data_dir}/signal_bars.csv {data_dir}/quotes.csv"
    )


if __name__ == "__main__":
    random.seed(42)  # Deterministic for reproducibility
    main()
