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
| [docs/reviews/PROMPT-REVIEW.md](reviews/PROMPT-REVIEW.md) | Critique of the source prompt. Several PRD structural choices deliberately depart from it — backtesting moved before the MVP gate, three setups specified to depth rather than fourteen shallowly, a viability section the prompt never asked for. The reasoning for each departure lives there, so this plan does not repeat it |
| [docs/reviews/REVIEW-v1.2.md](reviews/REVIEW-v1.2.md) | Independent review of PRD v1.2 — 23 findings, dispositions in its §8. Drove PRD v1.3 |
| [docs/reviews/REVIEW-v1.3.md](reviews/REVIEW-v1.3.md) | Independent review of PRD v1.3 — 6 findings, one blocking (rounding direction). Drove PRD v1.3.1 |
| [docs/reviews/REVIEW-2026-07-28.md](reviews/REVIEW-2026-07-28.md) | Independent review of the **code** — the first round to review the implementation rather than the specification. Four unenforced guarantees, all reproduced by execution, plus the fifth defect class. Drove package v0.1.0 and decisions D26–D28 |
| [docs/reviews/REVIEW-2026-07-29.md](reviews/REVIEW-2026-07-29.md) | Verification round over v0.1.0. Ten of the twelve F-findings confirmed closed; F12 correctly still open; **F8 not closed**. Nine G-findings, all small or spec questions, and one observation: the fifth defect class has a second population (a *parameter* registered and read by nothing, rather than a *mechanism* built and not called) that `test_enforcement.py` cannot see by construction. Its own first draft needed an adversarial fact-check that found nineteen substantive errors, two of them inherited from the round it was verifying — recorded in its appendix as the argument that two agents reading the same repository do not compose into a cold read |
| [docs/reviews/REVIEW-2026-07-30.md](reviews/REVIEW-2026-07-30.md) | The Phase 2a instrumentation, reviewed for the first time, and round 6 verified. Fifteen H-findings, three HIGH, every code finding in `scripts/spike2a/` — `make check` red at `3545adf` against four documents saying the guardrail was enforced; a hand-derived R that moved the §7 Q4 verdict from INERT to CALIBRATED; and half of every generated quote file discarded by an invalid timestamp, counted by a counter no caller read. Found the **sixth defect class**. Of round 6's ten G-findings, **eight dispositions hold**; G8's does not (fixed, then partly falsified by the next commit) and G10's conclusion is superseded. G1's 17 is now 11 |
| [docs/PHASE-2A-SPIKE.md](PHASE-2A-SPIKE.md) | Scope for the Phase 2a data feasibility spike (PRD §5.5 / V7). Four questions, pre-registered thresholds, and what each outcome rewrites. Written to remove the last available reason for deferring it |
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
- [ ] **Interfaces** — **one `Protocol` now exists, and it is not in the library.** `scripts.spike2a.feeds.QuoteFeed` is a two-member runtime-checkable protocol over the historical NBBO fetch, with a CSV implementation and an IBKR one whose *protocol* method raises `NotImplementedError`; `src/tradipy/` still contains no `Protocol`, ABC or interface signature. That is the shape this box was waiting for, appearing exactly where the box said it would — at the spike — but against a CSV rather than the "real vendor API" the resolution named, so it does not close the box. Prompt §6.9 asks for both, and this box was previously ticked on the strength of the contracts alone. The gap is diagnosed in [PROMPT-REVIEW](reviews/PROMPT-REVIEW.md) §3.11: the prompt named the interfaces without providing a specimen, so there is no shared notion of what "an interface" means here. **The proposed resolution failed and needs replacing.** The §21.1 fixture suite was to force real signatures by having to instantiate against something; it is now written and forced none, because the invariant layer is pure functions over `Decimal` and dataclasses — nothing in it has a collaborator to abstract. The first genuine interface will be the market-data feed, so resolve this at the Phase 2a spike, against a real vendor API rather than a hypothetical one
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
- [x] **Parameter registry check** — built (`src/tradipy/params.py`, `tests/test_parameter_registry.py`), scope extended to `scripts/` recursively, and **green as of review round 7 — it was red for two commits before it**. Note that the *registry check* being green is not `make check` being green: a real `ruff` run after round 7 shipped found seven `B007`s and a `ruff format --check` failure in `scripts/spike2a/synthetic_data_generator.py`, both predating `3545adf`. The `B007`s are fixed; **run `make format` before treating the gate as green**. 47 registered thresholds; a 68-entry frozen baseline of PRD prose restatements. This box read "and clean" while the lint was reporting five offenders in `scripts/spike2a/synthetic_data_generator.py`; a checkbox is a claim about the last time someone ran the check, and this one had not been run since the roots were widened
- [x] **Independent review of the code** — [REVIEW-2026-07-28.md](reviews/REVIEW-2026-07-28.md). Found the fifth defect class (below); four instances, all fixed in package v0.1.0
- [x] **Verification of that review's fixes** — [REVIEW-2026-07-29.md](reviews/REVIEW-2026-07-29.md). Ten of the twelve confirmed closed against file and line; F12 is correctly still open; and **F8 is not closed** — its validation-over-claim half was fixed, its no-literal half stands unqualified in all six places it appears, `CLAUDE.md` among them. No status row in the PLAN or PRD §19 over-claims a capability, which is the first round of which that is true. Nine new findings, none a correctness defect: three are spec questions (`daily_loss_pct`'s §7 enforcement point, §21.1's missing enforcement-fixtures row, a boolean in the registry) and the rest are small. **Not a cold read**, and now with evidence for why that matters — its own first draft needed an adversarial fact-check that found nineteen substantive errors, two inherited verbatim from the round it was verifying and repeated under the word "confirmed"

- [x] **Independent review of the Phase 2a instrumentation** — [REVIEW-2026-07-30.md](reviews/REVIEW-2026-07-30.md). Ten G-findings verified: **eight dispositions hold**, G8's does not (genuinely fixed, then partly falsified by the next commit) and G10's headline is superseded; within the eight, G1's count drifted from 17 to 11 and G3's mechanical half half-landed. Fifteen new findings — eleven in `scripts/spike2a/` and four documentation defects elsewhere — three of them HIGH, and the sixth defect class (below): **`make check` was red at `3545adf` while four documents said the guardrail it trips was enforced.** Not a cold read either — it is the third round performed with the repository in context

#### Six defect classes, six mechanical checks

Each review round found a class invisible to the check designed for the one before it. This is the strongest available argument that self-certification does not substitute for a cold reader.

| Round | Class | Example | What catches it |
|-------|-------|---------|-----------------|
| v1.1 | **Arithmetic** — examples violating their own rules | Stop at $6.22 where the rule required $6.20; T2 below T1 | Machine-checkable example fixtures (PRD §21.1) |
| v1.2 | **Consistency** — a threshold restated in two places, one updated | `room_gate_multiple` raised to 2.5 in §2.0/§3.1.1, left at `2 ×` in all three setup criteria; §15 carrying a scaling-in rule §7.1.1 had overturned | A parameter registry |
| v1.3 | **Joint incoherence** — two individually-correct parameters that cannot both hold | The §4.2 spread filter admitted 1% of price while §3.1.2's separation floor consumed spread as input; every worked example failed its own gate at the widest spread the filter allowed, and round-trip spread cost reached 83% of R | **Boundary fixtures** — recompute every example at the extremes its filters admit (PRD §21.1 worst-case row) |
| v1.3.1 | **Generalization** — a rule stated more broadly than its justification supports, then applied outside the range where it holds | D19 said "gate thresholds round **up**, which is always conservative." True for a floor you must exceed; the reverse for a ceiling you must stay under. The §3.1.3 spread cap inherited `ceil_to_tick` by analogy and became *more permissive* while the surrounding prose claimed conservatism | **Direction assertions.** A fixture must assert *why* a value is correct, not only that it matches. `assert cap == 0.01` passes under a wrong rule that happens to agree; `assert cap == floor_to_tick(x) and cap < x` does not |
| v0.0.1 (code) | **Unenforced guarantee** — a rule that is stated normatively, has a mechanism built for it, is believed to be enforced, and is not | `Config.polarity()` existed, was documented as the thing that decides rounding direction, and had **zero callers**: `gates.py` named `Polarity` members at the call site, so flipping a registry declaration broke no test. Three more of the same shape in one sitting — a mutable `MODE_PRESETS` read live past a "non-bypassable" cap, a registry lint blind to 7 of 29 parameters, and `Config(values)` skipping range validation under a docstring reading *"every construction path validates; there is no other"* | **Enforcement fixtures** (`tests/test_enforcement.py`). For every documented guarantee, write the test that *performs the violation it forbids* — not the one that confirms the happy path. Three of the four had a passing test immediately adjacent to the hole |
| 2026-07-30 (spike code) | **Unvalidated instrument** — the code that *produces* a number deciding a spec question is exempt from every check that protects the code the number is *about* | `synthetic_data_generator.py` derived R by hand — `price × 0.97` — under a docstring saying it used the library's stop functions, while importing `gates.apply_stop_floor_and_ceiling` and never calling it. R is the denominator of the §3.1.3 signal-time cap, so correcting it moved the §7 Q4 verdict on the same sample from **INERT to CALIBRATED**, with the cheapest decile at 14.29% on VWAP Reclaim — A21's stated worst case. Every check above was silent *on this defect*: the arithmetic was the library's, the boundaries and polarities right, every guarantee enforced. The one check that did fire — the v1.2-class registry lint, on five unrelated literals in the same file — is a pytest test in a repository whose pre-commit hooks do not run pytest, so it failed the build and told nobody | **Calibrate the instrument against the library, not around it.** Any value that could trigger a D7 disposition must be reproducible from a provenance-marked input, and the code producing it must derive from the library rather than restate it — the §21.1 discipline applied to the measurement, which PHASE-2A-SPIKE §8 exempted from it on purpose |

The v1.2 class was concealed by the v1.1 fix: verifying examples against the *new* value confirmed the examples and never asked whether the document agreed with itself. The v1.3 class was invisible to both — every value appeared exactly once and each was defensible alone, so a registry would have passed it clean. The v1.3.1 class is invisible to all three: the rule was stated once, the tables that applied it were arithmetically right, and the boundary fixture passed. It surfaced only because the prose and the tables disagreed, and prose comparison is the one check that does not mechanize.

**The fifth class arrived on schedule, and from the direction this table could not look.** The four rows above are all defects *in the document*. Once the document was hardened, the next defect class was the gap between the document and the code that claims to implement it — and it is invisible to all four earlier checks by construction. The rule appears once, so the registry passes. The values are arithmetically correct, so the fixtures pass. The boundary behaves as documented, so the boundary fixtures pass. The direction is right, so the polarity assertions pass. **Nothing asks whether the mechanism is wired to anything**, and the documentation asserting that it is, is what stops anyone checking. A third heuristic falls out, as cheap as the other two:

- **Every guarantee needs the test that breaks it.** For each sentence of the form "X cannot happen", write the test that attempts X and asserts it fails. A test that confirms the happy path passes whether or not the guarantee is enforced — which is why three of the four v0.0.1 instances had a passing test sitting immediately next to the hole.

The honest extrapolation at the time was that a sixth class existed; it was found two rounds later and is the last row of the table above. Note that the fifth was predicted here and still took a fresh reader to find, which is the argument for [Workstream 11's](#workstream-11--independent-verification--challenge) cold read rather than against it.

**Two heuristics fall out of this, both cheap:**

- **Scope every "always."** A normative statement carrying *always*, *never*, *in every case*, or *uniformly* is asserting something about cases it may not have enumerated. Each one is a place to ask which cases were actually checked. §20.13's closing sentence made exactly this claim and was false for the one case that had just been added.
- **Classify before choosing.** Every new threshold is declared a minimum or a maximum *before* a rounding function is attached to it, so the direction is derived from the constraint rather than copied from a neighbour.

#### The fifth class has a second population, and the check built for the first cannot see it

Found by [REVIEW-2026-07-29](reviews/REVIEW-2026-07-29.md), which was looking for a sixth class and did not find one. The four v0.0.1 instances were all *mechanisms* built and not called. The same defect exists one level down, in *parameters and hooks*: 17 of the 47 registered thresholds had no reader outside `params.py` — and of those, all but two were read nowhere at all — `select_flagpole`'s §3.2 qualification predicate has no shipped caller, `is_whole_tick` is called only from tests, and `daily_loss_pct` — which §7 marks NON-BYPASSABLE — has a legal range, a cap check, and no enforcement point at all.

**The count is now 11, and how it moved is the more useful number.** Review round 7 recomputed it: `scripts/spike2a/universe.py` and the synthetic generator read six of the seventeen — the six §4.2 *hard* price/volume filters — so 11 of 47 have no reader and 7 of those 11 none at all (`daily_loss_pct` and `max_open_positions` are still read inside `validate_couplings`). Two more (`rvol_lookback_days`, `bar_close_grace_ms`) gained a mention in a docstring or a print and no read, which is worth naming because a grep for the parameter name finds them and a search for a *reader* does not. The §4.2 soft filter `min_premarket_volume` is the one filter the spike did not pick up. So the gap closes as engines get written, exactly as predicted — and it closed here by six without anything in the registry recording that it had, which is still the finding.

**`tests/test_enforcement.py` is silent on every one of these by construction, and no fixture would help.** Its rule ranges over guarantees *the code makes* — for each, perform the violation it forbids. A guarantee the PRD makes that the code has not reached yet has nothing to violate. So the enforcement check is not weak here; it is out of scope here, and the gap looks identical from inside it. The distinction the registry cannot currently express is **registered** versus **enforced**, and it answers the first when asked the second — which is precisely what `Config.polarity()` did.

The heuristic this yields is the cheapest one yet: **for every registered threshold, name what reads it.** A parameter with no reader is not necessarily wrong — registering §4 and §7 ahead of their engines is what made D27 possible — but it must be marked, because the registry is the artifact this project points at when asked whether a rule is implemented.

The extrapolation this made — doubly supported at the time — was that a sixth class existed and that the next round should assume the check it is about to trust has a population it does not range over. Both held: the sixth class is below, and it was found in code the checks were pointed away from.

#### The sixth class: the instrument is not covered by the checks that protect what it measures

Found by [REVIEW-2026-07-30](reviews/REVIEW-2026-07-30.md), the round after the one that predicted it, in the code added between them. Six checks now stand between this project and a wrong threshold. **Five of them range over `src/tradipy/` and the PRD only** — the worked examples, the boundary and polarity assertions, the enforcement fixtures and the doc-count test say nothing about `scripts/`, and 123 of the suite's 126 functions do not reach it. The sixth, the registry lint, was pointed at `scripts/` on purpose by `d2e94a4`; it fired, named the file and named the parameter, and **it is a pytest test in a repository whose pre-commit hooks do not run pytest**, so its verdict reached nobody for two commits. The number that would actually move a threshold is produced by the spike, whose code PHASE-2A-SPIKE §8 exempts from coverage on the correct grounds that coverage obligations are how throwaway code becomes permanent. So the arithmetic deciding whether `max_spread_r` is recalibrated was the least-checked code in the repository — and its central defect was a stop derivation that disagreed with the shipped stop rule while claiming in its docstring to *be* the shipped stop rule.

**The class claimed its next victim inside the round that named it.** Round 7 could not run `ruff`, so it hand-built an AST check for the four rules it already suspected `synthetic_data_generator.py` of breaking, and reported the result beside genuine executions. A real `ruff` run afterwards found seven `B007`s and a `ruff format --check` failure in the same file, both predating the commit under review. The substitute was an instrument calibrated to the answer its author expected — which is the row above, applied to the review's own tooling. The distinction that matters for the next round: the round's `pytest` stand-in *discovered* something (it runs whatever tests exist, including ones whose subject nobody considered), and the lint stand-in could only *confirm* (it checks the rules its author enumerated). **A general substitute can find what you were not looking for; a specific one cannot.**

**Why this is a row and not a population of the fifth.** The fifth class is a mechanism built and not wired: the guarantee exists, the code does not honour it. Here the library is wired correctly and honours everything; the defect is in code that is deliberately outside the scope of every guarantee about behaviour. The distinction is operational, not philosophical — a `Param.enforced_by` field and a new enforcement fixture would each have caught nothing, and did catch nothing. Note what *did* catch something: the wider registry lint, which is why the mitigation is "point the checks at the instrument" and not "write another kind of check".

**And the counter-argument, because it is a good one.** The propagation mechanism was not new: `make check` was red, four documents said the guardrail was enforced and three that the tree was clean, and that is the F7/F8 shape — a documentation over-claim — for the third round running. This round holds that the over-claim is how the defect *survived* and not what it *was*; a reader who disagrees should read the sixth row as evidence that F7's class is the most persistent one here rather than as a new entry. What is not arguable is the mitigation, because it is different from all five above: the check has to point at the instrument.

The extrapolation, stated for the third time and now with a track record: **a seventh class exists.** Each of the six was invisible to the check built for the one before, and the two most recent were both found in code that the checks were not aimed at. The next place to look is therefore not a tighter check on `src/tradipy/` but whatever the current checks are pointed away from — today that is `scripts/`, `data/`, and CI's own configuration.

**Registry check:**

- [x] Every threshold appears in **exactly one** defining table with a canonical name — 47 in `tradipy.params`, each citing the PRD section that defines it, and each declaring whether its bounds were transcribed or originated in code
- [x] Every other mention references it **by name**, never by restating the literal — enforced across `src/` by an AST-based lint that follows the `D = Decimal` alias
- [x] A lint pass flags any numeric literal in the PRD that matches a registered default — 68 frozen in `tests/registry_baseline.json`; the lint fails on *new* occurrences rather than demanding zero
- [ ] Cross-check that §15 and §16 assert nothing that §3, §7 or §20 has superseded — **still open**, this one is prose comparison and does not mechanize

**Boundary check:**

- [x] Every §3 worked example recomputed at the **widest spread** its §3.1.3 caps admit, asserting the §3.1.2 separation floor still passes
- [x] Every gate whose input is bounded by a filter is tested at that filter's boundary, not only at illustrative values
- [x] Any pair of parameters where one constrains the other's input is documented as jointly calibrated — enforced in `validate_couplings`, or surfaced as a documented open finding where the incoherent combination is the shipped default (see `tests/README.md`)

**Enforcement check** (added after the v0.0.1 code review):

- [x] Every registry mapping is read-only, and no live `Config` can be reached through one
- [x] Rounding direction is read from the registry, not named at the call site — proved by flipping a declaration and asserting the gate's output changes
- [x] Every construction path validates ranges *and* couplings
- [x] Each lint has a guard on the guard: a test asserting the lint can still see what it claims to check

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
| 12 | 11 — Independent verification & challenge | All | **In progress** — five rounds done: [REVIEW-v1.2](reviews/REVIEW-v1.2.md) (23 findings), [REVIEW-v1.3](reviews/REVIEW-v1.3.md) (6), [REVIEW-2026-07-28](reviews/REVIEW-2026-07-28.md) (the code; 4 unenforced guarantees, fixed in package v0.1.0), [REVIEW-2026-07-29](reviews/REVIEW-2026-07-29.md) (verification; 10 of 12 confirmed closed, F12 correctly open, F8 not closed, 9 small findings of which 3 are spec questions), [REVIEW-2026-07-30](reviews/REVIEW-2026-07-30.md) (the spike instrumentation; 15 findings, 3 HIGH, the sixth defect class, and `make check` red against four documents saying the guardrail was enforced). Registry, boundary and enforcement checks are built and green — **and were verified green by execution for the first time in round 7, which is how the red one was found.** Still outstanding: the traceability check, the §15/§16 supersession sweep, and a round by a reader with **no prior context** — the third has now been outstanding across all six defect classes and all three code rounds, and remains the single most valuable open item |

Every row above is a **documentation** workstream, numbered 0–11. The two items below are **implementation** work, numbered by PRD §12.1 phase, and they do not queue behind the table — mixing the two numbering schemes in one column previously made "depends on 5" ambiguous between Workstream 5 and Phase 5.

| Concurrent technical work | Depends on | Status |
|---------------------------|------------|--------|
| **Phase 2a — data feasibility spike** (PRD §5.5) | Workstream 5 (documentation of data requirements) — *not* on step 12 completing | **Instrumented and exercised against fabricated input; not run against real data.** Scope and §7 pre-registration committed 2026-07-29; `scripts/spike2a/` carries the code for Q2, Q3 and Q4. It read "reading every threshold from the registry" until review round 7, which found five registered-threshold literals in the generator and a red `make check`; every threshold is read from the registry as of that round's fixes. Two halves of §7's sample definition — the window rule and the selection rule — are **still not joined in code** (H5). **Data is what is missing, and every blocker is external**: vendor trials for Q1 (a pre-determined negative for IBKR alone, per §7's 200-symbol clause against the ~100 line cap), a second float provider for Q2's disagreement condition, a paper connection for Q3, and historical intraday NBBO for Q4 — whose availability on the IBKR paper tier is **unverified**. Writing more about the spike is still not progress on it; what the code buys is that the measurement is pre-registered before it sees data |
| **PRD §21.1 fixture suite** — worked examples, boundary/worst-case, parameter-registry lint, rounding-direction assertions | Workstream 11's registry check is *satisfied by* building this, not a precondition for it | **Done** (package v0.0.1–v0.1.0). **126 test functions** across seven files. The coverage figure (~99% line and branch) and the mutation result (47/47) were measured at v0.1.0 and **have not been re-measured against the nine functions added since**; review round 7 ran the suite under a `pytest` stand-in (162 cases, all passing after its fixes) but could not run `pytest` itself, coverage or mutation. "153 cases" appeared here and in the root changelog as a collected-case count and is not carried forward, because nothing in the repository can currently reproduce it. Plus the three §20 computations that need no feed — §20.4 flagpole geometry, §20.10 composite score, §20.14 quote validity — and `python -m tradipy demo`, which replays the three §3 worked examples end to end and fails if any derived value disagrees with the tables |

**Why the fixture suite was built before the spike, which this plan ranked first.** The ordering was not an oversight and is recorded here because it was previously undocumented. The spike is blocked on external lead times and cannot start and finish inside one work session; the fixture suite could, and it is the precondition for trusting any number the spike comes back with. That said, **it has now deferred the spike twice**, and the argument does not survive a third use.

**The argument no longer applies.** It rested on there being work that fits in one sitting and is more valuable; the fixture suite is done, the four unenforced guarantees are closed, and [REVIEW-2026-07-29](reviews/REVIEW-2026-07-29.md)'s nine findings are six small fixes and three spec questions that block nothing. **This does not amount to progress on the spike.** Scoping it and pre-registering it are still documentation, and a third deferral is what it is regardless of how completely the reasons for the first two have been retired. The blocking action is a vendor trial account and historical NBBO data, neither of which any amount of further writing produces.

**Documentation is no longer the binding constraint, and neither is code.** Each review round grew the PRD (1,050 → 1,712 → 2,280 lines) while the marginal finding shrank; the invariant layer is now built, tested and runnable. **Data is the binding constraint.** Every threshold in the registry is calibrated against three hand-authored worked examples, and the suite proves they are used *consistently* — it cannot say whether `max_spread_r` = 0.15 admits 90% of qualifying setups or 5%. The Phase 2a spike is the only remaining work that can answer that.

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
| D26 | `room_gate_multiple` lower bound | **2.0 is legal**; the `room_gate_multiple > t1_r_multiple` coupling check is removed | The check made the value §1, §2.0, §3.1.1 and §7 all declare legal raise, and cited §3.1.1's *"cannot go below 2.0"* — which is `≥`, not `>`. It was also unnecessary: `min_separation` is a MINIMUM-polarity threshold over a strictly positive quantity (`sep_cost_multiple ≥ 1.0`, `est_round_trip_cost_per_share ≥ 0.001`), so it is at least one tick at every legal configuration; §3.1.2's separation term therefore strictly exceeds `t1_r_multiple × R` and is what actually guarantees `entry < T1 < T2`. **Not** via `min_sep_r × R > 0`, which a first draft of this decision argued in six places — §2.0 permits `min_sep_r = 0.0`, so that product is exactly zero at a legal configuration. The conclusion survived; the reasoning did not, and in six copies. Caught by the verification round on [REVIEW-2026-07-28](reviews/REVIEW-2026-07-28.md). At 2.0 the proportional term is **inert, not unsafe** — which is the state it is already in at its 2.5 default, a separate finding that remains open. Rejected: amending four PRD sections to exclude 2.0, hard-coding a bound the separation floor already makes unnecessary. Found by [REVIEW-2026-07-28](reviews/REVIEW-2026-07-28.md) F11 |
| D27 | Risk-setting configurability | **`max_risk_per_trade_pct` (0.25–2%), `daily_loss_pct` (1–5%), `max_open_positions` (1–3) and `max_consecutive_losses` (2–5) are registered parameters**; `MODE_PRESETS` becomes an overlay bundle on top of them | §2 declares all four user-configurable within stated ranges. No configuration path existed, and none of the bounds was in code — so the column was false. Worse, §7's "non-bypassable cap" was checked against `MODE_PRESETS`, a module constant no supported path could change: the guarantee was enforced against something immovable while the legal range beneath it did not exist. `validate_couplings` now checks the **effective** value. The §7 cap and the §2 ceiling are the same number in two places, held together by a test rather than by hope — and that test is also the alarm for the day a ceiling is raised above a cap, at which point the coupling check stops being redundant. **Changes trading behaviour** only for anyone who overrides; the defaults are unmoved. Found by F6 |
| D29 | Phase 3 dependency | **Phase 3 (scanner) is gated on Phase 2a, not only Phase 2** (PRD §12.1 amended) | §12.1 listed Phase 3 as depending on Phase 2, with 2a a sibling rather than a predecessor, and §5.5's only hard gate is on Phase 5. So the roadmap as written permitted building the scanner to §4.2's filter set before knowing whether that filter set is obtainable from any provider at any price — which is the specific waste §5.5 spends three paragraphs warning about, and a negative Q1 rewrites §4 and therefore the scanner's entire input contract. **Cost, stated because it is real:** vendor lead times are weeks, so this puts Phase 3 behind an external dependency, and if the spike stalls Phase 3 stalls with it. That is the intended effect — a stalled Phase 3 is cheaper than a rewritten one. Rejected: gating only the §4.2 hard filters while permitting the scanner skeleton, which needed a boundary specified in §12.1 for a saving of a few days on a phase that is not started; and leaving §12.1 alone on the grounds that rework is acceptable, which is the position §5.5 already argues against |
| D28 | `mode` default | **`beginner`**, as PRD §2.0 declares (was `experienced` in code) | The document's declared default disagreed with the code, and the PRD disagreed with itself: every §2.2/§3.2/§3.3/§3.4 worked example computes risk as 1% × $30,000, which is the *experienced* preset. Resolved in favour of the §2.0 row on two grounds — a risk system should default to the conservative setting, and a definition outranks an illustration. **Changes trading behaviour for every caller of `Config.default()`**: risk-per-trade 1.0% → 0.5%, daily loss 3% → 2%, open positions 3 → 1, consecutive losses 3 → 2, and every §3 share count halves. The examples now state which preset they use, and `python -m tradipy demo` runs in `experienced` for exactly that reason. Rejected: amending §2.0 to `experienced`, which would have made the safer setting the one you have to ask for. Found by F5 |

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
| **Spec drift between sections** | Six rounds of contradictions have been found, each of a class invisible to the previous fix (see Workstream 11). The parameter registry, the §21.1 worked-example / boundary / rounding-direction fixtures, and the enforcement fixtures are now **all built and green**, and §20 is declared normative. What remains unmitigated: the §15/§16 supersession sweep is prose comparison and does not mechanize, and **no version of this document has been read by anyone without prior context**. The pattern is that each round finds something the last one could not, and the fifth class was predicted here and still needed a fresh reader to find |
| **Drift between the spec and the code that implements it** | New in v0.1.0, and the fifth defect class. Four guarantees the documentation asserted were not enforced by the mechanism built for them, including one — `Config.polarity()` — that had zero callers while being documented as the thing deciding rounding direction. Mitigated by `tests/test_enforcement.py`, whose rule is: for every documented guarantee, write the test that performs the violation it forbids. **Residual risk is high**, because this class is created by ordinary maintenance — a mechanism silently stops being called and nothing but a purpose-built test notices |
| **The instrument is outside every check** | The sixth defect class, found by [REVIEW-2026-07-30](reviews/REVIEW-2026-07-30.md). Five of the six checks range over `src/tradipy/` and the PRD only; the sixth, the registry lint, does reach `scripts/spike2a/` and is a pytest test that pre-commit does not run, so it failed the build for two commits and told nobody. The number that would move a threshold is produced in `scripts/spike2a/`, which §8 exempts from coverage. A hand-derived R there moved the §7 Q4 verdict from INERT to CALIBRATED. **Residual risk is high and the mitigation is not built**: the proposal is that any value capable of triggering a D7 disposition must derive from the library and be reproducible from a provenance-marked input. Until then, treat every spike number as unverified regardless of how the pipeline reports it |
| **The gap between *registered* and *enforced*** | The second population of the fifth class, found by [REVIEW-2026-07-29](reviews/REVIEW-2026-07-29.md) and unmitigated. **11** of 47 registered thresholds have no reader outside `params.py` (17 when the finding was written; `scripts/spike2a/universe.py` and the generator now read six of the §4.2 filters), and 7 of the 11 are read nowhere at all, and `daily_loss_pct` — NON-BYPASSABLE per §7 — has a legal range, a cap check and no enforcement point. Not premature — registering §4 and §7 ahead of their engines is what made D27 possible — but **nothing in the registry marks which is which**, so it answers "registered" to a question about enforcement. `test_enforcement.py` cannot cover this: its rule ranges over guarantees the code makes, and these are guarantees the code has not reached. Proposed mitigation is a `Param.enforced_by` field with a test asserting it in both directions (G1) |
| Cost estimates are estimates | `est_round_trip_cost_per_share` ($0.015) drives the D17 separation floor, and `impact_coefficient` (1.0) drives D22's slippage term. Both are unmeasured. Calibrate from real paper fills in Phase 4b before trusting any expectancy figure |

---

## What This Plan Does NOT Include

Two of these have since been built and are struck through; the reason each was un-deferred is given.

- ~~Python project scaffolding (`pyproject.toml`, modules)~~ — **built.** `pyproject.toml`, `uv.lock`, Ruff, BasedPyright, CI and a tag-driven release workflow
- ~~The invariant layer~~ — **built** (package v0.1.0). Not a change of scope so much as a recognition that the §21.1 fixture suite could not exist without the rules it tests being executable. It carries the parameter registry, tick rounding, the pre-entry gates, the three §20 computations that need no feed, and `python -m tradipy` as a runnable proof of concept
- IBKR API integration code
- Backtester or scanner implementation
- Desktop GUI implementation

The remaining three are deferred until the Phase 2a spike reports. A scanner built against a data source that turns out not to exist is the specific waste PRD §5.5 warns about.

**One exception worth naming:** the Phase 2a data spike is investigative code, not implementation, and it should start now rather than waiting on the documentation queue. It answers whether a §4.2-matching candidate list is obtainable at all, at what cost, and with what spread distribution — three questions that between them determine whether the rest of this plan is buildable. **It has now been deferred twice**, both times in favour of work that could be finished in one sitting. That is a real reason and it does not get to be used a third time.
