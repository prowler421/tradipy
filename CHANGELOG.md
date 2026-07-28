# Changelog

All notable changes to the tradipy **package** are documented here. This file follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> The specification's own correction history is tracked separately in
> [`docs/CHANGELOG.md`](docs/CHANGELOG.md). This file tracks the code, tooling, and packaging.

## [Unreleased]

### Added

- `uv`-based project management: dev dependency group (PEP 735), `pyproject.toml` metadata
  (authors, license, classifiers, URLs), and a committed `uv.lock`.
- Ruff (lint + format) and BasedPyright configuration in `pyproject.toml`.
- Coverage configuration and `pytest-cov` in the dev group.
- `Makefile` with developer targets (`install`, `sync`, `test`, `coverage`, `lint`,
  `format`, `format-check`, `typecheck`, `check`, `clean`, `docs`, `precommit`, `release`).
- Pre-commit hooks (`.pre-commit-config.yaml`) for whitespace, Ruff, and BasedPyright.
- GitHub Actions CI (lint, format check, type check, tests + coverage) and a tag-driven
  release workflow.
- Documentation: top-level `README.md`, `CONTRIBUTING.md`, `LICENSE` (MIT, placeholder),
  and `docs/architecture.md`, `docs/development.md`, `docs/api.md`.
- `CLAUDE.md` and `.cursor/rules/` to keep AI-assisted contributions consistent with the
  project's invariants.
- Editor configuration (`.editorconfig`). VS Code settings stay local: `.vscode/` is
  git-ignored deliberately, so editor preferences are per-developer.
- `scripts/regen_registry_baseline.py` — a documented wrapper for regenerating the
  parameter-registry prose baseline.

### Changed

- Minimum Python raised to 3.13.
- `tradipy/__init__.py` now imports its three submodules, so the names it advertises in
  `__all__` resolve as attributes (`tradipy.gates` previously raised `AttributeError`).
- `Ladder` is exported from `tradipy.gates`; it is the return type of `exit_ladder` and was
  reachable but undeclared.
- Ruff and BasedPyright are pinned to a minor series, so a tool release cannot turn a passing
  branch red without a commit.
- The `PARAMS` registry is fenced with `# fmt: off` / `# fmt: on`. It transcribes the PRD's
  §2 / §2.0 tables and is reviewed against them row by row; the formatter would expand each
  row carrying a `polarity=` keyword into an eight-line block.
- The PRD's `×`, `–`, and `−` glyphs are allow-listed via Ruff's `allowed-confusables` rather
  than switching off RUF001-003, so an accidental homoglyph is still caught. Rewriting them to
  ASCII would break the PRD literal scan in `tests/test_parameter_registry.py`.
- `make check` now includes the formatting check, matching CI exactly.
- `license` is declared as a PEP 639 SPDX expression (`License-Expression: MIT` in the built
  metadata) instead of the deprecated `{ file = ... }` table.
- `pre-commit-hooks` updated to v6.0.0.
- Both workflows declare `permissions: contents: read`; the release workflow refuses to build
  when the pushed tag disagrees with `version` in `pyproject.toml`.

### Fixed

- The `trailing-whitespace` hook ran without `--markdown-linebreak-ext=md` and so stripped the
  hard line breaks from `docs/PRD.md`'s header, reflowing the normative document.
- `scripts/regen_registry_baseline.py` inherited environment: it replaced the child
  environment with two variables, dropping `HOME`, `TMPDIR`, and `VIRTUAL_ENV`.
- Documented installs referenced a `dev` extra that does not exist now that dev tools are a
  PEP 735 group; `pip install -e . --group dev` is the pip path.

Behavior of the invariant layer (`rounding`, `params`, `gates`) is unchanged; this release is
tooling, packaging, and documentation only.

## [0.0.1] - 2026-07-28

### Added

- Initial invariant layer: parameter registry (`params.py`), polarity-aware tick rounding
  (`rounding.py`), and pre-entry gates with position sizing (`gates.py`).
- Test suite defending four defect classes (worked examples, registry consistency, boundary
  and polarity invariants), verified by mutation testing.

[Unreleased]: https://github.com/prowler421/tradipy/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/prowler421/tradipy/releases/tag/v0.0.1
