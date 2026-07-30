"""Q4 real NBBO data collector for specific symbols from IBKR.

Instead of synthetic data, fetch real historical NBBO ticks from IBKR paper gateway
for your test symbols (MSFT, RGTI) to measure actual spread distributions.

Usage:
    python q4_collect_real_data.py <symbols> <start_date> <end_date>

Example (past 5 trading days):
    python q4_collect_real_data.py MSFT,RGTI 2026-07-21 2026-07-29

Output: data/spike2a/quotes_real.csv in the format q4_spreads expects

Prerequisites:
    - TWS or IB Gateway running on localhost:7497 (paper mode)
    - ib_insync installed: pip install ib_insync
    - Sufficient historical data available in your IBKR account
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from ib_insync import IB, Stock  # pyright: ignore[reportMissingImports]
except ImportError:
    print("ERROR: ib_insync not installed. Run: pip install ib_insync")
    sys.exit(1)


def fetch_historical_nbbo(
    symbols: list[str],
    start_date: str,
    end_date: str,
    output_path: Path,
) -> int:
    """Fetch historical NBBO ticks for symbols in date range."""

    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = int(os.getenv("IBKR_PORT", "7497"))

    print("Q4 Real NBBO Data Collection")
    print("=" * 62)
    print(f"IBKR: {host}:{port} ({'paper' if port == 7497 else 'live'})")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Output: {output_path}")
    print()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        ib = IB()
        print("Connecting...")
        ib.connect(host, port, clientId=2, readonly=True)

        if not ib.isConnected():
            print("ERROR: Could not connect. Make sure TWS/Gateway is running.")
            return 1

        print("✓ Connected")
        print()

        all_samples = []

        for symbol in symbols:
            print(f"Fetching {symbol}...")
            contract = Stock(symbol, "SMART", "USD")
            ib.qualifyContracts(contract)

            try:
                # Request historical ticks for BID/ASK
                # Note: This fetches up to 1000 ticks per call; full implementation needs paging
                ticks = ib.reqHistoricalTicks(
                    contract,
                    endDateTime=f"{end_date} 16:00:00",
                    startDateTime=f"{start_date} 09:30:00",
                    numberOfTicks=1000,
                    whatToShow="BID_ASK",
                    useRTH=True,  # Regular trading hours only
                    ignoreSize=False,
                )

                if not ticks:
                    print(f"  ⚠ No data for {symbol} in period")
                    continue

                print(f"  → {len(ticks)} ticks")

                for tick in ticks:
                    if hasattr(tick, "bid") and hasattr(tick, "ask"):
                        sample = {
                            "symbol": symbol,
                            "captured_at": tick.time.isoformat()
                            if hasattr(tick, "time")
                            else datetime.now().isoformat(),
                            "bid": str(tick.bid),
                            "ask": str(tick.ask),
                            "bid_size": tick.bidSize if hasattr(tick, "bidSize") else 100,
                            "ask_size": tick.askSize if hasattr(tick, "askSize") else 100,
                            "age_seconds": "0",
                        }
                        all_samples.append(sample)

            except Exception as e:
                print(f"  ERROR: {e}")

        ib.disconnect()
        print()

        if not all_samples:
            print("ERROR: No data collected. Check:")
            print("  1. Symbols are valid")
            print("  2. Date range has trading sessions")
            print("  3. IBKR has historical data for these symbols")
            return 1

        # Write CSV
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "symbol",
                    "captured_at",
                    "bid",
                    "ask",
                    "bid_size",
                    "ask_size",
                    "age_seconds",
                ],
            )
            writer.writeheader()
            writer.writerows(all_samples)

        print(f"✓ Collected {len(all_samples)} NBBO samples across {len(symbols)} symbols")
        print(f"✓ Wrote {output_path}")
        print()
        print("Next: create signal_bars.csv with test cases, then run Q4:")
        print(f"  python -m scripts.spike2a.q4_spreads signal_bars.csv {output_path}")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)

    symbols_str = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3] if len(sys.argv) > 3 else datetime.now().strftime("%Y-%m-%d")

    symbols = [s.strip().upper() for s in symbols_str.split(",")]
    output = Path("data/spike2a/quotes_real.csv")

    sys.exit(fetch_historical_nbbo(symbols, start_date, end_date, output))
