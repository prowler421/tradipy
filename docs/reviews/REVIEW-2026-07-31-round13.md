# Review round 13 — an independent read of the Phase 4 build

> **Scope.** Round 12 built `src/tradipy/session.py`, `src/tradipy/setups.py`, twenty registry
> rows, `python -m tradipy setups` and [PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md), and said plainly
> that its own review of that work was not independent — the same party wrote and reviewed it in
> one sitting, and `ruff` could not be run in that environment at all. This round is the first to
> read Phase 4 with a working `ruff`, and the first performed by a party that did not write it.
>
> **Commit.** Working tree at the head of `main` (round 12's Phase 4 commit), before this round's
> own edits. Nothing of this round's work is in that baseline.
>
> **Findings prefix `M`.** `L` was round 12.

---

## 0. `make check` — found red, root-caused, fixed

Round 12 could not run `ruff` in its environment and said so three times (its own header, §9 of
[PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md), and its appendix), rather than substituting a hand-built
check — the lesson it drew from round 7 hand-building one and missing seven `B007`s. This round
had a working `ruff` and ran it. **`make check` was red**, for reasons entirely inside the Phase 4
changeset:

| Gate | Result before this round | Cause |
|---|---|---|
| `ruff check` | **5 errors** | `I001` (unsorted imports, `__main__.py`), `RUF007` (`zip` over `itertools.pairwise`, `session.py`), `RUF005` ×2 (list concatenation, `test_enforcement.py` and `test_setups.py`), `RUF100` (stale `noqa`, `test_setups.py`) |
| `ruff format --check` | **4 Phase-4-touched files** unformatted | `src/tradipy/setups.py`, `tests/test_enforcement.py`, `tests/test_setups.py` (all new/rewritten by Phase 4), and **`docs/api.md`** — ruff 0.16 formats the Python fences in Markdown, and the `Reject`/`SoftFlag`/`ExitReason` block Phase 4 added to that file used column-aligned trailing comments the formatter does not preserve |
| `pytest` | 295 cases green on arrival; **297** after M6/M7's two fixtures | unaffected by M3–M5, which is what made them safe to fix inline |
| `basedpyright` | 0 errors | unaffected |
| `scripts/check_links.py` | 291/291 resolve | unaffected |
| `python -m tradipy demo` / `setups` | exit 0 both, self-checks pass | unaffected |

**Reproduced by execution**, on the project's own toolchain (`uv run ruff` 0.16.0, the pinned
version) — the gate round 12's own appendix named as the thing nobody had run against these four
files.

**Disposition: fixed in this change**, mechanically, with no behaviour change:

- `session.py`'s `zip`/`pairwise` lint is suppressed with `# noqa: RUF007` rather than switched to
  `itertools.pairwise` — importing `itertools` would have widened `session.py`'s import allowlist
  (`test_the_setup_layer_reads_nothing_and_imports_nothing_that_could`), which is exactly the kind
  of decision surface this codebase does not let a lint autofix touch quietly. Confirmed: the
  straightforward autofix was tried first, it broke that enforcement test, and was reverted for
  this reason rather than by widening the allowlist.
- The two `RUF005` sites and the stale `noqa` were fixed with `ruff check --fix` and by hand
  (iterable unpacking in place of concatenation); `ruff format` applied to the four files above
  only — **not** to `docs/PRD.md` or `docs/reviews/REVIEW-2026-07-28.md`, which also need
  reformatting under ruff 0.16 but predate this changeset entirely (`git diff --stat HEAD` against
  both is empty) and are out of this round's scope.
- Verified after: `ruff check .` and `ruff format --check` both clean on every file this round or
  Phase 4 touched; `pytest`, `basedpyright`, the link checker, `demo` and `setups` all still pass,
  confirming no behaviour moved.

This is not a numbered finding, on round 11's own precedent: that round found `make check` red
from a prior phase's un-run lint and fixed it "none of them prefixed," because a mechanical,
already-fixed lint gap is exactly what convention 8 says does not need the machinery. It is
recorded here at this length because it is the concrete answer to the question
[PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md) §9 and round 12's header both leave open, and because
`docs/PLAN.md`'s Workstream 11 registry-check row (line 170) still only names the *pre-Phase-4*
`ruff` gap (`synthetic_data_generator.py`, already fixed) — it does not yet know this one existed,
which is one more reason the "cold read" both documents call out as the most valuable open item
was worth doing now rather than later.

---

## 1. Verdict

**Phase 4's arithmetic holds up; its test coverage had a real hole.** Every claim in
[PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md) that this round checked by execution — the three worked
examples from bars, L2's §3.4 rejection, the look-ahead property, the registry counts, the
nineteen spec questions — reproduces exactly, and no fixture in `tests/test_setups.py` was
asserting a wrong value. But the fresh-eyes pass this round dispatched against `setups.py`
(§ appendix) found three dead branches (harmless — verified by mutation to change no behaviour)
and, more consequentially, **a documented §3.4 criterion that no fixture exercised at all**: every
existing bar series is far enough from HOD that its `near_hod` branch never activates, and forcing
it active on every one of them still left the whole suite green. That is the fifth defect class
this project's own history is built around — a guarantee with a passing suite next to an
unenforced mechanism — recurring in the module this round's own §0 had just finished declaring
clean.

| Area | State |
|---|---|
| `make check` | **Was red, now green** (§0) — the first time it has actually been run against Phase 4's four new/changed files |
| Worked examples, look-ahead property, registry counts, spec-question count | **All reproduce exactly** by execution; see §4 |
| Fresh-eyes pass over `session.py` / `setups.py` logic | Delegated to an independent sub-agent; found three dead branches (M3–M5, trivial, fixed) and two real test-coverage gaps (M6, M7) — see §5 and the appendix |
| Documentation self-consistency | **Two findings**, both trivial and both fixed: `architecture.md`'s dependency diagram (M1) and a miscounted enumeration in `PHASE-4-DESIGN.md` §6 (M2) |
| §3.4 crit 9 (HOD proximity consolidation) | **Was unenforced by any test** (M6, HIGH) — fixed by adding the fixture, not by changing the rule; the rule itself was already correct |
| `evaluate_vwap_reclaim`'s "prior HOD" reading | **Untested against a trigger bar that pierces the standing HOD** (M7, MEDIUM) — same disposition: rule already correct, coverage added |
| Round 12 (`L1`–`L8`) | Traced against file and line; **all hold as round 12 left them** — see §3 |
| New defect class | **Two, in fact — see M6/M7 below** — the documentation self-consistency class (M1/M2) round 12's own L1/L5/L6 already named, and the fifth defect class (CLAUDE.md convention 6: a guarantee with no test that would notice it failing), which round 12 did not surface in Phase 4 because its own review of Phase 4 was not independent |

---

## 2. What this round could and could not establish

It establishes that Phase 4's `ruff` status was previously an assumption, not a measurement, and
that the assumption was wrong in four files; that assumption is now replaced with a measurement,
and the measurement is green. It establishes that the specific numeric claims round 12 made under
the caveat "not independently reviewed" — three worked examples, the look-ahead property, 75
registered/74 baseline, nineteen spec questions with a 4/15 split — check out exactly. It does
**not** establish anything about calibration (D33 is unchanged: all twenty new rows are still
`(bounds: code)`), and it does not re-litigate L2, which is still open exactly as round 12 left it.

It is a genuine, if narrow, cold read: this round did not write any of the code under review. Five
of its seven findings (M1, M2 by this document's own author; M3–M5 by an independent sub-agent)
are in exactly the place a same-sitting review is worst-positioned to see — a document (or a
branch) that reads as obviously correct because nobody tried to break it. The remaining two (M6,
M7) are the place round 12's own review method could not have looked at all: it had no working
test runner, so "does a fixture actually exercise this branch" was not a question it could ask of
its own work, only of the arithmetic it could trace by hand.

---

## 3. Round 12 (`L1`–`L8`), verified

| Finding | Traced to | Status |
|---|---|---|
| L1 — PLAN's test count | `docs/PLAN.md` line 317: "**235 test functions** across twelve files" | **Holds.** `grep -c '^def test_' tests/test_*.py \| awk -F: '{s+=$2} END{print s}'` returns 235 across the twelve files listed |
| L2 — §3.4's worked example fails §3.1.1's room gate | `python -m tradipy setups` | **Holds, reproduced again.** Output unchanged: room gate `FAIL`, next whole dollar at $4.00, gap $0.17 vs required $0.28; "§3.4 is rejected on purpose" banner intact |
| L3 — K3's guard closes only the empty case | `scripts/spike2a/q1_vendors.py:113-133` | **Holds as left: open, unreachable until D31** (per round 12's own disposition; not re-executed this round, out of Phase 4's scope) |
| L4 — two documents outside `CHECKED_DOCS` | `tests/test_documentation.py` `CHECKED_DOCS` | **Holds as left: open, deliberately.** `PHASE-4-DESIGN.md` is still absent from the list (owed, per round 12) |
| L5 — PLAN's round-10 summary | `docs/PLAN.md` | **Holds fixed** — the appendix figures (24/15/39, seven claims) match the summary |
| L6 — two numbering schemes | `docs/PLAN.md` line 308 | **Holds fixed** — states both series and file counts explicitly |
| L7 — interpreter caveat | `docs/PHASE-2A-REPORT.md` | **Holds as left: to the report's owner**, not re-executed this round |
| L8 — registering a threshold turned two literals red | `scripts/spike2a/synthetic_data_generator.py`, `poc.py` | **Holds fixed** — `_VIX_BASELINE` and the `rvol` move to 8 are both in the working tree; the registry lint is clean (`75` registered, `74` baseline, confirmed by direct count, not inherited) |

No partial closures found beyond what round 12 already disclosed for K3/K6.

---

## 4. Where we stand against the PLAN and the PRD

Unchanged from round 12's own §3/§4, re-verified rather than re-derived:

- `PERMITTED_ORIGINS == {SIMULATED}`, test-pinned. D31 unwritten. Phase 3 and Phase 4 dependency
  rows in §12.1 stay unticked.
- Registry: **75** rows (`grep -c '^\s*_p("' src/tradipy/params.py`), **74**-entry baseline
  (`json.load` on `tests/registry_baseline.json`) — the 1-row difference is expected and explained
  in-repo (the baseline tracks distinct PRD-prose search keys, not a 1:1 mapping to rows), not a
  discrepancy.
- **Nineteen** spec-question rows in `docs/CHANGELOG.md`'s Phase 4 table (lines 67–85, counted
  directly), split 4 (behaviour-changing) / 15 (raised, not resolved) exactly as
  [PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md) §6 states — see M2 for the one place that split's own
  *enumeration* miscounted itself.
- `python -m tradipy demo` and `setups` both exit 0 with self-checks passing, including `setups`
  printing L2's rejection on the §3.4 example as designed.

---

## 5. Findings

### M1 — `architecture.md`'s dependency diagram implies an edge that does not exist — LOW-MEDIUM

**Claimed.** `docs/architecture.md`'s "Module structure" section drew the package's dependency
graph as an ASCII bus:

```
rounding.py  ◄── params.py ◄──┬── quotes.py ──────────────┐
                              ├── score.py  ──┐           │
rejects.py   ◄────────────────┴── gates.py  ──┴─ scanner.py ── poc.py ◄── __main__.py
                                              │             │
bars.py  ◄── session.py ◄───────────────────── setups.py ────┘
```

**Found.** `quotes.py`'s branch off the `params` bus is drawn *above* the row where `rejects.py`
merges into the same bus (column 30 in the source: `┬` at row 1, `├` at row 2, `┴` at row 3 where
`rejects.py`'s arrow arrives). Read top-to-bottom, that draws `quotes` and `score` as tapping the
bus before `rejects` joins it, and only `gates` as tapping after — which visually asserts `quotes`
depends on `params` alone. It does not: both the prose two lines below the diagram and
`src/tradipy/quotes.py`'s own import block (`from tradipy.rejects import Reject`) say `quotes`
depends on `params`, `rejects` **and** `rounding`. The prose itself compounded the same gap by
omitting `rounding` from the `quotes`/`gates` dependency list ("depend on `params` and `rejects`"),
though both modules import it directly.

**Reproduced by execution** — the diagram's junctions were mapped to source columns with a small
script rather than read by eye (`session_id`/column indices attached in the working notes), and
the `quotes`/`gates` import lists were confirmed against the actual `from tradipy... import`
statements in both files, not against the prose describing them.

**Why this is more than a nit, stated because the document under review says so about itself two
sections later.** [PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md) §3 explicitly rejected this exact
drawing style for this repository's dependency graph: *"the first version of this section was a
bus-style ASCII graph whose junctions implied six edges that do not exist, and whose caption
claimed a left-to-right invariant the drawing did not honour... a table cannot be geometrically
wrong."* That lesson was learned and applied to the *new* table in the same document, in the same
changeset that left the *pre-existing* bus diagram in `architecture.md` untouched — including
extending it with two new rows (`session.py`, `setups.py`) using the same technique. The bug this
diagram has is the same shape the sibling document names, one file over.

**Disposition: fixed.** `architecture.md`'s diagram is now the same table
[PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md) §3 uses, and the prose now lists `rounding` alongside
`params` and `rejects` for `quotes` and `gates`. Trivial by convention 8 — no spec implication, no
behaviour change, and it is a correction to a picture, not a rule.

### M2 — `PHASE-4-DESIGN.md` §6 enumerates sixteen items and calls them fifteen — LOW

**Claimed.** §6: *"The other fifteen are recorded with the same disposition... In the table's
order they are: [a semicolon-separated list]."*

**Found.** The list has sixteen semicolon-separated items. Fifteen map one-to-one to the fifteen
non-behaviour-changing rows in `docs/CHANGELOG.md`'s spec-question table (lines 69–85 minus the
four cited earlier in §6); the sixteenth is a second phrase — *"its depth reference"* — split off
from the item immediately before it, both of which come from the **same** CHANGELOG row (§3.4
crit 3: *"close or wick? And depth... against which VWAP"*, one row, two sub-questions). Every
other row in the table maps to exactly one list phrase; this one row maps to two, which is what
pushed the count from fifteen to sixteen without the header noticing.

**Reproduced by execution** — counted the semicolons directly against `docs/CHANGELOG.md`'s table
rows (line-numbered), not against the header's own claim.

**Why this one is worth naming rather than silently fixing.** It is the *identical defect shape*
round 12's own adversarial fact-check caught in an earlier draft of this same sentence — its
appendix records, of the second fact-check pass, *"an enumeration of 'the other fifteen' listing
fourteen."* The correction for that pass apparently landed on the wrong side: the shipped document
now lists sixteen instead of fourteen, having presumably passed back through fifteen at some
point in between. A sentence that explicitly warns *"restating [the count] here is what round 12's
own fact-check caught this section doing with the wrong number"* was, at the time this round
started, still doing it — in the other direction.

**Disposition: fixed.** The two sub-questions from the shared CHANGELOG row are now one list
phrase (*"the dip's close-versus-wick reading together with its depth reference (one
CHANGELOG.md row, two questions)"*), restoring the fifteen-phrase-per-fifteen-row correspondence
the header claims. Trivial by convention 8.

### M3–M5 — three dead conditions in `setups.py`, fixed inline (convention 8)

All three surfaced from the fresh-eyes sub-agent's pass (§ appendix) and were independently
re-derived from source before being fixed — not taken on the sub-agent's word. Each changes no
behaviour, confirmed by running the full suite (295 cases) before and after every fix, and each
is a one-line simplification with no spec implication, so per convention 8 these are logged here
rather than dispositioned individually.

- **M3** — `_trigger_bar_eligible`'s guard was `minute > 0 and i > 0`. `Session.__post_init__`
  requires strictly increasing, non-negative integer minutes, so `session.minute(i) >= i` for
  every valid `i` by induction; `minute > 0` is therefore true whenever `i > 0` and the
  conjunction can never differ from `i > 0` alone. Simplified; docstring corrected, since it had
  argued the opposite (that the second clause was doing independent work).
- **M4** — the room-gate `Criterion`'s `code` field read `room_verdict if room_verdict is not None
  else room.binding`. `room_verdict = check_room(entry, resistance.level, r, spread, cfg)` returns,
  whenever it is non-`None`, exactly `required_room(r, spread, cfg).binding` — the same pure call
  the caller already made to produce `room` one line above with identical arguments. The ternary
  cannot resolve to anything other than `room.binding` on either branch. Simplified to `room.binding`
  directly.
- **M5** — `evaluate_bull_flag`'s guard was `if chosen is None or not qualified:`, where `chosen =
  select_flagpole(plain, [pole_span], ...)` is given a single candidate scored by the identical
  predicate that produced `qualified` two lines above. With one candidate, `select_flagpole`
  returns `None` iff the predicate rejects it, so `chosen is None` and `not qualified` are the
  same fact computed twice. Simplified to `if chosen is None:`.

Each was proven inert by mutation before being touched: reverting the simplification and rerunning
`tests/test_setups.py` + `tests/test_enforcement.py` (122 cases) leaves every case green in all
three cases, which is the actual claim ("this branch never fires differently"), not an inference
from reading the arithmetic.

### M6 — §3.4 criterion 9 (HOD proximity consolidation) had no test at all — HIGH

**Claimed, implicitly.** `setups.py`'s module docstring and `params.py`'s registry both treat
`hod_proximity_pct` / `hod_proximity_min_candles` as an enforced §3.4/§2 rule: *"within
`hod_proximity_pct` of HOD, require `hod_proximity_min_candles` since the dip low."*

**Found.** No fixture in `tests/test_setups.py` or `tests/test_enforcement.py` puts a VWAP-Reclaim
trigger bar within `hod_proximity_pct` (0.5%) of the prior HOD — every existing series, including
the worked example, sits 4–8% away, so `near_hod` is `False` in every case the suite runs and
`proximity_ok` short-circuits on `not near_hod` without ever inspecting the candle count. Confirmed
by two independent mutations, both leaving the entire 295-case suite green: forcing `near_hod =
True` unconditionally (activating the branch on every fixture, including ones meant to pass), and
narrowing the "candles since the dip low" window to exclude the trigger bar itself (an off-by-one
in the opposite direction). Neither the rule's correctness nor its enforceability was ever in
question here — nothing calls it, in the sense that matters for `tests/README.md`'s open-findings
convention: no test would notice if it silently stopped firing.

**Reproduced by execution and by the guarantee-test procedure** (`.claude/skills/guarantee-test`):
restated as an attack ("hod_proximity_min_candles is not checked when near HOD"), proved the attack
would succeed by both mutations above against the *unmodified* suite, then wrote a fixture that
fails under both.

**Disposition: fixed — a test added, not a rule changed.**
`test_hod_proximity_consolidation_binds_at_exactly_two_candles_since_the_dip_low` (`boundary`) adds
three cases sharing one series up to the trigger: far from HOD with one qualifying candle (passes,
because §2's row does not apply this far out — proving the `not near_hod` bypass is real rather
than dead by construction), and a near-HOD series held exactly on the `hod_proximity_pct` boundary
with one candle (fails) versus two (passes, matching `hod_proximity_min_candles`). Each of the two
mutations above is independently re-confirmed to redden this new test specifically. No code in
`setups.py` changed for this finding — the rule was already implemented correctly; it simply had
no witness.

### M7 — VWAP Reclaim's "prior HOD" was untested against a trigger bar that pierces the standing HOD — MEDIUM

**Claimed.** `evaluate_vwap_reclaim`'s own docstring: *"'Still below HOD' means below the **prior**
HOD. Criterion 6's alternative — HOD including the trigger bar's own high — lets a reclaim bar
satisfy the criterion with its own wick."* The distinction is deliberate and stated; `prior_hod =
session.hod_through(i - 1)` is the line that implements it.

**Found.** No fixture has a VWAP-Reclaim trigger bar whose own high exceeds the HOD every earlier
bar established — in `VWAP_RECLAIM_BARS` and every derived fixture, the trigger's wick stays well
under the $4.15 opening-bar HOD. Mutating the line to `session.hod_through(i)` (the documented
wrong alternative) is **not caught** by any existing test, including
`test_truncating_the_series_changes_no_outcome` — which is structurally blind to this exact class
of bug: it compares the full series against `session.through(i)`, and both already include bar
`i`, so a function that should have read `i - 1` and instead reads `i` looks identical under
truncation. The same mutation applied to `evaluate_hod_breakout`'s analogous line **is** caught
immediately (7 failures), because a HOD-breakout trigger bar's high exceeds the prior HOD by
construction of that setup — confirming the gap is specific to VWAP Reclaim's fixture set, not a
property of the mutation being untestable in general.

**Reproduced by execution**, including the contrast case: applying `hod_through(i - 1) →
hod_through(i)` at `setups.py`'s VWAP-Reclaim call site changed nothing in the 295-case suite;
applying the identical substitution at the HOD-Breakout call site broke 7 tests immediately.

**Disposition: fixed — a test added, not a rule changed.**
`test_still_below_hod_and_its_proximity_read_the_prior_hod_not_the_trigger_bars_own_wick`
(`boundary`) constructs a trigger bar whose wick ($4.10) exceeds a $4.00 established HOD while its
close ($4.05) sits between the two — the one relationship where raising the ceiling from the prior
HOD to the trigger's own high changes the verdict (raising it can only ever make "still below it"
*easier*, never harder, so any fixture with entry unambiguously below both readings, which is every
other fixture in the file, cannot distinguish them). Confirmed to redden under the mutation above.

---

## 6. What is genuinely good

- **Every number in [PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md) that this round could check by
  execution — rather than by reading — checked out.** The worked examples, the look-ahead
  property, the registry counts, `python -m tradipy setups` printing L2's rejection banner
  verbatim: none of it needed correction. The document's *prose about its own prose* (§6's count)
  is where the miss was, which is a narrower failure mode than round 12 itself had reason to
  expect from a same-sitting review.
- **The import-allowlist test caught the obvious autofix.** Running `ruff check --fix`'s suggested
  `itertools.pairwise` replacement for `session.py`'s `RUF007` immediately reddened
  `test_the_setup_layer_reads_nothing_and_imports_nothing_that_could[session.py]` — the mechanism
  built to hold this module to a stdlib-only, no-feed import surface caught a lint tool trying to
  widen it, on the first attempt, with no special-casing needed.
- **Every rule M6 and M7 found under-tested was already implemented correctly.** Neither finding
  required a code change to `setups.py`'s logic — both were closed by writing the fixture that had
  been missing, and both new fixtures pass against the unmodified rule and fail under the
  documented wrong alternative. The gap was in what the suite could see, not in what the setup
  layer does.
- **The guarantee-test procedure caught what a reading could not.** M6 and M7 are exactly
  `.claude/skills/guarantee-test`'s target case — a docstring stating a guarantee with a passing
  suite beside it — and both were found by mutating the *unmodified* suite first, before any new
  test existed, which is the step that distinguishes a real gap from a hunch.
- **`test_truncating_the_series_changes_no_outcome`'s blind spot is now named rather than assumed
  away.** It is a genuine and valuable property test, and M7 does not weaken that; it identifies
  the one class of bug (reading bar `i` where `i - 1` was intended) that a truncation-based
  look-ahead test cannot see by construction, which is worth knowing the next time a similar
  off-by-one is being hunted with that test as the only net.

---

## 7. The risk this findings list does not capture

Round 12 named it and it is unchanged: **Phase 4 produces something that prints like a trade
instruction, on simulated data, on a ladder whose next rung is unwritten**, and every safeguard
against that confusion is a sentence rather than a test. This round's own experience with M1 is a
small instance of the same shape at the documentation layer — a bus diagram that looks precise and
is not, sitting one file away from a document that already explained why that style fails here.
The pattern generalizes: **a thing that looks like it has been checked and a thing that has been
checked are not the same object, and the gap between them is exactly where every defect class in
this project's history has been found.** Fixing this round's two documentation slips does not
retire that risk; it is one more data point for it.

---

## 8. Next steps

**Now**

1. Re-measure `docs/PLAN.md`'s Workstream 11 registry-check row (line 170) against this round's
   `ruff` result — it currently only names the pre-Phase-4 gap, and this round's fix should be
   folded into that sentence the next time it is touched, rather than left implicit in this file.
2. L2 is still the only open finding with a behaviour consequence. Unchanged from round 12.
3. M6 and M7 are closed by this round's own two new tests; no residual action. Worth flagging for
   whoever next runs coverage or mutation testing against Phase 4 (still outstanding from v0.1.0,
   per round 12 and the appendix here): both were found by hand-picked, targeted mutation of two
   specific lines this round chose to look at, not by a tool sweeping the file, so a real
   mutation-testing run against `setups.py` should be expected to surface more than these two.

**Raise as spec questions** — unchanged from round 12; all nineteen remain in `docs/CHANGELOG.md`.

**After the spike / after D31** — unchanged from round 12 (L3's shared Q-module guard, L4's
doc-count check sourced from `PROVENANCE.txt`).

---

## Appendix: how this review was verified

**What was run, directly, on the project's pinned toolchain** (`uv run`, no substitute
interpreter, no hand-built stand-in for any tool):

| Gate | Result |
|---|---|
| `ruff check .` | Red (5 errors) before this round's fixes; clean after |
| `ruff format --check` (repo-wide) | 6 files unformatted before; 4 of them (Phase 4's) fixed, 2 (`docs/PRD.md`, `docs/reviews/REVIEW-2026-07-28.md`) left as pre-existing and out of scope, confirmed by an empty `git diff --stat HEAD` against both |
| `pytest -q` | 295 cases green before M6/M7's fixtures were added; 237 test functions / all cases green after (`test_hod_proximity_consolidation_binds_at_exactly_two_candles_since_the_dip_low` and `test_still_below_hod_and_its_proximity_read_the_prior_hod_not_the_trigger_bars_own_wick`) |
| `basedpyright` | 0 errors, 0 warnings, before and after |
| `scripts/check_links.py` | 291/291 before, 292/292 after (one new cross-reference added by M1's fix) |
| `python -m tradipy demo` | exit 0, 3/3 accepted, self-check OK |
| `python -m tradipy setups` | exit 0, self-check OK including §3.4's printed rejection |

**Counts re-derived, not inherited:** 75 registry rows (`grep -c '^\s*_p("' src/tradipy/params.py`);
74 baseline entries (`json.load`); 235 test functions before this round's own two additions, 237
after (`grep -c '^def test_' tests/test_*.py`, summed); 19 spec-question rows and their 4/15 split
(counted against `docs/CHANGELOG.md`'s table by line number, independent of any document's own
claim about the count).

**Fresh-eyes sub-agent.** A separate agent, given no prior context on this review, was asked to
adversarially read `session.py` and `setups.py` line by line for off-by-one, look-ahead and
boundary defects, to run the test suite, and to attempt targeted mutations in the areas it found
most suspicious to check whether the suite would actually catch a regression there. It reported
five findings (M3–M7 above) and a list of specific checks that turned up nothing, plus nine
mutation results. Every one of the five findings was independently re-derived from source by this
document's author before being accepted — the equivalences behind M3–M5 were re-proven from
`Session`'s and `required_room`'s actual definitions rather than taken on the sub-agent's
arithmetic, and M6/M7's mutations were independently reapplied and rerun (both against standalone
scripts and against the actual test file) rather than trusted from the sub-agent's transcript;
every one reproduced exactly as reported. Its "checked, no problem found" list (`_run_ending_before`
boundaries, `nearest_resistance`'s tie handling, `ema_at` seeding, and others) was **not**
independently re-verified by this document's author — it is reported by the sub-agent alone and
carries whatever confidence that agent's own methodology warrants, not this round's.

**What this round could not do.** It did not re-run coverage or mutation-testing tools (both still
date from v0.1.0 per round 12) — M6/M7 were found by hand-driven, targeted mutation against
specific lines this round chose to attack, not by a mutation-testing tool sweeping the file, so a
tool run would very plausibly find more than these two. It did not re-derive L2's three candidate
resolutions or pick one — that is explicitly a decision, not a finding. It is **not a cold read of
the whole codebase**: it inherited round 12's list of where to look (the two new modules, the new
document, the registry diff) rather than re-surveying the repository from nothing; §21.1's full
"Workstream 11 cold read" that both round 12 and [PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md) call the
most valuable remaining item is still not this — and M6 in particular is a small, concrete instance
of exactly the gap that cold read exists to close.

**Error rate.** This document's own draft was checked once against its cited line numbers, counts
and file paths before being finalized (the diagram-column mapping in M1, the semicolon count in
M2, and the 75/74/235/19 figures in §4/appendix were each independently re-counted at least once
after the first draft). M6 and M7's mutations were each re-run a second time, against the actual
file, immediately before this document's finalization, after an earlier revert-and-reapply cycle
during their construction was found (by that re-run) to have silently undone the M3–M5 fixes —
`git checkout -- <file>` restores from the index, not from a clean-tree assumption, which cost one
extra round-trip through `ruff format` and the full suite to catch. No second, fully independent
adversarial pass was run against this draft the way round 12's own two-pass process was — recorded
as a limitation of this round's process, not as a claim that none would be found.
