# Ross Cameron Trading System — Phase 1 PRD Work Plan

## Objective & Scope

This document is the **work plan** for producing the Phase 1 Product Requirements Document (PRD) for tradipy — a Ross Cameron–style US equities momentum trading platform connected to Interactive Brokers (IBKR).

**In scope:** Specification, architecture design, trading rules, thresholds, discretion analysis, and implementation roadmap.

**Out of scope:** Python code, IBKR integration, backtester implementation, GUI implementation.

**Source of truth:** [prompts/ross_cameron_trading_system.pdf](../prompts/ross_cameron_trading_system.pdf)

**Primary deliverable:** [docs/PRD.md](PRD.md) — the complete Phase 1 specification.

**Companion:** [docs/PROMPT-REVIEW.md](PROMPT-REVIEW.md) — a critique of the source prompt. Several PRD structural choices deliberately depart from the prompt (backtesting moved before the MVP gate; three setups specified to depth rather than 27 shallowly; a viability section the prompt never asked for). The reasoning for each departure lives there, so this plan does not repeat it.

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

- [x] Populate threshold table for all 14 Section 3 parameters
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

- [x] Modular architecture with interfaces and data contracts
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

#### The parameter registry (added after the v1.2 sweep)

Two review rounds found two *different* defect classes, and the second was not caught by the fix for the first:

| Round | Class | Example | What would have caught it |
|-------|-------|---------|--------------------------|
| v1.1 | Arithmetic — examples violating their own rules | Stop at $6.22 where the rule required $6.20; T2 below T1 | Machine-checkable example fixtures (PRD §21.1) |
| v1.2 | **Consistency — a threshold restated in two places, one updated** | `room_gate_multiple` raised to 2.5 in §2.0/§3.1.1, left at `2 ×` in all three setup criteria; §15 carrying a scaling-in rule §7.1.1 had overturned; §4.3 carrying a composite score §20.10 documents as broken | A parameter registry |

Verifying the examples against the *new* value confirmed the examples and never questioned whether the document agreed with itself. The registry closes that:

- [ ] Every threshold appears in **exactly one** defining table (§2, §2.0, or §3.1.2) with a canonical name
- [ ] Every other mention references it **by name**, never by restating the literal
- [ ] A lint pass flags any numeric literal in §3–§7 that matches a registered default — each hit is either a legitimate worked-example value or a latent divergence
- [ ] Cross-check that §15 and §16 assert nothing that §3, §7 or §20 has superseded

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
22. Appendices (sources, glossary, IBKR costs, reserved future-phase extension points)

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
| 12 | 11 — Independent verification & challenge | All | **Pending — must be done by someone other than the author** |

---

## Acceptance Checklist (PDF Section 8)

The PRD is complete when all of the following are true. **Note: the checkmarks below are the author's self-assessment and remain pending independent sign-off under Workstream 11.**

- [x] Every setup in Section 4 has fully specified entry, exit, stop, target, and invalidation rules with numeric parameters where applicable
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
| D19 | Price rounding | **$0.01 ticks; all rounding conservative** — stops down, targets up, gate thresholds up (PRD §20.13) | Several rules produce non-tick levels (`VWAP × 0.99`, odd-R targets). Rounding direction is not cosmetic: the wrong direction tightens stops into noise or flatters backtested R. Asymmetric-conservative means no rounding decision can make a trade look better than it is (A20) |

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| **Strategy may have no edge** (the top risk) | Phase 4b lightweight validation gates the execution build; PRD §18.7 viability gate requires positive expectancy **net of costs** over ≥100 trades per setup, out-of-sample, before any capital |
| **Scanner may not be buildable on IBKR** | PRD §5.5: IBKR is an order-management API, not a screener, and float data is unreliable for small caps. Phase 2a data spike (V7) resolves provider, data quality and measured latency **before** Phase 5 |
| Ross rarely states exact numeric thresholds | Document confidence levels; mark community proxies as Medium confidence |
| IBKR data costs change | PRD includes approximate costs with "verify at subscription time" note |
| Discretionary gap (tape reading) | Proxy via volume/price-action rules; document in Known Limitations |
| Halt/LULD backtest complexity | Defer full halt simulation to Phase 7; MVP uses simplified model |
| News catalyst automation | MVP uses manual verification + keyword NLP soft filter |
| **Spec drift between sections** | Two rounds of internal contradictions have already been found (see Workstream 11). Mitigated by the parameter registry, PRD §21.1 worked-example fixtures, and §20 being declared normative — but **not yet independently verified** |
| Cost estimates are estimates | `est_round_trip_cost_per_share` ($0.015) drives the D17 separation floor and is unmeasured. Calibrate from real paper fills in Phase 4b before trusting any expectancy figure |

---

## What This Plan Does NOT Include

- Python project scaffolding (`pyproject.toml`, modules)
- IBKR API integration code
- Backtester or scanner implementation
- Desktop GUI implementation

These are deferred until the PRD passes Section 8 acceptance criteria and implementation is explicitly requested.

*(The repository is now under version control; git initialization is no longer pending and has been removed from this list.)*
