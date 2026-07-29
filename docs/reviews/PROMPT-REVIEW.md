# Review of the Source Architect Prompt

**Subject:** [prompts/ross_cameron_trading_system.pdf](../../prompts/ross_cameron_trading_system.pdf) — *"Quantitative Trading System Architect Prompt: Reverse-Engineering Ross Cameron's Discretionary Momentum Methodology," Revised Edition* (7 pages, ~2,350 words)

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

§4 lists **26** required strategy components — of which **14 are tradeable setups**; the other twelve are scanner filters (gap scanner, relative volume, low float, news catalysts), position management (scaling in, scaling out), risk rules (risk management, daily loss limits, max losses, position sizing), and operations (journaling, statistics). §6.3 then requires, **for every setup**: entry criteria, exit criteria, exact stop rule, profit targets, position sizing, pre/post-signal filters, invalidation rules, required *and* optional confirmations, edge cases, worked numeric examples, and known false-signal patterns.

That is roughly 170 specification cells across the tradeable setups alone. The predictable outcome is uniform shallowness: the three MVP setups — the only ones being built — received the same thin treatment as the eleven that will not be touched for a year. The prompt's own MVP logic (§6.12) contradicts its specification demand (§6.3).

**A secondary defect: the prompt calls all 26 "setups" in its acceptance criteria while calling them "components" in §4.** The two words carry different obligations, and §8's criterion 1 — "every setup ... has entry, exit, stop, target, and invalidation rules" — is unsatisfiable for twelve of them by construction. There is no stop placement for Statistics. The "where applicable" qualifier rescues the criterion technically, but leaves the denominator undefined, which is how earlier revisions of both the PRD and this review came to cite 27 setups and reason about "the remaining 24."

**Prompt fix:** *"Specify the three highest-confidence setups to implementation depth. Catalogue the remainder at one paragraph each, with confidence and a note on what full specification would require."*

### 3.7 Non-functional requirements get one sentence

§6.2 compresses performance, reliability, latency, security, logging, audit trail, configuration management, testing strategy, deployment, and scalability into a single sentence — versus a full page on trading setups.

Relative weighting in a prompt is read as relative importance. **Consequence in the docs:** v1.0 had no testing strategy, no crash-recovery or reconciliation design, no IB Gateway 2FA/daily-restart handling (the most common failure mode for unattended IBKR systems), no DST or half-day calendar handling, and a disconnect policy that was both impossible and unsafe. PRD §21 now covers this ground.

### 3.8 The source material is framed uncritically

§7.1 directs review of "publicly available educational material (books, videos, webinars, blog posts, documented examples)" without noting that this material is the commercial output of a trading-education business, or that its performance claims are unaudited and subject to survivorship and selection bias.

§7.2's request for confidence "that the rule reflects the original methodology" treats the methodology as **ground truth to be faithfully copied**, rather than a hypothesis to be tested. Combined with §3.2 above, the prompt has no mechanism for concluding "this strategy may not work."

**Prompt fix:** *"Treat the source material as a hypothesis, not ground truth. Note that performance claims originating from trading-education businesses are unaudited marketing and must not be treated as expected results."*

### 3.9 Solution is pre-specified where the problem should be

Python (§5), IBKR (§5), a desktop application with eleven named screens (§6.11), and a full relational schema (§6.10) are all fixed before any analysis. That is legitimate if they are hard constraints, and for a personal trading system they plausibly are.

The criticism is one of **opportunity cost, not waste** — the same argument as §3.6 and §3.10. §6.12 says "no fancy GUI required" *for the MVP gate* and schedules the GUI at Phase 8, so specifying a Phase 8 deliverable in a Phase 1 product spec is ordinary forward planning. But the prompt allocates eleven named screens and a full schema to components that will not be built for a year, and one sentence (§6.2) to the non-functional requirements needed to run the thing at all. Attention spent on GUI wireframes is attention not spent on computation semantics, and it is the missing semantics (§3.5) — not the presence of wireframes — that actually blocked implementation. The problem is the prompt's *weighting*, not the inclusion of any single item.

### 3.10 "Be exhaustive" conflicts with "minimal ambiguity"

§9 asks for both, and across 26 components they are in direct tension: exhaustive coverage consumes exactly the attention that precision requires. The prompt never ranks them, so the agent optimized for the more visible one — surface area.

### 3.11 Interfaces are named but never exemplified

§6.9 demands components with "clearly defined responsibilities, **interfaces, and data contracts**," then supplies a bulleted list of fifteen component *names* and no example of what an interface or a contract should look like.

Contrast §7.4, where a single filled-in specimen row successfully forced concreteness across an entire matrix. The outcome tracks the difference exactly: PRD §9.1 gave all fifteen components a responsibility and prose Inputs/Outputs, while §9.2 typed **two** payloads. Every arrow in the §9.3 event flow except signal→order was untyped until v1.3.

This generalizes into the single most useful observation in this review: **the prompt is strongest wherever it supplies an example, and weakest wherever it supplies only a list.** §7.4's specimen produced a 26-row matrix with no empty cells. §6.9's bare list produced two contracts out of fifteen. A specimen is worth more than an adjective — "interfaces and data contracts" produced neither, where one example dataclass would have produced fifteen.

**Prompt fix:** *"Supply one worked specimen for every artifact type you require — one dataclass, one interface signature, one contract — at the level of concreteness you expect. A list of names will be returned as a list of names."*

### 3.12 "Sensitivity" is demanded before measurement can exist

§3 requires, per threshold, "(b) sensitivity — **how much** performance may change if the value is altered." "How much" is a quantity. All fourteen rows in PRD §2 answer qualitatively and directionally ("High — 3× captures more names; 10× misses early movers"). Not one gives a magnitude.

This is arguably unanswerable at Phase 1: you cannot quantify sensitivity without the backtest that Phase 4b produces. It is therefore **a sequencing flaw of the same family as §3.1** — it demands, before any measurement exists, an output that only measurement can supply. The honest response would have been to state the substitution explicitly; the docs answered qualitatively without flagging it.

**Prompt fix:** *"Where a requested quantity cannot be produced without measurement that does not yet exist, say so explicitly and name the phase that will produce it. Do not silently substitute a qualitative answer."*

---

## 4. Rewrite checklist

If this prompt is reused, these twelve changes would address the substance of what went wrong
(the twelfth was added by §6.2 below; this sentence said "eleven" for two revisions after the
list grew — the same self-assessment miscount this document criticises at §3.6):

1. **Move falsification before construction.** Require an evidence gate — expectancy net of costs, out-of-sample — before any execution-engine or paper-trading phase.
2. **Add an economics section.** Breakeven win rate at the chosen R:R, estimated per-trade cost drag, and what evidence would falsify the strategy.
3. **Require normative computation semantics** for every indicator and level before any rule may reference it.
4. **Split setups by depth:** three to implementation depth, the rest catalogued.
5. **Make acceptance criteria correctness-based:** worked examples must be recomputed and must satisfy their own rules; no parameter may hold conflicting values across sections.
6. **Replace the "no clarifying questions" bullet** with an actual cold-reader test whose output must be an empty list.
7. **Give NFR/operations its own section** with weight comparable to the trading rules — explicitly including broker re-authentication, crash recovery, reconciliation, and time/calendar handling.
8. **Reframe the source as hypothesis**, and require explicit skepticism toward vendor performance claims.
9. **Require a parameter registry.** Every threshold defined exactly once with a canonical name; every other mention references it by name and never restates the literal. See §6.
10. **Supply a specimen for every artifact type demanded** — one dataclass, one interface, one contract — at the concreteness level expected. A bare list of names comes back as a list of names (§3.11).
11. **Forbid silent substitution.** Where a demanded output requires measurement that does not yet exist, the response must say so and name the phase that will supply it, rather than answering qualitatively as though the question had been met (§3.12).
12. **Require rules to state their own scope.** A rule asserted to hold "in every case" must enumerate the cases, and each new instance must be classified against that enumeration rather than matched by analogy to the nearest one in the text (§6.2).

---

## 5. Attribution: which PRD defects came from the prompt

| PRD/PLAN defect (v1.0) | Prompt origin |
|---|---|
| Backtesting after the paper-trading MVP gate | §6.12 phase order — inherited verbatim |
| No analysis of whether the strategy is profitable | §7/§8 measure fidelity only (§3.2 above) |
| Fully-ticked checklist over a contradictory document | §8 presence-based criteria (§3.3) |
| Four worked examples violating their own rules | §6.3 asks for examples, never for consistency (§3.3) |
| VWAP / HOD / flagpole height undefined | No computation-semantics requirement (§3.5) |
| 14 tradeable setups specified shallowly; 3 MVP setups no deeper | §4 + §6.3 breadth demand (§3.6) |
| Data contracts typed for 2 of 15 components | §6.9 names components, supplies no specimen (§3.11) |
| Sensitivity answered qualitatively for all 14 thresholds | §3 demands "how much" before any measurement exists (§3.12) |
| Slippage model lacked an impact term until v1.3 | §6.8 names "spread + impact" once in passing; §6.6 asks only for "slippage model & assumptions" |
| Security reduced to secrets handling | §6.2 compresses ten NFR topics into one sentence (§3.7) |
| No testing strategy, recovery, reconciliation, 2FA, DST | §6.2 one-sentence NFR treatment (§3.7) |
| Warrior Trading claims treated as reliable | §7.1 uncritical source framing (§3.8) |
| GUI wireframes for a deferred Phase 8 interface | §6.11 vs §6.12 conflict (§3.9) |
| Self-certified acceptance with no reviewer | §8 final bullet is unverifiable by the author (§3.4) |

**Defects *not* attributable to the prompt** — these were independent authoring errors: the Windows-1252 encoding corruption; the inverted flag-volume comparison; the unreachable VWAP stop branch; the unnormalized composite score; the UUID-based duplicate check that could never fire; the missing `signals` table behind declared foreign keys; and the timeline that did not sum to its own rows.

---

## 6. Postscript: three defect classes this review missed

This review was written alongside PRD v1.1 and helped shape it. A later round found a **second class** that neither the prompt's acceptance criteria nor this critique anticipated, and it is worth recording because the fix for the first class actively concealed it.

v1.1 corrected the trading rules but left superseded copies of them in downstream sections. The room-gate multiple was raised to 2.5 in §2.0 and §3.1.1 while all three setup criteria still read `≥ 2 ×` — and the worked examples, which *were* recomputed, used 2.5 and passed. Verification confirmed the examples against the new value and never asked whether the document agreed with itself. §15 likewise still carried a scaling-in rule that §7.1.1 had explicitly overturned, and §4.3 still carried the composite score §20.10 documents as broken.

Three observations:

1. **The prompt is partly culpable after all.** §3.3 above criticized §8's acceptance criteria for testing presence rather than correctness, but framed correctness as *arithmetic*. Internal agreement between sections is a distinct property, and no criterion tests it. The prompt fix in §3.3 should read: *"...and no parameter may hold conflicting values across sections."*
2. **This review is not exempt.** §3.9 above overreached and has been revised. A critique is subject to the same standard it applies.
3. **Neither fix is a sweep.** Worked-example fixtures (PRD §21.1) catch the arithmetic class; a parameter registry catches the consistency class. Both are mechanical, and mechanical checks are the only kind that survive the author's own confidence — which is the same argument §3.4 makes about the "no clarifying questions" criterion, applied to the document rather than the reader. Two further classes have since been found; see §6.1 and §6.2.

### 6.1 A third class, found by the v1.2 review

[REVIEW-v1.2.md](REVIEW-v1.2.md) found a class neither the arithmetic fixtures nor a parameter registry would catch: **two parameters that are individually correct and jointly incoherent.**

The §4.2 spread filter admitted spreads up to 1% of price. The §3.1.2 separation floor consumed spread as an input. Both were defensible in isolation; together they meant every worked example failed its own gate at the widest spread the scanner permitted, and that round-trip spread cost could reach 83% of R — above the erosion threshold PRD §18.2 identifies as fatal. The examples passed only because they assumed a $0.01 spread and never tested the boundary.

No consistency check catches this, because nothing is inconsistent. Each value appears once. The registry would have been satisfied.

**The generalizable fix is a boundary test, not a consistency test:** every worked example must be recomputed at the extreme values its own filters admit, not only at the convenient values chosen to illustrate it. That is now PRD §21.1's worst-case fixture row, and it belongs in the rewrite checklist as a strengthening of item 5:

> *Worked examples must satisfy their own rules at the boundary of every filter they depend on, not merely at illustrative values. An example that passes at a typical input and fails at a permitted one is a defect in the filter, the example, or both.*

### 6.2 A fourth class, found by the v1.3 review

[REVIEW-v1.3.md](REVIEW-v1.3.md) found a class invisible to all three checks above: **a rule stated more broadly than its justification supports, then applied outside the range where it holds.**

PRD §20.13 said price rounding was "asymmetric and conservative in every case," with gate thresholds rounding **up**. That is conservative for a floor a value must exceed — raising it makes the requirement harder to clear. It reverses for a ceiling a value must stay under: rounding a maximum spread *up* admits wider spreads than the unrounded threshold. When §3.1.3's spread cap was added it inherited `ceil_to_tick` from the neighbouring rule, and the gate became more permissive while the prose two sections away asserted the opposite.

Every existing check passes this. The rule is stated exactly once, so the registry is clean. The arithmetic in §3.1.3's tables is correct — the tables had in fact been computed with `floor`, the right function, which is why the boundary fixture passed. What was wrong was the *sentence*, and the disagreement between a formula and the tables that apply it is the one thing none of the three mechanical checks reads.

**The generalizable fix is to scope the universal claim.** Any normative statement carrying *always*, *never*, *in every case*, or *uniformly* is asserting something about cases that may not have been enumerated, and is the natural place to ask which ones actually were. §20.13's closing sentence was false for the one case that had just been added to it. The concrete mechanization is narrow but real: a fixture must assert *why* a value is correct, not merely that it matches — `assert cap == 0.01` passes under a wrong rule that happens to agree at that input, while `assert cap == floor_to_tick(x) and cap <= x` does not.

This adds a twelfth item to the rewrite checklist:

> *A rule that generalizes must state the range over which it holds. Where a rule is asserted to apply "in every case," the cases must be enumerable, and each new instance must be classified against that enumeration before the rule is applied to it — not matched by analogy to whichever instance is nearest in the text.*

### 6.3 Where this leaves the argument

Four review rounds, four distinct failure classes — arithmetic, cross-section consistency, joint parameter coherence, and over-general rules. Each was invisible to the check designed for the one before it, which is the strongest available argument that self-certification is not a substitute for a cold reader.

It is also, by now, an argument against expecting the next check to be the last one. The four fixes are worth building because each closes a class that has actually occurred, not because their conjunction is complete. The reasonable expectation is that a fifth class exists and that it will surface the same way the other four did: from a reader who did not write the document and therefore cannot see what it was meant to say.
