# `scripts/spike2a/` — Phase 2a data feasibility spike

**Throwaway investigative code.** Scope, method and the binding pre-registration are in
[docs/PHASE-2A-SPIKE.md](../../docs/PHASE-2A-SPIKE.md). This file says how to run it and what it
is not.

> **The spike is suspended by [PLAN](../../docs/PLAN.md) D30.** Every dataset here is simulated,
> the two collectors that pulled real IBKR ticks are gone, and §7 binds its thresholds to
> measured data — so **nothing in this directory can answer Q1–Q4**. What runs, runs on
> fabricated input and reports a *pipeline outcome*. [TEST_SETUP.md](TEST_SETUP.md) records what
> advancing the ladder costs.

`provenance.py` is the exception to "throwaway": it is the D30 gate, the measurement modules
refuse to run without it, and `tests/test_enforcement.py` tests it.

## What this is not

§8 of the spike document names the failure mode: *"the spike code works, and it becomes the
scanner by accretion."* So:

- nothing here is imported by `src/tradipy/`, and nothing here ever should be;
- there is no test-coverage obligation on this directory;
- if Q1 comes back positive, **Phase 3 is written fresh against the PRD**, not grown from here.

## Status of each question

| Q | What it needs | Runnable now |
|---|---|---|
| **Q1** — real-time candidate list | Vendor trials | **Pipeline yes, answer no.** `q1_vendors` applies §7's Q1 thresholds to a declared trial matrix; on simulated input it prints a pipeline outcome, not a §7 verdict. IBKR alone remains a *pre-determined* negative on measured data: §7 requires ≥ 200 concurrent symbols and §1 records IBKR's ~100 market-data line cap |
| **Q2** — float / short-interest quality | Two independent providers | **Pipeline yes, answer no.** Both staleness and disagreement conditions execute on the generator's two-provider `floats.csv`; on simulated input the A10 disposition is **withheld** |
| **Q3** — latency | Paper connection | **Pipeline yes, answer no.** The percentile logic runs on the generator's `latency.csv`; on simulated input the §5.5/§4.4 disposition is **withheld entirely** |
| **Q4** — realized spread distribution | Historical intraday NBBO | **The pipeline runs, on declared simulated CSVs, and reports a pipeline outcome rather than a §7 verdict.** Whether the IBKR paper tier serves `reqHistoricalTicks` BID_ASK for a 400-symbol-session sample is **unverified** — see [TEST_SETUP.md](TEST_SETUP.md) for the three limits to check |

Under D30 none of the four is answerable; the column says what *executes*, not what is settled.

Q4 runs first. §7's budget clause makes that binding rather than advisory: it needs no
subscription, so a budget overrun cannot cost the one answer that can invalidate a shipped
default.

## Running it

Every measurement module is stdlib-only and takes CSV input, so the whole pipeline runs with no
broker, no subscription and no network. Run from the repository root.

**`data/spike2a/` is gitignored and empty on a clean clone**, so nothing below runs until the
files exist. `synthetic_data_generator.py` fabricates all seven spike inputs
(`vix.csv`, `preopen.csv`, `signal_bars.csv`, `quotes.csv`, `floats.csv`, `latency.csv`,
`vendors.csv`) plus `PROVENANCE.txt` — enough to exercise Q1–Q4 end to end. No number computed
from that output answers Q1–Q4.

**Declaration is not optional.** The generator writes a `PROVENANCE.txt` naming `origin
SIMULATED` and listing each file with its SHA-256. **All seven measurement entry points** —
`windows`, `universe`, `sample`, `q1_vendors`, `q2_float`, `q3_latency`, `q4_spreads` — call
`provenance.require` before reading anything and exit `3` if a file is missing from it, has
changed since, or declares an origin D30 does not permit. Undeclared data is refused rather than assumed simulated.

For input the generator does not cover, declare it by hand:

```bash
uv run python -m scripts.spike2a.provenance data/spike2a/latency.csv
```

That **merges** into the existing marker rather than replacing it, so a hand-authored declaration
and the generator's files coexist. The generator does not merge — it rewrites the marker with
its own seven files, so **re-declare hand-authored input after regenerating**. Editing any declared
file also breaks its digest, which is the mechanism working, not a bug.

```bash
# Fabricate all spike inputs + PROVENANCE.txt. Synthetic.
uv run python -m scripts.spike2a.synthetic_data_generator

# The two §7 sample windows, chosen by the VIX rule. Input: date,close
uv run python -m scripts.spike2a.windows data/spike2a/vix.csv 2026-07-29

# Which symbol-sessions pass the §4.2 filter rule, over whatever the file contains — see below
# for why this is not yet the §7 sample on its own
uv run python -m scripts.spike2a.universe data/spike2a/preopen.csv

# The full §7 sample: the two selected windows, then the filter rule applied within them
uv run python -m scripts.spike2a.sample data/spike2a/vix.csv data/spike2a/preopen.csv 2026-07-29

# Q1 — vendor trial matrix (pipeline outcome on SIMULATED input)
uv run python -m scripts.spike2a.q1_vendors data/spike2a/vendors.csv

# Q4 — the measurement that matters
uv run python -m scripts.spike2a.q4_spreads data/spike2a/signal_bars.csv data/spike2a/quotes.csv

# Q2 — float staleness and disagreement (A10 disposition withheld on SIMULATED input)
uv run python -m scripts.spike2a.q2_float data/spike2a/floats.csv 2026-07-29

# Q3 — latency percentiles (disposition withheld on SIMULATED input)
uv run python -m scripts.spike2a.q3_latency data/spike2a/latency.csv
```

**`universe.py` alone does not filter to the windows `windows.py` selects, and that is by
design.** §7 defines the sample as every qualifying symbol-session *in the two windows*;
`universe.select_sample` applies only the filter half, unchanged, so a caller can run it directly
against a file already restricted by other means — see `universe.py`'s own module docstring, which
now states this. `sample.py` is the join — it computes the windows from a VIX series, restricts a
pre-open file to them, then calls `universe.select_sample` on what remains, reporting sessions
outside the windows as their own count rather than mixing them into a filter rejection or a §7
exclusion, and every parsed row is unit-checked regardless of window membership (a malformed row
outside the windows would otherwise never reach `universe.classify`, the only other caller of that
guard). "Outside windows" further splits into a session genuinely not selected by §7's window rule
and a session inside a window's calendar range but missing from the VIX series — the latter is a
disagreement between `vix.csv` and `preopen.csv`, not a property of the sample definition, and
`sample.py`'s CLI prints it as its own line when it occurs. This closes review round 7's H5; see
`docs/CHANGELOG.md`'s "Decided" section under Unreleased for why a composing module was chosen
over the other two options that finding named, and for the two further defects a read-only review
caught before merge.

**There is no broker-backed feed to run instead.** `IbkrHistoricalTicksFeed` was removed by D30
along with the two collectors, and no broker SDK, vendor client or network module may be imported
in `src/`, `scripts/` or `tests/` — `tests/test_enforcement.py` fails on any of the twenty roots
it enumerates. Twenty, not all: it is a denylist, and a new vendor's client is not on it.

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
| `signal_bars.csv` | `symbol,session,setup,price,r,signal_at` — `signal_at` is ISO 8601 UTC; Q4 selects the last quote at or before it |
| `quotes.csv` | `symbol,captured_at,bid,ask,bid_size,ask_size[,age_seconds]` |
| `floats.csv` | `symbol,provider,float_shares,as_of[,short_interest_shares]` |
| `latency.csv` | `kind,seconds[,note]` — `kind` is `data_to_signal` or `signal_to_order` |
| `vendors.csv` | `provider,monthly_cost_usd,concurrent_symbols,refresh_seconds,sample_coverage_pct,hard_filters_expressible[,notes]` — `hard_filters_expressible` is `true`/`false` or `yes`/`no` |

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

Convention 9 — all data is simulated — **is mechanical here too.** An import lint over `src/`,
`scripts/` and `tests/` fails on any of twenty enumerated broker, vendor and network roots;
`provenance.py` refuses undeclared input at all seven entry points; and the §7 verdict wording is
unreachable on simulated data. Each has a
test that performs the violation, and each was checked by removing the guard and confirming the
test goes red — the discipline the `guarantee-test` skill exists for.

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

The second obligation below **is now guarded, by a test rather than by the schema** — it was the
round-7 defect with teeth: `synthetic_data_generator.py` claimed in its own docstring to derive R
from the library's stop functions while multiplying by a hand-written percentage. Correcting it
moved the §7 Q4 verdict on the same synthetic sample from INERT to CALIBRATED — so an R computed by
hand is not a hygiene matter, it changes the answer. The schema still cannot enforce it —
`signal_bars.csv`'s `r` column parses identically regardless of how it was derived — but the
generator now is: `tests/test_spike2a_instrumentation.py` asserts by AST that `generate_signal_bars`
calls `apply_stop_floor_and_ceiling` and by runtime that `R = entry − stop`, and reintroducing the
hand-derived fraction fails both immediately.

Spike-only acceptance thresholds — §7's 30%, 2%, 95%, p95 seconds — live in `prereg.py` as `int`
percents and counts. They are **not** registered parameters and must not become any: a registered
parameter is a tunable of the trading system, and these are the acceptance thresholds of one
investigation. `prereg.py`'s docstring lists the numeric coincidences with registered defaults so
no reader has to wonder whether one is a restatement.
