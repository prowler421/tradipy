# Phase 3 Readiness — Review Gate

> **Purpose:** Checklist for a formal review of whether Phase 3 (scanner / §4.2 hard filters) may
> start per PRD §12.1 and PLAN **D29**.  
> **Last updated:** 2026-07-31

Phase 3 is **not** "implement the scanner." It is **permitted to start** only when Phase 2a has
answered whether the scanner's input contract (§4.2) is obtainable from real data.

---

## Gate matrix

| Requirement | Source | Status | Evidence |
|-------------|--------|--------|----------|
| Invariant layer sound | WS11 / rounds 7–8 | **Met** | `make check` green; `src/tradipy/` unchanged since round 7 |
| Phase 2a pre-registration committed | PHASE-2A-SPIKE §7 | **Met** | Byte-stable since 2026-07-29 |
| Phase 2a instrumentation | `scripts/spike2a/` | **Met** | Six entry points, provenance gate, H4/H6 schema |
| **Q1 answered on measured data** | D29, §5.5 | **Not met** | [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) |
| §4 matches reality (if Q1 negative) | D29 | **N/A** | Q1 not run |
| Q2–Q4 measured or explicitly deferred | PHASE-2A-SPIKE §6 | **Partial** | Pipeline validated; measurements pending PAPER |
| D30 ladder at PAPER for data reads | D30 | **Not met** | `PERMITTED_ORIGINS = {SIMULATED}` |
| Workstream 11 cold read | PLAN WS11 | **Not met** | Recommended before Phase 3 *implementation*, not D29 gate |

**Verdict for Phase 3 start:** **Not ready.** One blocking item: **Q1 on measured data** after D31
(PAPER rung).

---

## What "Phase 3 review" can mean today

A review round **can** be conducted now to:

1. Confirm instrumentation and documentation gaps from rounds 7–8 are closed (H4, H6, H7, I1).
2. Sign off on [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) as an honest partial completion.
3. Review the D31 decision draft and TEST_SETUP runbook before any market connection.
4. **Not** approve Phase 3 implementation until Q1 is measured.

A review round **cannot** honestly approve Phase 3 start without violating D29.

---

## Remaining gaps (ordered)

### 1. Advance data ladder — D31 (blocking)

- Record decision in `docs/PLAN.md` and `docs/CHANGELOG.md`.
- Set `PERMITTED_ORIGINS` to `{SIMULATED, PAPER}` in `scripts/spike2a/provenance.py` (test-pinned).
- Relax import denylist for `scripts/spike2a/` collectors only, or restore lazy `ib_insync` in
  `feeds.py` with explicit allowlist — see [TEST_SETUP.md](../scripts/spike2a/TEST_SETUP.md).
- Restore or rewrite `q4_collect_*` and latency collectors (recoverable at git `3ca9e7b`).

**Cost:** Connects the repository to read-only market data; reverses D30's "simulated only"
posture for spike inputs only — not LIVE trading.

### 2. Execute Phase 2a measurements (blocking for D29)

| Step | Command / artifact | Unblocks |
|------|-------------------|----------|
| Historical NBBO | Collector → `quotes.csv` + `signal_bars.csv` with `signal_at` | Q4 §7 verdict |
| Vendor trial | Q1 script / manual trial log | Phase 3 go/no-go |
| Second float provider | `floats.csv` with two providers | Q2 disagreement half |
| Paper timestamps | `latency.csv` from paper gateway | Q3 |

### 3. Disposition measured outcomes (after step 2)

- If Q1 **negative:** rewrite PRD §4 per PHASE-2A-SPIKE §6, then Phase 3.
- If Q4 **recalibrates** `max_spread_r`: D7 decision + `params.py` + tests.
- Update [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) and PLAN Phase 2a row → **Done**.

### 4. Recommended before Phase 3 *implementation* (non-blocking for D29)

- Workstream 11 cold read (no prior context).
- Re-run mutation testing (H13).
- WS9 interface decision — promote `QuoteFeed` or keep spike-local.

---

## Phase 3 scope reminder (when gate opens)

From PRD §12.1:

- **Phase 3:** Scanner implementing §4.2 **hard filters** (14 filters, rejection codes in WS4).
- **Written fresh** against the PRD — not grown from `scripts/spike2a/` (PHASE-2A-SPIKE §8).
- **Depends on:** Phase 2a gate passed, not Phase 2 market-data ingestion alone.

MVP scanner needs only hard filters for the three MVP setups' universe — not full soft-filter
scoring (Phase 4 strategy engine).

---

## Review checklist (for round 9 or human sign-off)

- [ ] [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) reviewed and accepted as partial completion
- [ ] H4/H6 schema change verified (`signal_at`, `quote_at_or_before`, tests green)
- [ ] H7 disposition accepted (synthetic ≠ data pull)
- [ ] D31 recorded before any `PAPER` data lands in `data/spike2a/`
- [ ] Q1 measured; §4 updated if negative
- [ ] PLAN Phase 2a row set to **Done**
- [ ] Explicit "Phase 3 may start" line added to PLAN sequencing table
