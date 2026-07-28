# CLAUDE.md

Guidance for Claude Code (and other AI assistants) contributing to **tradipy**.

## What this project is

tradipy is the **invariant layer** of a Ross Cameron momentum day-trading system. It is
deliberately *not* the strategy engine. It exists because four review rounds of
`docs/PRD.md` each surfaced a distinct defect class that the check designed for the previous
round could not catch. This code turns the PRD's rules into executable, tested invariants.

`docs/PRD.md` is **normative**. Section §20 (Computation Semantics) governs on any conflict
between prose, comments, and code. Read it before changing behavior.

## Architecture

Three small, pure modules under `src/tradipy/`:

- `rounding.py` — tick arithmetic and polarity-aware threshold rounding. The governing
  principle is *"rounding must never weaken a constraint."* `Polarity.MINIMUM` rounds up;
  `Polarity.MAXIMUM` rounds down and clamps to one tick.
- `params.py` — the parameter registry: the single source of truth for every tunable
  threshold, each with its legal range, source citation, and polarity. Also holds mode
  presets, hard caps, and the cross-parameter coupling validator.
- `gates.py` — pre-entry gates and position sizing (spread caps, separation floor, room
  requirement, exit ladder, stop construction, sizing). No numeric threshold literal appears
  here; every value is read from the registry by name.

Data flows one way: `rounding` ← `params` ← `gates`. Everything is `Decimal`.

## Repository layout

```
src/tradipy/        # the library (rounding, params, gates)
tests/              # pytest suite — worked examples, registry, boundary/polarity marks
docs/               # PRD.md (normative), PLAN, CHANGELOG (spec), reviews, architecture/dev/api
scripts/            # maintenance helpers (e.g. regen the registry baseline)
.github/workflows/  # CI and release
```

## Non-negotiable conventions

1. **One definition per threshold.** A registered threshold lives once in `params.PARAMS`
   and is read by name. No literal for a registered threshold anywhere else — the registry
   test enforces this against the PRD prose as well as the code.
2. **Polarity, not the call site, decides rounding.** Route all threshold rounding through
   `round_threshold(value, polarity)`.
3. **`Decimal` everywhere money is compared to a tick or summed into P&L** (PRD §9.2). No
   `float`.
4. **Assertions test the derivation, not the value.** `assert cap == floor_to_tick(x) and
   cap <= x`, never `assert cap == Decimal("0.01")` — the latter passes under a wrong rule
   that happens to agree at that input.
5. **Documented open findings stay documented.** Some incoherent couplings (e.g. the
   min-tradeable-price band) are deliberately surfaced, not enforced, because the incoherent
   combination is the shipped default. Do not silently enforce them; that is a spec decision.

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

- [ ] No new literal for a registered threshold.
- [ ] Rounding goes through `round_threshold` with the correct polarity.
- [ ] `Decimal` used for all price/P&L comparisons.
- [ ] Tests added/updated and assert the derivation.
- [ ] `make check` passes.
- [ ] `CHANGELOG.md` and docs updated for behavior changes.
- [ ] No unnecessary dependency, abstraction, or framework introduced.
