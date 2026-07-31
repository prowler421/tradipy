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
| **Q4** — spread distribution / `max_spread_r` | `q4_spreads` on NBBO + signal bars | Pipeline exercised; **0.64%** aggregate rejection on the synthetic sample at `e85a193` (see caveat below) | **Pipeline validated only** — not a §7 verdict |

**Phase 2a gate for Phase 3 (D29):** **Not passed.** Q1 must be answered on measured data before
PRD §4's scanner input contract is trusted. Instrumentation, pre-registration, and D30 guards are
complete; the remaining step is advancing the data ladder to `PAPER` and executing the spike (see
[PHASE-3-READINESS.md](PHASE-3-READINESS.md) and [scripts/spike2a/TEST_SETUP.md](../scripts/spike2a/TEST_SETUP.md)).

---

## What was completed in this interval

### Code and guards (rounds 7–8)

- **H5:** `scripts/spike2a/sample.py` joins window selection and universe filtering.
- **H3 / sixth defect class:** `tests/test_spike2a_instrumentation.py` guards R derivation.
- **D30:** `provenance.py` gates all seven spike entry points — `windows`, `universe`, `sample`,
  `q1_vendors`, `q2_float`, `q3_latency`, `q4_spreads`; simulated runs print *pipeline outcome*, not
  §7 verdict.
- **H4 / H6 (2026-07-31):** `signal_bars.csv` carries `signal_at`; `quote_at_or_before` selects
  the NBBO in force at that instant and derives `age_seconds` for §20.14 validity.

### Pipeline exercise (simulated)

Regenerated with `uv run python -m scripts.spike2a.synthetic_data_generator`. The generator is
seeded (`SEED = 42`, seeded inside `main()`), so these counts are reproducible and do **not** vary
between runs at the same commit — `PROVENANCE.txt` records each one beside its file digest.

| Artifact | At `b70fa7a` | At `e85a193` |
|----------|-------------:|-------------:|
| Symbol-sessions (`preopen.csv`) | 156 | 156 |
| Signal bars | 147 | 157 |
| NBBO samples | 8,820 | 3,566 |
| Q4 aggregate rejection | 1.36% (2/147) | 0.64% (1/157) |
| Q4 worst decile | d1 14.29% | d1 6.67% |

> **Regenerate before quoting the right-hand column.** The `b70fa7a` figures were verified by
> [REVIEW-2026-07-31.md](reviews/REVIEW-2026-07-31.md) under `pytest` on the project's own toolchain.
> The `e85a193` figures were reproduced by [claude-PHASE-3-REVIEW.md](reviews/claude-PHASE-3-REVIEW.md)
> (finding K1) on CPython 3.10 under a stdlib stand-in, because no 3.13 build was available to it —
> so they are correct relative to `b70fa7a` measured the same way, and should be re-run on 3.13
> before being cited elsewhere. The figures previously recorded here were `b70fa7a`'s, carried into
> the commit that rewrote the generator.

`q4_spreads` on simulated input reports **pipeline outcome (NOT a §7 verdict)** — by design under
D30 — and did so at every commit in the interval.

---

## Per-question detail

### Q1 — Real-time candidate list

**Pass threshold (§7):** ≥95% of sample symbol-sessions as candidates; full §4.2 hard set;
≥200 concurrent symbols; refresh ≤60 s; ≤$500/month all-in.

**Finding:** Not run. `q1_vendors` applies §7's thresholds to a declared trial matrix and
**withholds** its §7 verdict on simulated input, same as Q2 and Q3. IBKR's market-data line cap
(~100 concurrent symbols against §7's required 200) would be a **pre-determined negative** for the
200-symbol clause **if confirmed** — but that figure is currently **unsourced**: no IBKR
documentation is cited for it, and the only place it appears in this repository is one row of
`data/spike2a/vendors.csv`, which is generated, declared `SIMULATED`, and whose generator docstring
says its numbers were chosen to exercise the pipeline's pass/fail branches, not to describe IBKR.
Treat ~100 as a plausible estimate pending a cited vendor document or an actual trial, not as a
measured fact — see [claude-PHASE-3-REVIEW.md](reviews/claude-PHASE-3-REVIEW.md) finding K4. A
second vendor trial is required regardless of IBKR paper connectivity.

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

**Finding (simulated pipeline only):** at `e85a193`, aggregate rejection rate **0.64%** (1/157) with
the cheapest decile the only elevated one (d1 **6.67%**) — **pipeline outcome CALIBRATED by
elimination**, not a §7 verdict. Numbers validate arithmetic and wiring only. See the caveat under
"Pipeline exercise" above, and finding K1 in
[claude-PHASE-3-REVIEW.md](reviews/claude-PHASE-3-REVIEW.md).

---

## Spec questions raised by rounds 7–8, and where each now stands

| ID | Question | Impact on Phase 3 |
|----|----------|-------------------|
| **H7** | Does a synthetic run count as a §7 data pull? | **Decided in this interval:** no — see [CHANGELOG.md](CHANGELOG.md), Decided. How that decision was taken is finding K7 of [claude-PHASE-3-REVIEW.md](reviews/claude-PHASE-3-REVIEW.md) |
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
