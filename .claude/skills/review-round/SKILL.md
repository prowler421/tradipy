---
name: review-round
description: Conduct an independent review round on tradipy in house style — finding IDs and severities, the convention-8 triage call, routing spec questions instead of resolving them, and the mandatory adversarial fact-check. Use when asked to review the codebase or the PRD, to audit progress against PLAN/PRD, or to verify a previous round's fixes.
---

# Conducting a review round

Six rounds exist. Each found a defect class the check built for the previous one could not see.
The procedure below is what those rounds converged on; the parts that look like overhead are
each there because something was missed without them.

**The single most important rule: the fact-check is not optional.** Every round whose output was
checked needed correcting. The last one needed two passes, and the second pass found three errors
*created by the first*.

## 1. Establish scope and say what you could not run

State the commit. Read `docs/PLAN.md` and `docs/PRD.md` before the code — the question is
whether the code enforces what the documents claim, and you cannot answer it from the code alone.

Then run the gates: `make check`, and `uv run python -m tradipy demo`. **If you cannot run
something, say so explicitly in the appendix and list what is therefore unverified.** Coverage
percentages, case counts and mutation results that you did not reproduce are documented claims,
not findings. Reviews in this repo have been wrong by inheriting a number from the previous
round and repeating it under the word "confirmed".

## 2. Verify the previous round before adding to it

A self-reported disposition is exactly what this project does not accept. For every finding of
the last round, trace the claimed fix to a file and line and confirm it. Expect one or two to be
partly closed: F8's fix addressed one half of the finding and the whole was reported closed.

Watch the arithmetic. "All twelve closed" was wrong because one finding's disposition was
*leave it open*; the correction to "eleven" was also wrong because it left no slot for the one
that was not closed.

## 3. Number findings with a fresh prefix

Round 5 used `F1`–`F12`; round 6 used `G1`–`G10` so that citations to `F*` stay unambiguous. Use
the next letter. Severity: `HIGH` / `MEDIUM-HIGH` / `MEDIUM` / `LOW-MEDIUM` / `LOW`, plus
`(spec question)` where it applies.

Each finding needs: what is claimed, what is actually enforced, how you reproduced it, and a
proposed disposition. Reproduce by **execution or mutation** where you can — F1, F3, F5, F6 and
F9 were reproduced by running code; F2 and F4 by mutation. A finding you only read is weaker and
should say so.

## 4. Make the triage call — convention 8

**A finding fixable in one line, with no spec implication and no behaviour change, gets fixed in
the same change and one line in the review.** No `docs/CHANGELOG.md` entry, no decision, no
disposition block. A heading reading "four" above a list of six does not need six rounds of
machinery.

The convention names its own weak point: the triviality judgement. **When unsure, disposition
it.** A finding that turns out to recur, or to have a behaviour consequence, was never trivial.

## 5. Route the rest correctly

| Kind | Where it goes |
|---|---|
| Trivial | Fixed in this change; one line in the review |
| Code defect, no spec implication | Fixed; entry in the **root** `CHANGELOG.md` |
| Behaviour change | A numbered decision in `docs/PLAN.md` with its **rejected alternatives**, plus `docs/CHANGELOG.md`, plus the "changes trading behaviour" marker |
| Code diverges from PRD | **Raise, do not resolve.** `docs/CHANGELOG.md` under Unreleased, as a question with the trade-off — never settled in code |
| Documented open finding | Leave it. Some incoherent couplings are surfaced deliberately because the incoherent combination is the shipped default; `tests/README.md` lists them and each is pinned by a test |

## 6. Structure the document

`docs/reviews/REVIEW-YYYY-MM-DD.md`, following the existing two:

1. **Disposition block** at the top (add when actioned; state what was fixed vs left)
2. **Verdict** — two or three sentences that commit to a judgement, then a scorecard table
3. **Where we stand against the PLAN** — item by item, marking under- *and* over-reporting
4. **Where we stand against the PRD** — the §20 tally, §21.1 rows, registry fidelity
5. **Findings**
6. **What is genuinely good** — not padding; a review that only lists defects misrepresents
7. **The risk the findings list does not capture** — the top risk is usually not a finding
8. **Next steps**, split: now / raise as spec questions / after the spike
9. **Appendix: how this review was verified** — including what you could not run

**Cite `PLAN.md` and `docs/CHANGELOG.md` by section, never by line.** A review that edits them
invalidates its own line numbers; this happened in thirteen places in one round.

## 7. Fact-check adversarially — mandatory

Dispatch a *separate* agent to attack the draft. Ask it to verify every file:line citation, every
count, every PRD attribution, and every link, and to report only problems. Then **do it again
after correcting**, because corrections introduce errors at a rate the first pass will not catch.

Errors this step has caught: a finding overstated fourfold by reading the wrong PRD column; a
misattributed docstring; a tally applying two standards to two sections; an impossible count.

Record the error rate in the review's appendix. It is evidence about the method, and hiding it
would make the next round trust the output more than it should.

## 8. Wire it in

- `docs/README.md` review table
- `docs/PLAN.md` companion table, Workstream 11 checklist, and the sequencing row
- The five-defect-classes section **only if you found a genuinely new class** — a new population
  of an existing class is a subsection, not a row
- Root `CHANGELOG.md` for code and tooling; `docs/CHANGELOG.md` for spec matters

## 9. Two things a review here must not claim

**Do not claim a cold read.** Every round so far has been performed with the repository in
context, and each of the first four defect classes was found by a fresh reader. A verification
round inherits the previous round's idea of where to look. Say so in the appendix.

**Do not let a pleasing conclusion survive unchecked.** "Nothing in the docs over-claims a
capability" made it through a full draft and was false. The PLAN's own writeup of the fifth
defect class says it: *the claim was pleasing, which is why it survived a draft.*

## Checklist

- [ ] Commit stated; `make check` and the demo run, or their absence declared
- [ ] Every previous finding traced to file and line; partial closures called out
- [ ] Fresh finding prefix; severities assigned; each reproduced by execution or mutation
- [ ] Convention-8 triage applied, trivial items fixed in the same change
- [ ] Spec questions raised in `docs/CHANGELOG.md`, not resolved in code
- [ ] PLAN and docs/CHANGELOG cited by section, not line
- [ ] Adversarially fact-checked, then fact-checked again after correction
- [ ] Error rate recorded in the appendix
- [ ] Wired into `docs/README.md` and `docs/PLAN.md`
