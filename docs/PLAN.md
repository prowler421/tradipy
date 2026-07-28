# Ross Cameron Trading System — Phase 1 PRD Work Plan

## Objective & Scope

This document is the **work plan** for producing the Phase 1 Product Requirements Document (PRD) for tradipy — a Ross Cameron–style US equities momentum trading platform connected to Interactive Brokers (IBKR).

**In scope:** Specification, architecture design, trading rules, thresholds, discretion analysis, and implementation roadmap.

**Out of scope:** Python code, IBKR integration, backtester implementation, GUI implementation.

**Source of truth:** [prompts/ross_cameron_trading_system.pdf](../prompts/ross_cameron_trading_system.pdf)

**Primary deliverable:** [docs/PRD.md](PRD.md) — the complete Phase 1 specification.

**Companions:**

| Document | Role |
|----------|------|
| [docs/PROMPT-REVIEW.md](PROMPT-REVIEW.md) | Critique of the source prompt. Several PRD structural choices deliberately depart from it — backtesting moved before the MVP gate, three setups specified to depth rather than fourteen shallowly, a viability section the prompt never asked for. The reasoning for each departure lives there, so this plan does not repeat it |
| [docs/REVIEW-v1.2.md](REVIEW-v1.2.md) | Independent review of PRD v1.2 — 23 findings, dispositions in its §8. Drove PRD v1.3 |
| [docs/REVIEW-v1.3.md](REVIEW-v1.3.md) | Independent review of PRD v1.3 — 6 findings, one blocking (rounding direction). Drove PRD v1.3.1 |
| [docs/CHANGELOG.md](CHANGELOG.md) | Revision history. The PRD states current rules only; superseded rules and the reasoning behind each reversal live here |

---

## Workstreams

### Workstream 0 — Source Research

- [x] Review Ross Cameron / Warrior Trading public material
- [x] Distinguish consistently taught principles from one-off examples
- [x] Build bibliography / source index (see PRD Appendix A)
- [x] Flag gaps where no numeric threshold exists in source material

**Key sources used:**

| Source | Type | Reliability |
|--------|------|-------------|
| Warrior Trading — Stock Selection PDF | Official | High |
| *How to Day Trade* (2015) | Book | High |
| warriortrading.com articles (bull flag, low float, simplest strategy) | Official blog | High |
| Community summaries (TradingView 5 Pillars, Elite Trader) | Secondary | Medium |

---

### Workstream 1 — Quantitative Thresholds

- [x] Populate threshold table for the prompt's 12 Section 3 parameters — PRD §2 carries **14 rows**, having split one and added one. The extra rows are deliberate; the count belongs to the PRD, not to the prompt
- [x] Assign confidence ratings (High / Medium / Low)
- [x] Document Ross source or note absence
- [x] State sensitivity and user-configurable flag

**Output:** PRD Section 2

---

### Workstream 2 — Discretion Analysis

- [x] List all discretionary elements from PDF Section 7.3
- [x] Propose 2–3 deterministic alternatives per element
- [x] Recommend one implementation marked as Assumption
- [x] Document known limitations and future AI candidate flags

**Output:** PRD Sections 14–17

---

### Workstream 3 — Trading Rules per Setup

- [x] Specify rules for all Section 4 setup components
- [x] Include entry, exit, stop, target, invalidation, filters, edge cases
- [x] Add worked numeric example per primary setup
- [x] Select MVP setups (3 highest-confidence)

**MVP setups selected:**

1. **Bull Flag** — High confidence; fully specified in Ross material
2. **High-of-Day Breakout** — High confidence; core momentum entry
3. **VWAP Reclaim** — Medium-high confidence; well-defined level logic

**Output:** PRD Section 3

---

### Workstream 4 — Scanner Specification

- [x] Define 14 filters with default thresholds
- [x] Classify hard vs soft filters
- [x] Assign rejection reason codes

**Output:** PRD Section 4

---

### Workstream 5 — Market Data & IBKR

- [x] Specify data types and quality requirements
- [x] Document IBKR subscription requirements and cost estimates
- [x] Address low-float data quality issues

**Output:** PRD Section 5

---

### Workstream 6 — Execution Engine

- [x] Document order lifecycle and order types
- [x] Define partial fill, slippage, retry, and reconciliation policies

**Output:** PRD Section 6

---

### Workstream 7 — Risk Engine

- [x] Define all hard rules with condition → enforcement point → action
- [x] Mark daily loss limit and max risk-per-trade as non-bypassable

**Output:** PRD Section 7

---

### Workstream 8 — Backtesting Design

- [x] Address all realism requirements from PDF Section 6.8
- [x] Define required metrics and validation protocols

**Output:** PRD Section 8

---

### Workstream 9 — Architecture, Data Model, UI

- [x] Data contracts — 13 typed payloads, every §9.3 arrow annotated (PRD §9.2)
- [ ] **Interfaces** — no `Protocol`s, ABCs, or method signatures exist. Prompt §6.9 asks for both, and this box was previously ticked on the strength of the contracts alone. The gap is diagnosed in [PROMPT-REVIEW](PROMPT-REVIEW.md) §3.11: the prompt named the interfaces without providing a specimen, so there is no shared notion of what "an interface" means here. Resolve when the §21.1 fixture suite is written — the fixtures will need to instantiate against something, which forces the signatures to be real rather than described
- [x] Database schema
- [x] Desktop UI wireframe descriptions and framework recommendation

**Output:** PRD Sections 9–11

---

### Workstream 10 — Roadmap, MVP, Assumptions

- [x] Map Phases 0–10 with complexity estimates
- [x] Define MVP gate criteria
- [x] Centralize assumptions register
- [x] Reserve future AI extension points (names only)

**Output:** PRD Sections 12–13

---

### Workstream 11 — Independent Verification & Challenge

Every workstream above was self-authored and self-certified, so the acceptance criteria below carry an author's bias. This workstream exists to check the PRD against the source and against reality, independently of whoever wrote it.

- [ ] Independent reviewer (a second person, or a fresh agent with no prior context) re-checks every Section 8 acceptance criterion against the PDF and the PRD — not the author's own sign-off
- [ ] Trace each Section 2 threshold and Validation Matrix row back to a cited source; confirm confidence ratings match what the source actually supports (the RVOL 5× / 30-vs-50-day issue was found this way)
- [ ] Sanity-check the worked numeric examples in Section 3 (position sizing, R:R) by recomputation
- [ ] Confirm the "engineer could start with no clarifying questions" claim by having someone unfamiliar with Ross Cameron read the MVP sections and list every question they still have
- [ ] Pressure-test Section 18 (Strategy Viability): are the open risks complete, and is the viability gate strict enough?
- [ ] **Parameter registry check** — build the registry described below and verify it is clean

#### Four defect classes, four mechanical checks

Each review round found a class invisible to the check designed for the one before it. This is the strongest available argument that self-certification does not substitute for a cold reader.

| Round | Class | Example | What catches it |
|-------|-------|---------|-----------------|
| v1.1 | **Arithmetic** — examples violating their own rules | Stop at $6.22 where the rule required $6.20; T2 below T1 | Machine-checkable example fixtures (PRD §21.1) |
| v1.2 | **Consistency** — a threshold restated in two places, one updated | `room_gate_multiple` raised to 2.5 in §2.0/§3.1.1, left at `2 ×` in all three setup criteria; §15 carrying a scaling-in rule §7.1.1 had overturned | A parameter registry |
| v1.3 | **Joint incoherence** — two individually-correct parameters that cannot both hold | The §4.2 spread filter admitted 1% of price while §3.1.2's separation floor consumed spread as input; every worked example failed its own gate at the widest spread the filter allowed, and round-trip spread cost reached 83% of R | **Boundary fixtures** — recompute every example at the extremes its filters admit (PRD §21.1 worst-case row) |
| v1.3.1 | **Generalization** — a rule stated more broadly than its justification supports, then applied outside the range where it holds | D19 said "gate thresholds round **up**, which is always conservative." True for a floor you must exceed; the reverse for a ceiling you must stay under. The §3.1.3 spread cap inherited `ceil_to_tick` by analogy and became *more permissive* while the surrounding prose claimed conservatism | **Direction assertions.** A fixture must assert *why* a value is correct, not only that it matches. `assert cap == 0.01` passes under a wrong rule that happens to agree; `assert cap == floor_to_tick(x) and cap < x` does not |

The v1.2 class was concealed by the v1.1 fix: verifying examples against the *new* value confirmed the examples and never asked whether the document agreed with itself. The v1.3 class was invisible to both — every value appeared exactly once and each was defensible alone, so a registry would have passed it clean. The v1.3.1 class is invisible to all three: the rule was stated once, the tables that applied it were arithmetically right, and the boundary fixture passed. It surfaced only because the prose and the tables disagreed, and prose comparison is the one check that does not mechanize.

**Two heuristics fall out of this, both cheap:**

- **Scope every "always."** A normative statement carrying *always*, *never*, *in every case*, or *uniformly* is asserting something about cases it may not have enumerated. Each one is a place to ask which cases were actually checked. §20.13's closing sentence made exactly this claim and was false for the one case that had just been added.
- **Classify before choosing.** Every new threshold is declared a minimum or a maximum *before* a rounding function is attached to it, so the direction is derived from the constraint rather than copied from a neighbour.

The honest extrapolation is that a fifth class exists. It will not be found by tightening any of the four checks above.

**Registry check:**

- [ ] Every threshold appears in **exactly one** defining table (§2, §2.0, §3.1.2, or §3.1.3) with a canonical name
- [ ] Every other mention references it **by name**, never by restating the literal
- [ ] A lint pass flags any numeric literal in §3–§7 that matches a registered default — each hit is either a legitimate worked-example value or a latent divergence
- [ ] Cross-check that §15 and §16 assert nothing that §3, §7 or §20 has superseded

**Boundary check:**

- [ ] Every §3 worked example recomputed at the **widest spread** its §3.1.3 caps admit, asserting the §3.1.2 separation floor still passes
- [ ] Every gate whose input is bounded by a filter is tested at that filter's boundary, not only at illustrative values
- [ ] Any pair of parameters where one constrains the other's input is documented as jointly calibrated, with the calibration stated

**Traceability check (carries the one open finding from REVIEW-v1.2 #23):**

- [ ] Add page numbers for PDF and book sources; timestamps for any video or webinar source consulted
- [ ] Mark every §15 "Ross Teaching" cell as either sourced (with location) or community-derived
- [ ] Confirm no threshold is presented as a Ross statement when the source is a community proxy

**Output:** Verification notes / issues log; PRD Section 18 and Section 19 checklist signed off by someone other than the author.

---

## PRD Document Outline

The completed [docs/PRD.md](PRD.md) follows this table of contents:

1. Executive Summary
2. Quantitative Thresholds
3. Trading Setups & Rules
4. Scanner Specification
5. Market Data Requirements
6. Execution Engine
7. Risk Management Engine
8. Backtesting Framework
9. System Architecture
10. Database Design
11. User Interface
12. Development Roadmap & MVP
13. Assumptions Register
14. Strategy Validation & Discretion Analysis
15. Validation Matrix
16. Confidence Report
17. Known Limitations
18. Strategy Viability & Open Risks
19. Acceptance Criteria Checklist
20. Computation Semantics (Normative)
21. Non-Functional Requirements & Operations
22. Appendices (sources, glossary, data costs, reserved future-phase extension points)

Revision history lives in [CHANGELOG.md](CHANGELOG.md), not in the PRD (D23).

---

## Sequencing & Dependencies

| Step | Workstream | Depends on | Status |
|------|------------|------------|--------|
| 1 | 0 — Source research | — | Done |
| 2 | 1 — Thresholds | 0 | Done |
| 3 | 2 — Discretion analysis | 0 | Done |
| 4 | 3 — Trading rules | 1, 2 | Done |
| 5 | 4 — Scanner | 1 | Done |
| 6 | 5 — Market data | — | Done |
| 7 | 6 — Execution | — | Done |
| 8 | 7 — Risk engine | 3, 6 | Done |
| 9 | 8 — Backtesting | 3 | Done |
| 10 | 9 — Architecture/UI/DB | 4–8 | Done |
| 11 | 10 — Roadmap/MVP | 9 | Done |
| 12 | 11 — Independent verification & challenge | All | **In progress** — [REVIEW-v1.2.md](REVIEW-v1.2.md) and [REVIEW-v1.3.md](REVIEW-v1.3.md) have each completed a round (23 and 6 findings). Registry, boundary and traceability checks still outstanding; no round has yet been run by a reader with no prior context |

Every row above is a **documentation** workstream, numbered 0–11. The two items below are **implementation** work, numbered by PRD §12.1 phase, and they do not queue behind the table — mixing the two numbering schemes in one column previously made "depends on 5" ambiguous between Workstream 5 and Phase 5.

| Concurrent technical work | Depends on | Status |
|---------------------------|------------|--------|
| **Phase 2a — data feasibility spike** (PRD §5.5) | Workstream 5 (documentation of data requirements) — *not* on step 12 completing | **Not started — highest-value technical action.** Vendor lead times are weeks, and a negative result rewrites PRD §4 |
| **PRD §21.1 fixture suite** — worked examples, boundary/worst-case, parameter-registry lint, rounding-direction assertions | Workstream 11's registry check is *satisfied by* building this, not a precondition for it | **Not started — should be the first code committed.** It converts four rounds of hard-won invariants into executable form, and it closes the gap [REVIEW-v1.2](REVIEW-v1.2.md) §8.4 identifies: verification so far has been ad-hoc scripts that were never committed, so every reviewer restarts from zero |

**Documentation is no longer the binding constraint.** Each review round has grown the PRD (1,050 → 1,712 → 2,200+ lines) while the marginal finding has shrunk, and the remaining items are enumerable. The two rows above are where effort now belongs.

---

## Acceptance Checklist (PDF Section 8)

The PRD is complete when all of the following are true. **Note: the checkmarks below are the author's self-assessment and remain pending independent sign-off under Workstream 11.**

- [x] ~~Every setup in Section 4 has fully specified entry, exit, stop, target, and invalidation rules with numeric parameters where applicable~~ — **met for 3 of 14 tradeable setups; deliberate deviation for the remaining 11.** The prompt's §4 lists 26 *components*, twelve of which are not tradeable setups and are specified elsewhere. See PRD §19 and PROMPT-REVIEW §3.6
- [x] Section 3 thresholds are populated with proposed defaults, confidence ratings, and source notes
- [x] Every identified discretionary element has at least one recommended deterministic implementation and a documented alternative
- [x] The Validation Matrix covers all major components and contains no empty "Deterministic Rule" cells
- [x] Risk rules specify enforcement point and violation action; daily loss limit and max risk-per-trade are hard (non-bypassable)
- [x] Backtest design explicitly addresses the realism items in Section 6.8
- [x] An MVP scope is clearly defined and mapped to the roadmap (scanner + highest-confidence setups + risk + basic journal)
- [x] All assumptions are listed in one place with consequences
- [x] A software engineer unfamiliar with Ross Cameron could begin implementation of the MVP without needing to ask clarifying questions about trading logic

---

## Open Questions / Decisions Log

| ID | Question | Decision | Rationale |
|----|----------|----------|-----------|
| D1 | Which setups for MVP? | Bull Flag, HOD Breakout, VWAP Reclaim | Highest confidence from Ross source material; fully specifiable |
| D2 | RVOL lookback period | 30 trading days (assumption) | Architect prompt §7.4 example cites **50-day** ADV; 30-day chosen for faster adaptation to regime changes. Divergence flagged in A8; RVOL confidence lowered to Medium |
| D3 | Minimum gap % | 4% premarket OR 10% daily change | Ross uses 10% daily; premarket gappers often start at 4–5% |
| D4 | Float ceiling | 20M shares (prefer ≤10M) | "20-20 rule" ($20 price, 20M float); exceptions for obvious leaders |
| D5 | UI framework | PySide6 (Qt) for desktop | Native Python integration; mature charting via pyqtgraph/lightweight-charts |
| D6 | IBKR library | `ib_insync` (async wrapper over `ibapi`) | De facto standard; good event model for live trading |
| D7 | Database | PostgreSQL + TimescaleDB for bars | Production-grade; time-series optimized; SQLite acceptable for MVP dev |
| D8 | News feed | Manual catalyst flag for MVP; Benzinga/IBKR news API for v2 | Ross requires manual news verification; automate later |
| D9 | Level II requirement | Optional for MVP; required for halt/resumption trading | Ross uses L2 for tape reading; MVP uses L1 + T&S |
| D10 | Account size assumption | **$30,000** (was $25,000) | At exactly the $25K PDT minimum, the first losing trade drops equity below the threshold and PDT locks the account before the 3% daily loss limit binds. $30K leaves ~16% headroom (A5) |
| D11 | Premarket trading in MVP | **Disabled by default**; opt-in flag | Resolves the contradiction between premarket setups/scanning and the 09:30–15:55 trading-hours lockout. Premarket signals are logged, never routed (A17) |
| D12 | Canonical exit ladder | 50% at T1 (2R) / 25% at T2 (structural) / 25% trailed on 9 EMA, for **all** setups | Earlier drafts had 50/25/25 in one setup and 50/50 in two others, with §15 asserting a third variant as global default |
| D13 | Bull-flag flag volume | Must **contract** (≤ 70% of flagpole avg) | Reverses an earlier `≥ 70%` that contradicted the setup's own "low-volume consolidation" description (A13) |
| D14 | Pre-entry gate | Room gate at **2.5×** stop distance to nearest resistance | Replaces the tautological "R:R ≥ 2:1 to T1" (T1 *is* 2R, so it could never fail) and guarantees T1 < T2 with usable separation (A15) |
| D15 | Scaling in | Legal **only after T1 fills** and stop moves to breakeven | Old "total risk ≤ 1.5× original max risk" openly violated the non-bypassable per-trade cap (A16) |
| D16 | Risk denominator | **start-of-day equity**, frozen at 09:30 | Old rule used live equity *including* unrealized P&L, making the daily-loss threshold move as the loss accrued |
| D17 | T1/T2 collapse | **Absolute, cost-denominated separation floor** (PRD §3.1.2): `T2 − T1 ≥ 3 × (spread + $0.015)`, alongside the room gate | D14's 2.5R gate was meant to stop T1 and T2 collapsing into one exit. It cannot: T1 is fixed at 2R, so a 2.5R gate buys exactly 0.5R — and R shrinks on cheap stocks, which is where costs bite hardest. The §3.4 example cleared the gate with T1 and T2 **$0.06 apart on a $3.83 stock** and recorded it as a pass. One multiplier cannot serve a $3 stock and a $15 stock; the constraint has to be in dollars (A18) |
| D18 | Trailing-stop protection | **Mirror the ratcheted 9 EMA to a resting broker-side stop**, amended each bar close | §21.2 guarantees "protection lives at the broker" and §21.6 makes any unprotected position a Sev-1 — but a locally-computed EMA trail cannot be a static broker order, so the guarantee silently expired at `TRAILING`. Mirroring keeps it intact: if the client dies the last amended level stands, stale but never absent. Rejected: accepting the exposure and documenting it (A19) |
| D19 | Price rounding | **$0.01 ticks; rounding direction derived from constraint polarity** — stops down, targets up, **minimum** thresholds up, **maximum** thresholds down, every rounded maximum clamped to ≥ 1 tick (PRD §20.13) | Several rules produce non-tick levels (`VWAP × 0.99`, odd-R targets). Rounding direction is not cosmetic: the wrong direction tightens stops into noise or flatters backtested R. **Superseded the original form of this decision**, which said "gate thresholds up" without qualification — see D25 (A20) |
| D20 | Spread limits | **Two gates** (PRD §3.1.3): scan `≤ max(tick, floor_to_tick(min($0.02, 0.5% × price)))`; signal `≤ max(tick, floor_to_tick(0.15 × R))` | The old `≤ 1% of price` filter and D17's separation floor were never jointly calibrated, and they are incompatible: at 1% of price, round-trip spread cost reached **83% of R** on the §3.2 example — above the ~0.5R erosion threshold §18.2 identifies as fatal — and all three worked examples failed their own separation floor at that spread. A percentage-of-price cap also scales the wrong way (1% of $20 is ten ticks). **Changes trading behaviour**: the system will decline more trades, including some it previously took. Rejected alternative: lowering `sep_cost_multiple`, which would have preserved the ladder's appearance while still trading at negative expectancy (A21) |
| D21 | Correlated exposure | **`correlation_group`** — shared catalyst first, sector second, ungrouped third (PRD §7.1.3) | "One position per sector" had no data provider and modelled the wrong thing. Co-moving low-float gappers sharing one catalyst are frequently in different sectors, and same-sector names often do not co-move. Realized correlation is deliberately **not** estimated: too little same-session history for the number to mean anything, and a spurious estimate is worse than an admitted proxy. **Changes trading behaviour** where two watchlist names share a headline (A24) |
| D22 | Slippage impact term | **Square-root model**: `impact_coefficient × spread × sqrt(shares / bar_volume)`, coefficient 1.0 unvalidated | The prompt's §6.8 specifies "spread **+ impact**" and the model had only ticks + spread. §18.7's viability gate is judged net of modeled slippage, so an optimistic model biases the go/no-go toward "go" — the exact direction §18.2 warns about. Phase 4b must report the gate at 1× **and** 2× calibrated slippage |
| D23 | Revision history | **Extracted to [CHANGELOG.md](CHANGELOG.md)**; one inline note retained | ~20 passages of inline correction narrative had accumulated in the PRD. It kept reversals auditable but forced implementers to distinguish current rules from retracted ancestors inside sections whose purpose is to be unambiguous. The flag-volume note stays inline because `≤ 70%` reads as a typo to anyone expecting `≥` |
| D24 | Institutional-ownership filter | **Disabled by default** | Stated two ways (`≥ 80%` in §4.2, `> 80%` in §15) and, more importantly, unsourced and probably inert: ≥80% institutional ownership in a ≤20M-float universe is rare. Rejected alternative: deleting it outright — kept as an off-by-default hypothesis so Phase 4b can test it rather than silently losing the idea (A22) |
| D25 | Rounding-rule polarity | **Split D19 by constraint polarity**: minimums round up, maximums round down, and every rounded maximum is clamped to at least one tick (PRD §20.13, §3.1.3) | D19 asserted that rounding gate thresholds up was "conservative in every case." It is conservative for a floor you must exceed and the *reverse* for a ceiling you must stay under — so D20's spread cap, which inherited `ceil_to_tick` by analogy, was admitting spreads the unrounded threshold rejected while the prose claimed the opposite. §3.1.3's own tables had already been computed with `floor`, so the document contradicted itself and the tables were the correct half. The clamp is separate and load-bearing: `floor_to_tick(0.15 × R)` is `$0.00` for `R < $0.067`, which an unclamped gate would turn into a total silent outage reported as `SPREAD_TOO_WIDE` on every trade. Today's `min_stop_distance` keeps R above that line, but §2.0 permits values that do not (A25). Rejected alternative: flipping D19 wholesale to "round down," which would have fixed the spread gate and broken every floor in §3.1 |

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| **Strategy may have no edge** (the top risk) | Phase 4b lightweight validation gates the execution build; PRD §18.7 viability gate requires positive expectancy **net of costs** over ≥100 trades per setup, out-of-sample, before any capital |
| **Scanner may not be buildable on IBKR** | PRD §5.5: IBKR is an order-management API, not a screener, and float data is unreliable for small caps. Phase 2a data spike (V7) resolves provider, data quality and measured latency **before** Phase 5. **Start the spike concurrently with remaining documentation work** — vendor evaluations have multi-week lead times, and a negative result would require rewriting §4 anyway, mooting part of the doc queue |
| **Data cost is understated by an order of magnitude** | Appendix C previously quoted $14.50/month for IBKR alone while §5.5 concludes an external vendor is effectively mandatory. Realistic all-in is $45–$500/month, which against a $30,000 account is up to 20%/year of fixed drag and belongs in the §18.7 viability arithmetic. The spike must return real quotes, not estimates |
| **The new spread gate may reject most cheap-stock setups** | D20's `0.15 × R` signal-time cap is calibrated against three worked examples, not against real spread distributions. If it rejects too much, VWAP Reclaim — one of three MVP setups — could be effectively disabled. The Phase 2a spike must measure the realized spread distribution on qualifying names and report the implied rejection rate before Phase 4 (A21) |
| Ross rarely states exact numeric thresholds | Document confidence levels; mark community proxies as Medium confidence |
| IBKR data costs change | PRD includes approximate costs with "verify at subscription time" note |
| Discretionary gap (tape reading) | Proxy via volume/price-action rules; document in Known Limitations |
| Halt/LULD backtest complexity | Defer full halt simulation to Phase 7; MVP uses simplified model |
| News catalyst automation | MVP uses manual verification + keyword NLP soft filter |
| **Spec drift between sections** | Four rounds of internal contradictions have been found, each of a class invisible to the previous fix (see Workstream 11). Mitigated by the parameter registry, PRD §21.1's worked-example, boundary and rounding-direction fixtures, and §20 being declared normative — but **none of those mitigations is built**, and v1.3.1 has not been read by anyone without prior context. The pattern so far is that each round finds something the last one could not |
| Cost estimates are estimates | `est_round_trip_cost_per_share` ($0.015) drives the D17 separation floor, and `impact_coefficient` (1.0) drives D22's slippage term. Both are unmeasured. Calibrate from real paper fills in Phase 4b before trusting any expectancy figure |

---

## What This Plan Does NOT Include

- Python project scaffolding (`pyproject.toml`, modules)
- IBKR API integration code
- Backtester or scanner implementation
- Desktop GUI implementation

These are deferred until the PRD passes Section 8 acceptance criteria and implementation is explicitly requested.

**One exception worth naming:** the Phase 2a data spike is investigative code, not implementation, and it should start now rather than waiting on the documentation queue. It answers whether a §4.2-matching candidate list is obtainable at all, at what cost, and with what spread distribution — three questions that between them determine whether the rest of this plan is buildable.
