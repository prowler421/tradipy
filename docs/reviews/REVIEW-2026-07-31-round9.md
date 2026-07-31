# Project Review — Round 9 (Phase 3 readiness) — 2026-07-31

> ## Disposition
>
> **J1 — trivial, fixed directly in this change; no disposition block, per convention 8.**
> `docs/PLAN.md`'s Phase 2a row said `scripts/spike2a/` "carries Q2–Q4 code," and
> `docs/PHASE-2A-REPORT.md`'s Q1 section — "Not run. IBKR alone is a **pre-determined negative**
> for the 200-symbol clause..." — never mentioned that a Q1 pipeline module exists, unlike its
> Q2–Q4 siblings' sections. Both written before `q1_vendors.py` existed and never updated after it
> landed. One word and one added sentence, respectively; no spec question, no behaviour change.
> This is the third occurrence of the shape round 8 named for I1 (a document's claim about spike
> code's state outliving the commit that changed it) and is not a new population worth its own
> callout — see §6.
>
> **J2 — fixed in this change; root `CHANGELOG.md` entry added, no `docs/CHANGELOG.md` entry (no
> spec question).** `q1_vendors.py`'s guarantee that a `SIMULATED` run cannot print a real "§7
> verdict" — the same guarantee Q2, Q3 and Q4 each have a dedicated test for — had none.
> Reproduced by mutation: removing the `prov.answers_prereg` branch left all 197 tests green.
> `tests/test_enforcement.py::test_q1_withholds_its_disposition_on_simulated_input` closes it,
> proved to fail without the guard and to pass with it restored (§8).
>
> **The Phase 3 gate verdict is unchanged: not ready.** This round could not and does not attempt
> to close it — see §3.

Scope: the whole repository at `e85a193` (`Merge pull request #17 from
prowler421/docs/pre-phase-3-synth`, the tip of `main` at the start of this round), with the fixes
above applied on top and left uncommitted for the user to review alongside this document. Read
against [PLAN.md](../PLAN.md), the relevant sections of [PRD.md](../PRD.md) (§4, §5.5, §7 via
[PHASE-2A-SPIKE.md](../PHASE-2A-SPIKE.md) — not reread end to end; see the appendix for why),
[PHASE-2A-SPIKE.md](../PHASE-2A-SPIKE.md), [PHASE-2A-REPORT.md](../PHASE-2A-REPORT.md),
[PHASE-3-READINESS.md](../PHASE-3-READINESS.md), both changelogs, and
[REVIEW-2026-07-31.md](REVIEW-2026-07-31.md) (round 8).

**This round was requested as "the Phase 3 review."** [PHASE-3-READINESS.md](../PHASE-3-READINESS.md)
is explicit that this can mean two different things, and only one is available: a review round can
audit the gate — confirm what round 8 left open is still open, and check any new spike work against
it — but it **cannot** approve Phase 3 start, because D29 binds that to Q1 answered on *measured*
data and D30 keeps the project on `SIMULATED` input. This round is the first kind. §3 states the
verdict; nothing below should be read as a step toward the second kind that this round did not
also state plainly.

**One clarification on round 8's commit lineage, not a correction to round 8 itself.** Round 8
states its commit as `b70fa7a` and says `src/tradipy/` has a zero-line diff since round 7; both are
true, and round 8's own text never mentions `PHASE-2A-REPORT.md` or `PHASE-3-READINESS.md` — a
grep of `REVIEW-2026-07-31.md` for either name returns nothing, consistent with its stated scope
(`b70fa7a`, before either existed). What is worth stating plainly: `b70fa7a` predates the H4/H6 fix
(`feeds.quote_at_or_before`) *and* those two documents; all three, plus round 8's own review file
and I1's fix, landed together in the single commit `d03b35b`. So a reader tracing round 8's
citations against `b70fa7a` alone would not find `quote_at_or_before` there — not because round 8
is wrong about anything it says, but because the commit it names and the commit that made its
conclusions visible on `main` are not the same one. H4/H6 is `scripts/spike2a/` code, not
`src/tradipy/`, so round 8's zero-diff claim about the library is untouched either way. Not a
finding: no behaviour or spec consequence, and it is history by the time this round exists.
Recorded here rather than silently worked around.

This is the ninth review in the series and the fifth to review code, and the second in a row in
which `src/tradipy/` has a zero-line diff — confirmed fresh by `git diff f3a5fe2 e85a193 --
src/tradipy` returning nothing, where `f3a5fe2` is the merge that landed round 8.

---

## 1. Verdict

**The one substantive addition since round 8 — a real-time-feasibility (Q1) pipeline exerciser —
is correct but was shipped with a test-coverage gap in exactly the property the rest of the spike's
D30 guardrail exists to guarantee, and the two documents that exist specifically to state the
Phase 3 gate had not been told the new module exists.** Neither is a behaviour defect: `q1_vendors.py`
withholds its disposition on simulated input correctly today, and `PHASE-2A-REPORT.md`'s Q1 row
was not wrong, only thin relative to its Q2–Q4 siblings. Both are now fixed in this change (§8
proves the test is not vacuous). Nothing found here changes the Phase 3 verdict, which was never
in question this round: Q1 remains unanswered on measured data, and D30 keeps the ladder at
`SIMULATED`.

**Is the project up to par?** Yes, on the two axes this round could check. `make check` is green
at 198 cases (197 before this round's fix), `basedpyright` reports zero errors, `ruff` is clean,
and all 225 relative Markdown links resolve, measured after this document and its cross-references
in `docs/README.md`, `docs/PLAN.md` and `docs/PHASE-3-READINESS.md` were all in the tree — all four
gates run fresh by this review, not cited
from round 8. `src/tradipy/` is unchanged since round 7, now confirmed across two review rounds and
three merged PRs. The new `q1_vendors.py` module is a faithful transcription of §7's Q1 thresholds
— every one of its four numeric comparisons (`≥95%` coverage, `≥200` concurrent symbols, `≤60s`
refresh, `≤$500/month`) matches [PHASE-2A-SPIKE.md](../PHASE-2A-SPIKE.md) §7's table exactly, and
its boundary comparisons (`<` and `>`, never `<=`/`>=` against the threshold in the failing
direction) correctly admit the threshold value itself as a pass, consistent with the PRD's "≥" /
"≤" wording.

| Axis | Status |
|---|---|
| `make check` | Green — ruff, format, basedpyright (0/0/0), 225 links (incl. this file and its wiring), 198 test cases (this round: +1) |
| `src/tradipy/` diff since round 7 | Zero, confirmed by `git diff f3a5fe2 e85a193 -- src/tradipy` |
| New spike code (`q1_vendors.py`) faithfulness to §7 | Correct — four thresholds transcribed exactly, boundary directions correct |
| New spike code test coverage | **Gap found and closed this round (J2)** — the module had none of the withholding test its three siblings each have |
| Phase 2a / Phase 3 documentation currency | **One trivial lag found and closed this round (J1)** |
| Phase 3 gate (D29) | **Unchanged: not ready.** Q1 unanswered on measured data; `PERMITTED_ORIGINS = {SIMULATED}` |

---

## 2. Verifying round 8

Round 8's nine confirmed-fixed findings and its one new finding (I1, fixed in the same change) are
untouched by the interval `f3a5fe2..e85a193` — that diff touches `CHANGELOG.md`,
`scripts/spike2a/README.md`, `scripts/spike2a/provenance.py`, `scripts/spike2a/q1_vendors.py` (new),
`scripts/spike2a/synthetic_data_generator.py`, and `tests/test_enforcement.py`. None of round 7's
or round 8's cited files (`docs/PLAN.md`'s risk register text, `scripts/spike2a/sample.py`,
`tests/test_spike2a_instrumentation.py`) are in that diff, so I1's fix — and the H3/H5 mutation
guards it was about — stand exactly as round 8 left them. Re-run rather than assumed: the two
mutations round 8 used to verify H3 and H5 (reintroducing the hand-derived-R defect, and removing
each of `test_spike2a_sample.py`'s three guards in turn) were not repeated this round, because
nothing in this round's diff touches the files they attack; round 8's own reproduction stands.

H4, H6, H10 and H13 remain open for the reasons round 7 and round 8 gave. H7 remains **decided**
(under `docs/CHANGELOG.md`'s "Decided" heading: a synthetic run is not a §7 data pull) and H2's
coverage-exemption question remains an **open** spec question (under the same file's "Spec
questions — open" heading) — both unchanged from round 8, and not conflated with each other here.

---

## 3. Where this leaves the Phase 3 gate

[PHASE-3-READINESS.md](../PHASE-3-READINESS.md)'s gate matrix, checked line by line against this
round's findings:

| Requirement | Status before this round | Status after |
|---|---|---|
| Invariant layer sound | Met (rounds 7–8) | **Met (rounds 7–9)** — reconfirmed, zero diff |
| Phase 2a pre-registration committed | Met | Unchanged |
| Phase 2a instrumentation | Met (six entry points) | Unchanged — six entry points, all six now individually gated *and*, as of this round, all four Q-modules withholding-tested |
| Q1 answered on measured data | Not met | **Unchanged: not met.** A pipeline now exists (`q1_vendors.py`) but produces no measured answer — same status as Q2–Q4 have had throughout |
| §4 matches reality (if Q1 negative) | N/A | Unchanged |
| Q2–Q4 measured or deferred | Partial | Unchanged |
| D30 ladder at PAPER | Not met | Unchanged — `PERMITTED_ORIGINS = {SIMULATED}` |
| Workstream 11 cold read | Not met | Unchanged — still the longest-outstanding item across nine rounds |

**Verdict: unchanged. Not ready.** The one blocking item is exactly what round 8 and
[PHASE-3-READINESS.md](../PHASE-3-READINESS.md) already stated: Q1 on measured data, which needs
D31 (the PAPER-rung decision) first. This round's findings are about the *pipeline* that will run
once D31 lands, not about D31 itself, and closing them does not and should not move the verdict.

Of [PHASE-3-READINESS.md](../PHASE-3-READINESS.md)'s review checklist, this round can honestly
check off three items and no more — reflected in that document's own checklist, updated alongside
this review:

- [x] `PHASE-2A-REPORT.md` reviewed and accepted as partial completion (with J1's fix applied)
- [x] H4/H6 schema change verified (`signal_at`, `quote_at_or_before`, tests green — confirmed by
  this round's fresh `make check` run, not re-derived by mutation since round 8 already did that)
- [x] H7 disposition accepted (synthetic ≠ data pull) — unchanged from round 8, not re-litigated
- [ ] D31 recorded before any `PAPER` data lands in `data/spike2a/` — **not this round's to do**
- [ ] Q1 measured; §4 updated if negative — **blocked on D31**
- [ ] PLAN Phase 2a row set to Done — **blocked on the above**
- [ ] Explicit "Phase 3 may start" line — **cannot be added**

---

## 4. Findings

### J1 — Two documents undercounted the spike's own code (trivial, fixed directly)

`docs/PLAN.md`'s Phase 2a row read "`scripts/spike2a/` carries Q2–Q4 code," and
`docs/PHASE-2A-REPORT.md`'s Q1 section read "**Finding:** Not run. IBKR alone is a
**pre-determined negative** for the 200-symbol clause..." with no mention that a Q1 pipeline
module exists (unlike its Q2–Q4 sibling sections, each of which names its own module) — both
accurate when written (`d03b35b`, before `q1_vendors.py` existed) and stale the moment `eff7b0c`
added it. This is the third instance of the shape round 8 named for I1:
a document describing spike code's state, outliving the commit that changed that state. No spec
implication, no behaviour change — fixed directly in `docs/PLAN.md` and
`docs/PHASE-2A-REPORT.md` in this change. Per convention 8, no `docs/CHANGELOG.md` entry and no
root `CHANGELOG.md` line for this one, because nothing about the *code's behaviour* changed — only
prose describing it.

### J2 — `q1_vendors.py`'s disposition-withholding guarantee had no test (MEDIUM-HIGH; fixed)

**Claim, stated in the module's own docstring and in `scripts/spike2a/README.md`:** "On `SIMULATED`
input the outcome is a pipeline outcome, not a §7 verdict" — the same guarantee D30 built for Q2,
Q3 and Q4, each of which has its own `test_q{2,3}_withholds_its_disposition_on_simulated_input` (Q4
has the equivalent paired test at lines 696–734 of `tests/test_enforcement.py`). `q1_vendors.py`
has the same `if prov.answers_prereg` branch in `report()`, but no test exercised it directly — the
only test that touched the module at all was the generic six-entry-point gate test
(`test_every_spike_entry_point_gates_its_input`), which asserts `main()` returns `3`/`0` for
undeclared/declared input and says nothing about what the report's *text* claims once it runs.

**Reproduced by mutation, per the guarantee-test skill's step 2.** The `if prov.answers_prereg`
branch in `q1_vendors.report()`'s headline was removed, collapsing it to always print a real "§7
verdict" regardless of provenance. `uv run pytest tests/ -q` still reported all 197 cases passing —
zero test failures for a change that makes a `SIMULATED` run print exactly the sentence D30 exists
to prevent it from printing. The mutation was reverted immediately after confirming this.

**Why this matters more than a typical missing test.** Q1 is not one of four equally-weighted
questions — per [PHASE-3-READINESS.md](../PHASE-3-READINESS.md)'s own gate matrix, it is the
*single blocking item* for D29. A future refactor of `q1_vendors.py` that regressed this branch
would have shipped silently, and its failure mode is specifically "prints a §7 verdict over
fabricated data" — the exact defect D30 was built in response to (the sixth defect class, a
provenance-marked synthetic run printing a real verdict). Rated MEDIUM-HIGH rather than HIGH
because nothing is currently broken and the gap closes in this same change, and not LOW because of
what a silent regression here would license.

**Fix.** `tests/test_enforcement.py::test_q1_withholds_its_disposition_on_simulated_input`, placed
beside its Q2 sibling, asserting both the withheld case (`SIMULATED`, a `VendorTrial` that clears
every §7 threshold, and the withheld text is present while `"§7 verdict:"` is absent) and the
contrast case (`PAPER` provenance, the same trial, and the real verdict text is now present) — the
same non-vacuous pairing Q2's test uses, so the assertion is not merely "a string is absent," which
would pass just as well against a module with the string deleted entirely. Proved to fail against
the mutation above and to pass with the mutation reverted (§8).

---

## 5. What is genuinely good

**The new Q1 pipeline is a careful, faithful piece of work.** Its four thresholds
(`Q1_MIN_SAMPLE_COVERAGE_PCT`, `Q1_MIN_CONCURRENT_SYMBOLS`, `Q1_MAX_REFRESH_SECONDS`,
`Q1_MAX_MONTHLY_USD`) were checked against [PHASE-2A-SPIKE.md](../PHASE-2A-SPIKE.md) §7's table by
this review and match exactly — 95, 200, 60, 500 — with no drift and no unit confusion. The
synthetic vendor matrix `generate_vendor_trials()` produces one deliberate pass and two deliberate
failures, each annotated with *why* it fails ("pre-determined negative: concurrent cap ~100",
"refresh too slow; filters not expressible") rather than fabricated to agree with a foregone
conclusion — the same discipline PHASE-2A-SPIKE.md §1 and `scripts/spike2a/README.md` state in
prose about IBKR's concurrent-symbol cap being a *pre-determined* negative worth running anyway.

**The withholding guarantee itself is correctly built, just untested until this round.** This is
worth separating from J2's severity: the *code* was right on arrival. The gap J2 closes is a gap in
what would catch a *future* regression, not a defect in the delivered behaviour — the same
distinction round 8 drew about I1 being "wrong in the safe direction."

**`scripts/spike2a/prereg.py`'s own numeric-coincidence disclosure continues to hold up.** This
round independently recomputed the four coincidence claims in its docstring (30↔`rvol_lookback_days`,
5↔`min_rvol`, 2↔`t1_r_multiple`/`quote_stale_seconds`, and Q1's 500 colliding with nothing
registered) against the current values in `params.py` and found all four accurate — a small thing,
but the kind of self-checking claim that round 7 found *wrong* in this exact module (a collision on
20 that did not exist, two on 5 that were omitted), so its continued accuracy is not nothing.

---

## 6. The risk the findings list does not capture

**Round 8 already named the shape of J1** — "a document overstating how *un*guarded something is"
generalizing in both directions, and specifically warned that the opposite failure (a document
overstating how *guarded* the spike now is) "could happen next." J1 is not that: it is neither
direction of that warning, just a third instance of the older, narrower pattern (a document's
description of what code exists, stale after a commit). The interesting risk is adjacent to
round 8's, not identical to it: **the spike now has four Q-modules that look structurally
uniform** — each gated, each with a `report()` that takes a `Provenance` and branches on
`answers_prereg` — and that uniformity is exactly what made J2 easy to miss. A reviewer (or a future
contributor) skimming the four modules and seeing the same `if prov.answers_prereg` shape in all
four could reasonably assume the same *test* shape exists for all four, because the code shape is
identical. It was not, for the one module (Q1) most recently added and most consequential to the
gate. The fix does not eliminate this risk going forward — a fifth Q-module, if one is ever added,
inherits the same assumption-of-uniformity risk unless whoever adds it checks for the sibling test
explicitly rather than trusting that four consistent-looking modules imply four consistently-tested
ones.

---

## 7. Next steps

**Now:**
- None required beyond this change's fixes to J1 and J2.

**Raise as spec questions (unchanged from round 8 — not reopened, not resolved here):**
- H2's coverage-exemption question — should PHASE-2A-SPIKE §8 be narrowed. Still open, unchanged.
- H4, H6 — schema decisions, already implemented per round 8; no new question raised by this round.
  (H7 is decided, not open — see §2 — and is not listed here.)

**After the spike reports (or when D31 lands):**
- D31 itself — the PAPER-rung decision — is the actual next blocking step, not a review-round
  deliverable. This round deliberately does not draft it: `PHASE-3-READINESS.md` §1 is explicit that
  a review round can review a D31 draft, not author the policy decision it records.
- Execute the Q1 vendor trial once D31 lands; update `PHASE-2A-REPORT.md`'s Q1 row from "Not run" to
  a measured answer.
- Workstream 11's still-outstanding cold read — now the longest-outstanding item across nine
  rounds, unchanged by this one.
- H13 — mutation-testing tool run, still unavailable to this review for the same reason round 7 and
  8 left it that way.

---

## 8. Appendix: how this review was verified

**Gates run, not cited:** `make check` at `e85a193` plus this round's uncommitted fixes —
`ruff check` (clean), `ruff format --check` (38 files, no reformatting needed), `basedpyright`
(0 errors, 0 warnings, 0 notes), `scripts/check_links.py` (225 relative links resolve — measured
last, after this document and its wiring into `docs/README.md`, `docs/PLAN.md` and
`docs/PHASE-3-READINESS.md` were all in place, since each of those adds its own links), `pytest`
(198 passed, 0 failed, 0 skipped — 197 before this round's one added test).

**Executed, not read:**
- `git log --oneline b70fa7a..HEAD` and `git diff f3a5fe2 e85a193 --stat` — established the exact
  commit lineage (`b70fa7a` → `d03b35b`/`f3a5fe2` → `eff7b0c`/`e85a193`) and which files changed in
  each interval, rather than inferring it from either review's prose.
- `git show b70fa7a:scripts/spike2a/feeds.py | grep quote_at_or_before` — confirmed the function is
  absent at `b70fa7a`, establishing that H4/H6 landed in `d03b35b`, not before round 8's stated
  commit (§0's clarification).
- `git diff f3a5fe2 e85a193 -- src/tradipy` — empty, confirming the invariant layer is unchanged
  since round 8's merge.
- `scripts.spike2a.q1_vendors`'s four thresholds, hand-compared against
  [PHASE-2A-SPIKE.md](../PHASE-2A-SPIKE.md) §7's table (line 242) — exact match, no drift.
- `grep -rn "q1_vendors" tests/` before this round's fix — one match
  (`test_every_spike_entry_point_gates_its_input`'s parametrize table), confirming the absence of
  any dedicated Q1 report-content test prior to this round's addition.

**Reproduced by mutation:** `q1_vendors.py`'s `report()` headline branch on `prov.answers_prereg`
was deleted (collapsing to an unconditional `"§7 verdict: ..."`), and `uv run pytest tests/ -q` was
run against the full suite — 197 passed, 0 failed, confirming the guarantee was unenforced. The new
test `test_q1_withholds_its_disposition_on_simulated_input` was then written, confirmed to pass
against the intact code, confirmed to **fail** against the same mutation
(`AssertionError: assert 'pipeline outcome (NOT a §7 verdict)' in '...'`), and the mutation was
reverted and `make check` re-run green (198 passed) before this document was finalized.

**Not run:** a mutation-testing tool (`mutmut` or equivalent) — H13 remains unanswerable for the
same reason rounds 7 and 8 left it that way. A full re-read of `docs/PRD.md` end to end — `src/tradipy/`
is unchanged for the second round running, and this round's diff touches no PRD-governed code, so
the same budget argument round 8 made applies again and compounds: a partial reread would spend
budget a genuine cold read needs without changing this round's findings. A cold read with no prior
context was not attempted; this is the fifth round performed with the repository in context.

**This round found two findings (J1, J2), both fixed in the same change, none newly open.** The
low count reflects a narrow diff (six files, one of them new) rather than a clean bill for the
whole repository — this round did not re-examine `src/tradipy/`, the PRD, or any of round 7/8's
still-open items (H4, H6, H10, H13, H2, H7) beyond confirming their status is unchanged.

**Adversarial fact-check:** a separate subagent, given only this document and the repository (not
this review's drafting process), was asked to verify every commit hash, quote, count, and
disposition claim independently and report only problems. It found **four errors in the first
draft**, all now corrected above:

1. The link count was cited as a final, current-state number while this document was still being
   drafted and before its own wiring into `docs/README.md`, `docs/PLAN.md` and
   `docs/PHASE-3-READINESS.md` existed — each addition to the tree changes the total. All three
   citations now state 225, measured last, after every file this round touches was in place.
2. §0's clarification paragraph claimed round 8's own text "discusses [`PHASE-2A-REPORT.md`,
   `PHASE-3-READINESS.md`] as already existing." A grep of `REVIEW-2026-07-31.md` for either name
   returns nothing — round 8 never mentions them, consistent with its stated `b70fa7a` scope. The
   paragraph is rewritten to state only what is true: the two documents and round 8's own review
   file landed in the same commit (`d03b35b`), not that round 8's text refers to them.
3. §2 stated "H7 and H2's coverage-exemption question remain open spec questions," but H7 sits
   under `docs/CHANGELOG.md`'s "Decided" heading (a synthetic run is not a §7 data pull), not its
   "open" one — only H2 is open. §2 and §7 now state this correctly and separately for each.
4. The disposition block and J1 both quoted `PHASE-2A-REPORT.md`'s pre-fix Q1 section as having
   "said only 'Not run,'" when the actual text was a full sentence longer (the IBKR
   pre-determined-negative analysis). Both citations now quote the fuller text and state the
   actual gap accurately: no mention of the pipeline module, not no content at all.

The fact-check also independently reproduced the `make check` gate results, the four §7 threshold
values in `q1_vendors.py`, the `git diff f3a5fe2 e85a193 -- src/tradipy` zero-diff claim, and the
absence of any pre-existing Q1 report-content test, and found no problems with any of them. **Error
rate: 4 issues found across roughly 20 independently-checkable factual claims in the first draft —**
consistent with the skill's warning that this step routinely finds what a first pass misses. A
second fact-check pass, specifically over the four corrections above, found **one further error**:
correction 4 had been applied to the disposition block but not to §4's own J1 write-up, which still
quoted `PHASE-2A-REPORT.md`'s pre-fix text as if `"**Finding:** Not run"` were the complete
sentence. Corrected. A third, targeted re-check of that one spot plus a full re-run of `make check`
found no further errors.
