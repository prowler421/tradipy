# Review round 12 — Phase 4, and the verification of rounds 9 and 10

> **Scope, in two halves, kept separate on purpose.**
>
> 1. **Verification** of round 9 (`J*`) and round 10 (`K*`) at commit **`4e90d60`**, working tree
>    clean, nothing of this round's own work in it. Round 10's first draft was derived from a
>    working tree that silently included round 9's uncommitted edits and had to be re-derived from
>    `git archive`; that is why this boundary is stated before anything else.
> 2. **Review of Phase 4**, which this round also *built* — `src/tradipy/session.py`,
>    `src/tradipy/setups.py`, twenty registry rows, `python -m tradipy setups`,
>    `tests/test_setups.py`, PLAN **D33**, [PHASE-4-DESIGN.md](../PHASE-4-DESIGN.md). **A round
>    reviewing its own construction is not an independent review of it**, and nothing below should
>    be read as one. What it can honestly claim is stated in §2; what it cannot is stated twice.
>
> **Findings prefix `L`.** `K` was round 10. Round 11 wrote no review file: it is the
> `make check` run recorded in [PHASE-3-READINESS.md](../PHASE-3-READINESS.md)'s first-row note
> — *"Review round 11 ran it: **red**"* — eleven `ruff` errors and three `basedpyright` errors
> introduced by Phase 3, all fixed there, none of them prefixed. So `L` is this round's and the
> gap in the file series is real rather than a slip.
>
> **`make check` was not run in full.** `ruff check` and `ruff format --check` could not be run at
> all. See the appendix, and read every claim below in that light.

---

## 1. Verdict

**Rounds 9 and 10 hold, with one partial closure and one fix that was re-broken in the same
sentence it was fixed in.** J1, J2, K1, K2, K4, K5 and K7 are where their dispositions say they
are; K3's guard exists and is tested but closes only the *empty*-file half of what round 10
described; K6's third row — a test count in `docs/PLAN.md` — was corrected by round 10 and was
wrong again one commit later, which is **L1** and the fourth appearance of that shape.

**Phase 4 is built and it found a defect in the PRD that no previous round could have.** Applying
§3.1.1's resistance set as that section enumerates it, **§3.4's worked example is rejected by its
own room gate** — the next whole dollar ($4.00) is nearer than the HOD ($4.15) its table names, and
$0.17 above entry against a required $0.28. Every other line of the table reproduces exactly from a
bar series. That is **L2**, it is the v1.3 joint-incoherence class, and §5.2 explains why the
boundary fixtures built for that class were pointed away from it.

**The Phase 3 gate verdict (D29) is unchanged: not ready.** Nothing here measures anything.

| Area | State |
|---|---|
| Round 9 (`J1`, `J2`) | **Both hold.** J2's guarantee test is non-vacuous — mutation reddens exactly one case |
| Round 10 (`K1`–`K7`) | **K1, K4, K5 hold; K2 and K7 remain open as raised; K3 partially closed; K6 2 of 3** |
| `src/tradipy/` history | Zero-line diff from round 7 (`3545adf`) through round 10, which rounds 8, 9 and 10 each reported. **Phase 3 then changed it** at `184732f` — 7 files, +1,027/−65, including a new 551-line `scanner.py` — in round 11's interval. Phase 4 changes it again |
| Phase 4 construction | §3.2, §3.3, §3.4, §20.11 and §3's post-entry rules built; **two** of the three worked examples reproduce from bars exactly and the third to the room gate (L2); 295 cases green |
| Phase 4 calibration | **Not gated open and not claimed.** All twenty new registry rows have code-originated bounds, because no section that states them has a Bounds column |
| `make check` | **Not verified.** `pytest` (via a stand-in interpreter), `basedpyright` and `links` are green; `ruff` could not be run |
| New defect class | **No.** L2 is a new *population* of the third class; the argument against promoting it is in §5.2 |

---

## 2. What building Phase 4 does and does not establish

It establishes that §3.2, §3.3 and §3.4 are **executable as written**, which was not previously
known, and that two of the three worked examples reproduce end to end from a bar series — entry,
stop, R, T1, T2, share count, and every intermediate the tables state. That is PRD §21.1's
worked-example row met from the side it names (*"input **bar series**"*), and the older fixtures
could not do it because they are handed the very inputs the rules derive.

It does **not** establish that any threshold is right. All twenty registry rows Phase 4 adds are
marked `(bounds: code)`: eighteen cite §3.2, §3.3 or §3.4 — sections with no parameter table and no
Bounds column — and the other two cite §20.1 and §20.5, which have no Bounds column either. So no
range among them is spec; every one is this code's judgement. It does not resolve any of the nineteen spec questions
[CHANGELOG.md](../CHANGELOG.md) now records against §3, and it does not move the data ladder.

And it is not an independent review of itself. The Workstream 11 cold read is now more valuable
than before this round, not less: there are two new modules, 39 new test functions and 50 new
cases whose only reader has been their author.

---

## 3. Where we stand against the PLAN

| PLAN item | Claim | Found |
|---|---|---|
| Phase 2a — instrumentation complete, measured gate not passed | — | **Accurate.** Q1–Q4 exercise on simulated input; no measurement. `PERMITTED_ORIGINS == {SIMULATED}`, test-pinned |
| Phase 3 — built, not calibrated (D32) | — | **Accurate.** `scanner.py` unchanged this round; §4.2 parsed against the code in both directions still green |
| Phase 4 — **new row** | Built on simulated bar series, not calibrated (D33) | Written this round; the row states the nineteen open questions and the §3.4 contradiction rather than only the build |
| §21.1 fixture suite — "193 test functions across eleven files" | — | **Wrong: 196 across eleven at `4e90d60`** (L1). Now 235 across twelve. The row's *"seventy-four functions added since v0.1.0"* was also wrong — v0.1.0 (`523d8d6`) has 117, so 79 had been added, and 118 have now |
| Registry check — "55 registered thresholds; 68-entry baseline" | — | Accurate at `4e90d60`; **75 and 74** after D33. The baseline grew by six because `2%` became a search key |
| *Registered* vs *enforced* gap — "9 of 55" | — | Accurate at `4e90d60`; now **7 of 75**, not 9. Every Phase 4 row has a reader *and* two pre-existing unread rows gained one — `max_vwap_extension_pct` (§3.3 criterion 6) and `hod_proximity_pct` (§3.4 criterion 9) — which is the gap closing by two without anything in the registry recording that it did, exactly as the PLAN predicted. `ema_period` has a reader whose own caller does not exist (`session.ema_at`), which is the same shape one level out and is recorded in `tests/README.md` |
| WS11 — "eight rounds done" in the sequencing row | — | **Two numbering schemes in one sentence** (L6): eight is the file count minus `PROMPT-REVIEW`, while the same row says *"still green at rounds 8–10"* in series numbering |
| Round 10's summary in WS11 — "twenty-five further errors… three fixes the draft claimed to have applied" | — | **Misstates its own appendix** (L5): the appendix says 24 first-pass, 15 second-pass, 39 total, and enumerates **seven** claims of work not done |

---

## 4. Where we stand against the PRD

**§20 tally.** Phase 4 adds §20.1 (the ordinal half), §20.2, §20.3, §20.5 and §20.6 to the
implemented set, and §20.11 rules 1–2. Implemented: §20.2, §20.3, §20.4, §20.5, §20.6, §20.10,
§20.11 (partial), §20.13, §20.14, and §20.1's counting and gap rules. Not implemented, each with a
reason recorded on the module: §20.1's close detection and grace (needs a feed), §20.7's RVOL
(received as a ratio), §20.8's equity snapshot (needs a broker), §20.9 corporate actions
(ingestion), §20.11 rules 3–4 (persistence and position state), §20.12 (Phase 5/6), §20.15 ATR (no
MVP criterion needs it).

**§21.1 rows.** The worked-example row moves from *partially met* to **met for §3.2 and §3.3** and
*met as far as the PRD is self-consistent* for §3.4: all three now start from bars, and §3.4 has no
share count to assert because it rejects. Calling that row simply "met" would be the pleasing
version — §21.1 asks for an asserted share count and one of the three does not produce one. The look-ahead row moves from *absent* to **met**: the property is asserted
for all three setups at every legal trigger index of every fixture. The replay-harness row is
partly addressed and should not be called met — there is no `datetime.now()` anywhere in `src/`
and `SessionBar` carries an `int` rather than a clock reading, but there is no harness and no
recorded session to replay.

**§3 fidelity.** Two of three worked examples reproduce exactly. The third reproduces exactly up to
the room gate and then disagrees with the PRD — L2. Nineteen places where §3 admits more than one
reading, or defines nothing at all, are recorded in [CHANGELOG.md](../CHANGELOG.md) with the reading
taken and the test pinning it. That count is not a measure of sloppiness in §3 so much as of what
§20 was never asked to cover: §20.4 defines flagpole geometry and *nothing else* about a pattern.

---

## 5. Findings

### L1 — `docs/PLAN.md` understated its own test count, one commit after round 10 corrected it — MEDIUM

**Claimed.** PLAN's §21.1 fixture-suite row: *"**193 test functions** across eleven files, counted
with `grep -c '^def test_' tests/test_*.py`"*.

**Found.** That exact command returns **196** at `4e90d60`. The same sentence's *"seventy-four
functions added since [v0.1.0]"* is also wrong: v0.1.0 (`523d8d6`) carries 117 functions across six
files, so 79 had been added. Its third figure — *"156 across ten recorded before Phase 3"* — is
correct at `e85a193`.

**Reproduced by execution**, twice: the cited `grep` at `4e90d60`, and the same command against
`git archive 523d8d6` unpacked to a temporary directory.

**Why it is a finding and not a typo.** This is the sentence round 10's **K6** corrected. It went
wrong again in the commit that added the tests it counts — the count was written by the party
adding them, in the same changeset, which is the mechanism of I1, J1, K1 and K6 before it. Fourth
occurrence of one shape, and the first to recur *inside a fix for itself*.

**Disposition: fixed** in this change, with the count now naming twelve files, 235 functions, and
the 117 the coverage and mutation figures were actually measured against. Also recorded in the root
`CHANGELOG.md`. **Not** merely fixed as trivial: convention 8's own test is whether a finding
recurs, and this one has, four times.

### L2 — §3.4's worked example fails §3.1.1's room gate — HIGH (spec question)

**Claimed.** §3.4's worked-example table has a row whose Derivation cell reads *"nearest overhead
resistance"* against the value **$4.15** — the HOD — and a Room-test row reading
*"(4.15 − 3.83) = $0.32 ≥ $0.28"* with the value *"**PASS** ✓"*. The PRD calls this example
*"the reason §3.1.2 exists."*

**Found.** §3.1.1 defines the gate's input as *"the **nearest** overhead level above entry among
{HOD, next whole dollar, prior leg high, measured-move projection}"*. At the example's $3.83 entry
the next whole dollar is **$4.00** — in §3.1.1's own set, above entry, and nearer than the HOD.
The gap is **$0.17** against a required room of **$0.28**, so the example is **rejected** with
`TARGETS_TOO_CLOSE`.

**Reproduced by execution.** `python -m tradipy setups` prints the rejection, from a bar series
constructed to the table: VWAP $3.80 exactly, 18 bars above VWAP, a 4-bar dip to $3.74, depth
1.58%, stop $3.73, R $0.10, T1 $4.03, T2 $4.15, T2−T1 $0.12 — every one of those matches and only
the resistance does not. The intermediate steps of §20.13's stop chain (`$3.762 → $3.76 → $3.75`)
are **not** printed; they are asserted as inequalities in
`test_the_vwap_reclaim_band_is_a_maximum_and_never_widens_the_stop`.

**Three things make it more than a table correction.**

1. **§3.2's example applies the whole-dollar candidate explicitly** (*"measured move $5.51 (below
   next whole dollar $6.00)"*) and §3.3's uses it as *the* resistance ($7.00). Only §3.4 omits it,
   and under §3.1.1's set neither of those two changes verdict — checked, because a rule that
   rejected all three would be a different finding.
   **The evidence against reading this as an oversight, stated because it is the only evidence
   there is:** §3.4 criterion 7 is worded *"Room gate: **HOD (or nearest resistance)** ≥
   `required_room`"*, where §3.2 criterion 8 and §3.3 criterion 7 both say *"nearest overhead
   resistance"*. That parenthetical is the one textual hook for a per-setup candidate set, and it
   is why the third candidate resolution in [CHANGELOG.md](../CHANGELOG.md) exists. It is also not
   a definition, it names no set, and §20 — which governs — adds `PMH` to §3.1.1's enumeration
   without scoping it per setup. Hence HIGH and *raised*, not HIGH and *decided*.
2. **§3.4's sensitivity table is undermined as well.** Its three rows — HOD $4.05, $4.09, $4.15 —
   conclude that only the cost-denominated floor rejects a collapsed ladder. Under §3.1.1's set all
   three reject on the $4.00 level, which is a different reason and a different lesson.
3. **The consequence is material.** Requiring `required_room` of clear space below the next whole
   dollar rejects a large share of VWAP Reclaim setups on a $1–$20 universe. §3.1.3's own note says
   the correct response to a high rejection rate is to conclude the strategy cannot be traded on
   those names rather than to widen the gate — but nobody has measured this one.

**Disposition: raised, not resolved.** [CHANGELOG.md](../CHANGELOG.md) carries it with three
candidate resolutions; `tests/test_setups.py` pins **both** directions — the rejection, and that
the same trade passes against the level §3.4 names — so either resolution breaks one half
deliberately. `nearest_resistance` is one function and the omitted *"prior leg high"* is documented
on it.

### 5.2 Why the check built for this defect class did not catch it

L2 is the **v1.3 class**: two individually-defensible sections that cannot both hold. The check
built for that class is the boundary fixture — *"recompute every §3 worked example at the widest
spread its own §3.1.3 caps admit"* — and it has been green throughout, because it varies the
**parameters** an example admits and holds the example's **inputs** fixed. `resistance` is an input
in `poc.Candidate` and in every fixture that consumes it: `$4.15`, transcribed from the table it is
checking.

So the generalizable heuristic, and it is cheap:

> **For every value a worked example states as an input, ask whether some other section *derives*
> it.** If it does, the example is asserting a number the rules compute, and the two can disagree
> without any check noticing — because every fixture downstream inherits the assertion as a given.

**This is not a seventh defect class, and the temptation to call it one is worth naming.** It is the
third class reached through a new population: the *inputs* of the examples rather than the
*parameters* of the gates. The mitigation is not a new kind of check either — it is the one D33
already took, which is to compute the input instead of accepting it. What is true, and is the
strongest available argument for D33's build-rather-than-design choice, is that **no amount of
reading would have found this.** A design document reproduces the table; only executing §3.1.1
against §3.4 makes the two numbers collide.

### L3 — K3's guard closes the empty case and not the partial one — MEDIUM-HIGH

**Claimed.** Root `CHANGELOG.md`: *"`q1_vendors.report()` asserted a §7 Q1 negative from zero
vendor trials (review round 10, K3)"* — fixed, with a guard and a test.

**Found.** The guard exists at `scripts/spike2a/q1_vendors.py:113-133` and its test at
`tests/test_enforcement.py:1021-1052`; deleting the guard reddens exactly one case, so it is not
vacuous. But the guard is `if not trials`, and round 10's finding had an aggravating half about
*partially* unparsable input. On a measured-origin file with one parsable failing row and three
unparsable ones, `report()` still prints `§7 verdict: no provider passes Q1` and `Implication per
§6: PRD §4 is rewritten` — the largest consequence the spike can produce — while `main()` prints
`3 unparsable row(s) skipped` **after** the report. `feeds.py:140-143` already argues that an
unparsed *share* is the reportable figure; `q1_vendors` does not.

**Reproduced by execution** on a constructed vendor file at HEAD.

**Disposition: left open, and re-raised.** It is in `scripts/spike2a/`, which D30 currently
prevents from being fed anything measured at all, so the failure is unreachable until D31. Fixing
it is one line and the *right* fix is the shared helper round 10 asked for and did not get — all
four Q-modules now hand-write this guard. That is a decision about the spike's shape rather than a
one-line correction, so it is not fixed here.

### L4 — the two documents that produced eight wrong statements are outside the only mechanical doc check — MEDIUM

**Found.** `tests/test_documentation.py`'s `CHECKED_DOCS` (lines 44–55) lists eleven files.
`docs/PHASE-2A-REPORT.md` and `docs/PHASE-3-READINESS.md` are not among them. Those are precisely
the two files round 10 found eight wrong statements in, and K1 — a report quoting the previous
commit's numbers under the word *"Regenerated"* — was one of them. Round 10's own next-step 2 asked
for a doc-count test over the report's pipeline table; it was not built.

**Read, not executed** — this is a list, and the finding is what is absent from it.

**Disposition: left open, deliberately — and one part of it is this round's own doing.**
`docs/PHASE-4-DESIGN.md`, written here, states a registry count and a module count and is *also*
absent from `CHECKED_DOCS`; for that file adding the line would not be a false close, and it is
recorded as owed. For the other two, adding them to `CHECKED_DOCS` is one line and it would be a
*false* close: the patterns in that file match parameter counts, baseline sizes and
module counts, none of which those two documents state. What they state is *measured* figures — 157
signal bars, 0.64% — which the generator already writes into `PROVENANCE.txt` and which nothing
compares. That is a new pattern rather than a new entry in a list, and the honest version needs the
generator's own output as its source of truth. Recorded here rather than half-done.

### L5 — PLAN's summary of round 10 misstates round 10's own appendix — LOW-MEDIUM

**Found.** `docs/PLAN.md`'s Workstream 11 entry and its sequencing row both say the round-10
fact-check *"found **twenty-five** further errors, including **three** fixes the draft claimed to
have applied and had not."* That review's appendix records **24** first-pass errors, **15** on the
second pass, **39** total, and enumerates **seven** claims of work not actually done.

**Read, not executed.** Both numbers are in documents, and round 10 wrote both the summary and the
appendix.

**Disposition: fixed** in this change — the summary now quotes the appendix's own figures. Trivial
by convention 8: one line, no spec implication, no behaviour. Worth one sentence anyway, because a
review's error rate is *evidence about the method*, and a summary that understates it makes the
next round trust the round more than it should.

### L6 — one sentence, two numbering schemes — LOW

`docs/PLAN.md`'s sequencing row says *"**In progress** — eight rounds done"* and, in the same cell,
*"still green at rounds 8–10"*. The first is the file count in `docs/reviews/` minus
`PROMPT-REVIEW.md`; the second is the series numbering. They cannot both be read without knowing
which convention each uses — and round 11 (no file, recorded only in
[PHASE-3-READINESS.md](../PHASE-3-READINESS.md)) makes the two diverge permanently.

**Disposition: fixed** — the row now states the series count and names round 11's location. Trivial.

### L7 — an interpreter caveat that can now be retired — LOW

`docs/PHASE-2A-REPORT.md` carries a caveat that its regenerated figures may be an artefact of the
interpreter they were produced on. Running the generator at `b70fa7a` on this round's CPython
3.10 reproduces round 8's 3.13-measured figures **exactly** — 156 symbol-sessions, 147 signal bars,
8,820 NBBO samples, 1.36% aggregate, 14.29% worst decile — so the 157/3,566/0.64%/6.67% figures at
`e85a193` are a *generator* change and not an interpreter one.

**Reproduced by execution** at three commits on one interpreter.

**Disposition: left to the report's owner.** Retiring a caveat is a claim about reproducibility
across two interpreters, and this round has run only one of them.

### L8 — registering a threshold can turn an unrelated file red, and the wrong fix is inviting — LOW

**Found while doing it.** Adding `min_bars_above_vwap` (15 bars) and `ema_period` (9) widened the
registry lint's search set, and two pre-existing literals became offenders without either value
moving: a simulated VIX level of `Decimal("15")` in `scripts/spike2a/synthetic_data_generator.py`
(index points) and `rvol=D("9")` in `poc.simulated_universe`.

**Reproduced by execution** — the lint named both, which is the check working.

**Why it is worth a finding.** The obvious fix is to add 9 and 15 to `_UNDISTINCTIVE`, which would
exempt the two *new parameters* from the code lint everywhere — the exact shape of the blind spot
that left seven parameters unenforced until v0.1.0. The second obvious fix, `Decimal(15)` with an
integer argument, passes the lint by leaving its stated scope.

**Disposition: fixed, narrowly.** The generator's baseline is now `_VIX_BASELINE`, read at both use
sites (it had two copies), and `EXEMPT_ASSIGNMENTS` covers the **definition line only** — the same
treatment `TICK_SIZE` has for its 1% collision. The poc fixture's `rvol` moved 9 → 8, since it is
an arbitrary simulated input; SYNC's score moves 0.5000 → 0.4850 and no document quoted it.

---

## 6. What is genuinely good

- **The registry made Phase 4 cheap in the one way that matters.** Twenty new thresholds, and not
  one appears as a literal outside `params.py`; no rounding direction is named at any call site;
  `setups.py` joined the polarity check because a *derived* list of rounding modules noticed it. The
  mechanism built for the v1.2 and v1.3.1 classes absorbed a new phase without being touched.
- **`bars.select_flagpole`'s caller-supplied predicate was the right call, and it is now visible
  why.** It was built with no caller and recorded as such rather than being given invented
  thresholds. Phase 4 supplied §3.2 criterion 2 as that predicate without changing `bars.py` at all.
- **Two of three §3 worked examples reproduce exactly from bars**, and three figures that were
  printed by nothing and asserted by nothing are now asserted from the bars: §3.2's 7.29% combined
  move, its 28.57% retrace, and §3.3's 2.53% VWAP extension. The 0.55 volume ratio was already
  pinned before this round (`test_computations.py`), so it is not among them.
- **J2's and K3's guarantee tests are each the sole test of their branch**, which is what round 10
  claimed and what mutation confirms in both directions: mutating either leaves the other green.
- **`docs/PHASE-3-READINESS.md`'s first-row note is the best paragraph in the repository.** A
  readiness document that says *"this row read Met and the evidence was asserted by a party that had
  not run the gate"* is the fifth defect class caught in a document's own evidence column.

---

## 7. The risk the findings list does not capture

**Phase 4 makes the uncalibrated surface much larger, and the documents that say so are the same
documents that say Phase 4 is done.**

Before this round, every threshold in the system was calibrated against three hand-authored worked
examples, and PLAN said so plainly: *"data is the binding constraint."* After it, there are twenty
more thresholds, every one with bounds this code invented, and nineteen readings of §3 that are
executable rather than agreed. The suite proves they are applied *consistently*. Nothing anywhere
suggests any of them is *right* — and Phase 4's output is a **signal**, which is a much shorter
distance from an order than a scanner row is.

The specific way this goes wrong is not a defect in any of it. It is that `python -m tradipy setups`
prints `ACCEPT`, `shares 2,500`, `direction LONG` in a form that looks exactly like a trade
instruction, from a bar series constructed to a document's example, on the `SIMULATED` rung of a
ladder whose next rung is unwritten. Every safeguard against that is a *sentence* — the banner the
command prints, the design document, D33's cost paragraph — where D30's protections for the data
path are *tests*. The provenance gate constrains what may be read; nothing constrains what a signal
object may be mistaken for.

The second-order version, and the reason L2 belongs in this section as well as in §5: the §3.4
example has been quoted as a passing trade in the PRD, in the PLAN, in three review rounds and in
this repository's own demo output since v1.1. It took executing the rule to notice, and the rule was
sitting one section above the example the whole time.

---

## 8. Next steps

**Now**

1. **Run `make check` on a machine with the real toolchain**, and record the result in
   `docs/PHASE-3-READINESS.md`'s first row as an observation rather than an expectation. `ruff` has
   not been run against `session.py`, `setups.py`, `test_setups.py` or the Phase 4 enforcement block
   by anyone.
2. Re-measure coverage and mutation. Both figures date from v0.1.0, where the suite had 117
   functions; it now has 235, and the 118 added since include every §4.2 filter and all three §3
   setups.
3. Decide L2. It is the only finding here with a behaviour consequence, and all three candidate
   resolutions change which trades the system takes.

**Raise as spec questions** (all already in [CHANGELOG.md](../CHANGELOG.md))

4. The nineteen §3 readings — the flag's terminator, the bailout's three spellings, T3's two
   definitions, the conviction gate's status, and the rest. Four of them would change behaviour if
   settled the other way.
5. K2 and K7, unchanged from round 10.

**After the spike / after D31**

6. L3's shared guard across the four Q-modules, and L4's doc-count check sourced from
   `PROVENANCE.txt` rather than from a pattern list.
7. **The Workstream 11 cold read**, which is now the single most valuable open item by a wider
   margin than before: two new modules, 39 new test functions, and one author.

---

## Appendix: how this review was verified

**Commits.** Verification half at `4e90d60` (tree clean). Older commits read via
`git archive <sha> | tar -x` into temporary directories; the working tree was never checked out to
another commit. Phase 4's own code is **uncommitted working-tree state** at the time of writing,
and is reviewed as such.

**What was run.**

| Gate | Result | How |
|---|---|---|
| `pytest` | **295 cases green** (235 functions, twelve files) | Not the project's interpreter — see below |
| `basedpyright` 1.39.9 | **0 errors, 0 warnings** | Its bundled `dist/pyright.js` under system Node 22, with a config replicating `[tool.basedpyright]` (`pythonVersion` 3.13, `standard` mode, same include/exclude) |
| `scripts/check_links.py` | **all 291 relative links resolve** | Directly |
| `python -m tradipy demo` | exit 0, 3/3 examples accepted, self-check OK | Directly |
| `python -m tradipy scan` | exit 0 | Directly |
| `python -m tradipy setups` | exit 0, self-check OK **including §3.4's rejection** | Directly |
| **`ruff check`** | **NOT RUN** | No linux binary available; PyPI and npm both blocked from this environment |
| **`ruff format --check`** | **NOT RUN** | Same |
| Coverage | NOT RUN | — |
| Mutation testing | NOT RUN | — |

**The interpreter is not the project's.** `uv sync` cannot fetch CPython 3.13 here, so the suite ran
on CPython **3.10.12** with two compatibility shims — a minimal `exceptiongroup` stand-in (pytest 9
imports `BaseExceptionGroup` from it below 3.11) and `datetime.UTC` aliased to `timezone.utc` — and
with a `pytest.ini` replicating `[tool.pytest.ini_options]`, because pytest cannot parse
`pyproject.toml` without `tomli` on 3.10. The shims are in a temporary directory and touch no
repository file. **What this means:** the suite's *logic* is verified and the target interpreter is
not. Anything 3.13-specific — and `Decimal` behaviour is not, but exception grouping and
`datetime.UTC` are exactly what was shimmed — is unverified.

**No substitute was built for `ruff`, and that is deliberate.** Round 7 could not run it either,
hand-built an AST check for the four rules it already suspected, and reported the result beside
genuine executions; a real `ruff` run afterwards found seven `B007`s and a formatting failure in the
same file. The lesson recorded in PLAN's sixth-class section is that *a general substitute can find
what you were not looking for and a specific one cannot*, so no specific one is offered here. The
formatting of the new code follows the project's configuration by hand — 100-column lines, double
quotes, magic trailing commas — and that is a claim about care, not a verification.

**Not a cold read.** The seventh round performed with the repository in context, and the first
performed by the party that wrote the code under review. Both facts weaken §2 and neither is
mitigable from inside this round.

**Reproduction detail for the findings.** L1: the cited `grep` at two commits. L2: `python -m tradipy
setups`, plus `gates.check_room` called directly with §3.4's own $4.15 to show that branch passes.
L3: a constructed vendor file with one parsable and three unparsable rows, at HEAD. L7: the
generator run at `b70fa7a`, `e85a193` and HEAD on one interpreter. L8: the registry lint's own
output. L4, L5, L6: read, not executed, and each says so.

**Error rate of this review's own drafts — 47 errors over two adversarial passes.** Recorded
because a round that hides its own error rate makes the next one trust it more than it should, and
because round 10's second pass found fifteen further errors, **ten of them created by its own first
correction pass** — which is the specific risk the second pass here was pointed at.

| Pass | Errors | Notable |
|---|---|---|
| First | **30** (26 factual, 4 over-claims) | A false *"zero-line diff since round 7"* — Phase 3 changed `src/tradipy/` at `184732f`, which three earlier rounds' claim had made easy to repeat. A spec-question count of "twelve" against a table of nineteen. `docs/PLAN.md`'s two new rows separated from their tables by a blank line, so **D33 would not have rendered inside the decision log at all**. A `polarity`-marked fixture that was a tautology. A `boundary` row claiming all twenty new thresholds were tested at their limits where eight are |
| Second, over the corrections | **17**, of which **7 were created by the first correction pass** | The worst was the replacement dependency diagram: a bus-style ASCII graph whose junctions implied six imports that do not exist, under a caption asserting a left-to-right invariant the drawing did not honour. It is now a table, because a table cannot be geometrically wrong. Also `235 − 117 = 117`, written while correcting the arithmetic beside it; a *"third time"* that was the second; and an enumeration of "the other fifteen" listing fourteen |
| Substantive, not cosmetic | 2 of the 47 | **"9 of 75"** for the registered-versus-enforced gap was wrong in three documents: it is **7 of 75**, because Phase 4 gave `max_vwap_extension_pct` and `hod_proximity_pct` their first readers as well. And the §3.4 band's `polarity` fixture did not fail under a `ceil_to_tick` mutation — the $0.10 stop floor masked the direction on §3.4's own numbers. It is rebuilt on a case where the floor is inert, and the mutation now reddens exactly that one test |

Two of the second pass's findings were **test weaknesses rather than prose errors**, which is the
more useful half: a fixture asserting a constant identity it never used, and two assertions entailed
by a third and therefore looking like independent checks. Both are gone. The pattern across the two
passes is that the corrections were most dangerous where they were most confident — the diagram, the
counts recomputed by hand, and the sentence claiming a check was thorough.
