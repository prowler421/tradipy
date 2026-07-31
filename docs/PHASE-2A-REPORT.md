# Phase 2a — Completion Report

> **Status:** Instrumentation complete; **measured answers pending PAPER rung** (PLAN D30).  
> **Date:** 2026-07-31  
> **Binding pre-registration:** [PHASE-2A-SPIKE.md](PHASE-2A-SPIKE.md) §7, committed 2026-07-29, unchanged.

This report satisfies PHASE-2A-SPIKE §6's exit criterion — each question states a number and a
method, and any unanswered question records why — without claiming a §7 verdict where the data
ladder forbids one.

---

## Executive summary

| Question | Method | Measured answer | Status |
|----------|--------|-----------------|--------|
| **Q1** — real-time §4.2 candidate list | Vendor trial + §7 pass thresholds | — | **Unanswered** — D30; no PAPER data read |
| **Q2** — float / short-interest quality | Two-provider disagreement + staleness | — | **Unanswered** — needs measured `floats.csv` |
| **Q3** — latency | Paper connection timestamps | — | **Unanswered** — needs measured `latency.csv` |
| **Q4** — spread distribution / `max_spread_r` | `q4_spreads` on NBBO + signal bars | Pipeline exercised; **1.36%** aggregate rejection on synthetic sample | **Pipeline validated only** — not a §7 verdict |

**Phase 2a gate for Phase 3 (D29):** **Not passed.** Q1 must be answered on measured data before
PRD §4's scanner input contract is trusted. Instrumentation, pre-registration, and D30 guards are
complete; the remaining step is advancing the data ladder to `PAPER` and executing the spike (see
[PHASE-3-READINESS.md](PHASE-3-READINESS.md) and [scripts/spike2a/TEST_SETUP.md](../scripts/spike2a/TEST_SETUP.md)).

---

## What was completed in this interval

### Code and guards (rounds 7–8)

- **H5:** `scripts/spike2a/sample.py` joins window selection and universe filtering.
- **H3 / sixth defect class:** `tests/test_spike2a_instrumentation.py` guards R derivation.
- **D30:** `provenance.py` gates all six spike entry points; simulated runs print *pipeline
  outcome*, not §7 verdict.
- **H4 / H6 (2026-07-31):** `signal_bars.csv` carries `signal_at`; `quote_at_or_before` selects
  the NBBO in force at that instant and derives `age_seconds` for §20.14 validity.

### Pipeline exercise (simulated)

Regenerated with `uv run python -m scripts.spike2a.synthetic_data_generator` at commit after H4/H6:

| Artifact | Count |
|----------|------:|
| Symbol-sessions (`preopen.csv`) | 156 |
| Signal bars | 147 |
| NBBO samples | varies by run (deduped per symbol/instant) |

`q4_spreads` on simulated input reports **pipeline outcome (NOT a §7 verdict)** — by design under
D30.

---

## Per-question detail

### Q1 — Real-time candidate list

**Pass threshold (§7):** ≥95% of sample symbol-sessions as candidates; full §4.2 hard set;
≥200 concurrent symbols; refresh ≤60 s; ≤$500/month all-in.

**Finding:** Not run. IBKR alone is a **pre-determined negative** for the 200-symbol clause
(~100 market-data line cap vs §7's 200). A second vendor trial is required regardless of IBKR
paper connectivity.

**Reason recorded:** PLAN D30 — project reads `SIMULATED` only until a recorded decision advances
`PERMITTED_ORIGINS` to include `PAPER`.

### Q2 — Float quality

**Pass threshold (§7):** Disagreement >10% on >15% of symbols, or >10% of floats older than 30
days, trips A10.

**Finding:** Not run. `q2_float` correctly returns `UNANSWERED` for disagreement with zero
providers and **withholds** A10 disposition on simulated input.

### Q3 — Latency

**Pass threshold (§7):** p95 data-to-signal >30 s or p95 signal-to-order >2 s fails §5.5
assumption.

**Finding:** Not run. Collection scripts removed under D30; `q3_latency` withholds §5.5/§4.4
disposition on simulated input.

### Q4 — Spread distribution

**Pass thresholds (§7):** Recalibrate if >30% rejected (aggregate or cheap decile); inert if <2%
every decile; else calibrated.

**Finding (simulated pipeline only):** Last run before this report: aggregate rejection rate
**~1.36%** with elevated cheap-decile rate — **pipeline outcome CALIBRATED by elimination**, not a
§7 verdict. Numbers validate arithmetic and wiring only.

---

## Open spec questions (unchanged disposition)

| ID | Question | Impact on Phase 3 |
|----|----------|-------------------|
| **H7** | Does a synthetic run count as a §7 data pull? | **Decided:** no — see [CHANGELOG.md](CHANGELOG.md) Unreleased |
| **H2** | Narrow PHASE-2A-SPIKE §8 coverage exemption? | Does not block Phase 3 start |
| **H10** | §7 exclusions inert on generated fixtures | Documented; does not block |

---

## Next action to close the Phase 2a gate

1. Record **D31** — advance ladder to `PAPER` (edit `PERMITTED_ORIGINS` + PLAN decision).
2. Restore/build collectors per [TEST_SETUP.md](../scripts/spike2a/TEST_SETUP.md).
3. Run Q4 first (§7 budget ordering), then Q1 vendor trial, Q2 second provider, Q3 paper timestamps.
4. Update this report with measured outcomes; disposition any PRD changes in `docs/CHANGELOG.md`.
5. Set PLAN Phase 2a row to **Done** only after Q1 is answered (positive or negative with §4 rewrite).

See [PHASE-3-READINESS.md](PHASE-3-READINESS.md) for the Phase 3 review gate checklist.
