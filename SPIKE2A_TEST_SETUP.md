# Phase 2A Spike Test Setup — IBKR Paper Account

**Status: Ready to run Q4 (synthetic) and Q3 (live).**

---

## What's Ready

### ✅ Q4 — Spread Distribution (Synthetic Data)

Already ran and analyzed. Results:

```
signal bars      154
rejection rate   0.00% overall
§7 verdict: INERT — spread cap is decoration
```

**The synthetic test shows** `max_spread_r` is not rejecting any signals at the default value. This needs validation against real market data.

---

## What You Can Run Now

### Option A: Real Q4 Data (MSFT, RGTI)

Fetch real historical NBBO from your IBKR paper account:

```bash
# 1. Make sure TWS/Gateway is running on localhost:7497 (paper mode)
# 2. Install ib_insync if needed:
pip install ib_insync

# 3. Collect real NBBO data for the past 5 trading days:
PYTHONPATH=src python scripts/spike2a/q4_collect_real_data.py MSFT,RGTI 2026-07-21 2026-07-29

# 4. This creates signal_bars.csv with test cases, then:
PYTHONPATH=src python -m scripts.spike2a.q4_spreads data/spike2a/signal_bars.csv data/spike2a/quotes.csv
```

**What this measures:** Whether the spread cap `max_spread_r = 0.15` rejects actual MSFT/RGTI quotes or if it's inert in real market conditions.

---

### Option B: Q3 — Real Latency Measurement

Measure data-to-signal and signal-to-order latency on your paper account:

```bash
# 1. Install ib_insync:
pip install ib_insync

# 2. Start TWS or Gateway on localhost:7497 (paper mode)

# 3. Run the latency collector:
PYTHONPATH=src python scripts/spike2a/q3_collect.py MSFT,RGTI 300

# This collects measurements for 300 seconds (5 minutes) on both symbols
# Measures signal-to-order latency via whatIf preview round-trips

# 4. Analyze against §7 thresholds:
PYTHONPATH=src python -m scripts.spike2a.q3_latency data/spike2a/q3_measurements.csv
```

**What this measures:**
- p95 signal-to-order latency (threshold: ≤ 2 seconds)
- Validates §5.5's 30–60s refresh assumption and §20.1's grace period

---

## Prerequisites

- **IBKR TWS or Gateway** running on `localhost:7497` (paper mode, NOT 7496 which is live)
- **ib_insync**: `pip install ib_insync`
- **API enabled** in TWS: Edit → Global Configuration → API → Enable ActiveX and Socket Clients

---

## Test Checklist

- [ ] TWS/Gateway running on port 7497 (paper)
- [ ] ib_insync installed
- [ ] Run Q4 with real MSFT/RGTI data — compare to synthetic result
- [ ] Run Q3 for 5 minutes (300 seconds) — check p95 against thresholds
- [ ] Both results written to `data/spike2a/`

---

## What Each Measure Answers

| Q | What | Answer determines |
|---|------|---|
| **Q4** | Real spread distribution on MSFT/RGTI | Whether `max_spread_r = 0.15` is inert, calibrated, or needs recalibration (A21) |
| **Q3** | Real p95 latencies on paper gateway | Whether §5.5's 30–60s refresh assumption and §20.1's bar_close_grace_ms are realistic |

---

## Security Note

Your IBKR credentials are NOT stored anywhere. Both scripts connect at runtime using environment variables or local TWS/Gateway. After testing, consider changing your password as a precaution.

---

## Next Steps

1. Run one or both tests (Q4 and/or Q3)
2. Check results against §7 thresholds in `scripts/spike2a/prereg.py`
3. Report findings in a `data/spike2a/RESULTS.md` file
4. Any disposition (recalibration, inertness, coverage gaps) is raised as a spec question, **not** applied
