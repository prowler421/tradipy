# Phase 3 Readiness — Review Gate

> **Purpose:** Checklist for a formal review of whether Phase 3 (scanner / §4.2 hard filters)
> may start per PRD §12.1 and PLAN **D29**, and — since **D32** — of what its having been
> built on simulated data does and does not establish.  
> **Last updated:** 2026-07-31

Phase 3 is **not** "implement the scanner." It is **permitted to be trusted** only when Phase
2a has answered whether the scanner's input contract (§4.2) is obtainable from real data.

**What changed with D32.** Until D32 this document read that Phase 3 was not permitted to
*start*. D32 re-scoped D29's gate: it binds Phase 3's **calibration**, not its
**construction**, on the grounds that D30 had already removed ingestion from Phase 3's scope
and the parameter registry isolates the filter arithmetic from the numbers it applies. The
scanner is therefore **built** (`src/tradipy/scanner.py`, `python -m tradipy scan`), and the
blocking item below is **unchanged and still blocking**: no threshold in it is calibrated,
because Q1 is unanswered. Building it did not move that row and was not intended to.

---

## Gate matrix

| Requirement | Source | Status | Evidence |
|-------------|--------|--------|----------|
| Invariant layer sound | WS11 / rounds 7–9 | **Unverified here** | Suite green; **`make check` must be re-run** — see the note below |
| Phase 2a pre-registration committed | PHASE-2A-SPIKE §7 | **Met** | Byte-stable since 2026-07-29 |
| Phase 2a instrumentation | `scripts/spike2a/` | **Met** | Seven entry points behind the provenance gate, H4/H6 schema |
| §4.2 implemented against the document | D32 | **Met** | `HARD_FILTERS` / `SOFT_FILTERS` compared to §4.2's parsed table in both directions (`tests/test_scanner.py`) |
| Soft rows cannot reject; D24 row inert | D24, round 10 K5 | **Met** | Separate `SoftFlag` type; violation performed in `tests/test_enforcement.py` |
| **Q1 answered on measured data** | D29, §5.5 | **Not met** | [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) |
| **§4.2 thresholds calibrated** | D29, D32 | **Not met** | Follows from the row above — nothing has been measured to calibrate against |
| §4 matches reality (if Q1 negative) | D29 | **N/A** | Q1 not run |
| Q2–Q4 measured or explicitly deferred | PHASE-2A-SPIKE §6 | **Partial** | Pipeline validated; measurements pending PAPER |
| D30 ladder at PAPER for data reads | D30 | **Not met** | `PERMITTED_ORIGINS = {SIMULATED}`; D32 did not move it |
| Workstream 11 cold read | PLAN WS11 | **Not met** | Now covers `scanner.py` as well |

**Note on the first row, which this document got wrong.** It read *"**Met** — `make check`
green"* when Phase 3 landed, and that evidence was asserted from a passing test suite rather
than from the gate, by a party that had not run the gate. Review round 11 ran it: **red** —
eleven `ruff check` errors (ten `B008` from `Decimal(...)` calls in `poc._sim`'s defaults, one
`SIM300`), two files that had been hand-edited past `ruff format`, and three `basedpyright`
errors from an inline `sorted(..., key=lambda)` inside `pytest.mark.parametrize`. All were
introduced by Phase 3; all are fixed; **none of that is this row's evidence until someone runs
`make check` and says so.** The row now states what was observed rather than what was
expected, which is the whole point of the column.

That failure is worth naming beyond the lint errors themselves. This repository exists because
six review rounds each found a class of defect the previous check could not see, and the fifth
is *a guarantee believed enforced and not*. A readiness document asserting a gate is green
without running it is that class applied to the gate's own evidence column — and the sentence
was written into the same changeset it was describing.

**Verdict, in two parts.**

- **Phase 3 construction: done** (D32). The scanner applies §4.2 correctly and is tested to.
- **Phase 3 calibration: not gated open, and cannot be** until **Q1 on measured data** after
  D31 (PAPER rung). One blocking item, unchanged.

Nothing downstream inherits a pass from the first bullet. Phase 4 depends on a Phase 3 whose
numbers are unvalidated, and §12.1's Phase 3 dependency row is not ticked.

---

## What "Phase 3 review" can mean today

A review round **can** be conducted now to:

1. Confirm instrumentation and documentation gaps from rounds 7–8 are closed (H4, H6, H7, I1).
2. Sign off on [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) as an honest partial completion.
3. Review the D31 decision draft and TEST_SETUP runbook before any market connection.
4. Review `src/tradipy/scanner.py` against §4.2 and §4.3 — which is now a code review with a
   document to check it against, where before it was a plan review.
5. **Not** approve any §4.2 threshold as calibrated until Q1 is measured.

A review round **cannot** honestly call Phase 3 finished without violating D29 as D32 leaves
it. "The filters are right" and "the numbers are right" are different claims and only the
first is currently supportable.

---

## Remaining gaps (ordered)

### 1. Advance data ladder — D31 (blocking for calibration)

- Record decision in `docs/PLAN.md` and `docs/CHANGELOG.md`. **The number is still free** —
  D32 deliberately did not take it, because four documents already forward-reference D31 as
  the ladder advance.
- Set `PERMITTED_ORIGINS` to `{SIMULATED, PAPER}` in `scripts/spike2a/provenance.py` (test-pinned).
- Relax import denylist for `scripts/spike2a/` collectors only, or restore lazy `ib_insync` in
  `feeds.py` with explicit allowlist — see [TEST_SETUP.md](../scripts/spike2a/TEST_SETUP.md).
- Restore or rewrite `q4_collect_*` and latency collectors (recoverable at git `3ca9e7b`).

Note that `src/tradipy/scanner.py` is **not** affected by this step and must not become
affected by it: its import allowlist is asserted in `tests/test_enforcement.py`, and a
scanner that grows a feed is Phase 2's work landing in the wrong module.

### 2. Execute Phase 2a measurements (blocking for D29)

| Step | Command / artifact | Unblocks |
|------|-------------------|----------|
| Historical NBBO | Collector → `quotes.csv` + `signal_bars.csv` with `signal_at` | Q4 §7 verdict |
| Vendor trial | Q1 script / manual trial log | §4.2 calibration go/no-go |
| Second float provider | `floats.csv` with two providers | Q2 disagreement half |
| Paper timestamps | `latency.csv` from paper gateway | Q3 |

### 3. Disposition measured outcomes (after step 2)

- If Q1 **negative:** rewrite PRD §4 per PHASE-2A-SPIKE §6, then edit `HARD_FILTERS` and the
  registry rows to match. D32's bet is that this is a table edit rather than a rewrite; that
  bet is settled here, and if it loses, say so.
- If Q4 **recalibrates** `max_spread_r`: D7 decision + `params.py` + tests.
- Update [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) and PLAN Phase 2a row → **Done**.

### 4. Recommended, non-blocking

- Workstream 11 cold read (no prior context) — now with `scanner.py` in scope.
- Re-run mutation testing (H13), including the seven hard filters.
- WS9 interface decision — promote `QuoteFeed` or keep spike-local.
- Settle the §4.2 readings the scanner had to take and recorded rather than resolve — the
  LULD proportion, the Gap %/`pct_change` identification, days vs sessions, and the rest.
  [CHANGELOG.md](CHANGELOG.md)'s spec-question table is the list; each is localized to one
  function or one registry row and pinned by a test.

---

## What Phase 3 built

All fourteen §4.2 rows are implemented; per **K5**, only **7 of them reject**. §12.1 states no
count, and the 14 is the whole table. The distinction the K5 finding turns on is *rejection
paths*, not rows touched — a scanner that ignored the soft half could not rank, because two
soft rows are §20.10 inputs:

- **Hard (reject):** Gap %, Relative Volume, Float, Price Range, Average Daily Volume,
  Circuit Breakers, Liquidity / Spread. Codes on `Reject`.
- **Soft (flag, never reject):** Premarket Volume, Market Cap, Volatility (ATR),
  News / Catalyst, Recent Halts, Institutional Ownership, Short Interest. Codes on a separate
  `SoftFlag` type, so K5's failure mode — building the soft half as rejection paths, with
  `INST_OWN_HIGH` among them — is a type error rather than a review finding.
- **Ranked**, per §4.1's pipeline and §12.2 item 1, by the existing §20.10 composite score,
  cut to `watchlist_size`. This resolved an ambiguity no document had: this file previously
  said the MVP scanner needs "only hard filters… not full soft-filter scoring", while §12.2
  item 1 says "ranked watchlist" and §4.1/§4.3 make ranking a function of §20.10. Resolved
  toward the PRD, which is normative. Two soft rows (`PREMARKET_THIN`, `NO_CATALYST`) are
  §20.10 inputs, which is why the soft half could not simply be omitted.
- **Written fresh** against the PRD — not grown from `scripts/spike2a/` (PHASE-2A-SPIKE §8).
- **Sources nothing.** §4.1's universe is Phase 2 ingestion and its catalyst check is §12.2's
  one manual step; both arrive as inputs.

---

## Review checklist

- [x] [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) reviewed and accepted as partial completion
- [x] H4/H6 schema change verified (`signal_at`, `quote_at_or_before`, tests green)
- [x] H7 disposition accepted (synthetic ≠ data pull)
- [x] D32 recorded before any Phase 3 code landed, with its cost stated
- [x] `HARD_FILTERS` / `SOFT_FILTERS` checked against §4.2 by parsing the document
- [x] Every hard filter shown reachable; every soft flag shown unable to reject
- [ ] D31 recorded before any `PAPER` data lands in `data/spike2a/`
- [ ] Q1 measured; §4 and the registry updated if negative
- [ ] PLAN Phase 2a row set to **Done**
- [ ] Any §4.2 threshold described as *calibrated* anywhere

The last box is phrased as a trap on purpose. It should stay unticked, and anything that
ticks it needs measured data behind it.
