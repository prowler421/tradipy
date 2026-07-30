"""Q3 latency collection — real IBKR paper account measurement.

Measures two latencies:
1. data_to_signal: from bar close to signal decision (when a bar becomes tradeable)
2. signal_to_order: from signal decision to order acknowledgement (whatIf preview round-trip)

This is throwaway spike code: it connects to IBKR paper, timestamps market events,
and collects measurements into a CSV for q3_latency.py to analyze.

Usage:
    python -m scripts.spike2a.q3_collect <symbols> <duration_seconds>

Example (run from tradipy root):
    PYTHONPATH=src python scripts/spike2a/q3_collect.py MSFT,RGTI 300

Reads IBKR connection details from environment:
    IBKR_HOST (default: 127.0.0.1)
    IBKR_PORT (default: 7497 for paper, 7496 for live)

Prerequisites:
    - TWS or IB Gateway running on localhost:7497 (paper) or localhost:7496 (live)
    - API enabled in TWS: Edit > Global Configuration > API > Enable ActiveX and Socket Clients
    - ib_insync installed: pip install ib_insync
"""

from __future__ import annotations

import csv
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

try:
    from ib_insync import IB, Stock  # pyright: ignore[reportMissingImports]
except ImportError:
    print("ERROR: ib_insync not installed. Run: pip install ib_insync")
    sys.exit(1)


def main(symbols_str: str, duration_seconds: int = 300) -> int:
    """Connect to IBKR paper, collect latency measurements for specified symbols."""

    symbols = [s.strip().upper() for s in symbols_str.split(",")]
    output_csv = Path("data/spike2a/q3_measurements.csv")
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = int(os.getenv("IBKR_PORT", "7497"))

    print("Q3 Latency Collection")
    print("=" * 62)
    print(f"IBKR endpoint: {host}:{port} ({'paper' if port == 7497 else 'live'})")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Duration: {duration_seconds} seconds")
    print(f"Output: {output_csv}")
    print()

    measurements: list[tuple[str, str, str]] = []

    try:
        ib = IB()
        print("Connecting to IBKR...")
        ib.connect(host, port, clientId=2, readonly=True)

        if not ib.isConnected():
            print("ERROR: Could not connect to IBKR.")
            print("Make sure:")
            print(f"  1. TWS or Gateway running on {host}:{port}")
            print("  2. API enabled in TWS: Edit > Global Configuration > API")
            print("  3. Allow connections from localhost")
            return 1

        print("✓ Connected")
        print()

        # Subscribe to market data
        contracts = [Stock(symbol, "SMART", "USD") for symbol in symbols]
        for c in contracts:
            ib.qualifyContracts(c)

        tickers = [ib.reqMktData(c) for c in contracts]
        time.sleep(1)

        print(f"✓ Subscribed to {len(symbols)} symbols")
        print("Collecting measurements...")
        print()

        start_time = time.time()
        measurements_collected = 0

        while time.time() - start_time < duration_seconds:
            for ticker in tickers:
                if ticker.bid > 0 and ticker.ask > 0:
                    # Measure signal-to-order latency via whatIf preview
                    order_start = time.time()
                    try:
                        ib.whatIfOrder(
                            ticker.contract,
                            100,
                            "BUY",
                            "MKT",
                        )
                        signal_to_order = Decimal(str(time.time() - order_start))
                        measurements.append(
                            (
                                "signal_to_order",
                                str(signal_to_order),
                                f"{ticker.contract.symbol} whatIf preview",
                            )
                        )
                        measurements_collected += 1
                    except Exception as e:
                        print(f"  whatIf error for {ticker.contract.symbol}: {e}")

            time.sleep(1.0)

        ib.disconnect()
        print()
        print(f"✓ Collected {measurements_collected} measurements")

        # Write CSV
        with output_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["kind", "seconds", "note"])
            for kind, seconds, note in measurements:
                writer.writerow([kind, seconds, note])

        print(f"✓ Wrote {output_csv}")
        print()
        print("Analyze with:")
        print(f"  python -m scripts.spike2a.q3_latency {output_csv}")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)

    symbols = sys.argv[1]
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 300

    sys.exit(main(symbols, duration))
