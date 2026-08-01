# Review round 15 — the Phase 6 build, and the first measurement of the gate in three phases

> **Scope.** Phase 6 (PLAN **D35**): `src/tradipy/daily.py`, `src/tradipy/monitor.py`,
> `tests/test_phase6.py`, the §7/§10/§20.8/§20.12-flatten block appended to
> `tests/test_enforcement.py`, the diffs to `params.py`, `risk.py`, `rejects.py` and `__main__.py`,
> the `monitor` CLI command, and [PHASE-6-DESIGN.md](../PHASE-6-DESIGN.md).
>
> **Findings prefix `N`.** `H` was rounds 7 and 14, `M` round 13, `L` round 12.
>
> **What kind of round this is, and it is a kind the series has not had for three phases: this
> round has a working toolchain.** It ran `make check` on both sides of the changeset. Rounds 12
> and 14 could not run it at all; round 13 could and found it red; rounds 5–11 predate the
> relevant code. That single capability is what produced the only finding here that is not
> convention 8's category.
>
> This round is **not** the §21.1 / Workstream 11 cold read of the whole codebase by a reader with
> no prior context. That item is still outstanding, as it has been across all six defect classes.

---

## Verdict

Phase 6 is **well scoped and correctly built for what D35 claims.** Every load-bearing claim in
[PHASE-6-DESIGN.md](../PHASE-6-DESIGN.md) that this round checked was verified **by execution**
rather than by reading, and all of them hold. The two findings the phase surfaces are real,
reproduced, and pinned by tests that fail if the underlying gap ever closes — which is a rare
property in a design document and the main reason this verdict is what it is.

The one finding of substance is not in the code. **The changeset makes `make check` worse**, and
`make check` was already red before it.

| Area | Assessment |
|---|---|
| Gate posture (D35) | Clear; the §12.1 dependency really is met, and the doc argues only the §18.7 half |
| Module boundaries | Clean one-way graph; `poc` untouched; `daily`/`monitor` reuse rather than restate |
| PRD transcription | Verified row by row against §7; the row 2 / row 7 wording difference is transcribed, not smoothed |
| Registry discipline | 2 new rows, both `(bounds: code)`; one new coupling; baseline byte-identical |
| Test depth | 409 pass; the enforcement block performs the violations it claims |
| **`make check`** | **Red — 15 ruff, 9 unformatted files, 10 basedpyright. This change added 10 / 2 / 8** |

---

## Verified by execution, not by reading

Listed because the distinction is this round's whole contribution, and because
[REVIEW-2026-07-30](REVIEW-2026-07-30.md) established that a round reporting a hand-built
substitute beside a real execution is how the sixth defect class claimed its second victim.

1. **`RiskBlock` reachability.** All twelve members are reachable and `ACTION_FOR` is total over
   the enum — run, not read. This is the largest single thing Phase 6 buys and it is true.
2. **The CLI.** `demo`, `scan`, `setups`, `risk` and `monitor` all exit 0 and their self-checks
   pass. (`evaluate` exits 2 without `--entry/--stop/--resistance`, which is argparse's documented
   usage code and unrelated to this change.)
3. **The suite.** 409 cases, 0 failures.
4. **The test-count arithmetic in PLAN.md.** It claims 339 total and 294 before Phase 6.
   `test_phase6.py` adds 29 and `test_enforcement.py` grew by net 16 (17 added, 1 renamed away):
   294 + 29 + 16 = 339 exactly. Counted, not accepted.
5. **§7's table, transcribed.** `RULES_AT` and `ACTION_FOR` spot-checked against the PRD rows —
   row 2's *"for day"* against row 7's bare *"lock account"*, row 8's *"next day"*, row 11's
   *"Any"*. All correct, including the wording difference §5 records as a deliberate reading.
6. **The spec-question count.** *"Ten, plus the two findings"* in [CHANGELOG.md](../CHANGELOG.md)
   — rows counted by hand, and `test_documentation.py` enforces it mechanically, so it cannot
   drift silently.
7. **The D30 absence guarantees.** The AST call-check over `open` / `connect` / `dump` / `load` /
   `write_text` and the import allowlist for both new modules are present and real, not
   aspirational.

---

## N1 — `make check` is red, and this changeset made it redder *(MEDIUM-HIGH)*

Measured on both sides of the change:

| Target | Before | After | Added by Phase 6 |
|---|---|---|---|
| `ruff check` | 5 | 15 | **+10** |
| `ruff format --check` | 7 files | 9 files | **+2** (`monitor.py`, `test_phase6.py` — never formatted) |
| `basedpyright` | 2 | 10 | **+8** |
| `pytest` | — | 409 passed | 0 |

**Every one this change added is convention 8's category** — one line each, no spec implication,
no behaviour change — and all are **fixed in the same changeset**, listed in §N1.1 below rather
than dispositioned. That is what convention 8 requires and it is deliberately not written up
further. The table there has **twenty-two** rows against the eighteen this table counts, and the
difference is the point rather than an error: see §N1.1's first paragraph.

**What is not convention 8's category is the first column.** The gate was *already* red: 5 ruff
errors, 7 unformatted files and 2 basedpyright errors predate Phase 6, which means **Phase 5
shipped red**, and round 13 found it red at the Phase 3 merge before that. So the honest statement
is not *"three consecutive phases could not run the gate"* — which is what
[PHASE-6-DESIGN](../PHASE-6-DESIGN.md) §9 said — but **"the gate has been red across at least
three phases and nobody in a position to merge could see it."**

**Why this is the sixth defect class's family and not an instance of it.** That class is
*"`make check` was red while four documents said the guardrail it trips was enforced."* Here no
document claimed green: PHASE-6-DESIGN §9 stated the gate was not run and that nothing should be
read as evidence it passed. That is the correct disclosure and it is why this is a MEDIUM-HIGH
rather than a HIGH. But it is also the *precondition* for the class — a project that ships three
phases on "not run" has no way to distinguish "not run" from "red", and this round is the first
thing in three phases that could.

**The root cause is not the authoring environment.** An environment that cannot run the gate
explains why an author did not notice; it does not explain why a merge did not stop. Raised as
**N2** — where the first draft of this round asserted an answer and was wrong.

### N1.1 — the twenty-two, fixed in this changeset

| # | Rule | Where | Fix |
|---|---|---|---|
| 1–2 | `N818` — exception name should end in `Error` | `daily.SessionNotOpen`, `daily.ConfirmationRequired` | Renamed to `SessionNotOpenError` / `ConfirmationRequiredError`, with every reference updated across `daily.py`, both test files, `docs/api.md`, `docs/PHASE-6-DESIGN.md`, `README.md` and `CHANGELOG.md` — the last of those because the CLI prints `type(exc).__name__` and the README quotes that output |
| 3 | `F401` — unused import | `tests/test_enforcement.py` | `MappingProxyType`, left behind when the mutation it served was replaced by a `_evaluate_row` patch during the second fact-check pass |
| 4–6 | `RUF043` — unescaped metacharacter in a `match=` pattern | `tests/test_phase6.py` ×2, `tests/test_enforcement.py` ×1 | `match="§20.8"` → `match=r"§20\.8"`. Cosmetic — `.` matches itself — but the pattern was not what was meant |
| 7–10 | `I001` — import sorting | `__main__.py`, `monitor.py` | `ruff check --fix` |
| 11–12 | `ruff format --check` | `monitor.py`, `test_phase6.py` | `ruff format` — neither had ever been run through it |
| 13–18 | `basedpyright` — arithmetic on `Decimal | None` | `tests/test_phase6.py` ×3, `tests/test_enforcement.py` ×2 sites | Narrowing `assert x is not None` before use. Not appeasement: the value is optional precisely because §20.8 forbids a fallback, so the assert restates the invariant the fixture depends on |
| 19–22 | `basedpyright` — assignment to an attribute of an untyped `ModuleType` | `tests/test_enforcement.py`, two mutation fixtures (one Phase 5's, one Phase 6's) | Both patched a module global through `importlib.import_module(...)` plus `try/finally`, which a type checker cannot see and correctly refuses. Replaced with pytest's `monkeypatch` fixture against a normally-imported module handle — typed, and it restores what the hand-written `finally` restored. **These four surfaced only after 13–18 were fixed**, which is worth recording: a linter reports what it reports, so "eighteen" was never the total, only the total *visible at the time* |

**Twenty-two, where N1's table above counts eighteen — and the difference is a finding, not an
arithmetic slip.** Eighteen was the number visible on the **first** `make check`. Each subsequent
run surfaced more: `ruff check` went clean, then `ruff format` rewrote nine files, then
`basedpyright` reported four errors the earlier failures had masked, because `make` stops at the
first failing target and a checker only reports what the layer above it lets it reach. **Three
full runs were needed to reach green, and each was a strictly better measurement than the one
before.** That is the operational argument for running the gate — a single run establishes a
lower bound on what is wrong, never the total. N1's *before* column (5 / 7 / 2) is a first-run
number too and is a lower bound for the same reason.

**Division of labour, recorded because it bears on what is verified.** The author's environment
cannot run `ruff` or `basedpyright`, so items 7–12 — the mechanically auto-fixable ones — were
applied by this round's toolchain, and items 1–6 and 13–22 were written by the author and
verified here. **Nothing the author wrote was reported as lint-clean before this round ran the
linter**, which is the round 7 mistake and the reason the split is stated.

---

## N2 — a red gate survived merges through PRs that run the gate *(MEDIUM, root cause, unresolved)*

**This round's first draft asserted that "CI is not blocking on `ruff` or `basedpyright` — or is
not running them." That is false, and checking it rather than asserting it is the only reason the
claim is not in the shipped document.** It is recorded here rather than deleted, because a round
whose subject is *a guardrail's state asserted without being measured* has no business making the
same mistake in its own root-cause analysis. That is the sixth defect class, reproduced inside the
review of it, and it was one `sed` away from shipping.

What is actually the case, verified:

* **`.github/workflows/ci.yml` runs all five targets** as separate named steps — `ruff check`,
  `ruff format --check`, `basedpyright`, `check_links.py`, `pytest --cov` — on `pull_request` and
  on pushes to `main`. It is correctly configured and would fail on the current tree.
* **Work goes through pull requests.** `git log --merges` shows PRs #16–#20, one per phase,
  including `#20 … feat/phase-5-design-and-impl`. So CI *ran* on the changeset that introduced the
  pre-existing 5 / 7 / 2, and would have been red.
* **`.git/hooks/pre-commit` does not exist in this clone**, so `make install`'s `pre-commit
  install` was never run here and the local hooks could not have caught anything either. That is a
  contributing factor and it is checkable.

So the gate is configured, it runs, it would have failed, and the PR merged anyway. The one
remaining explanation is **branch protection not marking the `check` job as a required status
check** — a red X on a merged PR blocks nothing unless the setting says it does. That is a
repository *setting* and not a file in the tree, so **this round cannot verify it** and does not
claim it; it is where the answer is, and the check is one click in Settings → Branches.

This is arguably the actual finding and N1 is its symptom, which is why it is raised rather than
fixed: what blocks a merge is a policy decision. **And it lands exactly where
[PLAN](../PLAN.md)'s sixth-defect-class extrapolation said the next one would** — *"not a tighter
check on `src/tradipy/` but whatever the current checks are pointed away from — today that is
`scripts/`, `data/`, and CI's own configuration."* That prediction was made two rounds earlier;
this is the first round to test it, and the thing it found is not that CI is misconfigured but
that **nobody is required to look at it.** A check that runs, fails, and does not block is
indistinguishable from one that was never written — which is `Config.polarity()`'s shape at the
level of the repository rather than the module.

**Recommended, not done:**

1. Confirm whether the `check` job is a required status check on `main`. If it is not, that is the
   fix and it is a settings change, not a code change.
2. Run `pre-commit install` in every working clone — the absent hook here means the local half was
   never armed.
3. Clear the 5 + 7 + 2 of pre-existing debt in its own commit, kept separate from Phase 6's
   eighteen so the before/after measurement in N1 stays reproducible.

---

## N3 — the pre-existing debt was left, then swept; the trade is recorded *(LOW)*

**This finding changed during the round and both halves are kept**, because the reasoning for the
first half is the reason the second half has a cost.

**As first written:** the 5 ruff errors, 7 unformatted files and 2 basedpyright errors that
predate Phase 6 were *not* fixed, on the grounds that sweeping pre-existing debt into a phase
commit makes the before/after measurement in N1 unreproducible — and that measurement is this
round's evidence. One of the ruff errors, `positions.IllegalTransition`, is an `N818` on a Phase 5
**public type** whose rename ripples through `positions.py`, `monitor.py`, two test files and four
documents, which is larger than convention 8's "one line".

**As resolved:** a second `make check` run — the one that produced the nine findings itemised
below — was taken as an instruction to clear the lot, so the pre-existing ruff findings are fixed
here as well:

| Rule | Where | Fix |
|---|---|---|
| `N818` | `positions.IllegalTransition` | → `IllegalTransitionError`, propagated through `positions.py`, `monitor.py`, `daily.py`, `test_enforcement.py`, `docs/api.md`, both design records and the root changelog. The last exception in the tree without an `Error` suffix |
| `SIM300` ×2 | `tests/test_phase5.py` — `PDT_REACHABLE_EQUITY` on the left of a comparison | Operands flipped. Ruff reads a `CONSTANT_CASE` name as the constant, so `CONST == expr` is the Yoda form |
| `RUF043` | `tests/test_phase5.py` — `match="intended|filled"` | Raw string. The alternation is **intended** here, unlike the `§20.8` patterns, so `re.escape` would be the wrong fix |

**The cost, stated because N3's first half is exactly the argument against doing this.** The tree
no longer reproduces N1's *before* column. The measurement stands on this round's record of it and
on nothing else — which is a weaker form of evidence than a reader could regenerate, and is the
trade that was accepted rather than a free improvement.

Two of the nine in that second run were also **new**, introduced by this round's own first batch
of fixes: `SIM300` on `assert UNREACHABLE_BLOCKS == frozenset()` and on
`assert _PHASE_6_ROWS <= set(PARAMS)`, both written in the Phase 6 changeset and both invisible
until a linter ran. That is the same shape as the round's own N2 correction, one level down: **a
fix written without the tool that judges it is a guess**, and two of the eighteen in N1.1 were
guesses that happened to be wrong in a way only `ruff` could see.

---

## What is genuinely good

1. **The two findings are real, not decorative.** Finding 1 (three §7 inputs and row 8's next-day
   lock have no §10 column, so a restart silently *re-bases* both drawdown rules rather than
   erroring) and finding 2 (§20.12 cannot record a kill-switch flatten from four of five open
   states) are both reproduced by execution and pinned by tests that fail if the gap ever closes.
2. **The self-critique reports its own error rate.** Two adversarial passes, 30 discrepancies then
   10 more from the corrections, recorded with the counts rather than as a clean draft — including
   a fabricated PRD quotation and a count wrong in one place and right in six, both caught
   in-house.
3. **`UNREACHABLE_BLOCKS` is emptied and asserted rather than deleted**, which keeps the
   distinction between a deliberate gap and an accidental one written down.
4. **`flatten_all` derives from `positions.reachable_exit_reasons`** instead of re-walking
   `TRANSITIONS` — one definition of which flatten is legal, in the module whose job is to
   discover that it is nearly empty.

---

## Recommended next steps

**Now:** resolve N2 — establish whether CI blocks on `make check`, and if not, make it. Then clear
the pre-existing 5 + 7 + 2 in a commit of its own.

**Raise as spec questions, do not code-resolve:** Phase 6's two findings, and the ten readings in
[CHANGELOG.md](../CHANGELOG.md)'s D35 table. §20.12's missing edges in particular now block two
phases rather than one.

**Still outstanding, across all six defect classes and all seven code rounds:** a read by someone
with **no prior context**. Every round including this one carried full repository context.

---

## Appendix: verification limits

- **`make check`:** run, on both sides of the changeset. This is the first round in three phases
  able to report that, and the first ever to report a *before/after* rather than a single verdict.
- **Not run:** `make coverage` and the mutation protocol. The coverage figure (~99%) and the
  mutation result (47/47) were measured at v0.1.0 against a 117-function suite and have not been
  re-measured against the 222 functions added since — a gap [PLAN](../PLAN.md) already records and
  which this round does not close.
- **Review type:** a read of the Phase 6 artifacts with full repository context from `CLAUDE.md`,
  by a party that did not write them. **No second adversarial pass was run over this document's own
  draft**, which rounds 13 and 14 both recorded as a limitation and which applies here too.
