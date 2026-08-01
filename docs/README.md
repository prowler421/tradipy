# Documentation index

Nine documents plus this index and a review archive. They are not interchangeable, and two of
them are authoritative in ways the others are not — so read this page before citing any of them.

## Start here

| If you want to… | Read |
|---|---|
| Know what a rule *is* | [PRD.md](PRD.md) — normative |
| Understand the code's shape | [architecture.md](architecture.md) |
| Call the library | [api.md](api.md) |
| Set up and contribute | [development.md](development.md), then [../CONTRIBUTING.md](../CONTRIBUTING.md) |
| Know what is built and what is next | [PLAN.md](PLAN.md) |
| Know why a rule changed | [CHANGELOG.md](CHANGELOG.md) |
| Run the data spike | [PHASE-2A-SPIKE.md](PHASE-2A-SPIKE.md), [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) |
| Assess Phase 3 readiness | [PHASE-3-READINESS.md](PHASE-3-READINESS.md) |
| Understand what Phase 4 built, and what it refused to claim | [PHASE-4-DESIGN.md](PHASE-4-DESIGN.md) |
| Understand what Phase 5 built, and what it *refused to build* | [PHASE-5-DESIGN.md](PHASE-5-DESIGN.md) |
| Understand what Phase 6 built, and the two findings it turned up | [PHASE-6-DESIGN.md](PHASE-6-DESIGN.md) |

## The two authoritative documents

**[PRD.md](PRD.md) is normative.** §20 (Computation Semantics) governs on any conflict between
prose, comments and code. If the code diverges from it, that is a specification question — raise
it, do not resolve it silently in code. 2,280 lines; §20 is the part the library implements.

**[CHANGELOG.md](CHANGELOG.md) holds every correction to the PRD**, grouped by PRD version. The
PRD states current rules only; superseded rules and the reasoning behind each reversal live here
(decision D23). This is *not* the root [../CHANGELOG.md](../CHANGELOG.md) — that one tracks the
**package**: code, tooling, packaging, in Keep a Changelog form. The two are not interchangeable
and a change usually belongs in exactly one.

## Planning

| Document | Role |
|---|---|
| [PLAN.md](PLAN.md) | Workstreams 0–11, the sequencing table, the decision log D1–D35 (no D31), and the risk register. The defect-classes section is the most cited part of the repository, and PLAN is where its count is maintained — deliberately not restated here, so that this page cannot go stale against it |
| [PHASE-2A-SPIKE.md](PHASE-2A-SPIKE.md) | Scope and **binding pre-registration** for the data feasibility spike (PRD §5.5 / V7). Its §7 thresholds were committed before any data was pulled and are not to be retrofitted to a result |
| [PHASE-2A-REPORT.md](PHASE-2A-REPORT.md) | Completion report per §6 — Q1–Q4 status, measured vs pipeline-only |
| [PHASE-3-READINESS.md](PHASE-3-READINESS.md) | Gate checklist for whether Phase 3 (scanner) may start (D29). Also the only record of **review round 11**, which wrote no review file |
| [PHASE-4-DESIGN.md](PHASE-4-DESIGN.md) | Design record for the §3 strategy engine (D33): module shape, the nineteen readings and questions §3 forced, the scope boundary, and what simulated-only construction cannot establish |
| [PHASE-5-DESIGN.md](PHASE-5-DESIGN.md) | Design record for §7 pre-order risk and §6 order construction (D34). The one phase whose §12.1 scope is partly **forbidden** rather than deferred, so its §1.1 and §2 are load-bearing: it states what it refused to build, the two gates it did not pass, and the two guarantees it computes and cannot enforce |
| [PHASE-6-DESIGN.md](PHASE-6-DESIGN.md) | Design record for §7's *other five* enforcement points, §10's `daily_state` and §20.8 (D35). The first phase whose §12.1 dependency was actually met, so its §2 argues only the §18.7 half. Its §6 carries the two findings building it turned up: §7.1.2's restart guarantee is incomplete in §10's own schema, and §20.12 cannot record the flatten §7 demands from four of five open states |

## Engineering guides

| Document | Role |
|---|---|
| [architecture.md](architecture.md) | Module structure, the one-way dependency graph, and the five design invariants the test suite defends |
| [api.md](api.md) | Public surface of all sixteen library modules, with signatures and worked snippets |
| [development.md](development.md) | Environment, `make` targets, the testing markers, the release process, and the mutation protocol |

See also [../tests/README.md](../tests/README.md), which is where the **documented open
findings** live — spec discrepancies deliberately surfaced rather than enforced, each pinned by a
test that fails if someone resolves it silently.

## Review archive

[`reviews/`](reviews) holds every independent review round. They are kept unedited as the record
of what was found; corrections go to the changelogs, not into the review that found them.

| Round | Reviewed | Findings |
|---|---|---|
| [PROMPT-REVIEW.md](reviews/PROMPT-REVIEW.md) | The *source prompt*, not an output — where the PRD deliberately departs from what was asked for, and why | 12 departures |
| [REVIEW-v1.2.md](reviews/REVIEW-v1.2.md) | PRD v1.2 | 23; one still open (#23, citation granularity) |
| [REVIEW-v1.3.md](reviews/REVIEW-v1.3.md) | PRD v1.3 | 6, one blocking (rounding direction) → D25 |
| [REVIEW-2026-07-28.md](reviews/REVIEW-2026-07-28.md) | The **code**, first time | 12; four unenforced guarantees → package v0.1.0, D26–D28 |
| [REVIEW-2026-07-29.md](reviews/REVIEW-2026-07-29.md) | The code again, verifying the round above | 9; ten of twelve F-findings confirmed closed, F8 not |
| [REVIEW-2026-07-30.md](reviews/REVIEW-2026-07-30.md) | The **Phase 2a instrumentation** (`scripts/spike2a/`), first time; round 6 verified | 15, three HIGH; `make check` red against four documents saying the guardrail was enforced; the **sixth defect class** |
| [REVIEW-2026-07-31.md](reviews/REVIEW-2026-07-31.md) | D30 and the H5 join, verifying round 7; `src/tradipy/` unchanged | 1, LOW-MEDIUM; two documents understated a fix that shipped in the same commit as D30 — no new defect class |
| [REVIEW-2026-07-31-round9.md](reviews/REVIEW-2026-07-31-round9.md) | Phase 3 readiness / the new Q1 pipeline (`q1_vendors.py`), verifying round 8; `src/tradipy/` unchanged for the second round running | 2; MEDIUM-HIGH — Q1's disposition-withholding guarantee (the same one Q2–Q4 each have a test for) had none, reproduced by mutation. Phase 3 gate verdict unchanged: not ready |
| [claude-PHASE-3-REVIEW.md](reviews/claude-PHASE-3-REVIEW.md) | The **Phase 3 gate** and the same interval, conducted independently of round 9 and completed after it; findings prefixed `K*` so the two do not collide | 7; two MEDIUM-HIGH — a completion report quoting the previous commit's numbers under a claim of regeneration, and `q1_vendors` asserting a §7 Q1 negative from an empty matrix. Candidate **seventh defect class** raised, not decided. Phase 3 gate verdict unchanged: not ready |
| *(round 11 — no file)* | `make check` at the Phase 3 merge. Its record is the first-row note in [PHASE-3-READINESS.md](PHASE-3-READINESS.md) | **Red**: eleven `ruff` errors, two unformatted files, three `basedpyright` errors, all introduced by Phase 3 and all fixed there. Used no finding prefix, which is why round 12 uses `L` |
| [REVIEW-2026-07-31-round13.md](reviews/REVIEW-2026-07-31-round13.md) | `session.py` and `setups.py` with fresh eyes, and round 12 verified — the first round to read Phase 4 without having written it | 7, prefixed `M*`; one **HIGH** — §3.4 criterion 9 (HOD proximity consolidation) was implemented, documented and reachable with **no fixture that activated its branch**, so nothing would have noticed it breaking. **M7** is the same shape on the *prior HOD* reading. M3–M5 are three dead conditions in `setups.py`, fixed inline per convention 8. All eight of round 12's `L` findings hold |
| [REVIEW-2026-08-01-round14.md](reviews/REVIEW-2026-08-01-round14.md) | The **Phase 5 build** (D34) — `positions.py`, `risk.py`, `orders.py`, their fixtures and PHASE-5-DESIGN. The first cold read of Phase 5, by a party that did not write it | 7, prefixed `H*`; two **MEDIUM-HIGH** — **H1**, §7's total-open-risk cap makes `max_open_positions` > 1 unreachable while a position is at full risk, and **H3**, §20.12 cannot express a post-T1 invalidation or a kill-switch flatten, so Phase 4's post-entry predicates and Phase 5's state machine do not compose mid-ladder. H1, H2 and H3 were already raised by the build; **H6 fixed inline** per convention 8. **No new defect class** — H1 and H2 are further populations of the third. `make check` **not run** for the second round running, and the round says so |
| [REVIEW-2026-08-01-round15.md](reviews/REVIEW-2026-08-01-round15.md) | The **Phase 6 build** (D35) — `daily.py`, `monitor.py`, their fixtures and PHASE-6-DESIGN. **The first round in three phases with a working toolchain**, and the first ever to report `make check` *before and after* a changeset rather than a single verdict | 3, prefixed `N*`; one **MEDIUM-HIGH** — **N1**, the gate is red and this change made it redder (+10 ruff, +2 unformatted files, +8 basedpyright), on top of a 5/7/2 that predates it, which means **Phase 5 shipped red too**. The eighteen Phase 6 added are convention 8's category and are **fixed in the same changeset**, listed one line each. **N2** is the root cause and is raised, not fixed: CI *is* correctly configured and *does* run all five targets on every PR, and the PR merged red anyway — so the remaining explanation is branch protection not requiring the check, which is a repository setting this round cannot read and does not claim. Exactly where [PLAN](PLAN.md)'s sixth-defect-class extrapolation said to look next, and the round's first draft asserted the wrong answer before checking `ci.yml`. Not a new defect class: no document claimed the gate was green, so this is the class's *precondition* rather than an instance |
| [REVIEW-2026-07-31-round12.md](reviews/REVIEW-2026-07-31-round12.md) | Rounds 9 and 10 verified, and **Phase 4** — which this round also built, so it is explicitly not an independent review of it | 8, prefixed `L*`; one **HIGH** — §3.4's worked example is rejected by §3.1.1's own room gate, the next whole dollar being nearer than the HOD its table names. Reproduced by execution; raised, not resolved. Also K3 partially closed, and a test count that went wrong again one commit after K6 fixed it. No new defect class: L2 is a new *population* of the third |

**On the naming.** `REVIEW-v1.2` and `REVIEW-v1.3` are named for the PRD version they reviewed;
`REVIEW-2026-07-28` onward are dated because they review *code*, which has its own version
sequence. The inconsistency is informative and is left deliberately: the filename tells you
whether a round examined the specification or the implementation. Future rounds are dated.

New rounds go in `reviews/` and are added to the table above, to the companion table in
[PLAN.md](PLAN.md), and — if they find a new defect class — to the PLAN's defect-classes section.
The [`review-round`](../.claude/skills/review-round/SKILL.md) skill carries the full procedure,
including the mandatory adversarial fact-check.

## Conventions that govern all of this

- **A finding fixable in one line, with no spec implication, gets fixed — not dispositioned.**
  `CLAUDE.md` convention 8. Seven rounds of review machinery exist for defects that recur or need a
  spec call.
- **All data is simulated.** `CLAUDE.md` convention 9, decided as [PLAN](PLAN.md) **D30**. Every
  dataset sits on a `SIMULATED` → `PAPER` → `LIVE` ladder whose current rung is the first; no
  broker, vendor or network module may be imported anywhere in `src/`, `scripts/` or `tests/`;
  and data with no declared origin is refused rather than assumed simulated. The cost is that
  [PHASE-2A-SPIKE](PHASE-2A-SPIKE.md) §7 binds to *measured* data, so Q1–Q4 stay unanswered and
  a spike run prints a pipeline outcome, never a §7 verdict.
- **Every guarantee needs the test that breaks it.** For any sentence of the form "X cannot
  happen", write the test that attempts X and asserts it fails. See
  [`../tests/test_enforcement.py`](../tests/test_enforcement.py) and the
  [`guarantee-test`](../.claude/skills/guarantee-test/SKILL.md) skill.
- **Counts stated in prose are checked.** `tests/test_documentation.py` asserts that the numbers
  these documents quote — registered parameters, baseline entries, reject codes, library modules,
  and the size of each spec-question table — match the thing they describe. A count stated twice
  with one copy updated is the v1.2 defect class, and it has now recurred inside this documentation
  set **six times**, most recently when a review disposition added a row to a table and left the
  word above it alone — in the paragraph that had just finished explaining the previous instance.
  Two gaps that allowed it are closed: the checker's patterns matched only **digits**, so
  `**Fourteen**` was invisible, and the two design records were outside its scope entirely.
- **Relative links are checked.** `make links` (also a pre-commit hook and a CI step) validates
  every relative Markdown link and heading anchor in the repository.
