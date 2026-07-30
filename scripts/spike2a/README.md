# `scripts/spike2a/` — Phase 2a data feasibility spike

**Throwaway investigative code.** Scope, method and the binding pre-registration are in
[docs/PHASE-2A-SPIKE.md](../../docs/PHASE-2A-SPIKE.md). This file says how to run it and what it
is not.

## What this is not

§8 of the spike document names the failure mode: *"the spike code works, and it becomes the
scanner by accretion."* So:

- nothing here is imported by `src/tradipy/`, and nothing here ever should be;
- there is no test-coverage obligation on this directory;
- if Q1 comes back positive, **Phase 3 is written fresh against the PRD**, not grown from here.

## Status of each question

| Q | What it needs | Runnable now |
|---|---|---|
| **Q1** — real-time candidate list | Vendor trials | **No.** And IBKR alone is a *pre-determined* negative: §7 requires ≥ 200 concurrent symbols and §1 records IBKR's ~100 market-data line cap. §3.3 says to establish that concretely rather than assume it |
| **Q2** — float / short-interest quality | Two independent providers | **Half.** The staleness condition runs on one provider and can trip A10 alone. The disagreement condition cannot — `q2_float.disagreement` returns `None`, never `0` |
| **Q3** — latency | Paper connection | **Arithmetic yes, collection no.** The percentile and verdict logic is written and checkable; the `ib_insync` timestamping is not, because guessing at its event ordering measures the guess |
| **Q4** — realized spread distribution | Historical intraday NBBO | **Yes, on a CSV.** Whether the IBKR paper tier serves `reqHistoricalTicks` BID_ASK for a 400-symbol-session sample is **unverified** — see `feeds.IbkrHistoricalTicksFeed` for the three limits to check |

Q4 runs first. §7's budget clause makes that binding rather than advisory: it needs no
subscription, so a budget overrun cannot cost the one answer that can invalidate a shipped
default.

## Running it

Every measurement module is stdlib-only and takes CSV input, so the whole pipeline runs with no
broker, no subscription and no network. Run from the repository root.

**`data/spike2a/` is gitignored and empty on a clean clone**, so nothing below runs until the
files exist. `synthetic_data_generator.py` fabricates four of the six, which is enough to exercise
Q4 and nothing more — it writes a `PROVENANCE.txt` beside them saying so, and no number computed
from its output answers Q1–Q4. `floats.csv` and `latency.csv` have no generator: Q2 and Q3 are
blocked on a second float provider and a paper connection, so their inputs are hand-authored when
those arrive.

```bash
# Fabricate vix.csv, preopen.csv, signal_bars.csv, quotes.csv + PROVENANCE.txt. Synthetic.
uv run python -m scripts.spike2a.synthetic_data_generator

# The two §7 sample windows, chosen by the VIX rule. Input: date,close
uv run python -m scripts.spike2a.windows data/spike2a/vix.csv 2026-07-29

# Which symbol-sessions enter the sample. Input: the pre-open facts per symbol-session
uv run python -m scripts.spike2a.universe data/spike2a/preopen.csv

# Q4 — the measurement that matters
uv run python -m scripts.spike2a.q4_spreads data/spike2a/signal_bars.csv data/spike2a/quotes.csv

# Q2 — float staleness (and disagreement, once a second provider exists). No generator; needs
# a real provider extract.
uv run python -m scripts.spike2a.q2_float data/spike2a/floats.csv 2026-07-29

# Q3 — latency percentiles. No generator; needs a measured run.
uv run python -m scripts.spike2a.q3_latency data/spike2a/latency.csv
```

**`universe.py` does not filter to the windows `windows.py` selects** — §7 defines the sample as
every qualifying symbol-session *in the two windows*, and joining the two halves is an open
finding from review round 7, not a step you can run today. Until it is joined, `universe.py`
reports on whatever `preopen.csv` contains, and it is the caller's job to have restricted the file
to the selected sessions.

`IbkrHistoricalTicksFeed` needs `ib_insync`, which is **not** a package dependency and must not
become one — install it into a throwaway environment. Its default port is 7497, the TWS *paper*
socket, because §3.2 forbids live trading of any size for any reason and a default pointing at
the live socket is one typo from breaking that.

## Input schemas

| File | Columns |
|---|---|
| `vix.csv` | `date,close` |
| `preopen.csv` | `session,symbol,price,gap_premarket_pct,gap_daily_pct,rvol,adv_shares,float_shares[,halted_before_open,missing_nbbo_pct,soft_*]` |

**Units: `gap_premarket_pct`, `gap_daily_pct` and `missing_nbbo_pct` are fractions, not
percentages.** A 12% gap is `0.12`, not `12`. This matches the registry, where
`min_gap_premarket_pct` is `0.04`. Getting it wrong does not fail loudly on its own — `12 >= 0.04`
is true for every row, so the gap filter would stop rejecting anything, and `5 > 0.05` is true for
every row, so every session would be reported as a vendor coverage failure that never happened.
`PreOpenFacts.check_units()` therefore rejects any of the three above `1`, and `classify()` calls
it before anything else. `rvol` is *not* a fraction — `min_rvol` is a plain multiple of ADV.
| `signal_bars.csv` | `symbol,session,setup,price,r` |
| `quotes.csv` | `symbol,captured_at,bid,ask,bid_size,ask_size[,age_seconds]` |
| `floats.csv` | `symbol,provider,float_shares,as_of[,short_interest_shares]` |
| `latency.csv` | `kind,seconds[,note]` — `kind` is `data_to_signal` or `signal_to_order` |

### Two obligations the schemas cannot enforce

1. **Every `preopen.csv` value must be computed from data timestamped at or before 09:30 ET on
   `session`.** A gap computed from the day's close parses exactly as cleanly as one computed
   from the pre-market print. This is the survivorship boundary §4.1 calls the single most likely
   way to get a wrong answer to Q4, and no code here can check it.
2. **`signal_bars.r` must come from the library's own stop functions** —
   `gates.vwap_reclaim_stop` for §3.4, `gates.apply_stop_floor_and_ceiling` for the others. R is
   the denominator of the signal-time cap, so an R computed by hand means Q4 measures a stop rule
   that is not the shipped one.

## The guardrail

Convention 1 — no literal for a registered threshold — **is mechanical here.** The registry
lint's roots were extended from `src/tradipy/*.py` to include `scripts/` recursively, which
§8 called the prerequisite for this guardrail being a test rather than a policy. Planting
`Decimal("0.15")` in any module in this directory fails
`tests/test_parameter_registry.py::test_no_registered_literal_hardcoded_in_source` with a message
naming `max_spread_r`.

**Mechanical is not the same as green, and this file previously implied it was.** The commit after
the one that extended the lint added `synthetic_data_generator.py`, which tripped it five times; the
gate was red for two commits while four documents — this one among them — said the rule was
enforced, three statements across two of them going further and saying the tree was clean. Review
round 7 found it by running the test. The lesson is not about the lint, which
worked: run `make check` and read the output, because a sentence saying a check exists is not the
check's result.

The second obligation below is guarded by nothing at all, and it was the round-7 defect with teeth:
`synthetic_data_generator.py` claimed in its own docstring to derive R from the library's stop
functions while multiplying by a hand-written percentage. Correcting it moved the §7 Q4 verdict on
the same synthetic sample from INERT to CALIBRATED — so an R computed by hand is not a hygiene
matter, it changes the answer.

Spike-only acceptance thresholds — §7's 30%, 2%, 95%, p95 seconds — live in `prereg.py` as `int`
percents and counts. They are **not** registered parameters and must not become any: a registered
parameter is a tunable of the trading system, and these are the acceptance thresholds of one
investigation. `prereg.py`'s docstring lists the numeric coincidences with registered defaults so
no reader has to wonder whether one is a restatement.
