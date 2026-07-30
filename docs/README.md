# Documentation index

Seven documents plus this index and a review archive. They are not interchangeable, and two of
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
| Run the data spike | [PHASE-2A-SPIKE.md](PHASE-2A-SPIKE.md) |

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
| [PLAN.md](PLAN.md) | Workstreams 0–11, the sequencing table, the decision log D1–D29, and the risk register. The defect-classes section is the most cited part of the repository — six rows as of round 7, and the count is deliberately not restated here |
| [PHASE-2A-SPIKE.md](PHASE-2A-SPIKE.md) | Scope and **binding pre-registration** for the data feasibility spike (PRD §5.5 / V7). Its §7 thresholds were committed before any data was pulled and are not to be retrofitted to a result |

## Engineering guides

| Document | Role |
|---|---|
| [architecture.md](architecture.md) | Module structure, the one-way dependency graph, and the five design invariants the test suite defends |
| [api.md](api.md) | Public surface of all eight library modules, with signatures and worked snippets |
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
- **Every guarantee needs the test that breaks it.** For any sentence of the form "X cannot
  happen", write the test that attempts X and asserts it fails. See
  [`../tests/test_enforcement.py`](../tests/test_enforcement.py) and the
  [`guarantee-test`](../.claude/skills/guarantee-test/SKILL.md) skill.
- **Counts stated in prose are checked.** `tests/test_documentation.py` asserts that the numbers
  these documents quote — registered parameters, baseline entries, reject codes, library modules
  — match the code. A count stated twice with one copy updated is the v1.2 defect class, and it
  has recurred inside this documentation set as recently as this month.
- **Relative links are checked.** `make links` (also a pre-commit hook and a CI step) validates
  every relative Markdown link and heading anchor in the repository.
