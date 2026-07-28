# Full Review — PRD v1.2, PLAN, and the Source Prompt

**Scope:** [PRD.md](PRD.md) (1,712 lines, v1.2) · [PLAN.md](PLAN.md) (292) · [PROMPT-REVIEW.md](PROMPT-REVIEW.md) (177) · [prompts/ross_cameron_trading_system.pdf](../prompts/ross_cameron_trading_system.pdf) (7 pp, ~2,350 words)

**Reviewed:** 2026-07-28 · **Method:** every enumerated prompt requirement mapped to PRD coverage; every worked example recomputed programmatically; every recurring numeric threshold scanned for divergent restatement. Counts below were taken from the prompt PDF directly, not from the PRD's own claims.

> **Status: addressed in PRD v1.3.** See [§8 Response and resolution](#8-response-and-resolution) for what was fixed, one correction to this review's own arithmetic, and one defect it did not find. Read §8 alongside any finding below — two are amended there.

---

## 1. Verdict

The docs are now **implementable for the three MVP setups** and were not at v1.0. Three additions carried that change: `§20 Computation Semantics` (defines terms before use), `§21 Non-Functional Requirements & Operations`, and `§3.1.2` (the cost-denominated target-separation floor).

**Arithmetic: clean.** All three worked examples were recomputed independently — entries, stops, R, both gates, target ordering, share counts, and max-loss — and every line derives correctly from the stated rules. The separation floor demonstrably does what the room-gate multiple failed to do: it binds on cost for a $3.83 stock (requiring 0.80R) and on R for a $15 stock (0.50R), which is exactly the price-dependence that no single multiplier could express.

**Coverage against the prompt's enumerated inventories: near-complete.** Verified 1:1 — scanner filters 14/14, market-data types 10/10, execution concerns 10/10, risk hard rules 12/12, architecture components 15/15, database entities 9/9, discretionary elements 10/10, future-phase items 6/6, backtest metrics 9/9, UI areas 10/10 addressed (3 thinly).

**What remains is depth, not breadth** — plus four inputs to enforceable gates that `§20` does not define despite claiming to define every term. The prior recurring defect class (a threshold restated as a literal, one copy updated) has been swept and is now correctly logged as *outstanding* pending a parameter registry, rather than declared fixed.

**Two counts in the docs are wrong.** The prompt bullets **26** strategy components, not 27; so `§19`'s "remaining ~24" should be 23, and `PROMPT-REVIEW` §3.6/§3.10/§5 should say 26. Minor, but they appear inside self-assessments, which is where accuracy matters most.

---

## 2. The prompt as a specification instrument

`PROMPT-REVIEW.md` already covers this well and its two central charges hold up under re-examination:

- **Backtesting is sequenced after the paper-trading gate** (prompt §6.12). Confirmed. The cheapest falsification step is placed after the most expensive build work.
- **Acceptance criteria test presence, not correctness** (prompt §8). Confirmed — every bullet is of the form *exists / is populated / contains no empty cells*. This is precisely how a fully-ticked checklist sat atop four broken worked examples.

Re-reading the prompt against the finished docs surfaces **two further prompt defects the existing review does not name**:

### 2.1 The prompt never asks for interfaces to be typed, only "named"

Prompt §6.9 demands components with "clearly defined responsibilities, **interfaces, and data contracts**." It then supplies a bulleted list of 15 component *names* and no example of what an interface or contract should look like — unlike §7.4, where a filled-in specimen row successfully forced concreteness.

The result is predictable and visible: `§9.1` gives all 15 components a responsibility plus prose Inputs/Outputs, and `§9.2` types exactly **2 of 15** payloads (`TradeSignal`, `OrderEvent`). Every arrow in the `§9.3` event flow except signal→order is untyped. Where the prompt gave a specimen, it got concreteness; where it gave only a list, it got a list back.

**Lesson for prompt design:** a specimen is worth more than an adjective. "Interfaces and data contracts" produced neither; one example dataclass would have produced fifteen.

### 2.2 "Sensitivity" is requested but its unit is not

Prompt §3 requires, per threshold, "(b) sensitivity — **how much** performance may change if the value is altered." "How much" is a quantity. All 14 rows in `§2` answer qualitatively and directionally ("High — 3× captures more names; 10× misses early movers"). Not one gives a magnitude.

This is arguably unanswerable at Phase 1 — you cannot quantify sensitivity without the backtest that Phase 4b will produce — which makes it a **prompt sequencing flaw of the same family as §3.1**: it demands, before any measurement exists, an output that only measurement can supply. The honest response would have been to state that explicitly. The docs instead answered qualitatively without noting the substitution.

### 2.3 Where the docs correctly overrode the prompt

Worth recording as good judgment, not deviation: backtesting moved before the MVP gate (§12.1, Phase 4b + Viability Gate); `§18` added an entire viability analysis the prompt never requested; `§20` and `§21` invented requirements the prompt omitted; `§19` un-ticked an acceptance criterion the prompt's own wording would have allowed to pass. In each case the docs are better than their brief.

---

## 3. Remaining defects

### Tier 1 — would block or misdirect implementation

| # | Defect | Evidence | Origin |
|---|--------|----------|--------|
| 1 | **`spread_at_signal` is undefined.** It is the binding input to the `§3.1.2` separation floor, which gates *every* entry, and it is persisted in `signals`. No sampling point, no NBBO-vs-last convention, no staleness rule. `§20` defines VWAP, HOD, EMA, RVOL, tick size — and omits this | §3.1.2 L190, `signals` L887; absent from §20.1–20.13 | Authoring |
| 2 | **`ATR(14)` is undefined.** A hard-referenced scanner filter (`ATR(14) ≥ 1.5× 30-day avg ATR`) and a `§14.2` alternative. No period basis (daily vs 1-min), no true-range convention | §4.2 L491, §14.2 L1243; absent from §20 | Authoring |
| 3 | **Interfaces and data contracts: 2 of 15.** Prompt §6.9 requires them for every component | §9.1 vs §9.2 | **Prompt** (§2.1 above) + authoring |
| 4 | **Catalyst confirmation has no interface.** `§11.1` step 3 and `§12.2` item 6 make user catalyst confirmation the single mandatory human action in the MVP. `§11.4`'s four CLI commands (`scan`, `trade --paper`, `status`, `journal`) provide no way to perform it | §11.4 | Authoring |
| 5 | **Acceptance criterion 1 genuinely fails.** 3 of 26 setups carry invalidation rules. 8 in `§3.5` have entry/stop/(sometimes)target and no invalidation. Three — Premarket Gapper, Momentum Continuation, Pullback Entry — exist only as a one-line `§15` row with no stop, target, or invalidation anywhere | §3.5, §15 | **Prompt** (breadth demand) — honestly disclosed in §19 |

### Tier 2 — material gaps against the prompt

| # | Defect | Prompt requirement |
|---|--------|-------------------|
| 6 | **No tradeoff analysis for any discretionary element.** `§14.2` has Alt A / Alt B / Recommended but no "advantages / disadvantages of each," and no "how experienced traders typically interpret it" — both named by the prompt, absent for all 10 rows. Also breaches the prompt's §2 Core Principle ("Discuss the tradeoffs of each alternative") | §7.3, §2 |
| 7 | **Slippage model has no impact term.** `§6.5` models ticks + spread only; the prompt names "spread **+ impact**." `§18.2` concedes the model is optimistic for exactly this universe — and `§18.7`'s viability gate is judged *net of modeled slippage*, so an optimistic model biases the gate that decides whether to risk money | §6.8 |
| 8 | **News-timestamp look-ahead is uncontrolled.** The prompt names two specific traps: RVOL and news timestamps. RVOL is rigorously handled (`§20.7` as-of semantics + a shifted-data property test). News has no publication-vs-availability lag rule | §6.8 |
| 9 | **Assumptions register has no alternatives column.** 20 assumptions, "Consequence if Wrong" complete, but the prompt requires recommending alternatives per assumption; present inline for ~4 of 20 | §6.13 |
| 10 | **Schema omits data the PRD itself requires:** no halt-events table (needed by `§8.4` "halt events per symbol per day" and the `§4.2` recent-halt filter), no `bars_5m` or 1→5-min aggregation semantics (needed by `§5.1`, ORB, 5-Min Breakout), no news/headline table (catalyst is a scored filter; only a free-text `watchlists.catalyst` exists) | §6.10 (internal) |
| 11 | **News feed source and latency unspecified.** `§5.1` says "Manual + headline API"; the prompt names both "sources & latency" | §6.5 |
| 12 | **Screening-vendor cost omitted.** `§5.5` concludes an external vendor is probably mandatory; `§5.3`/Appendix C's ~$14.50/mo excludes it, so the stated data cost is structurally understated | §5 |
| 13 | **Security is secrets-handling only.** No authn/authz, no threat model, no encryption at rest — and the kill switch is triggerable by a world-writable file sentinel (`/tmp/tradipy_kill`) with no access control discussed. For a component whose job is to flatten the account, that is the wrong place to be casual | §6.2 |
| 14 | **Order-to-exchange latency unbudgeted.** `§5.2` specifies data-to-signal and signal-to-order; the prompt names order-to-exchange as its own leg | §6.2 |
| 15 | **Sector/correlated exposure is a stub.** Rule exists, but no sector data source (`symbols.sector` has no provider) and correlation is not modelled. For co-moving low-float gappers sharing one catalyst — the actual exposure — sector is a weak proxy the PRD never acknowledges | §6.7 |

### Tier 3 — consistency and quality

| # | Defect |
|---|--------|
| 16 | **Setup count wrong in self-assessments:** prompt has 26 bullets; `§19` says "~24 remaining" (should be 23), `PROMPT-REVIEW` says 27 in three places |
| 17 | **Institutional Ownership restated divergently** — `§4.2` `≥ 80%`, `§15` `> 80%`. Separately, its *plausibility* is doubtful: ≥80% institutional ownership in a ≤20M-float, ≤$2B universe is rare, so this filter likely never fires. Neither the threshold nor its direction is sourced |
| 18 | **Trade-count sufficiency restated inconsistently:** `§8.3` "< 100 trades in sample" vs `§11.3`/`§18.7`/`V1` "≥ 100 per setup" — a materially different bar |
| 19 | **Five-Minute Breakout specified two incompatible ways:** `§3.5` "same as HOD breakout, wider stops, smaller size" (undefined) vs `§15` "5-min close > 20-bar high on 2× vol" |
| 20 | **Sharpe frequency unspecified** — "annualized, rf=0" is ambiguous for an intraday strategy (per-trade? daily? which annualization factor?) |
| 21 | **Max Extension from HOD (0.5%)** now defers to "the setup's own consolidation requirement," which resolves the old 3-vs-2 candle conflict — but `§3.4` VWAP Reclaim has no consolidation requirement, so for that setup the parameter still resolves to nothing |
| 22 | **Opening-auction modeling is one sentence** ("model as first regular-session bar") — no imbalance or price-discovery treatment |
| 23 | **No citation granularity:** no page numbers or timestamps; `§15`'s "Ross Teaching" column is unsourced paraphrase; no video/webinar sources despite prompt §7.1 naming them as primary media. This makes Workstream 11's traceability pass harder than necessary |

### Tier 4 — a readability problem the docs are creating for themselves

**~20 passages of inline revision history.** The PRD now narrates its own corrections in place: "an earlier draft required ≥ 70%," "the earlier version quoted three different entry prices," "*(Removed: … was unreachable)*," "a previous revision stated ~11–12 weeks."

This was the right instinct — it prevented silent reversals and it is why the error-correction record is auditable. But it is now working against the document's primary job. An implementer reading `§3.2` must parse which rule is current and which is a retracted ancestor, in a section whose whole purpose is to be unambiguous. Revision history belongs in git history or a `CHANGELOG.md`; a normative spec should state what is true.

**Recommendation:** move the corrections narrative to `CHANGELOG.md`, keep at most a one-line pointer where a reversal is genuinely counter-intuitive (the flag-volume direction is the one case that earns an inline note, because ≤70% looks like a typo to anyone expecting ≥).

---

## 4. Attribution — prompt-caused vs authoring

Since the docs derive from the prompt, separating the two matters for deciding what to fix versus what to fix *in the prompt*.

**Traceable to the prompt:**

| Defect | Prompt cause |
|---|---|
| 23 of 26 setups shallow; criterion 1 fails | §4's 26-item list × §6.3's 12-element demand = ~300 cells; no depth ranking |
| Interfaces/contracts 2 of 15 | §6.9 names components but supplies no specimen (contrast §7.4, which worked) |
| Sensitivity qualitative | §3 demands "how much" before any measurement exists |
| Slippage lacks impact term | §6.8 names it once in passing; §6.6 asks only for "slippage model & assumptions" |
| Security thin | §6.2 compresses ten NFR topics into one sentence |
| GUI specified for a deferred phase | §6.11's 10 areas vs §6.12's no-GUI MVP |
| No functional-requirements inventory | §6.1 asks for "every feature" without a format |

**Authoring defects, not the prompt's fault:** `spread_at_signal` and `ATR(14)` undefined while `§20` claims to define every term; no catalyst-confirmation command; schema missing halt/5-min/news tables the PRD's own sections require; institutional-ownership divergence and implausibility; trade-count and 5-Min-Breakout restatements; the 26-vs-27 miscount; and the accumulating inline revision history.

---

## 5. Assessment of `PROMPT-REVIEW.md`

Still the most unusual artifact in the repo, and its analysis is sound. Three notes:

1. **Fix the count** — 26 setups, not 27 (§3.6, §3.10, §5).
2. **§3.9 remains overstated.** It says the prompt "guarantees wasted effort" by demanding a GUI spec the MVP excludes. The prompt says "no fancy GUI required" *for the MVP gate* and places the GUI at Phase 8 — specifying a Phase 8 deliverable during Phase 1 is not inherently waste. The defensible version is the opportunity-cost argument already made in §3.6/§3.10: attention spent on ten UI areas was attention not spent on computation semantics, which is what actually blocked implementation.
3. **Add the two new prompt findings** from §2 above: the missing-specimen problem (§2.1) and the unmeasurable-sensitivity demand (§2.2). Both are instances of a single deeper pattern worth stating outright — **the prompt is strongest exactly where it supplies an example, and weakest wherever it supplies only a list.** §7.4's specimen row produced a 26-row matrix with no empty cells; §6.9's bare list produced 2 typed contracts out of 15.

---

## 6. Recommended sequence

**Before any code:**

1. Define `spread_at_signal` and `ATR(14)` in `§20` (Tier 1 #1, #2) — both gate live decisions.
2. Add a catalyst-confirmation CLI command (#4), or remove the manual-confirmation requirement from the MVP definition. Right now `§12.2` cannot be satisfied as written.
3. Type the remaining data contracts (#3) — Bar, Quote, FeatureVector, ScanCandidate, Position, Fill, RiskDecision, BacktestResult. This is a mechanical afternoon and it closes the largest prompt gap.
4. Add the missing tables (#10): halt events, `bars_5m` + aggregation semantics, news headlines.
5. Add an impact term to the slippage model (#7) and a news-availability lag rule (#8) — both directly bias the Viability Gate, which is the decision that matters most.
6. Build the **parameter registry** already identified as outstanding: every threshold defined once, referenced by name, never restated as a literal. Then add the `§21.1` worked-example fixtures to CI. Together these retire the entire recurring defect class rather than sweeping it again.
7. Move revision history to `CHANGELOG.md` (Tier 4).

**Then:** run Workstream 11 with a reader who has not seen the document, against v1.2 rather than v1.0.

**Then, and this remains the highest-value technical action:** the Phase 2a data-feasibility spike (`§5.5`, `V7`). The specification is now good enough that the binding constraint has moved off documentation quality entirely. Whether a real-time candidate list matching `§4.2` can be sourced at all — and at what cost — determines whether the rest of this plan is buildable. Everything above is cheap by comparison.

---

## 7. One thing worth saying plainly

The single most valuable page in these documents is `§18` — the section arguing that the strategy may not be profitable, that the source's performance claims are unaudited marketing, and that no real capital should move until net-of-cost expectancy clears an out-of-sample gate. The prompt never asked for it. Everything else here is engineering quality; `§18.7` is the part that could prevent a real loss, and it is the part a reader under time pressure is most likely to skip.

*(Acted on: PRD §1 now carries a signpost to §18 immediately after the account-size note, on the reasoning that a section which can prevent a loss should not depend on the reader reaching page 18.)*

---

## 8. Response and resolution

Added after the review was verified against the PRD. This section records one arithmetic correction to the review itself, one defect it did not find, and the disposition of all 23 findings.

### 8.1 Correction: the denominator is 14, not 26

The count fix in §1 is right — the prompt bullets **26** items, not 27, and `PROMPT-REVIEW` has been corrected in three places. But the review then uses 26 as the denominator for acceptance criterion 1, and that is wrong.

The prompt's §4 heading reads "all major **components** of Ross Cameron's strategy." Twelve of the 26 are not tradeable setups: Gap scanner, Relative volume, Low float momentum, News catalysts (scanner filters); Scaling into winners, Scaling out (position management); Risk management, Daily loss limits, Maximum number of losses, Position sizing (risk rules); Trade journaling, Statistics (operations). Criterion 1's own "**where applicable**" qualifier excludes them — there is no stop placement for Statistics, and all twelve are fully specified elsewhere in the PRD (§4.2, §3.1.1, §7, §8.3, §10).

The PRD's own §3.1 inventory corroborates independently: 18 rows, of which Gap Scanner is labelled "filter, not trade setup" and three more are management or overlay — leaving exactly **14 tradeable setups**.

So Tier 1 #5 and the §4 attribution table should read **3 of 14 specified, 11 shallow**, not 3 of 26 and 23 shallow. Roughly half the size, and materially less damning. The review corrected one miscount and introduced another by applying the corrected total to the wrong population. PRD §19 and `PROMPT-REVIEW` §3.6 now state 14 and explain the split.

### 8.2 Tier 1 #5 is misclassified

Tier 1 is defined as "would block or misdirect implementation." Eleven shallow post-MVP setups block nothing: the MVP is three setups and all three are fully specified. It is a prompt-compliance gap, which the review's own Origin column concedes ("honestly disclosed in §19"). It belongs in Tier 2.

### 8.3 What the review did not find, and it is the largest item

**All three worked examples fail their own §3.1.2 separation floor at the maximum spread the §4.2 filter admitted.**

The filter allowed any spread up to 1% of price. At that limit:

| Setup | Price | Spread at 1% | Floor required | Actual T2−T1 | Result |
|-------|-------|-------------|---------------|-------------|--------|
| §3.2 Bull Flag | $5.16 | $0.05 | $0.20 | $0.11 | Rejected |
| §3.3 HOD Breakout | $6.48 | $0.06 | $0.23 | $0.22 | Rejected by one tick |
| §3.4 VWAP Reclaim | $3.83 | $0.03 | $0.14 | $0.12 | Rejected |

Every example assumed a $0.01 spread — the tightest possible — and none stated why that was representative of a sub-$20 low-float gapper during a momentum burst.

The examples are the symptom. The finding is that **at the filter's own limit, crossing the spread twice cost more than 1R**: on the HOD example, $0.06 against a $0.15 stop is 80% of R in spread alone, before commission or slippage. §18.2 states qualitatively that "a gross +0.5R edge can turn negative once round-trip slippage and fees exceed ~0.5R." The scanner was admitting trades that breached that threshold on spread alone. `sep_cost_multiple` and the spread filter had never been jointly calibrated.

**Resolved in v1.3** by §3.1.3: a two-tier spread gate (scan-time `min($0.02, 0.5% × price)`, signal-time `≤ 0.15 × R`), a unified room requirement folding the room gate and separation floor into one test, and a **worst-case fixture in §21.1** asserting that every worked example clears its separation floor at the widest spread its own filters permit. Loosening any of the four parameters now breaks CI.

This is a third distinct defect class — not arithmetic, not cross-section inconsistency, but **two individually-correct parameters that are jointly incoherent**. Neither worked-example fixtures nor a parameter registry would have caught it; every value appeared exactly once and each was defensible alone. The generalizable check is boundary testing, now recorded in `PROMPT-REVIEW` §6.1.

### 8.4 Two smaller notes

**The review's own verification is unreproducible.** §1 states the examples were "recomputed programmatically," but no script or fixture is committed — the same gap §21.1 exists to close, and the same reason the next reviewer starts from zero. Recommendation #6 is right and applies to the review as much as to the PRD.

**The data spike should run in parallel, not last.** §6 calls it "the highest-value technical action" and then schedules it after seven documentation fixes. Vendor evaluations have multi-week lead times, and if no provider can supply a §4.2-matching candidate list then §4 needs rewriting anyway, which moots part of items 1–7. PLAN now starts it concurrently.

### 8.5 Disposition

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | `spread_at_signal` undefined | Fixed — PRD §20.14 |
| 2 | `ATR(14)` undefined | Fixed — PRD §20.15 |
| 3 | Data contracts 2 of 15 | Fixed — §9.2 now types 11; §9.3 arrows annotated |
| 4 | Catalyst confirmation has no interface | Fixed — `tradipy catalyst` (§11.4) |
| 5 | Acceptance criterion 1 fails | Amended (§8.1, §8.2) and re-stated in §19 as 3 of 14 |
| 6 | No tradeoff analysis for discretionary elements | Fixed — §14.3 |
| 7 | Slippage has no impact term | Fixed — §6.5 square-root impact term + 2× stress requirement |
| 8 | News-timestamp look-ahead uncontrolled | Fixed — §8.2 `received_at` rule, `news_availability_lag` |
| 9 | Assumptions register has no alternatives | Fixed — §13 column added for all 24 |
| 10 | Schema omits halt/5-min/news | Fixed — three tables + `bars_5m` aggregation semantics |
| 11 | News source and latency unspecified | Fixed — §5.1 per-feed table |
| 12 | Screening-vendor cost omitted | Fixed — §5.3 and Appendix C now $45–$500 all-in |
| 13 | Security is secrets-handling only | Fixed — §21.5 threat model; kill switch moved off `/tmp` |
| 14 | Order-to-exchange latency unbudgeted | Fixed — §5.2 four-leg budget |
| 15 | Sector/correlated exposure is a stub | Fixed — §7.1.3 `correlation_group`; limitation stated (A24) |
| 16 | Setup count wrong | Fixed, with the denominator itself corrected (§8.1) |
| 17 | Institutional ownership divergent and implausible | Fixed — reconciled to `≥`, disabled by default (A22) |
| 18 | Trade-count sufficiency inconsistent | Fixed — per-setup everywhere |
| 19 | Five-Minute Breakout specified two ways | Fixed — §3.5 fully specified |
| 20 | Sharpe frequency unspecified | Fixed — daily returns, `× sqrt(252)` |
| 21 | Max Extension resolves to nothing for VWAP Reclaim | Fixed — §3.4 criterion 9 |
| 22 | Opening auction one sentence | Fixed — §8.2 non-participable print (A23) |
| 23 | No citation granularity | **Open** — deferred to PLAN Workstream 11; gap stated in Appendix A |
| — | Spread/separation joint incoherence | Found here (§8.3); fixed — §3.1.3 |

Outstanding after v1.3: citation granularity (#23), the parameter registry, the §21.1 fixtures, and independent review of v1.3 itself.
