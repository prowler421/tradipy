# Development

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Python 3.13 (uv can install it: `uv python install 3.13`)

## Setup

```bash
git clone https://github.com/prowler421/tradipy.git
cd tradipy
make install      # uv sync + pre-commit install
```

`uv sync` creates `.venv/` and installs the runtime package plus the `dev` dependency group.
Everything else runs through `uv run`, so you never activate the environment by hand.

## Everyday commands

| Command | What it does |
| --- | --- |
| `make check` | Lint + format check + type check + test — the same gate CI runs. Run this before every commit. |
| `make test` | Run the pytest suite. |
| `make coverage` | Tests with a coverage report (term + `coverage.xml`). |
| `make lint` | `ruff check`. |
| `make format` | `ruff format` — rewrites files. |
| `make format-check` | `ruff format --check` — verifies without rewriting; part of `make check`. |
| `make typecheck` | `basedpyright`. |
| `make clean` | Remove caches and build artifacts. |
| `make help` | List every target. |

Run a subset of tests directly:

```bash
uv run pytest -m boundary            # only boundary-marked tests
uv run pytest tests/test_worked_examples.py -vv
```

## Dependency management

Use uv exclusively.

```bash
uv add <package>                 # add a runtime dependency (rare — the runtime is stdlib-only)
uv add --group dev <package>     # add a dev tool
uv sync                          # reconcile the environment with uv.lock
uv lock                          # regenerate the lockfile after editing pyproject.toml
```

Commit `uv.lock` with any dependency change. CI installs with `uv sync --frozen`, so an
out-of-date lockfile fails the build.

Ruff and BasedPyright are pinned to a minor series in `pyproject.toml` on purpose. Both decide
whether CI is green, and an unpinned formatter turns a passing branch red with no commit behind
it. Bump the pin deliberately, then run `make format` and read the diff.

Without uv: `pip install -e . --group dev` (pip 25.1+). The dev tools are a PEP 735 dependency
group, not an extra, so `pip install -e ".[dev]"` installs nothing.

## Code style

- Python 3.13, modern typing, `pathlib`, `dataclasses`, `enum`.
- Google-style docstrings on public modules, classes, and functions.
- Ruff owns formatting and import order. Do not hand-format; run `make format`.
- Keep functions small and explicitly typed. Prefer readability over cleverness.

One formatting exemption exists: the `PARAMS` registry in `params.py` is fenced with
`# fmt: off` / `# fmt: on`. It is a row-by-row transcription of the PRD's §2 / §2.0 tables and
is reviewed against them, so one parameter per line is the point; Ruff would expand every row
carrying a `polarity=` keyword into an eight-line block. Do not widen that exemption.

## Type checking

BasedPyright runs in `standard` mode (configured in `pyproject.toml`). Prefer fixing a type
error over suppressing it; when a suppression is genuinely warranted, use a narrow
`# pyright: ignore[ruleName]` with a comment explaining why.

## Testing philosophy

Assertions are written against the **derivation** of a value, not the value itself. The
suite defends four defect classes and is verified by mutation testing; see
[`../tests/README.md`](../tests/README.md) for what each file catches. Use the `spec`,
`boundary`, and `polarity` markers where they apply.

### Regenerating the registry baseline

`tests/test_parameter_registry.py` deliberately refuses to self-heal. When a PRD edit
legitimately changes the set of restated thresholds:

```bash
uv run python scripts/regen_registry_baseline.py
git diff -- tests/registry_baseline.json
```

Read the diff before committing — each entry is either a legitimate worked example or a
latent divergence of exactly the kind the test exists to catch.

## Release process

The project uses [Semantic Versioning](https://semver.org/) and
[Keep a Changelog](https://keepachangelog.com/).

1. Move the `[Unreleased]` notes in `CHANGELOG.md` into a new dated version section.
2. Bump `version` in `pyproject.toml`.
3. `make check` and commit.
4. Tag: `git tag vX.Y.Z && git push --tags`.

The release workflow (`.github/workflows/release.yml`) builds the sdist and wheel with
`uv build`. Publishing to an index is left as a commented, opt-in step.

## Continuous integration

`.github/workflows/ci.yml` runs on every push to `main` and every pull request: install uv,
cache by `uv.lock`, `uv sync --frozen`, then Ruff lint, Ruff format check, BasedPyright, and
pytest with coverage. Those are the steps of `make check`, split up so a failure names itself
in the UI. Keep the two in step — if you change one, change the other.

Both workflows declare `permissions: contents: read`. The release workflow additionally
refuses to build when the pushed tag disagrees with `version` in `pyproject.toml`.
