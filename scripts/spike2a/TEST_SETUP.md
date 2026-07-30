# Testing `scripts/spike2a/` against a real IBKR paper account

This is the runbook for the two collectors that talk to a live paper gateway —
`q3_collect.py` (latency) and `q4_collect_real_data.py` (NBBO ticks) — as opposed to
`synthetic_data_generator.py`, which fabricates input and needs no connection. See
[README.md](README.md) for the synthetic path, the input schemas, and the two obligations the
schemas cannot enforce; this file does not repeat them.

**Moved from the repository root and rewritten in review round 7.** The original draft reported
a synthetic Q4 run — `154 signal bars, 0.00% overall, verdict INERT` — as "already ran and
analyzed" with no synthetic label, over a `max_spread_r` derivation that round 7's H3 finding
found and fixed (the corrected number is `CALIBRATED`, `2/147`, cheapest decile `14.29%` — see
`docs/reviews/REVIEW-2026-07-30.md`). Printing a verdict without saying what produced it is
exactly H7. Nothing below reports a result; it only says how to collect real input.

## What's real here and what isn't

**Everything downstream of `synthetic_data_generator.py` is fabricated**, `PROVENANCE.txt` says
so, and no number computed from it answers Q1–Q4 (§7). The two scripts below are the only things
in this package that touch real data, and only while TWS/Gateway is running:

- `q4_collect_real_data.py` writes `data/spike2a/quotes_real.csv` — real NBBO ticks. It does
  **not** write `age_seconds`: that column is a quote's age at the *signal instant*, which this
  collector does not know, and a written `0` would assert every tick was fresh — see the
  module's own docstring.
- `q3_collect.py` writes `data/spike2a/q3_measurements.csv` — real latency samples.

**Neither produces `signal_bars.csv`.** There is no generator for real signal bars against an
arbitrary symbol: that needs real pre-open facts, real setup detection, and R from
`gates.apply_stop_floor_and_ceiling` applied to a real stop (obligation 2 in the README) — none
of which exist for MSFT/RGTI today. Running `q4_spreads.py` against `quotes_real.csv` therefore
needs a hand-authored `signal_bars.csv` for the same symbols and sessions; there is nothing here
that builds one automatically. **Do not point `q4_spreads.py` at the synthetic `quotes.csv` and
a hand-authored `signal_bars.csv` and read the result as a real-data verdict** — that repeats H7
with an extra step.

## Prerequisites

- **IBKR TWS or Gateway** running on `localhost:7497` (paper mode — **not** 7496, which is live;
  §3.2 forbids live trading of any size for any reason)
- **`ib_insync`**, installed into a throwaway environment (`uv pip install ib_insync`). It is
  deliberately not a package dependency — see `feeds.py`'s module docstring
- **API enabled** in TWS: Edit → Global Configuration → API → Enable ActiveX and Socket Clients

## Running the collectors

```bash
# Real NBBO ticks for a symbol list and date range → data/spike2a/quotes_real.csv
uv run python -m scripts.spike2a.q4_collect_real_data MSFT,RGTI 2026-07-21 2026-07-29

# Real latency samples for 300 seconds → data/spike2a/q3_measurements.csv
uv run python -m scripts.spike2a.q3_collect MSFT,RGTI 300
uv run python -m scripts.spike2a.q3_latency data/spike2a/q3_measurements.csv
```

`IBKR_HOST` / `IBKR_PORT` override the connection if TWS/Gateway is not on the default paper
socket. Both scripts read credentials from nothing — they connect to a local socket that is
already authenticated by TWS/Gateway, and store no IBKR credential anywhere in the repository or
on disk.

## Checklist

- [ ] TWS/Gateway running on port 7497 (paper), API enabled
- [ ] `ib_insync` installed into a throwaway environment
- [ ] `q4_collect_real_data.py` run and `quotes_real.csv` written
- [ ] A `signal_bars.csv` hand-authored for the same symbols/sessions, R from
      `apply_stop_floor_and_ceiling`, if you intend to run Q4 against the real ticks
- [ ] `q3_collect.py` run for a long enough window to get a meaningful p95, and
      `q3_latency.py` run against its output

Any Q3/Q4 result — recalibration, inertness, a coverage gap — is raised as a spec question in
`docs/CHANGELOG.md`, per D7. It is not applied in code by this checklist or by whoever runs it.
