# Review of the Source Architect Prompt

**Subject:** [prompts/ross_cameron_trading_system.pdf](../prompts/ross_cameron_trading_system.pdf) — *"Quantitative Trading System Architect Prompt: Reverse-Engineering Ross Cameron's Discretionary Momentum Methodology," Revised Edition* (7 pages, ~2,350 words)

**Reviewed:** 2026-07-28 · **Reviewer note:** this is a critique of the *prompt*, not of the PRD it produced. Several defects found in PLAN.md and PRD.md trace directly back to instructions here, and are attributed below.

---

## 1. Summary judgment

This is a well-above-average specification prompt. It correctly identifies that the hard problem is converting *judgment* into *rules*, and it builds real machinery to force that conversion — confidence ratings, a discretion register, a validation matrix with a worked example row, and an assumptions register. The backtest-realism section (§6.8) is more sophisticated than most retail algorithmic-trading specifications.

Its weaknesses are structural rather than careless, and they are consequential:

1. It sequences backtesting **after** the paper-trading gate.
2. It measures fidelity **to Ross**, and never once asks whether the strategy is profitable.
3. Its acceptance criteria are **presence checks**, not correctness checks — which let a document with fourteen internal contradictions and four broken worked examples pass a fully-ticked checklist.

The net effect: the prompt reliably produces a document that *looks* complete and is not implementable. That is what happened.

---

## 2. What the prompt gets right

| # | Strength | Where |
|---|----------|-------|
| 1 | Names the real problem — every subjective decision must become an explicit rule or a documented assumption, with "do NOT leave discretionary logic unspecified" | §2 |
| 2 | Demands, per threshold: source citation, confidence rating, **sensitivity**, and user-configurability. Forcing sensitivity analysis is unusually good practice | §3 |
| 3 | Requires multiple deterministic alternatives per discretionary element, with tradeoffs, plus one recommendation marked as an assumption | §2, §7.3 |
| 4 | Backtest realism list is genuinely expert: partial fills on thin names, halt/LULD resumption gaps, look-ahead controls **naming RVOL and news timestamps specifically**, opening-auction modeling, corporate actions, walk-forward, Monte Carlo bootstrap for drawdown confidence | §6.8 |
| 5 | Risk rules must specify condition + enforcement point + violation action, and at least two rules must be non-bypassable | §6.7, §8 |
| 6 | Provides a filled-in example row to set the expected level of concreteness — good prompt technique, and the one thing that made a source discrepancy detectable | §7.4 |
| 7 | "Distinguish consistently taught principles from isolated examples. Do not treat every example as a strict rule." Excellent epistemic instruction | §7.1 |
| 8 | Explicit scope discipline: reserve AI extension points, **do not design them yet** | §6.14 |
| 9 | Asks the agent to challenge assumptions and identify hidden complexities and risks | §9 |
| 10 | Closing framing — transparent, auditable, testable, with every divergence from discretionary judgment documented — is exactly the right goal | §9 |

---

## 3. Structural flaws, ranked by consequence

### 3.1 Backtesting is sequenced after the MVP gate — the worst decision in the prompt

§6.12 lays out: Phase 5 execution → Phase 6 risk engine → **MVP Gate (paper-trade ready)** → Phase 7 backtesting.

This instructs the agent to design and build order routing, risk enforcement, and live paper trading **before any evidence exists that the setups have an edge**. Backtesting is the cheapest possible falsification step — it needs only historical bars — and it is placed after the most expensive build work.

**Consequence in the docs:** PRD §12.1 inherited this order verbatim. It has since been overridden with a Phase 4b lightweight validation and a Viability Gate placed *before* the execution engine (PRD §12.1, §18.7).

**Prompt fix:** *"Before specifying the execution engine, define the minimum evidence required to believe the strategy is profitable net of costs, and place that evidence gate before any paper- or live-trading phase."*

### 3.2 It never asks whether the strategy makes money

This is the deepest flaw, and it is easy to miss because the prompt is so thorough about everything else.

Every validation mechanism in §7 measures **fidelity to Ross Cameron**. §7.2 asks for "confidence level that the rule reflects the original methodology." §7.6's Confidence Report categorizes how objectively each component can be implemented. §8's acceptance criteria check completeness of specification.

**Nowhere does the prompt ask: is this profitable? What is the expected value per trade? Does the edge survive slippage and commissions? What evidence would falsify it?**

"Faithful to Ross" and "profitable" are different questions. A specification can score High confidence on every row of the validation matrix and describe a system that loses money on every trade. The prompt's entire quality apparatus is pointed at the wrong target.

**Consequence in the docs:** the PRD's economic foundation was a single unexamined line in the assumptions register (A2: "2:1 R:R produces positive expectancy at ~50% win rate"). PRD §18 now exists to address this, but the prompt gave it no place to live.

**Prompt fix:** require a section stating the breakeven win rate at the chosen R:R, the estimated per-trade cost drag, and the specific evidence that would falsify the strategy.

### 3.3 Acceptance criteria test presence, not correctness

Every bullet in §8 has the form *"X exists / is populated / contains no empty cells"*:

- "thresholds are **populated** with defaults, confidence ratings, source notes"
- "Validation Matrix ... contains **no empty** 'Deterministic Rule' cells"
- "All assumptions are **listed** in one place"

Not one criterion requires the rules to be mutually consistent, or the arithmetic to be right. **A document can satisfy 100% of §8 while contradicting itself throughout** — and the v1.0 PRD did exactly that: a fully-ticked checklist sat on top of four worked examples that violated their own stop rules, an inverted target ladder, a scaling-in rule that broke a non-bypassable risk cap, and a circular daily-loss denominator.

**Prompt fix:** add — *"Every worked example must be recomputed from the stated rules and must satisfy them. Any example contradicting its own rules is a defect. Cross-check that no two sections specify conflicting values for the same parameter."*

### 3.4 The "no clarifying questions" criterion is unverifiable and counterproductive

§8's final bullet: *"A software engineer unfamiliar with Ross Cameron could begin implementation of the MVP without needing to ask clarifying questions about trading logic."*

Two problems. First, **the author cannot verify this** — only an actual unfamiliar engineer can, so the criterion structurally invites self-certification. Second, it rewards *sounding* unambiguous. "Hard stop at the low of the pullback" reads as precise and passes the check, while concealing: which low, measured from which candle, and what happens when that low is 7% away?

**Consequence in the docs:** this box was ticked in PRD §19 while a cold review by a fresh reader produced a long list of blocking questions. PLAN Workstream 11 now converts the criterion into an actual test.

**Prompt fix:** *"A reviewer unfamiliar with the methodology must read the MVP sections and enumerate every remaining question. The criterion is met only when that list is empty."*

### 3.5 It never asks for computation semantics

The prompt asks for "entry criteria (boolean + numeric)" (§6.3), which sounds rigorous. It is satisfied by `close > VWAP` — without ever requiring a definition of VWAP.

Nothing in the prompt asks for: VWAP session anchoring and whether premarket volume is included; whether HOD is wick- or close-based; bar timestamp conventions (open-labeled or close-labeled) and partial-bar handling; EMA seeding; as-of semantics for cumulative features; or how "tighter" and "wider" resolve for a long stop.

These are exactly the details that separate a document an engineer can build from one they must interrogate. **This omission is the single largest cause of the implementability gap in the PRD**, and it prompted the addition of PRD §20 (Computation Semantics, normative).

### 3.6 Breadth is demanded at the expense of depth

§4 lists ~27 required strategy components. §6.3 then requires, **for every setup**: entry criteria, exit criteria, exact stop rule, profit targets, position sizing, pre/post-signal filters, invalidation rules, required *and* optional confirmations, edge cases, worked numeric examples, and known false-signal patterns.

That is roughly 300 specification cells. The predictable outcome is uniform shallowness: the three MVP setups — the only ones being built — received the same thin treatment as the twenty-four that will not be touched for a year. The prompt's own MVP logic (§6.12) contradicts its specification demand (§6.3).

**Prompt fix:** *"Specify the three highest-confidence setups to implementation depth. Catalogue the remainder at one paragraph each, with confidence and a note on what full specification would require."*

### 3.7 Non-functional requirements get one sentence

§6.2 compresses performance, reliability, latency, security, logging, audit trail, configuration management, testing strategy, deployment, and scalability into a single sentence — versus a full page on trading setups.

Relative weighting in a prompt is read as relative importance. **Consequence in the docs:** v1.0 had no testing strategy, no crash-recovery or reconciliation design, no IB Gateway 2FA/daily-restart handling (the most common failure mode for unattended IBKR systems), no DST or half-day calendar handling, and a disconnect policy that was both impossible and unsafe. PRD §21 now covers this ground.

### 3.8 The source material is framed uncritically

§7.1 directs review of "publicly available educational material (books, videos, webinars, blog posts, documented examples)" without noting that this material is the commercial output of a trading-education business, or that its performance claims are unaudited and subject to survivorship and selection bias.

§7.2's request for confidence "that the rule reflects the original methodology" treats the methodology as **ground truth to be faithfully copied**, rather than a hypothesis to be tested. Combined with §3.2 above, the prompt has no mechanism for concluding "this strategy may not work."

**Prompt fix:** *"Treat the source material as a hypothesis, not ground truth. Note that performance claims originating from trading-education businesses are unaudited marketing and must not be treated as expected results."*

### 3.9 Solution is pre-specified where the problem should be

Python (§5), IBKR (§5), a desktop application with eleven named screens (§6.11), and a full relational schema (§6.10) are all fixed before any analysis. Legitimate if they are hard constraints — but §6.11 demands a full GUI specification while §6.12's MVP explicitly excludes the GUI. That guarantees wasted effort, and it duly appeared: PRD §11 contains wireframes for an interface deferred to Phase 8.

### 3.10 "Be exhaustive" conflicts with "minimal ambiguity"

§9 asks for both, and across 27 setups they are in direct tension: exhaustive coverage consumes exactly the attention that precision requires. The prompt never ranks them, so the agent optimized for the more visible one — surface area.

---

## 4. Rewrite checklist

If this prompt is reused, these eight changes would address the substance of what went wrong:

1. **Move falsification before construction.** Require an evidence gate — expectancy net of costs, out-of-sample — before any execution-engine or paper-trading phase.
2. **Add an economics section.** Breakeven win rate at the chosen R:R, estimated per-trade cost drag, and what evidence would falsify the strategy.
3. **Require normative computation semantics** for every indicator and level before any rule may reference it.
4. **Split setups by depth:** three to implementation depth, the rest catalogued.
5. **Make acceptance criteria correctness-based:** worked examples must be recomputed and must satisfy their own rules; no parameter may hold conflicting values across sections.
6. **Replace the "no clarifying questions" bullet** with an actual cold-reader test whose output must be an empty list.
7. **Give NFR/operations its own section** with weight comparable to the trading rules — explicitly including broker re-authentication, crash recovery, reconciliation, and time/calendar handling.
8. **Reframe the source as hypothesis**, and require explicit skepticism toward vendor performance claims.

---

## 5. Attribution: which PRD defects came from the prompt

| PRD/PLAN defect (v1.0) | Prompt origin |
|---|---|
| Backtesting after the paper-trading MVP gate | §6.12 phase order — inherited verbatim |
| No analysis of whether the strategy is profitable | §7/§8 measure fidelity only (§3.2 above) |
| Fully-ticked checklist over a contradictory document | §8 presence-based criteria (§3.3) |
| Four worked examples violating their own rules | §6.3 asks for examples, never for consistency (§3.3) |
| VWAP / HOD / flagpole height undefined | No computation-semantics requirement (§3.5) |
| 27 setups specified shallowly; 3 MVP setups no deeper | §4 + §6.3 breadth demand (§3.6) |
| No testing strategy, recovery, reconciliation, 2FA, DST | §6.2 one-sentence NFR treatment (§3.7) |
| Warrior Trading claims treated as reliable | §7.1 uncritical source framing (§3.8) |
| GUI wireframes for a deferred Phase 8 interface | §6.11 vs §6.12 conflict (§3.9) |
| Self-certified acceptance with no reviewer | §8 final bullet is unverifiable by the author (§3.4) |

**Defects *not* attributable to the prompt** — these were independent authoring errors: the Windows-1252 encoding corruption; the inverted flag-volume comparison; the unreachable VWAP stop branch; the unnormalized composite score; the UUID-based duplicate check that could never fire; the missing `signals` table behind declared foreign keys; and the timeline that did not sum to its own rows.
