# Changelog

All notable changes to the tradipy **package** are documented here. This file follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> The specification's own correction history is tracked separately in
> [`docs/CHANGELOG.md`](docs/CHANGELOG.md). This file tracks the code, tooling, and packaging.

## [Unreleased]

### Added

- **`scripts/spike2a/`** — the Phase 2a data feasibility spike, instrumented. Throwaway
  investigative code per PHASE-2A-SPIKE.md §8: not imported by `src/tradipy/`, no coverage
  obligation, and Phase 3 gets written fresh against the PRD rather than grown from it. Eight
  modules — `prereg.py` (§7's pre-registration table, so the pass thresholds are read rather than
  re-typed), `windows.py` (the VIX window rule), `universe.py` (the §7 selection rule and its
  three exclusions), `feeds.py` (the swappable NBBO fetch layer), `q4_spreads.py`, `q2_float.py`,
  `q3_latency.py`. Stdlib-only and CSV-driven, so the whole pipeline runs with no broker and no
  subscription; `ib_insync` is imported lazily inside one constructor and is deliberately not a
  package dependency. Q4 computes its caps with `gates.spread_caps` and its spread with
  `quotes.spread_at_signal` rather than reimplementing either (§4.3). **No `src/tradipy/` change
  and no new dependency.**
- **`PreOpenFacts.check_units()`** — rejects `gap_premarket_pct`, `gap_daily_pct` or
  `missing_nbbo_pct` above `1`, because the registry stores gap thresholds as fractions and a CSV
  supplying `12` for a 12% gap compares `12 >= 0.04` — true for every row, so the gap filter stops
  rejecting anything while still reporting that it filtered. The same error on `missing_nbbo_pct`
  inverts it: every session becomes a vendor coverage failure that never happened. Called from
  `classify()` and deliberately not from `from_csv_row`, which folds `ValueError` into an
  unparsable-row count where a `UnitError` would vanish. It caught a real instance immediately —
  the synthetic fixture used to smoke-test the module had `missing_nbbo_pct=9`.
- **Two guard tests on the registry lint's new roots** —
  `test_the_lint_scans_scripts_recursively` asserts `scripts/` is in scope and that a nested file
  is reached; `test_the_lint_catches_a_planted_literal` asserts the detection half fires on a file
  in a subdirectory. Two tests because the roots can be right while the offender construction
  drops every hit, which is the failure mode the `normalize()` blind spot actually had.

### Changed

- **`[tool.ruff] src` gains `"scripts"`** (`pyproject.toml`). Without it isort does not classify
  `scripts.spike2a.*` the way it classifies `tradipy.*`, so every spike module importing from both
  — which is every module that reads a registered threshold — trips `I001`. Fixed in the config
  rather than per-file so the next such module does not rediscover it.
- **The registry lint now scans `scripts/` recursively**, not `src/tradipy/*.py` alone
  (`test_parameter_registry.lint_roots()`). PHASE-2A-SPIKE.md §8 called this a prerequisite rather
  than an improvement: the spike's central task is measuring whether `max_spread_r` is calibrated,
  its code lives in `scripts/spike2a/`, and until now the only thing keeping a second definition of
  `max_spread_r` out of the code that measures `max_spread_r` was a sentence in a document.
  Verified by mutation — `Decimal("0.15")` planted in `scripts/spike2a/q4_spreads.py` fails with a
  message naming `max_spread_r`. Two related changes: the `params.py`/`__init__.py` filename
  exemption now applies **inside `src/tradipy/` only**, because exempting a filename exempts
  whatever anyone later puts in it; and offenders are labelled by repo-relative path rather than
  bare filename, since `scripts/` has subdirectories and two files called `sample.py` would
  otherwise report identically. The six live statements of convention 1's scope (`CLAUDE.md`,
  `CONTRIBUTING.md`, `params.py`, `api.md`, `architecture.md`, `.cursor/rules/tradipy.mdc`) are
  updated to match, per the rule F8 established.

- **`tests/test_documentation.py`** — asserts that counts stated in prose match the code:
  registered parameters, frozen-baseline entries, library-module count, the re-exported count in
  `__all__`, every `Reject` member being documented, and every declared pytest marker being both
  documented and applied. The v1.2 defect class (a quantity stated twice, one copy updated) was
  solved for thresholds by the registry and unsolved for the documentation's own numbers; it had
  recurred by v0.1.0 in `tests/README.md`. Verified by injecting three mutations and confirming
  each fails.
- **`scripts/check_links.py`** plus `make links`, a `check-links` pre-commit hook and a CI step —
  validates every relative Markdown link and heading anchor in the repository. Stdlib-only and
  offline by design. It found a broken citation in this file on its first run.
- **Two agent skills**, `.claude/skills/guarantee-test/` and `.claude/skills/review-round/`,
  with mirrored Cursor rules in `.cursor/rules/`. They encode convention 6 (write the test that
  performs the violation a guarantee forbids) and the review procedure including the mandatory
  adversarial fact-check.
- **`docs/README.md`** — documentation index, stating which documents are authoritative and how
  the two changelogs differ.
- **`.python-version`** pinning 3.13, and **`.github/dependabot.yml`** for GitHub Actions only —
  deliberately not for pip/uv, since the runtime is stdlib-only and `uv.lock` exists precisely
  so pins do not move on their own.
- **Coverage floor** of 95% (`fail_under`), below the ~99% measured, so the gate fails on
  collapse rather than on the next honest commit. The floor is not the claim.

### Changed

- **`docs/` reorganized**: the five review documents moved to `docs/reviews/`. They are the only
  part of the documentation set that grows by one file per round. All 120 relative links updated
  and verified by the new link checker; review filenames left as they are, because
  `REVIEW-v1.2` versus `REVIEW-2026-07-28` tells a reader whether a round examined the
  specification or the code.
- **`make check` now includes `make links`**, and `make docs` shows the index rather than a bare
  directory listing.
- **`CLAUDE.md` convention 1 and five other statements of the no-literal rule** now carry the
  registry lint's actual scope (`src/tradipy/*.py` non-recursive, skipping `params.py` and
  `__init__.py`, exempting undistinctive values, `scripts/` not scanned). The unqualified form
  was finding F8, reported closed and not closed.
- **`CLAUDE.md` gains convention 8**: a finding fixable in one line, with no spec implication and
  no behaviour change, gets fixed in the same change rather than dispositioned. Six rounds of
  review machinery exist for defects that recur or need a spec call.
- **`docs/development.md`** documents the manual mutation protocol. It is *not* automated, and
  says so — a mutation harness whose own correctness is undemonstrated is a mechanism built and
  not wired.

### Fixed

- `tests/README.md` heading read "Four open spec discrepancies" above a list of six.
- `tests/test_boundary.py` said eleven surviving rounding mutations where `tests/README.md`, this
  file and `docs/reviews/REVIEW-2026-07-28.md` all say twelve.
- A stale citation in this file pointing at the pre-move review path.

## [0.1.0] - 2026-07-29

Driven by [`docs/reviews/REVIEW-2026-07-28.md`](docs/reviews/REVIEW-2026-07-28.md), the first review of the
**code** rather than of the specification. It found four guarantees the documentation asserts
and the code did not enforce, all reproduced by execution. **Three of the four fixes change
behaviour**, and one changes it for every caller: `Config.default()` is now `beginner` mode.

### Fixed — four unenforced guarantees

- **`MODE_PRESETS` was a mutable module dict read live by `Config.__getitem__`.** One
  assignment raised an already-validated config's `max_risk_per_trade_pct` to 50%, past a cap
  PRD §7 calls non-bypassable, with no validator re-running. `PARAMS`, `MODE_PRESETS`,
  `HARD_CAPS` and the inner preset dicts are now `MappingProxyType`, and the preset is
  resolved into `Config.values` at construction rather than read on every lookup.
- **The registry lint was blind to 7 of 29 parameters.** Its search set was built from
  `Decimal.normalize()`, which renders trailing-zero values in scientific notation —
  `Decimal("30000")` became `3E+4`, a string that cannot occur in source. Six hardcoded
  thresholds injected into `gates.py` passed it clean, `start_of_day_equity` among them. The
  lint now parses an AST instead of matching a regex, which also fixes two further holes it
  had: it follows the `D = Decimal` alias, and it no longer reports literals *described* in
  docstrings.
- **`Config(values)` never range-validated.** `Config({**defaults, "max_spread_r": 99})` was
  accepted, taking the §3.1.3 signal-time spread cap to $14.85 on a $0.15 R — the gate off,
  silently, on a config reporting itself validated. `__post_init__` now validates every value
  against its `Param` bounds before checking couplings, and rejects unregistered names.
- **Rounding polarity was decided at the call site, not by the registry.** `gates.py` named
  `Polarity` members directly and `Config.polarity()` had zero callers, so flipping a
  registry declaration broke no test. Every rounded threshold now routes through
  `_rounded(cfg, value, *governed_by)`, which reads the direction from the parameters that
  govern it; `gates.py` no longer imports `Polarity` at all.

### Changed — behaviour

- **`Config.default()` defaults to `beginner`** (D28), as PRD §2.0 declares. This halves
  `max_risk_per_trade_pct` (1.0% -> 0.5%), lowers `daily_loss_pct` (3% -> 2%),
  `max_open_positions` (3 -> 1) and `max_consecutive_losses` (3 -> 2). The PRD's worked
  examples are computed at the *experienced* preset and now say so explicitly.
- **`room_gate_multiple = 2.0` is legal again** (D26). `validate_couplings` rejected it while
  PRD §1, §2.0, §3.1.1 and §7 all state it is legal, citing a section that says
  "cannot go below 2.0" — which is `>=`, not `>`. The check is removed: `min_separation` is a
  MINIMUM-polarity threshold over a strictly positive quantity (`sep_cost_multiple >= 1.0`,
  `est_round_trip_cost_per_share >= 0.001`), so it is at least one tick at every legal
  configuration and §3.1.2's separation term guarantees `entry < T1 < T2` whatever the
  proportional multiple is. At 2.0 the term is inert, not unsafe. (**Not** via
  `min_sep_r * R > 0`, which a first draft of this entry argued in six places — §2.0 permits
  `min_sep_r = 0.0`, so that product is exactly zero at a legal configuration.)
- **The three §2 risk settings are configurable** (D27). `max_risk_per_trade_pct`,
  `daily_loss_pct`, `max_open_positions` and `max_consecutive_losses` are registered
  parameters with the ranges §2 states (0.25–2%, 1–5%, 1–3, 2–5). `MODE_PRESETS` is now an
  overlay bundle applied on top of the registry defaults, which is what §2.0 calls it.
  `validate_couplings` checks the **effective** value against `HARD_CAPS` rather than the
  preset, which is a constant and could never have violated it.
- **`position_size` refuses a stop the §20.13 ceiling rejects**, raising `ValueError`. It
  never consulted `max_stop_pct`, so honouring the ceiling was a convention rather than an
  invariant; any path deriving a stop without `apply_stop_floor_and_ceiling` could size a
  trade the spec requires be skipped.
- **`Config` rejects an unknown `mode` at runtime.** `Literal` is a static hint, and the
  failure was previously a bare `KeyError: 'typo'` escaping from inside `validate_couplings`.

### Added — PRD §20 computations

The three subsections that need no market-data feed to be correct. All were fully specified
and entirely absent; §20.14 had a registered parameter and two `Reject` members that no code
returned.

- **`tradipy.quotes` (§20.14)** — `Quote`, `check_quote`, `spread_at_signal`,
  `estimated_spread`. Spread is `ask - bid` from the NBBO; odd-lot or one-sided quotes are
  `DATA_QUALITY_DEGRADED`, `ask <= bid` is `QUOTE_CROSSED` and is never clamped to zero, and
  a quote older than `quote_stale_seconds` at bar close is `QUOTE_STALE`.
- **`tradipy.bars` (§20.4)** — `Bar`, `green_runs`, `flagpole_ending_at`, `select_flagpole`,
  `flagpole_height`, `measured_move`, `retrace_pct`. §3.2 criterion 2's three thresholds have
  no registry entry, so `select_flagpole` takes the qualification test as a caller-supplied
  predicate rather than inventing them.
- **`tradipy.score` (§20.10, §14.2)** — `Catalyst`, `ScoreInputs`, `Score`,
  `composite_score`, `meets_conviction_gate`. §20.10's promise that the score lands in [0, 1]
  holds only if the five weights sum to 1, which is now a coupling check.
- **`tradipy.rejects`** — the `Reject` enum, moved out of `gates` so `quotes` does not have to
  depend on it. Re-exported from `tradipy.gates`, so existing imports still work. Gained
  `DATA_QUALITY_DEGRADED`.

### Added — a runnable proof of concept

- **`python -m tradipy demo`** replays the three PRD §3 worked examples through every gate,
  printing each verdict and its arithmetic, and self-checks every derived value against the
  tables. Exit 1 on disagreement. §3.2's stop, flag high, flagpole height and T2 are derived
  from a bar series via §20.4 rather than transcribed, which is what §21.1 asks
  worked-example fixtures to do.
- **`python -m tradipy evaluate --entry ... --stop ... --resistance ...`** runs one candidate
  of your own through the same chain. Exit 0 accept, 3 reject. Optional `--rvol` and friends
  add the §20.10 score. Stdlib `argparse` only — still no runtime dependencies.
- **`tradipy.poc`** — the composition layer both use. Explicitly *not* the strategy engine: it
  takes a candidate that has already been found.

### Added — registry and tests

- 18 new registered parameters: the four §2 risk settings; §2's `min_premarket_volume`,
  `max_vwap_extension_open_pct` and `hod_proximity_pct` (all previously prose-only); §20.10's
  five weights, four normalization caps and catalyst midpoint; and §14.2's
  `min_conviction_score`. 29 -> 47.
- Every `Param.source` now declares whether its bounds were **transcribed** from a PRD table
  or **originated here**. Roughly half were originated — §2, §3.1.1, §3.4, §20.10 and §20.14
  state defaults with no bounds column — while `params.py` claimed all of them came from the
  document. `test_code_originated_bounds_are_declared_as_such` enforces the distinction.
- `tests/test_enforcement.py` — the fifth defect class, **unenforced guarantee**: a rule that
  is stated, has a mechanism, is believed to be enforced, and is not. Invisible to all four
  earlier checks by construction.
- `tests/test_computations.py` and `tests/test_poc.py`.
- The suite is 153 cases (was 63) at 99% line and branch coverage (was 91%), verified against
  47 mutations, 47 caught. Twelve of those forty-seven survived a release candidate — every
  rounding direction and truncation outside the five gate thresholds was unenforced, because
  all three §3 worked examples are numerically degenerate. See `tests/README.md`.

### Fixed — documentation

- `docs/architecture.md` claimed every construction path validated individually *and*
  jointly. It did not; see above.
- `README.md`'s override example was labelled `tighter` and was in fact looser
  (`max_spread_r` is a MAXIMUM defaulting to 0.15, so 0.20 admits more), with a second
  override that restated the default and changed nothing.
- `docs/PLAN.md` (WS11, sequencing, risk table) and `docs/PRD.md` §19 marked the parameter
  registry, the §21.1 fixture suite and the rounding-direction assertions as outstanding.
  All were built and green.
- `docs/PRD.md` §3.4's sensitivity table labelled the `$4.05` row's binding term
  "proportional" while showing the separation term's value.
- `CHANGELOG.md` claimed BasedPyright was pinned to a minor series; the specifier is
  `>=1.39,<2`. The guarantee holds via `uv.lock` and CI's `--frozen`, and now says so.
- `scripts/regen_registry_baseline.py` printed "Done. Review the diff" even when pytest
  failed and no baseline had been written.

### Tooling, packaging and documentation

Merged into this release rather than kept as a separate one: it was sitting under
`[Unreleased]` and was never tagged.

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

- Minimum Python raised to 3.13.
- `tradipy/__init__.py` now imports its submodules, so the names it advertises in `__all__`
  resolve as attributes (`tradipy.gates` previously raised `AttributeError`).
- `Ladder` is exported from `tradipy.gates`; it is the return type of `exit_ladder` and was
  reachable but undeclared.
- Ruff is pinned to a minor series (`>=0.16,<0.17`) and BasedPyright to a major one
  (`>=1.39,<2`). Reproducibility across the pair comes from the committed `uv.lock` and CI's
  `uv sync --frozen`, not from the specifiers — an earlier entry here claimed both were
  pinned to a minor series, which was true of only one.
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

- The `trailing-whitespace` hook ran without `--markdown-linebreak-ext=md` and so stripped the
  hard line breaks from `docs/PRD.md`'s header, reflowing the normative document.
- `scripts/regen_registry_baseline.py` inherited environment: it replaced the child
  environment with two variables, dropping `HOME`, `TMPDIR`, and `VIRTUAL_ENV`.
- Documented installs referenced a `dev` extra that does not exist now that dev tools are a
  PEP 735 group; `pip install -e . --group dev` is the pip path.

### Migrating from 0.0.1

- `Config.default()` now returns a **beginner** config. Pass `mode="experienced"` to keep
  0.0.1's behaviour; every share count halves otherwise.
- `Config(values)` now rejects out-of-range values, unregistered names and unknown modes.
  A dict that used to construct may now raise `ValueError`.
- `position_size` raises `ValueError` when the stop exceeds `max_stop_pct × entry`. Check the
  `Reject` from `apply_stop_floor_and_ceiling` before sizing.
- `PARAMS`, `MODE_PRESETS` and `HARD_CAPS` are read-only. Code that mutated them — which was
  never supported and is what this release closes — now raises `TypeError`.
- `Reject` moved to `tradipy.rejects` and is re-exported from `tradipy.gates`; both import
  paths work.

## [0.0.1] - 2026-07-28

### Added

- Initial invariant layer: parameter registry (`params.py`), polarity-aware tick rounding
  (`rounding.py`), and pre-entry gates with position sizing (`gates.py`).
- Test suite defending four defect classes (worked examples, registry consistency, boundary
  and polarity invariants), verified by mutation testing.

[Unreleased]: https://github.com/prowler421/tradipy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/prowler421/tradipy/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/prowler421/tradipy/releases/tag/v0.0.1
