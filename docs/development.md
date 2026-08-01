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

## Project layout

```
src/tradipy/
    __init__.py     imports and re-exports the fifteen library modules
    rounding.py     tick arithmetic, Polarity, round_threshold        (§20.13)
    rejects.py      Reject, SoftFlag, ExitReason, RiskBlock — four namespaces
    params.py       the parameter registry, Config, coupling validator (§2, §2.0)
    bars.py         flagpole geometry and measured move                (§20.4)
    quotes.py       NBBO quote validity and spread_at_signal           (§20.14)
    score.py        composite score and the conviction gate      (§20.10, §14.2)
    gates.py        pre-entry gates and position sizing         (§2.2, §3.1.x)
    scanner.py      the §4.2 hard filters, soft flags and ranking  (§4.1-§4.3)
    session.py      VWAP, HOD, EMA and the gap rule over a series (§20.1-§20.6)
    setups.py       the three MVP setups and §20.11 arbitration    (§3.2-§3.4)
    positions.py    the §20.12 state machine and the §3.1.1 ladder split
    risk.py         §6.3's pre-order checks and §7's rule table
    orders.py       §6.1 bracket construction and §6.7's key — submits nothing
    daily.py        §10's daily_state, §20.8's snapshot, §9.2's ClosedTrade — no store
    monitor.py      §7's other five enforcement points — flattens nothing
    poc.py          composition: one candidate through every gate, plus the
                    simulated universe behind `scan`
    __main__.py     the `python -m tradipy` CLI entry point
tests/              fourteen pytest files (see below) + registry_baseline.json
docs/               PRD.md (normative), PLAN, CHANGELOG, PHASE-2A-SPIKE,
                    reviews/, these guides
scripts/            regen_registry_baseline.py, check_links.py
    spike2a/        the Phase 2a spike — throwaway, in the registry lint's scope, and
                    suspended by D30. provenance.py is the exception: it is the D30
                    gate, it is tested, and it is not throwaway
data/spike2a/       spike inputs. Gitignored; empty on a clean clone; every file
                    simulated and declared in PROVENANCE.txt (D30)
.github/workflows/  ci.yml, release.yml
```

The dependency graph is one-way and shallow. `rounding`, `rejects` and `bars` import nothing
from the package; `params` imports `rounding`; `quotes` and `gates` import `params`, `rejects`
and `rounding`; `score` imports `params`; `poc` composes all of them, and `__main__` is a
front end over `poc`. Keeping an edge from pointing the other way is why `Reject` has its own
module: `gates` and `quotes` both raise it, and a quote is the lower-level construct, so
leaving the enum in `gates` would have made `quotes` depend on `gates`.

`docs/api.md` documents every name in every module's `__all__`.

## Everyday commands

| Command | What it does |
| --- | --- |
| `make check` | Lint, format check, type check, **links**, test — the gate CI runs. Run before committing, and read the output: review round 7 found this gate red at `3545adf`, tripped by the commit before it, with four documents asserting the guardrail was enforced. Note that **pre-commit does not run `pytest`**, so the hooks passing is not this gate passing. |
| `make test` | Run the pytest suite. |
| `make coverage` | Tests with a coverage report (term + `coverage.xml`). |
| `make lint` | `ruff check src tests scripts`. |
| `make format` | `ruff format` — rewrites files. |
| `make format-check` | `ruff format --check` — verifies without rewriting; part of `make check`. |
| `make typecheck` | `basedpyright`. |
| `make run` | Run a package module, e.g. `make run ARGS="-m tradipy demo"`. |
| `make sync` | Sync the environment to `uv.lock`. |
| `make precommit` | Run every pre-commit hook against every file. |
| `make clean` | Remove caches and build artifacts. |
| `make docs` | List the files in `docs/`. |
| `make release` | Print the release checklist. |
| `make help` | List every target. |

Run a subset of tests directly:

```bash
uv run pytest -m boundary            # only boundary-marked tests
uv run pytest tests/test_poc.py -vv
```

## Running the proof of concept

`python -m tradipy` makes the invariant layer runnable, so the rules can be exercised against
arbitrary inputs instead of only against the fixtures. It is **not** the strategy engine: it
takes a candidate that has already been found — entry, stop, structural target, resistance and
a quote — and applies the gates in the order PRD §3.1 states them. Under uv, prefix everything
below with `uv run`.

### `demo`

Replays the three PRD §3 worked examples through every gate and self-checks each derived value
against the tables. It exits 1 on any disagreement, which makes it a smoke test of the whole
layer as well as a demonstration: a table that drifts from its own rules fails instead of
passing quietly.

```console
$ uv run python -m tradipy demo
──────────────────────────────────────────────────────────────────────────────
tradipy Phase 1 — PRD §3 worked examples
──────────────────────────────────────────────────────────────────────────────
mode=experienced  start_of_day_equity=30000  max_risk_per_trade_pct=0.01

§20.4 flagpole geometry, derived from 8 bars:
  flagpole      bars [0..3], low 4.80 -> high 5.15
  height        0.35
  flag          high 5.12, low 5.05
  retrace       28.6%  (§3.2 crit. 3: <= 50%)
  flag/pole vol 0.55   (§3.2 crit. 5: <= 0.70, contraction)

§3.2 bull_flag  —  entry 5.16, resistance 5.51
  PASS  quote validity     §20.14   bid 5.15 x500 / ask 5.16 x500, age 0s -> spread 0.01
  PASS  stop construction  §20.13   raw 5.04 -> 5.04; R = 0.12; ceiling = 0.2580 (0.05 x 5.16)
  PASS  spread gate        §3.1.3   observed 0.01 vs binding cap 0.01 (scan 0.02, signal 0.01)
  PASS  room gate          §3.1.2   available 0.35 vs required 0.32 (proportional 0.300, separation 0.320)
  PASS  exit ladder        §3.1.1   T1 5.40 (2.0R), T2 5.51; ordering entry < T1 < T2 holds
  PASS  separation floor   §3.1.2   T2 - T1 = 0.11 vs floor 0.08 (cost term 3.0 x (0.01 + 0.015))
  PASS  position size      §2.2     2,500 sh = floor(300.00 / 0.12); risk at stop 300.00, notional 12900.00
  ->  ACCEPT

[§3.3 hod_breakout and §3.4 vwap_reclaim follow, in the same form]

──────────────────────────────────────────────────────────────────────────────
3/3 examples accepted by the gate chain.
Self-check OK — every derived value matches the PRD §3 tables.
```

`demo` is the default subcommand: bare `python -m tradipy` runs it. It is also the only thing
that runs in `experienced` mode by default. Every share count in the PRD's worked examples is
computed as 1% × $30,000, which is the experienced preset, while §2.0's declared default is
`beginner` (see D28 in `docs/CHANGELOG.md`). `--mode beginner` prints the different share
counts and *skips* the self-check rather than reporting a spurious failure.

### `evaluate`

Runs one candidate of your own through the same chain. `--entry`, `--stop` and `--resistance`
are required; `--stop` is the pattern-derived stop **before** the §20.13 floor and ceiling,
which the tool applies for you.

```console
$ uv run python -m tradipy evaluate --entry 6.48 --stop 6.34 --resistance 7.00
mode=beginner  equity=30000  risk=0.005

candidate  —  entry 6.48, resistance 7.00
  PASS  quote validity     §20.14   bid 6.47 x500 / ask 6.48 x500, age 0s -> spread 0.01
  PASS  stop construction  §20.13   raw 6.34 -> 6.34; R = 0.14; ceiling = 0.3240 (0.05 x 6.48)
  PASS  spread gate        §3.1.3   observed 0.01 vs binding cap 0.02 (scan 0.02, signal 0.02)
  PASS  room gate          §3.1.2   available 0.52 vs required 0.36 (proportional 0.350, separation 0.360)
  PASS  exit ladder        §3.1.1   T1 6.76 (2.0R), T2 7.00; ordering entry < T1 < T2 holds
  PASS  separation floor   §3.1.2   T2 - T1 = 0.24 vs floor 0.08 (cost term 3.0 x (0.01 + 0.015))
  PASS  position size      §2.2     1,071 sh = floor(150.000 / 0.14); risk at stop 149.94, notional 6940.08
  ->  ACCEPT
```

Every gate is reported, not only the first failure, because a candidate's other near-misses
are the useful part of the output. The one exception is an unusable quote: every later gate
consumes the spread, so the run stops there rather than reporting them against a fabricated
value. Move the resistance in and three gates fail at once:

```console
$ uv run python -m tradipy evaluate --entry 6.48 --stop 6.34 --resistance 6.70
mode=beginner  equity=30000  risk=0.005

candidate  —  entry 6.48, resistance 6.70
  PASS  quote validity     §20.14   bid 6.47 x500 / ask 6.48 x500, age 0s -> spread 0.01
  PASS  stop construction  §20.13   raw 6.34 -> 6.34; R = 0.14; ceiling = 0.3240 (0.05 x 6.48)
  PASS  spread gate        §3.1.3   observed 0.01 vs binding cap 0.02 (scan 0.02, signal 0.02)
  FAIL  room gate          §3.1.2   available 0.22 vs required 0.36 (proportional 0.350, separation 0.360)  [TARGETS_TOO_CLOSE]
  FAIL  exit ladder        §3.1.1   T1 6.76 (2.0R), T2 6.70; ordering entry < T1 < T2 VIOLATED  [TARGETS_TOO_CLOSE]
  FAIL  separation floor   §3.1.2   T2 - T1 = -0.06 vs floor 0.08 (cost term 3.0 x (0.01 + 0.015))  [TARGETS_TOO_CLOSE]
  PASS  position size      §2.2     1,071 sh = floor(150.000 / 0.14); risk at stop 149.94, notional 6940.08
  ->  REJECT  TARGETS_TOO_CLOSE
$ echo $?
3
```

The remaining flags: `--target` (T2; defaults to `--resistance`), `--spread` (defaults to one
tick), `--bid-size`, `--ask-size`, `--quote-age` and `--spread-estimated` for the §20.14 quote
validity test, and `--mode`. Passing `--rvol` additionally computes the §20.10 composite score
and the §14.2 conviction gate, and is what enables that block:

```console
$ uv run python -m tradipy evaluate --entry 6.48 --stop 6.34 --resistance 7.00 \
    --rvol 12 --pct-change 7.29 --float-shares 8000000 \
    --premarket-volume 450000 --catalyst headline_only
[gate chain as above]

  §20.10 composite score  0.4387  (gate >= 0.7: FAIL)
      pct_change      0.1458
      rvol            0.6000
      float_inverse   0.6000
      premarket_vol   0.4500
      catalyst        0.5000
```

`--pct-change` is in **percent** units (`7.29` for a 7.29% move), matching §20.10; every
`_pct` parameter in the registry is a fraction, so this is the one place the two conventions
meet.

### `scan`

Runs a **simulated** universe through PRD §4.2's seven hard filters and seven soft flags and
prints the §4.3 ranked watchlist. The universe is `tradipy.poc.simulated_universe` — fourteen
constructed candidates, seven that survive and seven that each fail exactly one hard row, so
every filter is visibly reachable and the `watchlist_size` truncation is visible too.

```console
$ uv run python -m tradipy scan
──────────────────────────────────────────────────────────────────────────────
tradipy Phase 3 — PRD §4.2 scanner over a simulated universe
──────────────────────────────────────────────────────────────────────────────
mode=beginner  watchlist_size=5

Data origin: SIMULATED (PLAN D30). ...

§4.2 evaluation — 14 candidate(s), 7 hard filters, 7 soft flags:
  PASS    SYNA     score 0.8090   flags: HIGH_SHORT_INTEREST
  ...
  REJECT  SYNLLD   NEAR_LULD   flags: HIGH_SHORT_INTEREST
            Circuit Breakers       nearest band 0.01 (up 0.01, down 1.4875) vs required 0.43

§4.3 watchlist — top 5 of 7 survivor(s):
  1.  SYNB     0.8160   pct_change 0.8200  rvol 0.9000  float 0.6900  ...
```

`--verbose` prints all fourteen §4.2 rows for every candidate rather than only the failing
ones, which is the quickest way to see that a soft flag on a passing name is advisory: the
flags are listed and the verdict is still `PASS`.

**Simulated is a policy position, not a shortcut.** PLAN **D30** puts the project on the
`SIMULATED` rung of the data ladder, and **D32** opened Phase 3 without advancing it. The
universe is constructed rather than read, so it touches no file and needs no `PROVENANCE.txt`
— the provenance gate constrains reads, and there are none. Consequently the filters are
applied correctly and no threshold is *calibrated*: Phase 2a Q1 is unanswered. See
[PHASE-3-READINESS.md](PHASE-3-READINESS.md).

### `monitor`

Runs one session through PRD §7's **other five** enforcement points — the ones
[`risk`](#exit-codes) does not cover, because `risk.approve` is the *Pre-order* column and §7
names six. §20.8 opens the session with no equity and refuses to be evaluated; a §9.2
`ClosedTrade` derived from §3.2's own signal is accrued at *Post-trade close*; the daily-loss row
is driven to its limit and produces §7's *"Flatten all; lock account for day"*; §7 row 8 fires at
*End of day* and locks **tomorrow** rather than today; and `flatten_all` prints one directive per
open state, four of which §20.12 cannot record.

Every figure is derived from the §3.2 bar series and the registry — nothing in the output is a
number a reader typed. It exits 1 if §20.8 lets an unopened session reach §7's rules, if a
breached daily-loss row fails to require a flatten, or if §20.12 turns out to record every
flatten (which would mean the finding it prints has gone stale). **Nothing is flattened,
cancelled, sent or written**: this layer computes §7's Violation Action and stops, and there is
no 1-second loop because a cadence is a clock. See
[PHASE-6-DESIGN.md](PHASE-6-DESIGN.md).

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Success — the demo self-check passed, the scan ran, or the candidate was ACCEPTed |
| 1 | A self-check disagreed with the PRD (`demo`, `setups`, `risk` or `monitor`) |
| 2 | Usage error (argparse) |
| 3 | The candidate was REJECTed |

3 rather than 2 for a rejection: argparse already owns 2, and a rejected candidate is a
correct answer rather than a failure to run. `demo` only ever returns 0 or 1 and `scan` only
ever 0, so both can be wired into CI as smoke tests with no extra interpretation. Note that
`scan` returning 0 says the pipeline ran, not that anything reached the watchlist — an empty
watchlist is a correct answer.

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
- Ruff owns formatting and import order at a line length of 100. Do not hand-format; run
  `make format`.
- Keep functions small and explicitly typed. Prefer readability over cleverness.

Two deliberate configurations to leave alone. The `PARAMS` registry in `params.py` is fenced
with `# fmt: off` / `# fmt: on`: it is a row-by-row transcription of the PRD's §2 / §2.0
tables and is reviewed against them, so one parameter per line is the point, and Ruff would
expand every row carrying a `polarity=` keyword into a multi-line block. And the PRD's `×`,
`–` and `−` glyphs are allow-listed in Ruff's `allowed-confusables` rather than switching
RUF001-003 off, so an accidental homoglyph is still caught; ASCII-ifying them in the source
would also break the PRD scanner in `test_parameter_registry.py`, which searches for a literal
`×`. Do not widen either exemption.

## Type checking

BasedPyright runs in `standard` mode over `src`, `tests` and `scripts` (configured in
`pyproject.toml`). Prefer fixing a type error over suppressing it; when a suppression is
genuinely warranted, use a narrow `# pyright: ignore[ruleName]` with a comment explaining why.

## Testing philosophy

Assertions are written against the **derivation** of a value, not the value itself:
`assert cap == Decimal("0.01")` passes under a wrong rounding rule that happens to agree at
that input, while `assert cap == floor_to_tick(x) and cap <= x` does not.

Nine files. The first four each defend a defect class that the check built for the previous
one could not see; the next two cover the §20 computations and the PoC; the seventh defends the
documentation's own counts; the last two defend the instrument that produces spec-deciding
numbers and the §7 sample definition it ranges over.

- `test_worked_examples.py` — **arithmetic**: an example that violates its own rules. PRD
  v1.0 shipped four, and all four passed a fully-ticked acceptance checklist.
- `test_parameter_registry.py` — **consistency**: a registered threshold restated as a
  literal, in `src/` or in PRD prose, with one copy updated and the other left behind.
- `test_boundary.py` — **joint incoherence** (`boundary` marks): two individually-legal
  parameters that cannot both hold, tested at the limit the filters themselves admit rather
  than at an illustrative value. Also **generalization** (`polarity` marks): a rounding rule
  stated more broadly than its justification supports.
- `test_enforcement.py` — **unenforced guarantee**: a rule that is stated normatively, has a
  mechanism built for it, is believed to be enforced, and is not. Invisible to all four
  earlier checks by construction: the rule appears once, the values are correct, the boundary
  behaves as documented and the direction is right. None of them asks whether the mechanism
  is wired to anything, and the documentation asserting that it is, is what stops anyone
  checking.
- `test_computations.py` — the three §20 computations that need no feed: §20.4 flagpole
  geometry, §20.10 composite score, §20.14 quote validity. Each was fully specified and
  entirely absent from the code through v0.0.1.
- `test_poc.py` — the PoC chain and the CLI, including that the demo's self-check is not
  vacuous. A demo that silently stops checking is worse than no demo, because its green
  output is what people trust instead of reading the code.
- `test_spike2a_instrumentation.py` — **unvalidated instrument**: spike code that produces
  spec-deciding numbers while restating the library. The sixth defect class, found when a
  hand-derived R in the generator moved a §7 verdict from INERT to CALIBRATED under a docstring
  claiming the library's stop functions.
- `test_documentation.py` — the **documentation's own counts**: registered parameters, frozen
  baseline entries, library modules, the re-exported count in `__all__`, every `Reject` member
  documented, every declared marker documented and applied. The v1.2 class applied to prose.
  Note what it does not range over, because review round 7 found all four drifted: the number of
  test files, the number of test cases, the number of documents in `docs/`, and the composition of
  `scripts/`.

Three markers, declared in `pyproject.toml` and enforced by `--strict-markers`:

- `spec` — asserts a rule stated normatively in `docs/PRD.md`.
- `boundary` — asserts behaviour at a filter's own limit, not at an illustrative value.
- `polarity` — asserts a rounding direction follows from constraint polarity (PRD §20.13).

The suite is verified by mutation testing;
[`../tests/README.md`](../tests/README.md) records what each mutation killed, the open spec
findings the tests pin, and why the mutant tree must include `docs/`.

`python -m tradipy demo` is a check of a different kind, outside pytest: it exercises the
whole chain end to end and exits non-zero when a derived value disagrees with the PRD tables.

### The mutation protocol

The "47 of 47 mutations caught" figure the PLAN and root `CHANGELOG.md` cite was produced by
hand and **is not automated**. That is a deliberate limitation, stated here rather than papered
over with a `make` target that does not work: a mutation harness whose own correctness has not
been demonstrated is a mechanism built and not wired, which is the defect class this project
exists to prevent.

Until it is automated, the protocol is manual and should be run whenever the rounding, registry,
or gate arithmetic changes:

1. Pick a mutation that a *wrong but plausible* implementation would make. The productive
   families here are rounding direction (`ceil` ↔ `floor` ↔ `round`), truncation
   (`//` ↔ `/`), comparison strictness (`<` ↔ `<=`), and polarity declarations in the registry.
2. Apply it to one place in `src/tradipy/`.
3. Run `make test`. **The suite must fail.** If it passes, you have found a hole — write the
   test that closes it before reverting the mutation.
4. Revert. Never commit with a mutation in place.

`tests/README.md` records the families already covered and which test kills each. Two cautions
it also records, both learned the hard way:

- **The three PRD §3 worked examples are numerically degenerate** — whole-tick levels, exact
  risk divisions — so `ceil`, `floor` and `round` agree on every one of them. Twelve rounding
  mutations survived the entire suite because of this. Mutate against the `NON_TICK_R` /
  `NON_TICK_CFG` block in `tests/test_boundary.py`, not the worked examples.
- **The mutant tree must include `docs/`**, because the registry lint reads PRD prose. A
  mutation confined to `src/` cannot exercise it.

`make links` and `tests/test_documentation.py` cover the two classes that *are* mechanised:
broken relative citations, and counts stated in prose that no longer match the code.

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

The release workflow (`.github/workflows/release.yml`) runs `make check`, then builds the sdist
and wheel with `uv build`. Publishing to an index is left as a commented, opt-in step.

## Continuous integration

`.github/workflows/ci.yml` runs on every push to `main` and every pull request: install uv,
cache by `uv.lock`, `uv sync --frozen`, then Ruff lint, Ruff format check, BasedPyright, the
documentation link check, and pytest with coverage. Those are the steps of `make check`, split
up so a failure names itself in the UI. Keep the two in step — if you change one, change the
other.

Coverage carries a **floor of 95%** (`fail_under` in `pyproject.toml`), which is deliberately
below the ~99% the documentation records. The floor exists to fail on collapse, not to pin the
measurement: a floor equal to the current score fails on the next honest commit, and a gate that
fails for a non-reason gets removed rather than heeded. Raise it deliberately, with the new
measurement in the commit message.

`.github/dependabot.yml` proposes monthly GitHub Actions bumps and **nothing else**. The runtime
is stdlib-only and `uv.lock` pins the dev group; a bot opening PRs against a lockfile whose job
is not to move on its own would be noise. Actions are different — they rot silently as runners
change, and a stale one fails the build for reasons unrelated to the change under test.

Both workflows declare `permissions: contents: read`. The release workflow additionally
refuses to build when the pushed tag disagrees with `version` in `pyproject.toml`.
