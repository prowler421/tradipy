# Phase 3 Readiness Review — round 10

> ## Disposition
>
> **Seven findings, `K1`–`K7`. Three fixed in this change, four raised and deliberately not
> resolved.**
>
> Fixed here, each with a finding rather than convention 8's silent path because the shape has now
> recurred four rounds running: **K1** (`docs/PHASE-2A-REPORT.md` reports the previous commit's
> pipeline numbers under a claim of regeneration), **K5** (`docs/PHASE-3-READINESS.md` doubles Phase
> 3's filter scope and attributes the number to a PRD section that states none), and **K6** (three
> documents undercount what the same interval built). Each is a factual correction to a document,
> changes no code, and gets no `docs/CHANGELOG.md` entry.
>
> Raised, not resolved: **K2** (`feeds.quote_at_or_before` overrides a supplied `age_seconds`
> unconditionally while its docstring says it derives one only when absent — a behaviour question
> about which age governs §20.14 on measured data), **K3** (`q1_vendors.report` turns an empty or
> wholly-unparsable vendor matrix into a §7 Q1 *negative* and a PRD §4 rewrite; the fix is a
> behaviour change plus a new guarantee test, which is more than convention 8 authorises), **K4**
> (a fabricated vendor figure restated in prose as a finding about the world — a candidate
> **seventh defect class**, and whether it is one is not the reviewer's call), and **K7** (H7 was
> decided by the party §7's amendment clause constrains, and this round is asked to ratify it after
> four documents already rely on it).
>
> **Prefix and numbering.** Round 5 used `F*`, 6 `G*`, 7 `H*`, 8 `I*`. A concurrent round —
> `REVIEW-2026-07-31-round9.md` — claims round 9 and `J*`. This is
> therefore **round 10 with `K*`**, so that citations stay unambiguous whichever of the two lands
> first. The two rounds were conducted independently and their findings are complementary; see
> "Relationship to the concurrent round 9" below.
>
> **Round 8's single finding, I1, is closed.** Traced to both claimed sites and confirmed:
> `scripts/spike2a/README.md:178-180` now states that `test_spike2a_instrumentation.py` catches the
> hand-derived R by AST and by runtime, and PLAN's risk register (§ Risks & Dependencies, "The
> instrument is outside every check") now reads *"would now be caught"* and separates instance from
> class. Of round 7's H-findings, **H4 and H6 are closed and H7 is decided** in this interval, all
> three recorded in `docs/CHANGELOG.md`; **H10, H13 and H2's coverage-exemption half remain open**
> exactly as round 7 left them — H2's is easy to lose, because round 8 counts H2 in both its fixed
> list and its open-questions list, and a first draft of this round closed it by arithmetic.
> Nothing regressed.
>
> **Verdict on the gate itself: Phase 3 may not start, and `docs/PHASE-3-READINESS.md` is right
> about why.** Q1 is unanswered on measured data, D29 gates Phase 3 on that answer, and D30 makes it
> unobtainable until a recorded decision advances the ladder. This review does not tick that box and
> could not honestly have ticked it. What it does find is that the two documents written to report
> that state — the ones a reader consults *instead of* running anything — are the least accurate
> artefacts in the repository, and that the module built in this interval to answer Q1 will assert
> the spike's strongest verdict from an empty file.

Scope: the whole repository at **committed** `e85a193` (`Merge pull request #17 from
prowler421/docs/pre-phase-3-synth`, the tip of `main`), read against [PLAN.md](../PLAN.md),
[PRD.md](../PRD.md) (§4.2, §12.1 and §20.14 re-read directly; not reread end to end — `src/tradipy/`
has a zero-line diff over the interval, confirmed by `git diff b70fa7a HEAD -- src/`),
[PHASE-2A-SPIKE.md](../PHASE-2A-SPIKE.md), [PHASE-2A-REPORT.md](../PHASE-2A-REPORT.md),
[PHASE-3-READINESS.md](../PHASE-3-READINESS.md), both changelogs and
[REVIEW-2026-07-31.md](REVIEW-2026-07-31.md). The interval under review is `b70fa7a..e85a193` —
five commits — `d03b35b` ("review current stage"), `eff7b0c` ("synth data") and the merges `834937c`, `f3a5fe2`, `e85a193` — touching documentation,
`scripts/spike2a/` and `tests/` only.

**Committed HEAD, not the working tree.** The working tree carried uncommitted work by a concurrent
round while this review was in progress. Every count and citation below was re-derived from a
pristine `git archive e85a193` checkout after that was discovered; the appendix records the error and
how it was caught, because it invalidated a first draft of this document.

**Citations to `PLAN.md` and both changelogs are by section, never by line** — this round edits
`PLAN.md`. Line numbers into `docs/PHASE-2A-REPORT.md`, `docs/PHASE-3-READINESS.md`,
`docs/README.md` and `scripts/spike2a/*.py` are as of `e85a193`, before this round's own edits.

This is the tenth review in the series and the sixth to review code. It is the third consecutive
round in which no code in `src/tradipy/` changed at all, and the first whose subject is a **gate
decision** rather than a diff: `docs/PHASE-3-READINESS.md` §"What 'Phase 3 review' can mean today"
pre-states what a round conducted now can and cannot approve, and this round takes that framing.
That the reviewed artefact specifies its own review's terms of reference is itself worth naming; see
§6.

### Relationship to the concurrent round 9

`REVIEW-2026-07-31-round9.md` was written independently over the same
interval and, at the time this round was completed, was uncommitted. Its findings and this round's
overlap in one place and nowhere else, which is itself evidence about how much of this repository a
single round sees:

- **Its J2 and this round's K3 are adjacent but not the same.** It found that
  `q1_vendors.report()`'s `answers_prereg` branch had no test — Q2, Q3 and Q4 each have one — and it
  added `test_q1_withholds_its_disposition_on_simulated_input`, reproduced by mutation. **K3 is a
  different hole in the same function:** the *empty-sample* path, which that test does not reach and
  which the new test's own measured-origin assertion runs straight past. Both are real; neither
  subsumes the other.
- **One row of K6 was independently fixed by it** — PLAN's Phase 2a row now reads "carries Q1–Q4
  code" rather than "Q2–Q4". That row is dropped from K6's table below and credited there.
- **Its edit to `docs/PHASE-2A-REPORT.md` rewrote the exact paragraph K4 is about and preserved the
  unsourced IBKR claim**, which is not a criticism of that round — it was fixing something else —
  but it does mean the paragraph was under a reviewer's eye in this window and the claim survived.
- **Nothing else overlaps.** K1, K2, K4, K5, K7 and the remaining three rows of K6 are untouched by
  it.

---

## 1. Verdict

**The gate assessment is correct and the reporting around it is not.** `PHASE-3-READINESS.md`
reaches the right conclusion — not ready, one blocking item, Q1 on measured data — and by the right
route, refusing to convert instrumentation completeness into a Phase 3 go-ahead. The D30 machinery
holds: seven spike entry points gate on a declared origin, the twenty-root import denylist is
enforced across `src/`, `scripts/` and `tests/`, and every measurement module refuses to print a §7
verdict over simulated input. All of that was verified here by execution, not read.

**What this round found is that the interval's two new documents are wrong about the interval's own
work — eight statements between them, enumerated below.** `docs/PHASE-2A-REPORT.md:42` reports 147 signal bars
and a 1.36% aggregate Q4 rejection rate as *"Regenerated … at commit after H4/H6"*. Those are round
8's figures, verified correct at `b70fa7a`. The commit that added the report, `d03b35b`, also rewrote
the generator: at `d03b35b` and at `e85a193` alike the seeded generator produces **157** signal bars,
**3,566** NBBO samples and a **0.64%** aggregate rate with a 6.67% worst decile. The numbers were
stale in the commit that wrote them. This is the failure mode the `review-round` skill names in its
own §1 — *"wrong by inheriting a number from the previous round and repeating it under the word
'confirmed'"* — occurring for the first time in a project document rather than in a review, under the
word "Regenerated".

The one over-claim runs the other way and is the more consequential: `q1_vendors.py`, new in this
interval, is the only one of the four measurement modules with no empty-sample guard. Q2 prints
`UNANSWERED — needs two independent providers, have 0`; Q3 prints `no measurements — unanswered, not
passed`; Q4 returns CALIBRATED with the reason `no gated bars — nothing measured, so nothing is
claimed`. Q1, on measured input, prints **`§7 verdict: no provider passes Q1`** followed by
**`Implication per §6: PRD §4 is rewritten before Phase 3 (scanner) starts`** — from zero trials.
That is the largest consequence the spike can produce, reachable from an empty file.

**Is the project up to par?** On the invariant layer, yes, and this round could check it: 197
collected cases pass, 207 relative links resolve, `python -m tradipy demo` exits 0 and reproduces the
§3 worked examples. On the spike instrumentation, yes with the two exceptions above. On the
documentation *about* the spike, no — and that matters more than usual, because D30 has removed every
measurement from the repository's reach, so for the duration of the suspension the documents *are*
the deliverable, and two of the three rows in the report's own pipeline table are wrong.

**The eight, so the number is checkable rather than rhetorical.** In `docs/PHASE-2A-REPORT.md`:
(1) `:47` 147 signal bars; (2) `:48` NBBO samples "varies by run"; (3) `:20` and (4) `:91` the 1.36%
aggregate, twice; (5) `:35` "all six spike entry points"; (6) `:96` the heading "Open spec questions
(unchanged disposition)" above a row reading "Decided". In `docs/PHASE-3-READINESS.md`: (7) `:18`
"Six entry points"; (8) `:83`, under the "From PRD §12.1:" heading at `:81`, "14 filters" for a
7-filter hard set attributed to a section that states no count.

**Two things deliberately excluded from that eight**, because a count that absorbs everything stops
being evidence. The IBKR line-cap figure (`:62-64`) is **unsourced, not shown to be false** — K4 is a
provenance finding, not a factual correction. And items (5) and (7) are *stale* rather than wrong at
birth: both were accurate at `d03b35b`, the commit that added both documents, and were falsified by
`eff7b0c` two commits later. Four of the eight — (1) through (4) — were wrong the moment they were
written.

### Scorecard

| Dimension | Assessment |
|---|---|
| Specification quality | Unchanged. §4.2, §12.1 and §20.14 re-read directly for K2 and K5; no PRD defect found this round |
| Invariant-layer correctness | Unchanged from rounds 7–8 — `src/tradipy/` has a zero-line diff since `b70fa7a`, confirmed by `git diff`, not assumed |
| Spike-instrumentation correctness | **Mixed.** H4/H6's quote selection is a real improvement, built and tested; `q1_vendors.py` ships the spike's only unguarded empty-sample path (K3) and `quote_at_or_before` silently discards a documented input column (K2) |
| Gate status | **Partially verified — see the appendix.** 197 cases pass and 207 links resolve, both executed. `ruff`, `ruff format --check` and `basedpyright` **could not be run**; `make check` is therefore *unverified as a whole* this round, and any claim that it is green is inherited, not reproduced |
| Documentation accuracy | **Worst of any round.** Three findings (K1, K5, K6) spanning three documents; eight wrong statements in the two written this interval, enumerated in §1 |
| Test rigour | 156 test functions / 197 collected cases across ten files, up from round 8's 154/194 across nine. The two added are the right two (`quote_at_or_before`'s selection and its age derivation) — and one of them is why K2 is a finding rather than a clean closure: it tests the branch beside the hole |
| Phase 3 gate | **Not passed, correctly.** One blocking item (Q1 on measured data), correctly identified, correctly attributed to D29 + D30, and not softened anywhere |

---

## 2. Where we stand against the PLAN

Cited by section, not line.

- **§ Sequencing & Dependencies, the Phase 2a row** — **under-reported** `scripts/spike2a/` as
  carrying "Q2–Q4 code" one commit after `q1_vendors.py` landed. **Independently fixed by the
  concurrent round 9**; noted here because it is the *same PLAN row* round 8's I1 corrected,
  understating the repository again one interval later, which is the argument for treating this class
  as recurring rather than trivial.
- **§ Sequencing & Dependencies, the §21.1 fixture-suite row** — says "**154 test functions** across
  nine files". At `e85a193` it is **156 across ten**. The same sentence then explains that "153
  cases" was dropped from the row *because nothing in the repository can reproduce it* — so the row
  states the principle and violates it two clauses earlier. Fixed in this change (K6).
- **§ Risks & Dependencies, "The instrument is outside every check"** — now accurate, and it is the
  I1 fix. It draws the instance/class distinction correctly: the specific hand-derived R is caught,
  the class is not. This round adds two data points in favour of that caution — K1 and K4 are both
  cases where the sixth class's *mitigation* held on the machine path and leaked on the prose path.
- **§ Workstream 11 checklist** — accurately records rounds 1–8. The cold read remains outstanding
  and remains the most valuable open item; this round is the sixth performed with the repository in
  context and inherits round 8's idea of where to look, which is why its findings cluster in the two
  files round 8 never saw.
- **Decision log** — D29 and D30 are cited correctly by every document that relies on them, checked
  one by one. **D31 does not exist yet** and four documents refer to it by number
  (`PHASE-2A-REPORT.md`, `PHASE-3-READINESS.md`, `docs/CHANGELOG.md`, and PLAN's own Phase 2a row). Forward-reference by design rather than a defect — D31's content is described
  consistently in all four — but the number is spent, and a different decision taken first would have
  to skip it.
- **Nothing in the PLAN over-claims a capability that this round could find.** Stated plainly
  because PLAN's own writeup of the fifth defect class warns this is the sentence that survives a
  draft unchecked; the adversarial fact-check was pointed at it specifically. What this round found
  instead is documents *under*-claiming (K6) and one over-claiming a measurement it did not make
  (K1) — and PLAN is on the under-claiming side both times.

## 3. Where we stand against the PRD

No PRD-governed code changed in this interval, so the §20 tally, the §21.1 fixture rows and the
registry's fidelity to the PRD's Bounds columns stand on round 7's read and are not re-derived.
Three sections were read directly, because a finding turned on each:

- **§4.2 Filter Definitions** — **14 rows, of which 7 are Hard and 7 are Soft**, counted by parsing
  the table's Hard/Soft column rather than by eye. This is K5: `PHASE-3-READINESS.md:83` states Phase
  3's scope as "§4.2 **hard filters** (14 filters…)", the whole table's row count standing in for the
  hard subset.
- **§12.1 Phase Map** — the Phase 3 row reads "Scanner (hard filters)" and states **no count at
  all**, so the "(14 filters)" attributed to it under `PHASE-3-READINESS.md`'s "From PRD §12.1:"
  heading is not from §12.1. The 14 traces to PLAN's Workstream 4 checklist item "Define 14 filters
  with default thresholds", where it correctly means all of them.
- **§20.14 / `quote_stale_seconds`** — registered at `2` seconds with `Polarity.MAXIMUM`, and
  `src/tradipy/quotes.py:33` documents `age_seconds` as "the quote's age **at bar close**, not at the
  time of evaluation". `quote_at_or_before`'s derived age matches that reading; what does not match
  is its docstring's claim to derive only when the CSV omits the column (K2).

Reconfirmed by execution rather than by citation: 47 registered parameters, the 68-entry frozen
baseline in `tests/registry_baseline.json`, and `python -m tradipy demo` exiting 0 with all three §3
worked examples reproducing their documented values. Re-run despite the empty `src/` diff, on the
skill's own principle that an unreproduced pass is a documented claim.

## 4. Findings

### K1 — MEDIUM-HIGH — the completion report's pipeline numbers are the previous commit's, under a claim of regeneration

**What is claimed.** `docs/PHASE-2A-REPORT.md:42` — *"Regenerated with `uv run python -m
scripts.spike2a.synthetic_data_generator` at commit after H4/H6"* — above a table (`:44-48`) giving
156 symbol-sessions, **147** signal bars and, for NBBO samples, **"varies by run (deduped per
symbol/instant)"**. Lines `:20` and `:91` report the Q4 aggregate rejection rate as **1.36%**.

**What is actually produced.** The generator is seeded (`SEED = 42`, seeded inside `main()` rather
than under `__main__` so that a *programmatic* call is reproducible too — under `__main__` the
marker's claim was true from the command line and false for any other caller), so none of this varies:

| Figure | Report says | Seeded generator produces | Verified at |
|---|---|---|---|
| Symbol-sessions | 156 | 156 | ✓ correct |
| Signal bars | 147 | **157** | `d03b35b`, `e85a193` |
| NBBO samples | "varies by run" | **3,566**, deterministic, and printed into the generator's own `PROVENANCE.txt` | `d03b35b`, `e85a193` |
| Q4 aggregate | 1.36% (2/147) | **0.64% (1/157)** | `d03b35b`, `e85a193` |
| Q4 worst decile | not stated (the report says only "elevated cheap-decile rate") | d1 **6.67%**, down from 14.29% at `b70fa7a` | `d03b35b`, `e85a193` |

**How this was reproduced.** By execution at three commits on one interpreter, which is what rules
out the reviewer's own toolchain as the explanation. At `b70fa7a` — round 8's commit — the generator
produces exactly the documented 156 / 147 / 8,820 and `q4_spreads` prints exactly 1.36% (2/147) with
d1 at 14.29%. At `d03b35b`, the commit that *added this report*, it already produces 156 / 157 /
3,566 and 0.64% (1/157) with d1 at 6.67%. At `e85a193`, identical to `d03b35b`. So the figures were
correct as of round 8, the same commit that introduced the report rewrote the generator, and the
report carried round 8's verified numbers across that rewrite under the word "Regenerated".

**Why the "varies by run" row is the tell.** Of the three data rows, the one that changed most —
8,820 → 3,566, a 60% drop — is the one replaced with a prose hedge instead of a number, for a
generator whose seed is fixed, whose docstring says the seed exists "so a regeneration is
reproducible", and whose marker file prints the exact count. A row that resists re-measurement being
converted to "varies" rather than re-measured is the same instinct that left the other two alone.

**What survives.** The *qualitative* conclusion is unaffected and this finding does not overturn it:
at `e85a193` the outcome is still CALIBRATED by elimination, the cheapest decile is still the only
hot one, and it is still a pipeline outcome rather than a §7 verdict. Only the figures are wrong.

**Disposition — fixed in this change**, and deliberately fixed *without* substituting this
reviewer's numbers as authoritative: the report now gives both columns, attributes the 147/1.36%
figures to `b70fa7a` where they are independently verified, carries the interpreter caveat from the
appendix, and says they must be regenerated on the project's own Python 3.13 before being quoted
elsewhere.

**A third document carries the same figures, and it is the root `CHANGELOG.md`.** Its Unreleased
"Fixed" entry for the seed move states *"Output is unchanged: 156 symbol-sessions, 147 signal bars,
8,820 NBBO samples, and Q4 still reports 1.36% aggregate with 14.29% in the cheapest decile"* — five
figures, of which four are superseded by `d03b35b` and only the 156 survives. **The sentence was true
of the change it describes**, which is why it is not counted among the eight above: the seed move
genuinely did not alter the output. What went stale is its present tense. The fix applied here keeps
the claim and pins its scope — "output was unchanged **by this fix**", measured at `b70fa7a` — rather
than restating figures the entry was never about.

The same file quotes `2/147` and `14.29%` again further down, and `14.29%` and `1.36%` separately in
two more places, all inside `## [Unreleased]` rather than a dated release. Those are left alone
deliberately, but not on the grounds a first draft of this paragraph gave — it called them a dated
historical entry, which they are not. The actual grounds: each sits inside a narrative describing a
defect and the state it was found in, where the figure is part of the story rather than a claim about
the present. That is a judgement, and a reader who disagrees should change them. No
`docs/CHANGELOG.md` entry for K1 (no spec question); the root `CHANGELOG.md` edit is a correction to
an existing entry rather than a new one.

### K2 — MEDIUM — `quote_at_or_before` overrides a supplied `age_seconds`; its docstring says it derives one only when absent

**What is claimed.** `scripts/spike2a/feeds.py:54-56`: *"When `age_seconds` is not supplied in the
CSV, it is derived from `instant - captured_at` so the validity half of Q4 can fire on measured input
(H6)."* `CsvQuoteFeed`'s docstring (`:131`) advertises the schema
`symbol,captured_at,bid,ask,bid_size,ask_size[,age_seconds]`, and `_parse` (`:169`) reads that column
into the sample.

**What is enforced.** `quote_at_or_before` (`:49-73`) computes `age` unconditionally at `:64` and
passes it to the returned `QuoteSample` at `:72`. `chosen.age_seconds` is never read. There is no
"when not supplied" branch. Since `load_signal_bars` routes every Q4 row through this function
(`q4_spreads.py:283`), the documented `age_seconds` column has **no effect on the only path that
consumes it**.

**How this was reproduced — execution.** A one-row quote CSV with `age_seconds=999` and
`captured_at` equal to the signal instant:

```
age as parsed from CSV        : 999
age after quote_at_or_before  : 0.0
gate on CSV-supplied age      : (None, Reject.QUOTE_STALE)
gate on derived age           : (Decimal('0.02'), None)
```

A quote the CSV declares 999 seconds stale is gated as valid, with a spread of 0.02 folded into the
rejection-rate denominator. `quote_stale_seconds` is 2.

**Why the tests do not catch it.** Both tests in `tests/test_spike2a_q4_quote_selection.py` build
samples through a `_sample` helper (`:17-25`) that omits `age_seconds`, so the field is always at its
`Decimal(0)` default. `test_quote_at_or_before_derives_age_seconds_from_signal_instant` asserts the
derivation happens when the column is absent — which is what its own docstring says it is for,
*"§20.14 staleness must be computable **without** a CSV `age_seconds` column (H6)"*. The case the
code actually differs on is untested in both directions.

**Which way is right is not obvious, which is why this is raised rather than fixed.** For a
historical replay the derived age is arguably correct and the column vestigial. For a measured feed
reporting its own NBBO age — exchange timestamp versus receipt — the supplied value is the physically
meaningful one, and discarding it weakens §20.14's staleness test in the only direction that matters,
exactly as `rounding.py`'s governing principle forbids for thresholds.

**Proposed disposition.** Either (a) honour a supplied non-zero age and derive only when absent,
matching the docstring, or (b) remove `age_seconds` from `CsvQuoteFeed`'s documented schema and from
`_parse`, and rewrite the docstring to say the age is always derived and why. Both need the test
convention 6 demands: a sample carrying a stale supplied age, asserting which one governs. Raised in
`docs/CHANGELOG.md` under Unreleased as a question, not settled here.

### K3 — MEDIUM-HIGH — `q1_vendors` asserts a §7 Q1 negative, and a PRD §4 rewrite, from an empty sample

**What is claimed.** `q1_vendors.py`'s module docstring: *"On `SIMULATED` input the outcome is a
**pipeline outcome, not a §7 verdict**, for the same reason as Q2–Q4."* More broadly, D30's stated
posture is that a fabricated or absent input cannot license a disposition.

**What is enforced.** The simulated/measured split is enforced. The **empty-sample** case is not.
`report()` initialises `any_pass = False` (`:96`) and, on measured input with zero trials, falls
straight through to the negative branch (`:108-119`, `:129-133`).

**How this was reproduced — execution.** Constructing a `Provenance` with `origin=DataOrigin.PAPER`
and calling `report([], measured)`:

```
providers evaluated   0
§7 verdict: no provider passes Q1
Implication per §6: PRD §4 is rewritten before Phase 3 (scanner) starts.
```

This is the mutation half of the finding: rather than advancing `PERMITTED_ORIGINS`, the measured
branch was reached by constructing the object the gate would have produced, which exercises the
defect without touching the ladder.

**The contrast with the other three modules is exact**, and each guard is a single line:
`q2_float.py:155` prints `UNANSWERED — needs two independent providers, have {n}`;
`q3_latency.py:93` prints `no measurements — unanswered, not passed`; `q4_spreads.py:220` returns
`CALIBRATED` with the reason `no gated bars — nothing measured, so nothing is claimed`. Q1 — the
newest module, and the one whose negative answer carries by far the largest consequence, since D29
gates all of Phase 3 on it and §6 makes it a PRD §4 rewrite — has no equivalent.

**One aggravating detail.** `main()` prints the count of unparsable rows *after* the report
(`:156-157`), so a wholly malformed `vendors.csv` prints the strongest verdict in the spike with the
reason it should not be trusted below it.

**On the concurrent round 9's fix.** At committed `e85a193` `q1_vendors.report()` has no test at all
beyond the parametrized provenance-gate case in `tests/test_enforcement.py`, which feeds it a
header-only `vendors.csv` and asserts both that an undeclared origin exits 3 and that a declared one
exits 0 — but nothing about what the report says. Round 9 adds
`test_q1_withholds_its_disposition_on_simulated_input`, which is the right test for the branch it
targets and closes a real hole. It does not close this one: it passes a *populated* trial list, and
its measured-origin half asserts the positive verdict. The zero-trial path stays as reproduced above.

**Why it is not fixed here.** Latent, not live: the negative branch needs `answers_prereg` true,
which needs a `PAPER` origin, which `PERMITTED_ORIGINS` forbids. But it becomes live in the same
decision (D31) that makes the Q1 trial possible at all, which is the worst possible timing. The fix
is a behaviour change to a measurement module plus a new guarantee test, which is more than
convention 8's one-line-no-behaviour-change path authorises; per convention 8's own "when unsure,
disposition it", it is dispositioned. **Proposed disposition:** a `no trials — unanswered, not
failed` guard before the verdict; a guarantee test calling `report([], measured)` and asserting the
absence of both `§7 verdict` and `PRD §4 is rewritten`; and — because this is the fourth module to
need the same guard — one shared helper rather than a fourth hand-written one. Root `CHANGELOG.md` on
landing; no PRD rule changes.

### K4 — MEDIUM (spec question) — a fabricated vendor figure restated in prose as a finding about the world

**What is claimed.** `docs/PHASE-2A-REPORT.md:62-64`, under Q1, in a paragraph headed **Finding**:
*"IBKR alone is a **pre-determined negative** for the 200-symbol clause (~100 market-data line cap vs
§7's 200). A second vendor trial is required regardless of IBKR paper connectivity."* The Q1 row in
the same document's executive summary (`:17`) gives its status as **Unanswered**.

**Where the number comes from.** `data/spike2a/vendors.csv`, written by
`synthetic_data_generator.py`, declared `SIMULATED` in `PROVENANCE.txt`, and generated fresh by this
review:

```
provider,monthly_cost_usd,concurrent_symbols,refresh_seconds,sample_coverage_pct,hard_filters_expressible,notes
ibkr,450,100,30,98,true,pre-determined negative: concurrent cap ~100
polygon_screener,400,500,45,97,true,simulated pass candidate
finviz_manual,50,50,120,99,false,refresh too slow; filters not expressible
```

The generator's own module docstring describes this file as *"A vendor trial matrix with one passing
and two failing providers (Q1)"* — the numbers were chosen to exercise the pipeline's pass and fail
branches, not to describe IBKR. The report's one substantive Q1 finding is a cell from a fabricated
CSV, with the `notes` column's hedge promoted into the document's voice.

**How this was reproduced.** By regenerating the dataset, reading the file, and locating the
generator function that writes it. Weaker than K1–K3: established by reading, not by making anything
fail. It should be read as such. Note also that the claim is *plausible* — IBKR's default market-data
line entitlement is of that order — which is exactly what makes it durable. Plausible and unsourced
is the combination that survives review.

**Why this is a spec question and possibly a new defect class.** Every mechanism built for the sixth
defect class constrains the *machine* path. `Provenance.answers_prereg` is false for `SIMULATED`;
`banner()` prints the origin above every report; each module withholds its §7 verdict; D30's stated
mitigation is that *"any value capable of triggering a D7 disposition must be reproducible from a
provenance-marked input"* — and this value **is** reproducible from a provenance-marked input, which
is precisely why nothing fired. Nothing constrains a human quoting that input in prose with the
marker left behind. Provenance travels with the data and with the module's printed output; it does
not travel with a quotation. That is mechanically distinct from all six recorded classes, and K1 is
arguably a second instance of the same mechanism.

**Whether it is a seventh class is not the reviewer's call** and the defect-classes section in
`docs/PLAN.md` is untouched by this round. The `review-round` skill permits a new row only for a
genuinely new class and a subsection for a new population; the honest position is that this one sits
on the boundary. Raised in `docs/CHANGELOG.md` under Unreleased with both readings stated.
**Independent of that call, one thing should change:** the IBKR figure is either cited to a vendor
document or marked as an unsourced estimate. As written, the only source in the repository for a
claim about the world is a file the same repository refuses to let any module read a verdict from.

### K5 — MEDIUM — the Phase 3 gate document doubles Phase 3's filter scope, and attributes the number to a section that states none

**What is claimed.** `docs/PHASE-3-READINESS.md:81-85`, under the heading **"From PRD §12.1:"** —
*"**Phase 3:** Scanner implementing §4.2 **hard filters** (14 filters, rejection codes in WS4)."*

**What the PRD says.** §4.2's table has 14 rows: **7 Hard** (Gap %, Relative Volume, Float, Price
Range, Average Daily Volume, Circuit Breakers, Liquidity/Spread) and **7 Soft**. §12.1's Phase 3 row
reads "Scanner (hard filters)" and gives no count. So the sentence takes the row count of the whole
table, applies it to the hard subset, and attributes it to a section that states neither.

**How this was reproduced.** By parsing §4.2's Hard/Soft column programmatically rather than counting
by eye — deliberately, because the error being reported *is* a hand-count of the wrong column, and
the skill records "a finding overstated fourfold by reading the wrong PRD column" as an error a
previous round's fact-check had to catch. The count is 7 hard / 7 soft / 14 total. The 14 traces to
PLAN's Workstream 4 checklist, "Define 14 filters with default thresholds", where it is correct.

**Why it matters more than a typo.** This is the document that governs whether Phase 3 may start,
and this is its statement of what Phase 3 *is*. A reader sizing the scanner from it plans double the
filter set, and the soft filters that are off-by-default or flag-only — `INST_OWN_HIGH` among them,
which D24 keeps deliberately inert — would be built as rejection paths. **Disposition — fixed in this
change**: the bullet now says 7 hard of §4.2's 14, names them, cites §4.2 for the count, and leaves
§12.1 cited for what it actually states.

### K6 — LOW-MEDIUM — three documents undercount what the same interval built

One mechanism: a document's account of the repository outliving the commit that changed the
repository. All three are fixed in this change; they are dispositioned rather than taken down
convention 8's silent path because this is the **fourth consecutive round** to find this shape —
round 7's H1 (a document claiming a guardrail held while `make check` was red), round 8's I1 (two
documents claiming a guardrail did not exist after it shipped), round 9's own findings, and now
these. Convention 8's weak point is the triviality judgement, and a finding that recurs was never
trivial.

| Where | Says | Is |
|---|---|---|
| `docs/PHASE-2A-REPORT.md:35` | "`provenance.py` gates all **six** spike entry points" | **Seven** — `windows`, `universe`, `sample`, `q1_vendors`, `q2_float`, `q3_latency`, `q4_spreads` all call `provenance.require`. Six at `b70fa7a` **and six at `d03b35b`, the commit that added this document** — `q1_vendors.py` arrived one commit later, at `eff7b0c`, which did not revisit either document. Correct when written; stale two commits later, inside the same interval |
| `docs/PHASE-3-READINESS.md:18` | "**Six** entry points, provenance gate, H4/H6 schema" — as the evidence that instrumentation is **Met** | Same seven. The gate matrix undercounts the guard it certifies |
| PLAN, § Sequencing & Dependencies, §21.1 row | "**154 test functions** across **nine** files" | **156 across ten**. The two added: `test_quote_at_or_before_derives_age_seconds_from_signal_instant` and `test_quote_at_or_before_selects_last_tick_not_session_end`, both in the new `tests/test_spike2a_q4_quote_selection.py`. A third function changed name only |

A fourth instance — PLAN's Phase 2a row reading "carries Q2–Q4 code" — was **independently found and
fixed by the concurrent round 9** and is therefore not carried here.

**How these were reproduced.** By execution and by `git`, both against a pristine `e85a193`
checkout: `grep -l "require(" scripts/spike2a/*.py | grep -v provenance.py` returns seven at `e85a193` and six at `b70fa7a` (the unfiltered form returns eight and seven, since `provenance.py` defines `require`);
`grep -c "^def test_"` over `tests/test_*.py` gives 156 at `e85a193` and 154 at `b70fa7a`, with the
two new names isolated by diffing the sorted function lists between the commits.

**Fixed in this change.** No `docs/CHANGELOG.md` entry — none is a spec question — and no root
`CHANGELOG.md` entry, since no code changed.

### K7 — LOW-MEDIUM (spec question) — H7 was decided by the party §7's amendment clause constrains, and this round is asked to ratify it afterwards

**What happened.** Round 7 raised H7 — does a synthetic run count as a §7 data pull? — and explicitly
declined to answer it, on a stated principle recorded in `docs/CHANGELOG.md`: *"§7's amendment rule is
the one thing in the spike that cannot be amended by the person it constrains."* It proposed "no" and
left it open. In this interval H7 moved to that document's **Decided** table with the answer "no",
PLAN's Phase 2a row records "H7 decided", `PHASE-2A-REPORT.md:100` lists it as decided, and
`PHASE-3-READINESS.md:96` gives the review a checkbox: *"H7 disposition accepted (synthetic ≠ data
pull)"*.

**What is not in question.** The answer is right, it is the answer round 7 proposed, and the
alternative — §7 frozen against a random number generator — is absurd. Its operational enforcement
(`Provenance.answers_prereg`, the withheld verdicts) is real, built, and verified by execution here.
The reasoning is also recorded honestly in D30, which lists amending §7 among its rejected
alternatives for this exact reason.

**What is.** The decision was taken by the party the clause constrains, and the independent check was
scheduled *after* four documents came to rely on it. A checkbox in the reviewed document asking the
reviewer to accept a disposition already load-bearing in four places is ratification, not review.
This round declines to tick it as a finding of independence — while stating plainly that it agrees
with the substance. **Note for whoever merges the two rounds:** in the working tree that box is now
ticked, by round 9's edit rather than this one, so the repository will carry an accepted H7 checkbox
and a finding objecting to how it was accepted, side by side. That is the correct outcome only if the
objection is read; it is recorded here rather than resolved by un-ticking someone else's box.

**Proposed disposition.** Either give H7 a numbered PLAN decision with its rejected alternatives,
like every other behaviour-relevant call in this repository, or record in `docs/CHANGELOG.md` that
its Decided entry was self-certified and by whom. Raised, not resolved.

### Trivial, fixed in this change (convention 8)

- `docs/PHASE-2A-REPORT.md:96` — the heading "Open spec questions (unchanged disposition)" sits above
  a row whose entry reads "**Decided**", for a disposition that changed in this very interval.
  Heading corrected.
- `docs/README.md:35` — "six rows as of round 7, and the count is deliberately not restated here"
  restates the count in the clause that claims not to, and is stale by two rounds. Reworded to point
  at PLAN as the authority without carrying a number.

### Round 8's findings, reverified

| ID | Round 8's disposition | State at `e85a193` |
|---|---|---|
| I1 | Fixed in that change (PLAN risk register + `scripts/spike2a/README.md`) | **Closed.** Both sites traced and confirmed — `scripts/spike2a/README.md:178-180`, and PLAN § Risks & Dependencies, "The instrument is outside every check", which now reads "would now be caught" and separates instance from class |
| H2 | Split by round 7 — mechanical half fixed, coverage-exemption question left open; round 8 counted it in both its lists | **Half open, unchanged.** The §8 no-coverage-obligation question is still in `docs/CHANGELOG.md`'s open-questions table and in `PHASE-2A-REPORT.md:101`. Listed here because a first draft of this round folded it into the nine "fixed" and closed it by arithmetic |
| H4 | Open | **Closed this interval** — `signal_at` required, `quote_at_or_before` selects the quote in force. Recorded in `docs/CHANGELOG.md`'s Decided table. K2 is a defect *in that fix*, not a reopening of H4 |
| H6 | Open | **Closed this interval**, same entry. Staleness is now reachable without a fake zero default — via derivation only, which is K2 |
| H7 | Open spec question | **Decided this interval** — see K7 |
| H10 | Open, documented (§7 exclusions inert on generated fixtures) | **Open, unchanged.** Still documented in `PHASE-2A-REPORT.md:102` as non-blocking |
| H13 | Open (mutation testing not re-run) | **Open, unchanged.** `PHASE-3-READINESS.md:74` correctly lists it as non-blocking for D29. This round could not run a mutation tool either — see the appendix |

**The arithmetic, stated because this repository has got it wrong twice.** Round 8 raised **one**
finding and it is closed. Round 7 raised fifteen: nine were fixed and reconfirmed by round 8, H5 was
fixed in the interval before round 8 and verified there, **H4, H6 and H7 close or resolve in this
interval**, and **H10 and H13 remain open**. 9 + 1 + 3 + 2 = 15.

**One qualification on that nine, which a first draft of this paragraph got wrong.** H2 sits in
round 8's list of nine fixed *and* in its list of open spec questions, because round 7 split it: the
mechanical half was fixed and the coverage-exemption question — should PHASE-2A-SPIKE §8's
no-coverage grant be narrowed? — was left open, and round 7 explicitly said the open half is the
substantive one. It is still open at `e85a193`, still carried in `docs/CHANGELOG.md`'s open-questions
table and in `PHASE-2A-REPORT.md:101`. So the accurate statement is: **nothing regressed, no finding
was reopened, and one finding counted as fixed (H2) has an open half that this round did not close
either.** Round 9's own fact-check caught the same H7/H2 conflation in its draft; that two
independent drafts made it is a fair warning that the nine/open overlap is a trap in the source
material, not a slip.

## 5. What is genuinely good

- **The Phase 3 gate is refused correctly, and the refusal is the hard direction.** Everything a
  motivated reader would need to talk themselves into starting Phase 3 is present — complete
  instrumentation, a validated pipeline, a green suite, a document headed "Completion Report" — and
  `PHASE-3-READINESS.md` still says not ready, names the single blocking item, and includes the
  sentence *"A review round cannot honestly approve Phase 3 start without violating D29."* A document
  that pre-commits its own author's review to a conclusion they may not want is rare, and this one
  does it.
- **The empty-sample guards in Q2, Q3 and Q4 are the right instinct, three times.** K3 is a finding
  *because* the other three make the honest choice; had none guarded it, the finding would be a
  design gap rather than an omission. `q4_spreads.py:220` in particular returns CALIBRATED with the
  reason "nothing measured, so nothing is claimed" rather than the tempting INERT — a zero rejection
  rate over zero bars is not evidence a gate is decoration.
- **H4/H6's fix is a real improvement, not a papering-over.** Requiring `signal_at` and failing the
  row when it is missing — rather than defaulting to the session's last tick — means Q4 can no longer
  quietly attribute one quote to every setup on a symbol-session. Both new tests attack the behaviour
  rather than confirm it, and `test_quote_at_or_before_selects_last_tick_not_session_end` asserts the
  two setups get *different* quotes, which is the assertion that would have caught H4.
- **The generator's seed placement is documented as a defect that was fixed.**
  `synthetic_data_generator.py:477-483` explains that seeding used to live under `__main__`, making
  reproducibility true from the command line and false for any programmatic caller. That is the fifth
  defect class in miniature, caught and written up. The irony that K1 is a stale number from the same
  file is worth stating: the mechanism is right and the reporting around it is what failed.
- **`docs/CHANGELOG.md`'s Decided table is doing its job.** H4/H6, H5 and H7 each carry the
  reasoning and, for H5, the two further defects a first draft of that fix contained and how they were
  caught. A changelog that records the defects in its own fixes is unusual.
- **Two independent rounds over the same interval found almost disjoint sets of defects, and both
  found something in `q1_vendors.py`.** That is the strongest available evidence for the PLAN's
  standing claim that the cold read is the most valuable open item — two readers, one file, two
  different holes, neither seeing the other's.

## 6. The risk the findings list does not capture

**The documents have become the deliverable, and nothing checks them.** D30 is correct and this round
does not question it — but its effect is that no measurement in this repository can currently produce
a number about the world. What the project ships during the suspension is prose: a spike report, a
readiness gate, a decision log. PLAN's own count is six mechanical checks, five of which range over `src/tradipy/` and the PRD
only; the sixth, the registry lint, reaches `scripts/spike2a/`. **Not one of them can tell whether a sentence in `docs/PHASE-2A-REPORT.md` is
true.** K1, K4, K5 and K6 are all instances — the four findings this round reached by
reading documents, three of which it then confirmed by execution because reading alone could not
settle them — eight wrong statements in two files added the same day as the commit under review. The suspension has moved the project's entire output surface outside its entire verification
surface, and the sixth defect class's diagnosis — *"the instrument is outside every check"* — now
applies to the reporting layer with none of the mitigation D30 bought for the measurement layer.

The cheap partial mitigation is mechanical and worth naming: the generator prints its counts and
writes them into `PROVENANCE.txt`; a test could assert that any count appearing in
`docs/PHASE-2A-REPORT.md`'s pipeline table matches a fresh run, the way `tests/test_documentation.py`
already pins doc counts elsewhere. That would have caught K1 and K6's first two rows. It would not
have caught K4, which is the harder half and probably needs a convention rather than a test: **a
number sourced from a `SIMULATED` file may not appear in prose without the word simulated beside
it.**

**Second, structural: this round's terms of reference were written by its subject.**
`PHASE-3-READINESS.md` §"What 'Phase 3 review' can mean today" enumerates what a round conducted now
may conclude, and §"Review checklist (for round 9 or human sign-off)" pre-writes its checklist,
including a box for accepting a decision the same interval took (K7). The enumeration is accurate and
the checklist useful — three of its seven boxes are the right ones to put in front of a reviewer
(accepting the report as partial completion, verifying the H4/H6 schema, and requiring D31 before any
`PAPER` data lands). The H7 box is not one of the three; see K7. But a review whose scope is supplied
by the artefact under review inherits that artefact's idea of where to look, on top of the context
problem every round here already has. Two of this round's seven findings are *in the checklist
document itself*, and neither is in any box.

**Third, unchanged and still first: no one without prior context has read any of this.** Six code
rounds, six defect classes, and the cold read is still outstanding. This round is the sixth performed
with the repository in context and it shows in the shape of the findings: they cluster in the two
files that did not exist when round 8 formed its idea of where the risks were. A reader without that
idea would look elsewhere, and on this repository's record, would find something none of the ten
rounds did.

## 7. Next steps

**Now (this change):** K1, K5, K6 and the two trivial items are fixed. Round 10 is wired into
`docs/README.md`'s review table and PLAN's companion table, Workstream 11 checklist and sequencing
row. The defect-classes section is **not** touched — see K4.

**Now (not this change, and small):**

1. **K3's guard**, before D31 rather than after it. One shared "nothing measured" helper for all four
   Q-modules, plus the guarantee test that calls `report([], measured)`. This is the one finding whose
   window closes on a schedule: D31 makes the negative branch reachable.
2. **A doc-count test** over `docs/PHASE-2A-REPORT.md`'s pipeline table against a fresh generator
   run, on the model of `tests/test_documentation.py`.
3. **Reconcile the two round-9/round-10 reviews** into one entry per round in `docs/README.md` and
   PLAN, so the `J*`/`K*` split is explained where a future citation will look for it.

**Raise as spec questions (`docs/CHANGELOG.md`, Unreleased — this change adds them):**

4. **K2** — which `age_seconds` governs §20.14 on the Q4 path, and whether `CsvQuoteFeed`'s
   documented column should be honoured or removed.
5. **K4** — whether provenance leaking on the prose path is a seventh defect class or a second
   population of the sixth; and, either way, sourcing or marking the IBKR figure.
6. **K7** — whether H7's decision needs a numbered PLAN decision or a note recording that it was
   self-certified.

**After the ladder advances (D31), in §7's own budget order:**

7. Q4 first, on measured NBBO — it needs no subscription, and K2's answer must land before it runs,
   because on measured ticks the derived-versus-supplied age question stops being hypothetical.
8. Q1's vendor trial, with K3's guard in place and the IBKR line-cap question answered from a vendor
   document rather than from `vendors.csv`.
9. Q2's second float provider, Q3's paper timestamps, then the D29 gate assessment — the first moment
   a review can honestly tick the Phase 3 box.

**Still outstanding, unchanged, and still the most valuable:** the cold read, the traceability check,
the §15/§16 supersession sweep, and H13's mutation run.

## 8. Appendix: how this review was verified

**Gates run:** the test suite — **197 collected cases, 0 failed, 0 skipped**, across ten test files;
`scripts/check_links.py` — **all 207 relative Markdown links resolve**; `python -m tradipy demo` —
exits 0 and reproduces all three §3 worked examples with every derived value matching. All three
against a pristine `e85a193` checkout.

**Gates NOT run, and what is therefore unverified.** `ruff check`, `ruff format --check` and
`basedpyright` **could not be executed**. The sandbox available to this review has no network route
to PyPI and no CPython 3.13 build — `uv sync --frozen` fails downloading the interpreter and
`uv pip install ruff` fails resolving the index. **`make check` is therefore unverified as a whole by
this round.** Lint, formatting and type errors introduced in this interval would not have been caught
here; round 8's green `make check` at `b70fa7a` is inherited, not reproduced, and this sentence exists
so the next round does not read "197 passed" as "the build is green". Also not run: coverage, and any
mutation-testing tool — **H13 remains unanswerable** for the third consecutive round.

**How the suite was run, stated because it changes what "197 passed" means.** Under a **stdlib-only
`pytest` stand-in written for this review** (`mark.spec`/`boundary`/`polarity` as no-ops, stackable
`mark.parametrize`, `raises(match=)`, `fixture`, `skip`, and `tmp_path`/`capsys`/`monkeypatch`), on
**CPython 3.10.12**, with `datetime.UTC` backfilled via `sitecustomize` since the project targets
3.13. Round 7 used a stand-in of its own for the same reason. **Round 8 did not** — it ran `ruff`,
`basedpyright` and `pytest` itself on the project's toolchain, which makes its 154 functions / 194
cases a real `pytest` figure. That this round's stand-in reports 156 / 197 over two added test
functions is therefore a usable cross-check on the collection, though not proof of identity.

**On the interpreter risk to K1, and why it is ruled out.** Anything version-dependent — `random`
stream differences between 3.10 and 3.13 above all — could in principle move the generator's counts.
The method is what excludes it: the same interpreter and the same stand-in were used at `b70fa7a`,
`d03b35b` and `e85a193`, and at `b70fa7a` the generator reproduces round 8's documented 156 / 147 /
8,820 and 1.36% exactly. A version artefact cannot produce round 8's figures at round 8's commit and
different figures at the next one. The absolute values in the right-hand column of K1's table should
still be re-run on 3.13 before being quoted, and the fix applied to
`docs/PHASE-2A-REPORT.md` says so.

**Executed, not read:**

- `synthetic_data_generator.py` at `e85a193`, `d03b35b` and `b70fa7a` — three checkouts, one
  interpreter. Counts 156/157/3,566 at the first two, 156/147/8,820 at the third.
- `q4_spreads.py` against each of those datasets — 0.64% (1/157), d1 6.67% at `e85a193` and
  `d03b35b`; 1.36% (2/147), d1 14.29% at `b70fa7a`. All three printed the "pipeline outcome (NOT a §7
  verdict)" wording, so D30's withholding is verified by execution at every commit in the interval.
- `q1_vendors.py` and `q3_latency.py` on the generated inputs — both print the withheld-disposition
  wording on `SIMULATED` origin, as documented.
- `q1_vendors.report([], prov)` with a hand-constructed `Provenance(origin=DataOrigin.PAPER, …)` —
  **K3**.
- `CsvQuoteFeed` + `quote_at_or_before` + `spread_at_signal` on a one-row CSV carrying
  `age_seconds=999` — **K2**. `QUOTE_STALE` standalone, `PASS` with spread 0.02 through
  `quote_at_or_before`.
- §4.2's Hard/Soft column parsed programmatically — **K5**. 7 hard, 7 soft, 14 rows. Counted by
  machine because the finding is a hand-count of the wrong column.
- `grep -l "require(" scripts/spike2a/*.py | grep -v provenance.py` at both commits — **K6**, seven
  versus six. The filter matters: unfiltered the command returns eight and seven, because
  `provenance.py` defines `require` and matches its own name.
- `grep -c "^def test_" tests/test_*.py` at both commits, plus a sorted diff of the function names —
  **K6**, 156 versus 154, with the two additions isolated by name.
- `git diff b70fa7a HEAD -- src/` — empty. The invariant layer is unchanged, confirmed rather than
  assumed from the absence of a claim otherwise.
- `git log --diff-filter=A -- docs/PHASE-2A-REPORT.md` and `git log b70fa7a..HEAD --
  scripts/spike2a/synthetic_data_generator.py` — established that `d03b35b` both added the report and
  rewrote the generator, which is what makes **K1** a same-commit staleness rather than a subsequent
  drift.

**An error this review made, recorded because the alternative is that the next round inherits it.**
The first draft was derived from a snapshot of the *working tree*, not of `e85a193`, taken while a
concurrent round's edits were uncommitted on disk. Four files were contaminated —
`tests/test_enforcement.py`, `docs/PLAN.md`, `docs/PHASE-2A-REPORT.md` and the root `CHANGELOG.md` —
and the draft consequently reported 157 test functions and 198 cases (both including another round's
uncommitted test), 222 links (including another round's new file), and framed K3 around a test that is
not in the commit under review. It was caught when an `Edit` against `docs/PLAN.md` failed because the
string it was replacing had already been corrected by someone else. Everything was then re-derived
from `git archive e85a193`, and the surviving numbers in this document are from that checkout. The
class is the one this repository already knows: **a measurement taken from the wrong subject, reported
under the name of the right one** — K1 with the reviewer as the subject.

**Not a cold read.** This round was performed with the repository in context, and it read round 8's
review before forming its own view of where to look — which is visible in the result: five of seven
findings are in files round 8 never saw, and none is in `src/tradipy/`, where four rounds of attention
have already been spent. Two agents reading the same repository do not compose into a cold read, and
ten rounds do not either.

**Adversarial fact-check — two passes, and the error rate.** A separate agent was given the draft
and the pristine checkout each time, and asked to verify every file:line citation, every count, every
PRD attribution and every link, and to report only problems.

**First pass: 24 substantive errors.** *Four wrong line numbers* — `:101`→`:100` for H7, `:103`→`:102`
for H10, `q4_spreads.py:285`→`:283` for the `quote_at_or_before` call site, and a function extent
given as `:58-73` for a function that starts at `:49`. *Six miscounts* — a `grep` command returning
eight where the text claimed seven (`provenance.py` defines `require` and matches its own name),
"four documents" for three, "six boxes" for seven, "two merges" for three, "fifth round in context"
for the sixth, and "three of the four numbers" in a table with three rows. *Two dates wrong* — two
documents described as eight days old that were added the same day as the commit under review.
*Three claims that inverted their source* — the generator's seed move described as protecting
command-line reproducibility when its own comment says the command line was already fine and the
*programmatic* caller was not; `TEST_SETUP.md` named as a D31 reference when it never mentions D31;
and PLAN's six mechanical checks described as covering the link graph, which is not one of them.
*Two link and description defects* — three references to round 9's review linked to a file untracked
in the committed repository, which would have failed `scripts/check_links.py`, and
`test_every_spike_entry_point_gates_its_input` described as asserting only refusal when it asserts
acceptance too. And *seven claims of work not actually done*: the draft said K6's PLAN row was fixed,
the `docs/README.md` trivial item was fixed, the round was wired into both index tables, and three
spec questions had been raised in `docs/CHANGELOG.md`. **None of that had been applied.** That last
group is the serious one — a review asserting its own dispositions were discharged is the fifth
defect class with the reviewer as its subject — and it was corrected by doing the work, not by
softening the claim.

**Second pass: 15 further errors, ten of them created by the first correction pass.** The created
ones cluster exactly where new prose was written: the enumeration of wrong statements added in pass
one absorbed an unsourced-but-not-false claim (the IBKR figure) and split one defect into two to
reach ten, so the honest count is eight; the H2 paragraph added in pass one was not reflected in the
Disposition block, which went on listing the open set without it; the root-`CHANGELOG.md` paragraph
added in pass one miscounted five figures as four, called an `[Unreleased]` entry a dated historical
one, missed two further occurrences, and contradicted §1 on whether the sentence was ever wrong; the
fact-check section itself reported 14% where its own text implied 10%, and double-counted one defect
as both a miscount and a source inversion; and the "seven boxes" correction left it unstated which
three boxes are the right ones, one clause after objecting to a fourth. Four errors survived the
draft rather than being created: the `grep` fix applied at one site and not its sibling in the
appendix — structurally the same slip round 9's own second pass caught in its draft — a claim that
round 8 used a `pytest` stand-in when round 8 ran `pytest` itself, K6's first row borrowing K1's
"same commit" story when `q1_vendors.py` actually arrived one commit after both documents, and the
claim that this round was wired into PLAN's *companion* table, which at that point it still was not.
One was new information rather than an error: round 9's edit has since ticked the H7 checkbox that
K7 declines to tick.

**Error rate: 39 substantive errors across a draft making roughly 120 checkable claims — about 33%,
with 10 of the 39 introduced by the correction pass and two thirds of the second pass's findings
created by the first.** That is by a wide margin the worst of any round here: round 6's first draft
needed nineteen corrections, round 8's five then zero, round 9's four then one. Two things account
for the gap and neither is flattering. The draft was built on a snapshot of the working tree rather
than the commit, so a whole class of counts was measured against the wrong subject. And it asserted
its own fixes before making them, which no amount of care in the prose can compensate for. **A third
pass would very likely find more**, on the second pass's own evidence that corrections introduce
errors faster than this document's authors catch them; two passes is what the procedure requires and
what was run, and this sentence is here so the next round does not read "fact-checked twice" as
"clean".


---

*Round 10. `e85a193`. Seven findings, three fixed, four raised. Phase 3 remains gated on Q1 measured,
per D29 and D30, and this review does not lift that gate.*
