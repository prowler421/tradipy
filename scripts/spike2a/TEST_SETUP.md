# Advancing past simulated data

**This was a runbook for two collectors that no longer exist.** PLAN **D30** puts every dataset
in this repository on the simulated rung of a three-rung ladder — simulated, then paper, then a
funded account — and `q3_collect.py`, `q4_collect_real_data.py` and
`feeds.IbkrHistoricalTicksFeed` were removed with it. They are recoverable at `3ca9e7b`, the
last commit that contains them. Nothing in this package connects to anything. See
[README.md](README.md) for the path that does run.

The file is kept, rewritten, because deleting it would lose the part that outlives the scripts:
what the next rung actually costs. A rung is advanced by a recorded decision, not by restoring a
file.

## The ladder

| Rung | What it means | What advancing to it requires |
|---|---|---|
| **SIMULATED** | Current. Every input is fabricated by `synthetic_data_generator.py` and declared in `PROVENANCE.txt` | — |
| **PAPER** | Read-only market data, and orders that reach a paper account only | A PLAN decision superseding D30's `PERMITTED_ORIGINS`; a `QuoteFeed` implementation and a collector to replace what was removed; the four items below |
| **LIVE** | A funded account | Everything above, plus the PRD **§18.8** evidence bar in full — positive expectancy net of modeled slippage and fees over ≥100 trades per MVP setup, out-of-sample, with Monte Carlo 95th-percentile max drawdown inside the account's risk tolerance |

`PERMITTED_ORIGINS` in `provenance.py` is the single line that encodes the current rung.
Widening it without the corresponding decision is the failure D30 exists to prevent, so
`tests/test_enforcement.py` asserts what it currently holds — the test fails when the line
changes, which is the point. Changing both together is the recorded decision; changing the line
alone is not possible.

## What the paper rung has to solve, and why it is not one afternoon

These were true before D30 and stayed true; they are the reason "just point it at a real feed"
was never a small change.

- **`reqHistoricalTicks` BID_ASK at the sample's volume and lookback is unverified.** Three
  limits could each sink it — a 1000-tick per-request ceiling needing paging, historical tick
  depth shorter than the §7 window rule's 12-month range and not uniform across symbols, and
  pacing violations that arrive as empty responses rather than errors. A negative answer there
  is a **Q1** finding, not a bug.
- **There is no generator for real signal bars.** `signal_bars.csv` needs real pre-open facts,
  real setup detection, and R from `gates.apply_stop_floor_and_ceiling` applied to a real stop
  (README obligation 2). A hand-authored file paired with real quotes is not a real-data run,
  and reading it as one is the H7 defect with an extra step.
- **Latency has to be measured, not modeled.** Q3's `signal_to_order` leg was specified as a
  `whatIf` preview round trip — a margin check that never reaches a venue. It understates true
  fill latency and does not cover venue routing, and any report of it must say so.
- **Credentials.** Nothing here has ever stored one, and nothing should. A local socket
  authenticated by TWS/Gateway is the only shape that keeps that true.

## What does not change on any rung

Any Q1–Q4 result — recalibration, inertness, a coverage gap — is raised as a spec question in
`docs/CHANGELOG.md`, per D7. It is not applied in code by whoever runs the collection. That held
when the collectors existed and holds now; D30 removed the data, not the disposition rule.

Simulated data cannot answer Q1–Q4 at all. §7 binds its thresholds to measured data and states
that a synthetic run is not a data pull — untouched by D30, and enforced by
`provenance.Provenance.answers_prereg`, which is why `q4_spreads.py` prints a pipeline outcome
today and not a §7 verdict.
