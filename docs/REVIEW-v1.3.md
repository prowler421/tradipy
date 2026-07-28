# Full Review — PRD v1.3, PLAN, and the Source Prompt

**Scope:** [PRD.md](PRD.md) (2,200 lines, v1.3) · [PLAN.md](PLAN.md) (323) · [CHANGELOG.md](CHANGELOG.md) (104) · [PROMPT-REVIEW.md](PROMPT-REVIEW.md) (215) · [REVIEW-v1.2.md](REVIEW-v1.2.md) (233) · [prompts/ross_cameron_trading_system.pdf](../prompts/ross_cameron_trading_system.pdf)

**Reviewed:** 2026-07-28 · **Purpose:** consistency clearance before coding begins.

**Method:** all worked examples recomputed programmatically, including under both rounding conventions; the new §3.1.3 spread gate independently re-derived; every cross-document identifier (A/D/V-ids), the PLAN table of contents, and every threshold stated in both documents machine-compared; all 23 REVIEW-v1.2 dispositions spot-verified in place.

---

## 1. Verdict

**The documents are consistent enough to start coding.** That was not true at v1.0, v1.1, or v1.2.

What closed since v1.2 is not just the 22 findings but the *class* of failure. The v1.2 defect was "a threshold restated in two places, one updated." This time the spread change propagated correctly and completely: §3.1.3 defines the two gates, §4.2's filter row was rewritten to reference them by name, §15's liquidity row was rewritten, §21.6 added the rejection-rate metric that monitors the calibration, and §21.1 encodes a fixture that breaks CI if any of the four parameters is loosened. That is the first change in this project's history to land in every place it touches.

**Verified clean:**

| Check | Result |
|---|---|
| Worked-example arithmetic (R, T1, T2, ordering, shares, max loss) | All 3 correct |
| Cost-as-%-of-R claims under the old 1% filter (83% / 80% / 60%) | Reproduce exactly |
| A-ids | 24 defined, **all** referenced, **none** orphaned |
| V-ids | 7 defined, all referenced |
| PLAN table of contents vs PRD headings | 22 = 22, zero mismatches |
| Thresholds stated in both PRD and PLAN | No divergence found |
| §9.3 event-flow arrows | Every arrow carries a §9.2 type |
| Kill-switch path (§7.2 vs §21.5) | Consistent — both `$XDG_STATE_HOME`, `/tmp` explicitly rejected |
| §-references to prompt/PROMPT-REVIEW sections | All correctly attributed, none ambiguous |
| Encoding | Clean UTF-8, zero mojibake across all 5 files |

**§8.3 of REVIEW-v1.2 is the best finding in this project's review history.** It identified a third defect class — two individually-correct parameters that cannot jointly hold — that neither worked-example fixtures nor a parameter registry would have caught, because every value appeared exactly once and each was defensible alone. The correction to my own denominator (14 tradeable setups, not 26) is also right, and I had introduced that error by applying a corrected total to the wrong population.

**Six items remain.** One is a live formula ambiguity that will produce wrong code; the rest are consistency housekeeping.

---

## 2. Findings

### 2.1 BLOCKING — §3.1.3's stated formula contradicts every table that applies it

`§3.1.3` states the signal-time gate as:

```
require:  spread_at_signal ≤ ceil_to_tick(max_spread_r × R)
```

Its own "Robustness invariant" table computes the widest admitted spread using **floor**, not ceil:

| Setup | R | `0.15 × R` | Table says | ceil_to_tick | floor_to_tick |
|-------|---|-----------|-----------|-------------|--------------|
| §3.2 Bull Flag | $0.12 | 0.0180 | **$0.01** | $0.02 | **$0.01** ✓ |
| §3.3 HOD | $0.15 | 0.0225 | **$0.02** | $0.03 | **$0.02** ✓ |
| §3.4 VWAP Reclaim | $0.10 | 0.0150 | **$0.01** | $0.02 | **$0.01** ✓ |

All three match floor. None matches the stated `ceil_to_tick`.

**This is not cosmetic.** Re-deriving the invariant under the formula as written:

| Setup | Cap (ceil) | Separation floor required | Actual T2−T1 | Margin |
|-------|-----------|--------------------------|-------------|--------|
| §3.2 Bull Flag | $0.02 | $0.11 | $0.11 | **+$0.00** |
| §3.3 HOD | $0.03 | $0.14 | $0.22 | +$0.08 |
| §3.4 VWAP Reclaim | $0.02 | $0.11 | $0.12 | +$0.01 |

Under ceil the invariant still passes, but Bull Flag passes with **exactly zero margin** — one tick of drift in any input flips it to failing. Under floor it has $0.03. The section's claim that the examples clear their floor "at the widest spread their own filters admit" is therefore true under floor and marginally-true-by-luck under the formula it prints.

**Compounding this, D19's rounding rule points the wrong way for a cap.** D19 specifies "stops down, targets up, **gate thresholds up**" as uniformly conservative. That holds for a *floor* you must exceed — rounding it up is stricter. It inverts for a *ceiling* you must stay under: rounding a maximum spread up **admits wider spreads**. D19 as written makes the spread gate more permissive while claiming to be conservative.

**Fix:** amend D19 and §20.13 to distinguish the two cases explicitly —

- *Minimum you must exceed* (separation floor, room gate, min stop distance) → `ceil_to_tick` (stricter)
- *Maximum you must stay under* (spread caps, max stop distance, max extension) → `floor_to_tick` (stricter)

Then correct §3.1.3's formula to `floor_to_tick`, which is what its tables already assume. Both `§3.1.3` and `§20.13` need the edit, and the §21.1 worst-case fixture should assert the direction, not just the outcome.

*Related, same root cause:* the "spread at 1%" column in §3.1.3 and in REVIEW-v1.2 §8.3 uses floor-to-tick silently — 1% of $3.83 is $0.0383, tabled as $0.03. Internally consistent and the conclusion is unaffected (that trade fails either way), but the convention is never stated, which is exactly how the ceil/floor divergence arose.

### 2.2 §9.2's own count does not match what it delivers

§9.2 reads: *"Earlier revisions typed only `TradeSignal` and `OrderEvent`, leaving eleven of thirteen inter-component payloads as prose."* That asserts **13** payloads. Eleven types exist: `Bar`, `Quote`, `FeatureVector`, `ScanCandidate`, `TradeSignal`, `RiskDecision`, `OrderEvent`, `Fill`, `Position`, `ClosedTrade`, `BacktestResult`.

All 11 appear in the §9.3 flow, so the flow is internally complete — but two of §9.1's fifteen components sit at the end of arrows with no type: **`NotificationSystem`** (no `Notification` / `Alert` contract, despite §21.6 defining severity routing) and **`TradeJournal`**'s entry payload (no `JournalEntry`, though `journal_entries` exists in §10).

Either the sentence should say "eleven of eleven" and the two components be documented as intentionally untyped, or the two contracts should be added. Given `Alert` carries severity, dedupe key, and acknowledgement state — all of which §21.6 specifies behaviourally — typing it is the better call.

### 2.3 CONSISTENCY — the D-id reference graph is one-way

This is the largest *cross-document* consistency gap and it matters specifically for coding.

| Register | Defined | Referenced from the other document |
|---|---|---|
| A-ids (PRD §13 assumptions) | 24 | All 24 — perfectly closed |
| **D-ids (PLAN decisions log)** | **24** | **5** (D2, D10, D11, D12, D16) |

Nineteen decisions — including every behaviour-changing one: **D17** (separation floor), **D18** (mirrored trailing stop), **D19** (rounding), **D20** (spread gates), **D21** (correlation groups), **D22** (slippage impact) — have no inbound reference from the PRD.

The consequence is concrete. An engineer implementing §3.1.3 sees the two spread gates and their defaults. What they do *not* see is D20's warning that this **changes trading behaviour** — "the system will decline more trades, including some it previously took" — or that lowering `sep_cost_multiple` was explicitly considered and rejected because it "would have preserved the ladder's appearance while still trading at negative expectancy." That is precisely the reasoning that stops someone from "fixing" an inconvenient rejection rate in week three.

**Fix:** cite the D-id wherever the PRD states a decided value, exactly as A-ids already are. Minimum set: §3.1.2 → D17, §3.1.3 → D20, §20.13 → D19, §21.2 trailing → D18, §7.1.3 → D21, §6.5 → D22.

### 2.4 PLAN's Sequencing table mixes two numbering systems

Steps 1–12 map to **Workstreams** (0–11). Step 13 is a **Phase** (2a). Its "Depends on" cell reads `5`, which in a workstream table means Workstream 5 (Market Data) — while PRD §12.1 has Phase 2a depending on Phase 2. Same intent, two schemes in one table, and `5` is ambiguous between them.

**Fix:** either move Phase 2a out of the workstream table into its own "Concurrent technical work" line, or label the cell `Workstream 5 / Phase 2`.

### 2.5 Two PLAN self-assessment ticks overstate

- **WS9** ticks *"Modular architecture with interfaces **and data contracts**."* Data contracts are now genuinely done (11 types, flow annotated). **Interfaces are not** — there are no `Protocol`s, ABCs, or method signatures anywhere; prompt §6.9 asks for both, and PROMPT-REVIEW §2.1 correctly diagnoses why (the prompt gave a list, not a specimen). The tick should be split: contracts ✓, interfaces ☐.
- **WS1** says *"threshold table for all 14 Section 3 parameters."* PRD §2 does have 14 rows, but the prompt's §3 names **12**. The PRD legitimately split one row and added one; the PLAN just shouldn't attribute 14 to the prompt. Trivial — flagged only because miscounts inside self-assessments are what §19's preamble is about, and this project has now been burned by exactly that twice.

### 2.6 Still open, correctly tracked

Not defects — recorded here so nothing is lost at the doc→code boundary:

| Item | Status |
|---|---|
| Citation granularity (REVIEW-v1.2 #23) | Open, assigned to WS11 traceability check, gap stated in Appendix A |
| Parameter registry | Specified (§21.1, PLAN WS11) — **not built** |
| Worked-example + worst-case fixtures | Specified (§21.1) — **not built** |
| Independent review of v1.3 itself | Not done. Every prior round found a class the previous fix could not see |
| `est_round_trip_cost_per_share` = $0.015, `impact_coefficient` = 1.0 | Both unmeasured; drive the separation floor and the slippage model respectively |
| `max_spread_r` = 0.15 | Calibrated against three worked examples, not a real spread distribution (A21). May disable VWAP Reclaim in practice |

---

## 3. On the prompt

`PROMPT-REVIEW.md` now carries the two findings added in the v1.2 review (missing specimen; unmeasurable sensitivity) plus §6.1's boundary-testing lesson. Re-reading the prompt against v1.3, I have nothing further to add — the critique is complete and its central charges (backtesting sequenced last; acceptance criteria testing presence rather than correctness; fidelity-to-Ross measured instead of profitability) all hold.

One observation about the *arc* rather than the prompt: three review rounds found three distinct defect classes, and each was invisible to the check designed for the previous one.

| Round | Class | Would the previous fix have caught it? |
|---|---|---|
| v1.1 | Arithmetic — examples violating their own rules | — |
| v1.2 | Consistency — threshold restated, one copy updated | No. Verifying examples against the *new* value confirmed the examples and never asked whether the document agreed with itself |
| v1.3 | Joint incoherence — two correct parameters that cannot both hold | No. Every value appeared once; a registry passes it clean |

PLAN WS11 already records this table, which is the right response. The honest extrapolation is that **a fourth class probably exists**, and that the argument for an independent read of v1.3 is not ceremony.

---

## 4. Recommendation: stop reviewing prose, start encoding invariants

The remaining work is six enumerable items, five of which are housekeeping. Documentation quality is no longer the binding constraint — and there is a real risk in continuing to polish, because each round has added length (1,050 → 1,712 → 2,200 lines) and the marginal finding is getting smaller while the surface area grows.

**Order I would follow:**

1. **Fix §2.1 (rounding direction).** It is the only item that produces wrong code, and it is a two-line edit in §3.1.3 plus a clause in D19/§20.13.
2. **Write the §21.1 fixture suite as the first code committed.** Worked examples, worst-case boundary, parameter registry lint. This converts three review rounds of hard-won invariants into executable form, and it is the only thing that stops class four from landing silently. It also closes the gap REVIEW-v1.2 §8.4 fairly identified in my own work: my verification scripts were never committed, so every reviewer restarts from zero.
3. **Add the D-id back-references (§2.3)** — mechanical, and it's what keeps the rationale attached to the rule once someone is in an editor rather than reading the PLAN.
4. **Start the Phase 2a data spike now, concurrently.** PLAN already says this and it is right. Vendor lead times are weeks; a negative result rewrites §4 and moots part of the queue above.
5. Items §2.2, §2.4, §2.5 — batch whenever.

**One thing to carry into coding:** the invariant worth protecting above all others is that `§20` governs. Every one of the three defect classes was ultimately a case of the same quantity being expressed in two places. The parameter registry is not documentation hygiene — it is the mechanism that makes "§20 governs" true in code rather than aspirational in prose. Build it before the strategy engine, not after.

And `§18.7` still deserves its own sentence: no real capital until net-of-cost expectancy clears an out-of-sample gate over ≥100 trades per setup. Nothing in v1.3 changed that, and it remains the only part of these documents that can prevent an actual loss.
