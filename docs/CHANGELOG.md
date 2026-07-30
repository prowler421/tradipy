# Changelog — PRD

Corrections and reversals to [PRD.md](PRD.md), extracted so the spec itself can state only what is true.

**Why this file exists.** Through v1.2 the PRD narrated its own corrections in place — roughly twenty passages of the form "an earlier draft required ≥ 70%," "the earlier version quoted three different entry prices," "(Removed: … was unreachable)." That was the right instinct during review: it prevented silent reversals and made the error-correction record auditable. But it worked against the document's primary job. An implementer reading §3.2 should not have to work out which rule is current and which is a retracted ancestor, in a section whose entire purpose is to be unambiguous.

**One inline note is retained deliberately.** §3.2 criterion 5 keeps its correction marker, because `≤ 70%` reads as a typo to anyone expecting `≥` and the reversal is genuinely counter-intuitive. Every other correction lives here.

**Reading this file.** Entries are grouped by the release that made the change. Each says what the rule *was*, what it *is*, and why — the "why" being the part that stops the same error recurring.

---

## Unreleased — raised by REVIEW-2026-07-30, not yet dispositioned

Driven by [REVIEW-2026-07-30.md](reviews/REVIEW-2026-07-30.md), the third round to review code and the first to review the Phase 2a instrumentation. **No rule in the PRD changes here, and no threshold moves.** Every *code* finding is in `scripts/spike2a/` — four of the fifteen are documentation defects elsewhere — and `src/tradipy/` is behaviourally identical to v0.1.0 (`git diff 114ef86 HEAD -- src/` is two formatting reflows and one docstring). The round's own gate finding — `make check` red at `3545adf` while four documents said the guardrail was enforced — is a code defect and is recorded in the root [CHANGELOG.md](../CHANGELOG.md), not here. What is below is the part that is not the reviewer's to settle.

### Spec questions — open

| Where | The question | Why it is a spec question, not a fix |
|-------|--------------|-------------------------------------|
| PHASE-2A-SPIKE §7 (**H7**) | §7 binds every threshold "before any data was pulled" and permits amendment "only in a commit that predates the next data pull." **Synthetic data now exists and a §7 verdict has been printed over it — twice, with different answers.** Does a synthetic run count as a data pull for that clause? | If it does, §7 is now frozen against fabricated input, which is absurd — the pre-registration would be locked by a random number generator. If it does not, "no data existed yet" stops being checkable from the repository, since the artifact that proves a run happened is gitignored. The round proposes **"no" — a provenance-marked synthetic run is not a data pull** — and declines to write that into the document: §7's amendment rule is the one thing in the spike that cannot be amended by the person it constrains |
| PHASE-2A-SPIKE §7 (**H5**) | §7 defines the sample as "every symbol-session **in the two windows** that passes the selection rule." `windows.select_windows` computes the windows and `universe.select_sample` applies the filters, and **nothing joins them** — the module has no window parameter, so the 400-cap and the filters range over whatever CSV is supplied. Does the join belong in `universe.select_sample`, in a new composing module, or in the collection script §7 assumes? | Each answer makes a different thing authoritative. Putting it in `select_sample` makes the module the definition of the sample and changes a documented signature; putting it in a composer leaves `universe` reporting on a population §7 does not define, which is how the round found it; leaving it to the collection script means the binding half of the sample definition is enforced by a script that is not in the repository. §8 forbids the spike growing into the scanner, and "compose the two halves" is the first step of exactly that growth — so the boundary is a scope decision |
| §21.1 / PHASE-2A-SPIKE §8 (**H2**) | §8 grants `scripts/spike2a/` **no test-coverage obligation**, and the first defect found there was a timestamp expression emitting `09:60`–`09:89` that silently discarded half a quote file. Should the exemption be narrowed — e.g. to "no coverage obligation, but any file the measurement reads must have a parse-rate assertion"? | The exemption is load-bearing and correct in its intent: coverage obligations are how throwaway code becomes permanent. But it was granted on the assumption that spike defects are cheap, and this one changed a §7 verdict. Narrowing it is a change to what §8 protects against; keeping it means the measurement that gates Phase 3 is the least-tested code in the repository, deliberately. Not the reviewer's call |

### Raised, and not answerable here

`tests/README.md` states **47/47** mutations caught and enumerates 22 + 13 + 11 = **46**. Review round 6's G8 reconciled `test_boundary.py`'s header to "twelve", matching the prose rather than the enumeration; one of the two is wrong and **this round cannot say which**, because mutation testing needs an environment it did not have (see the review's appendix). Resolve it by re-running the twelve rounding mutations and recording the result, not by editing whichever number is easier to reach.

---

## Unreleased — raised by REVIEW-2026-07-29, not yet dispositioned

Driven by [REVIEW-2026-07-29.md](reviews/REVIEW-2026-07-29.md), a verification round over package v0.1.0. **No rule in the PRD changes here, and no threshold moves.** The round's job was to check that v1.3.2's twelve findings were really closed — **ten** are, against file and line; F12 is correctly still open because leaving it open was its disposition; and **F8 is not closed**, its no-literal half standing unqualified in all six places it appears, `CLAUDE.md` among them — and its own findings are either small code fixes or the three spec questions below. They are recorded now, unresolved, because [CLAUDE.md](../CLAUDE.md) requires a divergence between code and PRD to be raised rather than settled in code, and because a finding that lives only in a dated review file is one refactor from being lost.

### Spec questions — open

| Section | The question | Why it is a spec question, not a fix |
|---------|--------------|-------------------------------------|
| §7 (**G2**) | `daily_loss_pct` is marked **No (NON-BYPASSABLE)** in §7's Bypassable column, has a legal range in code (D27) and a `HARD_CAPS` check — and **no enforcement point**. Nothing in the package tracks realized P&L. Should its §7 *Enforcement Point* cell be qualified, e.g. "Continuous (1 sec) — Phase 6"? | §7's form is *condition → enforcement point → action*, and this row names an enforcement point that does not exist. Qualifying the cell makes the deferral visible in the normative text that asserts the guarantee; leaving §7 alone and noting it only in `params.py` keeps an unqualified non-bypassable claim in the spec. Either way it is an edit to a row the PRD calls hard, which is not a code decision. Note the shape: F6 was a cap guarding a constant that could not vary; this is a cap guarding a value nothing reads. **Scope correction:** the review's first draft claimed this of four limits, having read §2's configurability column instead of §7's Bypassable column — `max_open_positions`, `max_consecutive_losses` and the two drawdown limits are all marked bypassable by §7 itself, so their absence from code is unremarkable |
| §21.1 (**G4**) | §21.1 enumerates the fixture types and has **no row for the enforcement fixtures** — the check for the fifth defect class, 17 functions in `tests/test_enforcement.py`, named in `CLAUDE.md` convention 6 and in the PLAN's five-class table. Should it gain one? | Because §19 already ticks a row for them (`PRD.md:1898`), the two sections disagree about what the testing strategy contains: the status table credits a fixture type the strategy table does not enumerate. That is the v1.2 class between two sections of one document. The four §21.1 rows are the checks for defect classes one through four; the fifth class's check is missing from the section that catalogues them and present in the section that scores them |
| §2 (**G9**) | `premarket_trading_enabled` (D11, A17) has no home in code because **`Param.default` is `Decimal`-typed and the registry cannot represent a boolean**. Does the registry gain a type, or does the flag live outside it? | If it lives outside, §2's "user-configurable" column means two different things depending on the row, and the registry stops being the single source of truth for tunables. If it goes in, `Config.values`, the AST lint and the frozen baseline all have to accommodate a non-`Decimal`. `impact_coefficient` (D22) and the §2.1 premarket RVOL `× 0.05` coefficient are also unregistered, but neither has this excuse — both are numbers and should be registered when §18.7's arithmetic is implemented at Phase 4b |

### Decided

| ID | Decision |
|----|----------|
| **D29** | **Phase 3 (scanner) is gated on Phase 2a**, not only Phase 2. PRD §12.1's Phase 3 dependency cell is amended from `2` to `2a (gate passed)`. §12.1 as written permitted building the scanner to §4.2's filter set before knowing the set is obtainable from any provider at any price, which is the waste §5.5 spends three paragraphs on; a negative Q1 rewrites §4 and therefore the scanner's input contract. Cost, stated because it is real: Phase 3 now sits behind a weeks-long external dependency, and if the spike stalls Phase 3 stalls. That is intended — a stalled Phase 3 is cheaper than a rewritten one. Full rationale and rejected alternatives in [PLAN](PLAN.md) |

### Convention added, and the reason

`CLAUDE.md` gains convention 8: **a finding fixable in one line, with no spec implication and no behaviour change, gets fixed in the same change and one line in the review — no CHANGELOG entry, no decision, no disposition block.** The six-round review apparatus exists for defects that recur or need a spec call. A heading reading "four" above a list of six needs neither, and this review's first two drafts gave it the same treatment as an unenforced non-bypassable risk limit. The convention names its own weak point: the triviality judgement. When unsure, disposition it — a finding that turns out to recur was never trivial.

Applied immediately to G8, which is therefore **fixed rather than logged**: all six unqualified statements of the no-literal rule now carry the lint's actual scope (`src/tradipy/*.py` non-recursive, skipping `params.py` and `__init__.py`, exempting undistinctive values, not covering `scripts/`) in `CLAUDE.md`, `CONTRIBUTING.md`, `params.py`, `api.md`, `architecture.md` and `.cursor/rules/tradipy.mdc`; `tests/README.md`'s heading reads six; `test_boundary.py:496` reads twelve.

> **Superseded two commits later, and this entry is the seventh copy of the scope it describes.** The parenthetical above — "not covering `scripts/`" — was true when written and false from `d2e94a4`, which extended the lint to walk `scripts/` recursively and updated the six live statements it had just been told about. It did not update this record of the fix, which is F8's own defect class inside F8's own disposition. Left in place with this note rather than rewritten, because the entry is history: what it got wrong is not the scope, it is that a changelog entry restating a rule *is* one of the copies. Found by review round 7.

### Corrections to the PLAN

| Change | Why |
|--------|-----|
| The closing line of the five-defect-classes section read *"The honest extrapolation is that a fifth class exists. It will not be found by tightening any of the four checks above."* Replaced with a forward-looking statement about the sixth | Stale by one round, and it contradicted a paragraph four lines above it that already recorded the fifth class as found and named its check. Exactly the v1.2 class — a claim restated in two places with one updated — in the document whose own table defines that class. Found while wiring in this review, not by the review |
| Added a subsection recording that the fifth defect class has a **second population**: a *parameter* registered and read by nothing, as against a *mechanism* built and not called | 17 of 47 registered thresholds have no reader outside `params.py`, and all but two of those have none at all; `select_flagpole`'s §3.2 qualification predicate has no shipped caller; `is_whole_tick` is called only from tests. `tests/test_enforcement.py` cannot see any of them, because its rule ranges over guarantees *the code makes* and these are guarantees the code has not reached. The gap looks identical from inside the check built for the first population, which is the whole point of recording it |
| New risk row: **the gap between *registered* and *enforced*** | The registry is the artifact this project points at when asked whether a rule is implemented, and it answers "registered". That is the same conflation as F4 |

### Recorded against this round itself

The review's first draft was adversarially fact-checked before it shipped, then fact-checked again after correction. Both passes were needed.

**First pass — nineteen substantive errors**, five in a finding's headline claim. G2 overstated its scope fourfold by reading §2's configurability column instead of §7's *Bypassable* column, two lines from the claim it was making. "All twelve F-findings closed" ignored that F12's disposition was to leave them open. G8 cited a `params.py` docstring that does not mention the lint, and missed five further live instances of the rule it was about. G3 undercounted the spec's reject-code namespace. §20.9 was classified absent on a standard §20.14 was simultaneously credited by. A further thirteen citations were stale `PLAN.md:` line numbers, invalidated by this round's own PLAN edit — now replaced by section names for that reason.

**Second pass — nine more, three of them created by the first pass.** The F-finding count went 12 → 11 → **10**: "eleven closed plus F12 open" accounts for all twelve and leaves no slot for F8, three lines above a table marking F8 not closed. G3's correction asserted that three enum members were code-originated; `PRD.md:241` names two of them, and `rejects.py:35-39` already marks the third exactly as the finding demanded. G8's correction credited three doc ranges to the no-literal rule that are about a different over-claim entirely, so the rule is unqualified in six of six places rather than "the rest." G4's stated *reason* was falsified by a line the review's own F7 row cites: §19 already ticks an enforcement-fixtures row, which makes the finding better — §19 and §21.1 disagree about what the testing strategy contains.

Two errors were **inherited verbatim from REVIEW-2026-07-28 and repeated under the word "confirmed"**: the non-degenerate rounding fixture is not "at the end of `test_boundary.py`", and the twelve surviving mutations are eleven according to the block's own header comment. Recorded here rather than quietly corrected, because between them these two passes are the most direct evidence yet for what Workstream 11 has asked for across six rounds. A verification round inherits the previous round's idea of where to look; a correction pass inherits the correction's. **Agents reading the same repository do not compose into a cold read, however many of them there are.**

---

## v1.3.2 — package v0.1.0

Driven by [REVIEW-2026-07-28.md](reviews/REVIEW-2026-07-28.md), the first review of the **code** rather than of this document. Three of these change trading behaviour and are recorded as decisions D26–D28 in [PLAN](PLAN.md).

The distinctive thing about this round: every finding was a place where the *document was right and the code was not*, which is the reverse of the previous four. Four review rounds hardened the prose; nothing had yet checked whether the implementation of that prose enforced it. Three of the four highest-severity findings sat directly beneath a sentence asserting the opposite, and that sentence is what stopped anyone looking.

### Strategy behaviour

| Section | Was | Is | Why |
|---------|-----|-----|-----|
| §2.0 `mode` (**D28**) | Code defaulted to `experienced` while the §2.0 row says `beginner` | Code defaults to **`beginner`**, as stated | The document's declared default won over its own worked examples, which are all computed at 1% × $30,000 and are therefore *experienced*. Two reasons: a risk system should default to the conservative preset, and the examples are illustrations while the §2.0 row is a definition. **Changes every default share count** — §3.2's Bull Flag is 1,250 shares at the default and 2,500 at the preset the tables use. The examples now say so, and `python -m tradipy demo` runs in experienced mode for exactly this reason. Rejected: amending §2.0 to `experienced`, which would have made the safer setting the one you have to ask for |
| §1, §2.0, §3.1.1, §7 `room_gate_multiple` (**D26**) | All four sections state 2.0 is legal; `validate_couplings` rejected it | 2.0 is legal, and inert | The code's justification cited §3.1.1's *"cannot go below 2.0"* — which is `≥ 2.0`, not `> 2.0` — so the cited section did not support the check, and the deviation was declared nowhere. It was also unnecessary: `min_separation` is a MINIMUM-polarity threshold over a strictly positive quantity (`sep_cost_multiple ≥ 1.0`, `est_round_trip_cost_per_share ≥ 0.001`), so it is at least one tick at every legal configuration and §3.1.2's separation term `t1_r_multiple × R + min_separation` strictly exceeds `t1_r_multiple × R`. **Not** via `min_sep_r × R > 0`, which a first draft argued in six places — §2.0 permits `min_sep_r = 0.0`, so that product is exactly zero at a legal configuration; the v1.3.1 class (a rule generalized past its justification) restated the v1.2 way (in more than one copy), inside the fix for a finding about unenforced guarantees. The `entry < T1 < T2` ordering never came from the proportional multiple. Rejected: amending four PRD sections to exclude 2.0, which would have hard-coded a bound the separation floor already makes unnecessary. The separate finding that the multiple is **inert at its 2.5 default** is unaffected and still open |
| §2 risk settings (**D27**) | §2 states three settings are user-configurable within ranges; no configuration path existed and none of the four bounds was in code | `max_risk_per_trade_pct` (0.25–2%), `daily_loss_pct` (1–5%), `max_open_positions` (1–3) and `max_consecutive_losses` (2–5) are registered parameters; `MODE_PRESETS` is an overlay bundle on top of them | §7's "non-bypassable cap" was being checked against `MODE_PRESETS`, a module constant that no supported path could change — so the guarantee was enforced against something immovable while the legal range beneath it did not exist. The check now reads the **effective** value. The §7 cap and the §2 ceiling are the same number stated twice; `test_hard_caps_match_the_registry_ceilings` holds them together and is also the alarm that fires if a registry ceiling is ever raised above a §7 cap, at which point the coupling check stops being redundant |

### Corrections to this document

| Section | Change | Why |
|---------|--------|-----|
| §3.4 sensitivity table | The `$4.05` row labelled its binding term "proportional" while showing `$0.28`, which is the *separation* term's value | At R = $0.10 the proportional term is $0.25 and does not bind. This is the same fact `test_room_gate_multiple_can_never_strictly_bind_at_defaults` pins from the other direction: at the 2.5 default the proportional term can tie the separation term but never exceed it |
| §19 status table | Three rows marked ☐ outstanding — machine-checkable example fixtures, the parameter registry check, rounding-direction assertions | All three were built and green. A status table that under-reports is not a harmless error: §19's own preamble argues that *"a self-certified checklist is not evidence"*, and a checklist that is wrong in the pessimistic direction erodes the same trust as one that is wrong in the optimistic one |
| §2.0 mode presets | Added a note that §3's worked examples are computed at the `experienced` preset | Consequence of D28. Without it the tables and `Config.default()` disagree with no explanation, which is precisely the drift this file exists to prevent |

### Thresholds the PRD states in prose but never defines

Recorded rather than fixed, because giving each a §2.0-style row is a spec edit and this round was a code review. All are now registered in `tradipy.params` with code-originated bounds, and every such bound is marked `(bounds: code)` in its `source` so a reader can tell a transcribed bound from an invented one.

| Threshold | Where the PRD states it | Registered as |
|---|---|---|
| Premarket volume floor, 100,000 shares | §2, prose only | `min_premarket_volume` |
| VWAP extension in the first 30 minutes, 5% | §2, the second branch of a two-branch rule whose first branch *was* registered | `max_vwap_extension_open_pct` |
| HOD proximity trigger, 0.5% | §2, prose only | `hod_proximity_pct` |
| Composite-score weights and normalization caps (nine values) | §20.10 code block; §20.10 calls the caps "configurable" | `score_weight_*`, `score_cap_*` |
| Catalyst midpoint, 0.5 for headline-only | §20.10 code block | `score_catalyst_headline` |
| Conviction gate, 0.7 | §14.2 | `min_conviction_score` |
| VWAP stop band, `VWAP × 0.99` | §3.4 | `vwap_stop_band_pct` (open since v0.0.1) |

Two further observations for a future spec round:

- **§2 has no Bounds column.** Roughly half of the registry's `lo`/`hi` pairs are therefore this implementation's judgement rather than specification. That is unavoidable — something has to constrain the range — but it was previously undeclared, and `params.py` claimed all bounds were transcribed from the document.
- **`score_cap_float` (§20.10) and `max_float_shares` (§2) are both 20,000,000.** §20.10 states its normalizer independently of §2's scanner ceiling, so they are two parameters rather than one restated; but they mean nearly the same thing and will drift. Pinned by `test_score_float_cap_currently_equals_the_scan_filter`.

---

## v1.3.1

Driven by the independent review in [REVIEW-v1.3.md](reviews/REVIEW-v1.3.md). One change alters trading behaviour: the spread gates now round the other way, and are clamped.

### Strategy behaviour

| Section | Was | Is | Why |
|---------|-----|-----|-----|
| §3.1.3, §20.13 | Spread gates rounded with `ceil_to_tick` | `max(tick_size, floor_to_tick(...))` on both gates | **A maximum rounded up is a maximum weakened.** §20.13's rule said gate thresholds round up "conservative in every case" — true for a floor a value must exceed, reversed for a ceiling it must stay under. §3.1.3 inherited `ceil` by analogy and admitted spreads the unrounded threshold rejected. Its own robustness tables had been computed with `floor` throughout, so the tables were right and the formula was wrong. Under `ceil` the §3.2 Bull Flag example cleared its separation floor by exactly $0.00 — a pass by coincidence; under `floor` it clears by $0.03 (D25) |
| §3.1.3 | — | One-tick clamp on both rounded maxima | `floor_to_tick(0.15 × R)` is `$0.00` for `R < $0.067`. No spread is ≤ 0, so an unclamped gate rejects every trade and reports `SPREAD_TOO_WIDE` on each — an outage indistinguishable from a working filter. Today's `min_stop_distance` keeps R above the boundary; §2.0's bounds permit values that do not (A25) |

### Rationale relocated to where it is applied

| Section | Change | Why |
|---------|--------|-----|
| §13 preamble, §3.1.2, §3.1.3, §6.5, §20.5, §20.13, §4.2 | PRD now cites the PLAN decision (D17–D22, D24) wherever it states a decided value, and carries the rejected alternative inline for every behaviour-changing one | A-ids were perfectly closed — 24 defined, 24 referenced — while 19 of 24 D-ids had no inbound reference. An implementer reading §3.1.3 saw the gates and defaults but not that lowering `sep_cost_multiple` had been considered and rejected for "preserving the ladder's appearance while still trading at negative expectancy." That is exactly the reasoning that stops a rule being tuned away by someone who meets only its inconvenient consequences |

### Corrections

| Section | Change | Why |
|---------|--------|-----|
| §9.2 | "eleven of thirteen inter-component payloads" delivered 11 types; `Alert` and `JournalEntry` added, making 13 | `NotificationSystem` and `TradeJournal` sat at the end of §9.3 arrows with untyped payloads. §21.6 already specifies `Alert` behaviour — severity routing, Sev-1 pinned until acknowledged — which is not implementable against an undefined payload |
| §21.1 | Added rounding-direction assertions and cross-parameter coupling to the registry check | `assert cap == 0.01` passes under a wrong rounding rule that happens to agree at that input. Tests must assert the derivation, not the value |
| [PLAN](PLAN.md) WS9 | "Modular architecture with interfaces and data contracts" ✓ split into contracts ✓ / interfaces ☐ | Contracts are done; no `Protocol`, ABC, or method signature exists anywhere. The tick was carried by the contracts alone |
| [PLAN](PLAN.md) WS1, sequencing table | WS1 no longer attributes 14 threshold rows to the prompt (it names 12); implementation work moved out of the workstream-numbered table | "Depends on 5" was ambiguous between Workstream 5 and Phase 5 |
| [PLAN](PLAN.md) WS11, [PROMPT-REVIEW](reviews/PROMPT-REVIEW.md) §6.2 | Fourth defect class recorded: **generalization** — a rule stated more broadly than its justification supports | Invisible to all three prior checks. The rule appeared once (registry clean), the tables applying it were arithmetically correct (fixtures clean), and the boundary case passed. Only the prose disagreed with the tables |

---

## v1.3

Driven by the independent review in [REVIEW-v1.2.md](reviews/REVIEW-v1.2.md). Two changes alter trading behaviour rather than wording: the spread gate (§3.1.3) and the correlated-exposure rule (§7.1.3).

### Strategy behaviour

| Section | Was | Is | Why |
|---------|-----|-----|-----|
| §4.2, §3.1.3 | Scanner spread filter `≤ 1% of price`; no signal-time spread test | Scan: `≤ min($0.02, 0.5% × price)`. Signal: `≤ 0.15 × R` | At 1% of price, round-trip spread cost reached 83% of R on the §3.2 example and **all three worked examples failed their own §3.1.2 separation floor** at the widest spread the filter admitted. §18.2 warns that costs above ~0.5R erase the edge; the old filter admitted trades that breached it on spread alone. The filter and the floor had never been jointly calibrated |
| §3.1.2 | Room gate and separation floor evaluated as two independent tests | Unified: `required_room = max(room_gate_multiple × R, 2R + min_separation)` | On wide-spread names the separation floor is the stricter of the two, so evaluating them separately obscured which one bound. `signals.required_room` now records the value and which term produced it |
| §7.1.3 | "Max sector exposure: > 1 position same sector" — `symbols.sector` had no provider and correlation was not modelled | `correlation_group`, assigned by shared catalyst first, sector second, ungrouped third | Sector is a weak proxy for the exposure that actually exists: co-moving low-float gappers sharing one catalyst are frequently in different sectors, and unrelated same-sector names often do not co-move. Realized correlation is deliberately *not* estimated (A24) — too little history for the estimate to mean anything |
| §6.5 | Slippage = ticks + spread | Adds a square-root impact term, `impact_coefficient × spread × sqrt(shares / bar_volume)` | The prompt's §6.8 specifies "spread **+ impact**." §18.7's viability gate is judged net of modeled slippage, so an optimistic model biases the go/no-go toward "go." Phase 4b must also report the gate at 2× calibrated slippage |
| §4.2 | Institutional Ownership `≥ 80%`, soft filter, active | Disabled by default (A22) | The premise is doubtful: ≥80% institutional ownership in a ≤20M-float, ≤$2B universe is rare, so the filter likely never fires, and where it does the causation is unclear. No source in Appendix A states the threshold. §15 separately stated it as `> 80%`; reconciled to `≥` |
| §8.2 | "Model opening auction as first regular-session bar" | Auction print excluded from the participation cap; no simulated entry inside the 09:30 bar; still counts toward VWAP and HOD (A23) | Auction volume is a cross, not participable intraday liquidity. Treating it as an ordinary bar overstates achievable fills at the open |

### Definitions that were used before being defined

| Section | Change | Why |
|---------|--------|-----|
| §20.14 | **`spread_at_signal` defined** — NBBO source, sampling at signal-bar close, validity, 2 s staleness rule, crossed-market rejection, backtest substitute | It was the binding input to the §3.1.2 separation floor (which gates every entry) and persisted in `signals`, while §20 claimed to define every term. Introduced undefined in v1.2 in the same edit that added §20.13 on the principle that terms must be defined before use |
| §20.15 | **`ATR(14)` defined** — Wilder's smoothing, true range including the gap term, daily basis for §4.2, warm-up handling | A hard-referenced scanner filter and a §14.2 alternative with no period basis or true-range convention |
| §10.1 | **`bars_5m` added** with normative aggregation semantics — session-anchored boundaries, derived from `bars_1m`, `source_bar_count`, `BAR_INCOMPLETE` below 3 | §5.1 lists 5-min bars as MVP and ORB and Five-Minute Breakout both depend on them; no table or aggregation rule existed |
| §10.1 | **`halt_events` added** | §8.4 requires "halt events per symbol per day," §4.2 has a recent-halt filter, §8.2 simulates halts — none had storage |
| §10.1 | **`news_headlines` added** with separate `published_at` and `received_at` | Catalyst is a scored filter and a §20.10 score component, but the only storage was a free-text `watchlists.catalyst`, which cannot support look-ahead control |

### Prompt requirements previously unmet

| Section | Change | Prompt |
|---------|--------|--------|
| §9.2 | Typed contracts raised from 2 to 11: `Bar`, `Quote`, `FeatureVector`, `ScanCandidate`, `TradeSignal`, `RiskDecision`, `OrderEvent`, `Fill`, `Position`, `ClosedTrade`, `BacktestResult`. §9.3 arrows annotated with the type each carries | §6.9 requires interfaces and data contracts for every component |
| §14.3 | Advantages/disadvantages per alternative and "how experienced traders read it" for all 10 discretionary elements; three elements marked as having no adequate proxy | §7.3 and §2 Core Principle |
| §13 | "Recommended Alternative" column added for all 24 assumptions | §6.13 |
| §8.2 | News look-ahead rule: backtests filter on `received_at`, never `published_at`; `news_availability_lag` default 60 s where only publication time exists | §6.8 names RVOL *and news timestamps* as the two traps; RVOL was rigorously handled and news was not |
| §5.1 | Per-feed source and latency table, including news (publisher-to-API 1–60 s, API-to-system 1–5 s) | §6.5 asks for sources **and** latency |
| §5.2 | Latency decomposed into data-to-signal, signal-to-order, **order-to-exchange**, and end-to-end | §6.2 names order-to-exchange as its own leg |
| §21.5 | Threat model, loopback-only Gateway binding, read-only client IDs, audit-trail permissions, explicit out-of-scope list | §6.2 — previously secrets handling only, labelled security |
| §11.4 | `tradipy catalyst` command added | §12.2 item 6 made catalyst confirmation the one required manual action and no command performed it, so the MVP definition was unsatisfiable |

### Corrections to self-assessment

| Section | Was | Is |
|---------|-----|-----|
| §19 | "met for the three MVP setups; deliberate deviation for the remaining ~24"; PROMPT-REVIEW cited 27 setups in three places | 3 of **14 tradeable setups**; 11 remaining. The prompt bullets **26 components**, not 27, and twelve of them are not tradeable setups — scanner filters, position management, risk rules, and operations, all fully specified elsewhere. The criterion's own "where applicable" qualifier excludes them |
| §8.3 | Trade-count sufficiency "< 100 trades in sample" | "< 100 trades for any individual setup," matching §18.7's "≥ 100 per MVP setup" — the aggregate form was a materially weaker bar |
| §8.3 | Sharpe "annualized; rf = 0" | Daily-return basis, `× sqrt(252)`, with per-trade Sharpe explicitly excluded and the reason given |
| §3.5, §15 | Five-Minute Breakout specified two incompatible ways — "same as HOD breakout, wider stops, smaller size" versus "5-min close > 20-bar high on 2× vol" | The §15 form, fully specified in §3.5 with stop and target. "Smaller size" was never a rule; §2.2 sizing already shrinks share count as R widens |
| §2, §3.4 | Max Extension from HOD delegated the consolidation test to setup-specific rules, but VWAP Reclaim had none — so the parameter resolved to nothing for that setup | §3.4 criterion 9 added; every MVP setup now has a consolidation requirement, and §2 notes that a new setup without one leaves the parameter unresolved |
| §5.3, App. C | "$14.50/month" presented as the data cost | IBKR subtotal separated from a realistic $45–$500 all-in, since §5.5 concludes an external vendor is effectively mandatory |

---

## v1.2

A cross-section consistency sweep. Every defect in this release was the same failure mode: **a threshold restated as a literal in more than one place, with only one copy updated.** The durable fix is the parameter registry (PLAN Workstream 11), not another sweep.

| Section | Was | Is |
|---------|-----|-----|
| §3.2, §3.3, §3.4 | All three setup criteria hard-coded `≥ 2 × stop_distance` | Reference `room_gate_multiple`. §2.0 and §3.1.1 had been raised to 2.5 while the criteria an engineer implements from still read 2.0, and every worked example computed at 2.5 |
| §3.1.2 | The 2.5R room gate was claimed to prevent T1 and T2 collapsing into one exit | Absolute, cost-denominated separation floor (A18). The gate did not achieve it: T1 is fixed at 2R, so 2.5R buys exactly 0.5R of separation, and R shrinks on cheap stocks where costs bite hardest. The §3.4 example passed the gate with **$0.06 of separation on a $3.83 stock** — roughly one spread plus commission — and recorded it with a ✓ |
| §21.2, §20.5, §20.12 | "Protection lives at the broker," but the T3 leg trailed a locally computed 9 EMA that cannot be a static broker order | The ratcheted level is mirrored to a resting broker-side stop, amended upward each bar close (A19). The guarantee had silently expired at `TRAILING`, while §21.6 made any unprotected position a Sev-1 |
| §2 | Max Extension from HOD required consolidation with "≥ 50% retrace" while Bull Flag criterion 3 required "≤ 50%", and specified ≥ 3 candles against the setups' ≥ 2 | Proximity trigger only; the consolidation test is owned by the setup |
| §4.3 | Carried an unnormalized composite score that summed premarket volume in shares (~10⁵) against `float_inverse` (0–1) | Points at §20.10. The duplicate is what allowed the two copies to diverge; the unnormalized version made the score effectively "premarket volume, ranked" and could not satisfy the `score ≥ 0.7` gate |
| §15 | Scaling In, Stop Loss, Position Sizing and Daily Loss Limit rows carried rules that §3, §7 and §20 had overturned | Reconciled to the current rules with section references |
| §3.4 | Invalidation "reclaim on volume < 1.5× dip average" | Removed — unreachable, since entry criterion 5 requires ≥ 2× dip average |
| §20.13 | No tick size or rounding convention, while several rules computed non-tick levels (`VWAP × 0.99`, `entry + 2R` on odd R) | $0.01 tick; stops round down, targets and gate thresholds round up. Rounding is conservative in every direction |
| §8.1, §8.2 | Three incompatible liquidity models: 1% ADV live sizing, 5% bar-volume backtest fills, and a 10% partial-fill trigger | `participation_rate` is the sole fill model; backtest sizing matches live sizing including the ADV guard |
| §21.7, §4.1 | A 200-symbol limit introduced in an ops section, contradicting §4.1's full-market scan | Two-tier topology stated explicitly: external screening tier, IBKR execution tier |
| §2.2 | "$0.005–$0.01/share round-trip" alongside a $15–30 figure for 1,500 shares that only follows from per-side costs | Per-side reading, which is correct and is the basis for `est_round_trip_cost_per_share` |
| §11.3, footer | Dashboard showed a stale account figure and Bull Flag price; footer read v1.0 | Updated to match A5 and the corrected §3.2 example |

---

## v1.1

Recomputation of every worked example, after a cold review found four arithmetic errors sitting behind a fully-ticked acceptance checklist.

| Section | Was | Is |
|---------|-----|-----|
| §3.2 example | Quoted three different entry prices — $5.20 stated, $5.21 as the trigger close, $5.12 as the actual trigger level | Single derivation from the rules; entry $5.16 |
| §3.3 example | Stop at $6.22 while the rule required the consolidation low of $6.20; T2 ($7.00) set below T1 ($7.06) | Stop $6.33 from `min(consolidation low, breakout candle low) − 1 tick`; T1 $6.78 < T2 $7.00 |
| §3.4 exits | T1 labelled HOD and T2 labelled 2R, inverting the ladder whenever HOD sat above 2R | Canonical ladder: T1 = 2R, T2 = HOD retest |
| §3.1.1 | Partial-exit schedule differed per setup — 50/25/25 in one place, 50/50 in others | One ladder governs every setup |
| §3.2 crit. 5 | Flag volume `≥ 70%` of flagpole average | `≤ 70%` — the setup's own description calls for low-volume consolidation (A13). **This is the one correction still noted inline**, because the corrected form looks like a typo |
| §3.2 crit. 6 | Trigger "above the prior red candle's high" | "Closes above the highest high of the flag" — the old wording allowed a trigger inside the flag range, colliding with the "closes back inside flag range" invalidation |
| §3.2 stop | "If VWAP is above flag low, use VWAP − 1 tick" | Removed — unreachable, since criterion 4 requires the flag low to be above VWAP |
| §3.2 false signals | Listed "volume drying up" as a false signal | Reworded to the *breakout* candle, since volume contraction within the flag is required by criterion 5 |
| §3.5 Scaling In | "Total risk ≤ 1.5× original max risk" | Total open risk from live stops ≤ the non-bypassable cap (A16). The old wording openly violated §7 |
| §6.6, §21.2 | "Cancel all open orders if reconnect not established within 10 sec" | Preserve broker-side brackets; never attempt cancels while disconnected. The old rule was both impossible (a disconnected client cannot send cancels) and unsafe |
| §6.7 | "Reject duplicate `signal_id` within 5 min," where `signal_id` was a freshly generated UUID | Deterministic `idempotency_key` from signal identity. The old check could never fire — a new UUID is unique by construction |
| §7.1 | Daily loss tested `realized + unrealized ≤ −equity × pct` with equity *including* unrealized P&L | Frozen `start_of_day_equity` denominator. The threshold previously moved as the loss accrued, so the limit could never be reached deterministically |
| §2 | Max Open Positions row said "max 3" and "max 4" in the same row | Hard ceiling 3 |
| §12.3 | "~11–12 weeks," which did not equal the sum of its own rows and omitted the §5.5 data spike | 10–15 weeks, the honest sum |
