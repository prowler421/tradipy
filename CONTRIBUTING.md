# Contributing to tradipy

Thanks for helping keep tradipy correct. This project has an unusually strong bias toward
*provable* correctness, because its entire reason to exist is to catch the defect classes
that ordinary review misses. A few conventions matter more than usual here.

## Ground rules

1. **`docs/PRD.md` is normative.** Section §20 governs on any conflict between prose, code
   comments, and code. If your change makes the code diverge from the PRD, that is a
   specification decision — raise it in an issue, do not resolve it silently in code.
2. **One definition per threshold.** Every tunable threshold is registered once in
   `tradipy.params.PARAMS` and read by name. Never write a numeric literal for a registered
   threshold anywhere else; the registry test enforces this against the PRD prose too.
3. **Polarity decides rounding, and the registry decides polarity.** In `gates.py` route
   rounding through `_rounded(cfg, value, *governed_by)`, never by naming a `Polarity`
   member — that gives direction a second definition, and a test asserts `gates.py` does not
   import `Polarity` at all.
4. **`Decimal`, never `float`, for anything compared to a tick or summed into P&L.**
5. **Every guarantee needs the test that breaks it.** If you write "X cannot happen"
   anywhere — docstring, README, architecture doc — write the test that attempts X and
   asserts it fails. Four guarantees were unenforced at once in v0.0.1, three of them with a
   passing happy-path test right beside the hole. See `tests/test_enforcement.py`.

## Getting set up

```bash
git clone https://github.com/prowler421/tradipy.git
cd tradipy
make install     # uv sync + pre-commit install
make check       # confirm a clean baseline
```

## Making a change

1. Create a branch: `git checkout -b feature/short-description`.
2. Make the change. Keep functions small and typed; prefer readability over cleverness.
3. Add or update tests. Assert the **derivation**, not a magic value — e.g.
   `assert cap == floor_to_tick(x) and cap <= x`, not `assert cap == Decimal("0.01")`.
   Use the `spec`, `boundary`, and `polarity` markers where they apply.
4. Update `CHANGELOG.md` (under `[Unreleased]`) and any affected `docs/` and docstrings.
5. Run `make check` (lint + format check + type check + tests). It must be green.
6. Open a pull request. CI runs the same `make check`.

## Style

- Python 3.13, modern typing (`X | None`, builtin generics, `collections.abc`), `pathlib`,
  `dataclasses`, `enum`. No legacy `typing` aliases.
- Google-style docstrings on public modules, classes, and functions.
- Formatting and import order are Ruff's job — `make format`. Do not hand-format.
- The runtime is stdlib-only. Adding a dependency needs a stated, concrete justification.

## Regenerating the registry baseline

`tests/test_parameter_registry.py` refuses to self-heal so that a latent divergence cannot
slip in. When a PRD edit legitimately changes the set of restated thresholds:

```bash
uv run python scripts/regen_registry_baseline.py
git diff -- tests/registry_baseline.json    # read this before committing
```

## Review checklist

- [ ] No new literal for a registered threshold; any new bound the PRD does not state is
      marked `(bounds: code)` in its `Param.source`.
- [ ] Rounding routed through `_rounded`, with the polarity read from the registry.
- [ ] `Decimal` used for all price/P&L comparisons.
- [ ] Tests added/updated and assert the derivation, with the right marker.
- [ ] Every new guarantee has a test that performs the violation it forbids.
- [ ] `make check` passes, and `python -m tradipy demo` still exits 0.
- [ ] Root `CHANGELOG.md` updated for code/tooling; `docs/CHANGELOG.md` for spec decisions.
- [ ] No unnecessary dependency, abstraction, or framework introduced.
