# CLAUDE.md

Guidance for Claude Code (and other AI assistants) contributing to **tradipy**.

## What this project is

tradipy is the **invariant layer** of a Ross Cameron momentum day-trading system. It is
deliberately *not* the strategy engine. It exists because five review rounds each surfaced a
distinct defect class that the check designed for the previous round could not catch — four
in `docs/PRD.md`, and a fifth in the code implementing it. This code turns the PRD's rules
into executable, tested invariants.

`docs/PRD.md` is **normative**. Section §20 (Computation Semantics) governs on any conflict
between prose, comments, and code. Read it before changing behavior.

## Architecture

Eight small, pure modules under `src/tradipy/`, plus a CLI:

- `rounding.py` — tick arithmetic and polarity-aware threshold rounding. The governing
  principle is *"rounding must never weaken a constraint."* `Polarity.MINIMUM` rounds up;
  `Polarity.MAXIMUM` rounds down and clamps to one tick.
- `rejects.py` — the `Reject` reason codes. Separate from `gates` so `quotes` need not depend
  on `gates`; re-exported from `tradipy.gates` for compatibility.
- `params.py` — the parameter registry: the single source of truth for every tunable
  threshold, each with its legal range, source citation, and polarity. Also holds the §2.0
  mode presets (an overlay on the registry defaults), the §7 hard caps, and the
  cross-parameter coupling validator.
- `bars.py` — PRD §20.4 flagpole geometry and the measured move.
- `quotes.py` — PRD §20.14 NBBO spread and quote validity.
- `score.py` — PRD §20.10 composite score and §14.2's conviction gate.
- `gates.py` — pre-entry gates and position sizing (spread caps, separation floor, room
  requirement, exit ladder, stop construction, sizing). No numeric threshold literal appears
  here, and no rounding direction either; both are read from the registry by name.
- `poc.py` / `__main__.py` — the proof of concept. `poc` composes the gates into one
  evaluation; `__main__` is `python -m tradipy demo` / `evaluate`, argparse and nothing else.
  Explicitly not the strategy engine: it gates a candidate, it does not find one.

Data flows one way. `rounding`, `rejects` and `bars` import only the standard library;
`params` imports `rounding`; `quotes` and `gates` import `params` and `rejects`; `score`
imports `params`; `poc` imports the lot, and only `__main__` imports `poc`. Everything is
`Decimal`.

## Repository layout

```
src/tradipy/        # the library (rounding, rejects, params, bars, quotes, score, gates)
                    # plus poc.py and __main__.py — the runnable proof of concept
tests/              # pytest suite — worked examples, registry, boundary/polarity marks,
                    # enforcement fixtures, and doc-count consistency
docs/               # start at docs/README.md (index)
  PRD.md            #   normative; §20 governs on any conflict
  PLAN.md           #   workstreams, sequencing, decision log D1–D29, risks
  CHANGELOG.md      #   PRD corrections — NOT the root CHANGELOG.md, which tracks the package
  PHASE-2A-SPIKE.md #   data spike scope with binding pre-registration
  api.md architecture.md development.md
  reviews/          #   every independent review round, kept unedited as the record
scripts/            # maintenance helpers — registry baseline, link checker
.claude/skills/     # guarantee-test, review-round (mirrored as .cursor/rules/*.mdc)
.github/workflows/  # CI and release; dependabot.yml covers Actions only
```

## Non-negotiable conventions

1. **One definition per threshold.** A registered threshold lives once in `params.PARAMS`
   and is read by name. No literal for a registered threshold anywhere else — the registry
   test enforces this against the PRD prose as well as the code, **within its stated scope**:
   the lint walks `src/tradipy/*.py` non-recursively plus `scripts/` recursively, skips
   `params.py` and `__init__.py` **inside `src/tradipy/` only**, and exempts an `_UNDISTINCTIVE`
   value set. `tests/` is not scanned, deliberately — fixtures must state literals (convention
   4). State the rule with that scope wherever it appears; an unqualified version of it is what
   F8 was about.
2. **Polarity, not the call site, decides rounding.** In `gates.py` this means
   `_rounded(cfg, value, *governed_by)`, which reads the direction from the registry. Do not
   import `Polarity` into `gates.py` and do not name a member at a call site: that gives
   direction two definitions, and a test proves the import is absent.
3. **`Decimal` everywhere money is compared to a tick or summed into P&L** (PRD §9.2). No
   `float`.
4. **Assertions test the derivation, not the value.** `assert cap == floor_to_tick(x) and
   cap <= x`, never `assert cap == Decimal("0.01")` — the latter passes under a wrong rule
   that happens to agree at that input.
5. **Documented open findings stay documented.** Some incoherent couplings (e.g. the
   min-tradeable-price band, documented on `min_tradeable_price_from_stop_bounds` and
   `signal_cap_ticks_at_min_r`, not on `validate_couplings`) are deliberately surfaced, not
   enforced, because the incoherent combination is the shipped default. Do not silently
   enforce them; that is a spec decision.
6. **Every guarantee needs the test that breaks it.** For any sentence of the form "X cannot
   happen", write the test that attempts X and asserts it fails. A test confirming the happy
   path passes whether or not the guarantee is enforced — which is how four guarantees came
   to be unenforced at once in v0.0.1, three of them with a passing test right beside the
   hole. This is the fifth defect class; see `tests/test_enforcement.py`.
7. **A bound the PRD does not state must say so.** `Param.source` marks code-originated
   ranges `(bounds: code)`. §2, §3.1.1, §3.4, §20.10 and §20.14 have no Bounds column, so
   their `lo`/`hi` are this module's judgement, not spec.
8. **Fix trivial findings; do not disposition them.** A review finding that is fixable in one
   line, has no spec implication and changes no behaviour gets **fixed in the same change**,
   listed in one line in the review, and gets no `docs/CHANGELOG.md` entry, no decision, and no
   disposition block. Six rounds of review machinery exist for defects that recur or that
   require a spec call; a heading that says "four" above a list of six needs neither, and
   putting it through the full apparatus costs more than the defect. **The judgement is the
   convention's weak point** — when unsure whether a finding is trivial, disposition it. A
   finding that turns out to recur, or to have a behaviour consequence, was never trivial.

## Coding standards

- Python 3.13. Modern typing (`X | None`, builtins generics, `collections.abc`), `pathlib`,
  `dataclasses`, `enum`. No legacy `typing` aliases.
- Small functions, explicit types on public APIs, Google-style docstrings on public modules,
  classes, and functions.
- Formatting and imports are Ruff's job. Never hand-format. Two deliberate configurations to
  leave alone: the `PARAMS` registry is fenced with `# fmt: off` / `# fmt: on` so the PRD table
  reads row by row, and the PRD's `×`, `–`, `−` glyphs are allow-listed in Ruff's
  `allowed-confusables` (ASCII-ifying them breaks the PRD scanner in
  `test_parameter_registry.py`).
- The runtime is stdlib-only. Do not add a dependency, framework, Docker, CLI, or logging
  without a concrete, stated need.

## Testing expectations

- Every behavior change needs a test in `tests/`. Use the `spec`, `boundary`, and `polarity`
  markers where they apply.
- Regenerate the registry baseline only deliberately:
  `uv run python scripts/regen_registry_baseline.py`, then read the diff.
- `make check` (lint + format check + typecheck + test) must be green before work is done.

## Dependency management

Use `uv` exclusively: `uv sync`, `uv run ...`, `uv add ...`. Dev tools live in the `dev`
dependency group. Commit changes to `uv.lock`.

## Release process

Semantic Versioning. Bump `version` in `pyproject.toml`, add a dated section to
`CHANGELOG.md` (Keep a Changelog format), commit, tag `vX.Y.Z`, and push tags. The release
workflow builds the sdist and wheel.

## Documentation requirements

When behavior changes: update `CHANGELOG.md`, the relevant `docs/` file, and any affected
docstring. If a rule in the code diverges from `docs/PRD.md`, that is a spec question — raise
it, do not resolve it silently in code.

## Review checklist

- [ ] No new literal for a registered threshold; any bound the PRD does not state is marked
      `(bounds: code)` in its `Param.source`.
- [ ] Rounding goes through `_rounded`, with the polarity read from the registry.
- [ ] `Decimal` used for all price/P&L comparisons.
- [ ] Tests added/updated and assert the derivation, with the right marker.
- [ ] Every new guarantee has a test that performs the violation it forbids.
- [ ] `make check` passes, and `uv run python -m tradipy demo` still exits 0.
- [ ] Root `CHANGELOG.md` updated for code/tooling; `docs/CHANGELOG.md` for spec decisions.
- [ ] No unnecessary dependency, abstraction, or framework introduced.
