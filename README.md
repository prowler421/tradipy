# tradipy

The **invariant layer** of a Ross Cameron momentum day-trading system. tradipy takes the
rules established over six independent review rounds of [`docs/PRD.md`](docs/PRD.md) and
makes them executable and tested, rather than prose. It is deliberately *not* the strategy
engine — it is the layer that guarantees the strategy engine cannot violate its own
specification.

- **Status:** Phase 1 (invariant layer + runnable PoC). Alpha.
- **Runtime dependencies:** none. Standard library only (`Decimal`, `dataclasses`, `enum`).
- **Python:** 3.13+.

## Why it exists

Six review rounds have each found a distinct defect class that the check built for the
previous round could not see: an arithmetic error; a threshold restated inconsistently; two
individually-legal parameters that could not both hold; a rounding rule stated more broadly
than its justification; once the document was hardened, a rule the documentation said was
enforced with a mechanism built for it that nothing actually called; and once the library was
wired, measurement code that restated the library's arithmetic while claiming to use it.
This package encodes the rules so they are enforced by tests rather than by vigilance, and
every guarantee it states has a test that performs the violation it forbids. See
[`docs/PLAN.md`](docs/PLAN.md) Workstream 11 for the full defect-class table.

## Try it

```bash
uv run python -m tradipy demo
```

Replays the three PRD §3 worked examples through every gate, showing the arithmetic, and
fails if any derived value disagrees with the document's own tables. Then run your own:

```bash
uv run python -m tradipy evaluate --entry 4.00 --stop 3.90 --resistance 4.26
#   FAIL  room gate  §3.1.2  available 0.26 vs required 0.28 ...  [TARGETS_TOO_CLOSE]
#   ->  REJECT  TARGETS_TOO_CLOSE
```

Exit codes: `0` accept, `1` demo self-check failed, `2` usage error, `3` candidate rejected.

## Architecture

Small, pure modules with a strict one-way dependency graph. `rounding`, `rejects` and `bars`
depend on nothing but the standard library, and only `__main__` depends on `poc`.

| Module | Responsibility |
| --- | --- |
| `tradipy.rounding` | Tick arithmetic and polarity-aware threshold rounding. *Rounding must never weaken a constraint.* |
| `tradipy.rejects` | The `Reject` reason codes, each citing the PRD section that defines it. |
| `tradipy.params` | The parameter registry — the single source of truth for every threshold: default, legal range, source citation, and polarity. Plus mode presets, hard caps, and the coupling validator. |
| `tradipy.bars` | PRD §20.4 — flagpole detection, height, measured move, retrace. |
| `tradipy.quotes` | PRD §20.14 — NBBO spread, quote validity, staleness, crossed markets. |
| `tradipy.score` | PRD §20.10 / §14.2 — the normalized composite score and the conviction gate. |
| `tradipy.gates` | Pre-entry gates and sizing: spread caps, separation floor, room requirement, exit ladder, stop construction, position size. No threshold literal appears here, and no rounding direction either — both are read from the registry by name. |
| `tradipy.poc` | Composes the gates into one evaluation. Explicitly *not* the strategy engine: it takes a candidate that has already been found. |

Everything that touches money uses `Decimal`. See [`docs/architecture.md`](docs/architecture.md)
for the full picture and the design invariants.

## Installation

tradipy uses [uv](https://docs.astral.sh/uv/). Install uv, then:

```bash
git clone https://github.com/prowler421/tradipy.git
cd tradipy
uv sync            # creates .venv and installs the dev group
```

Without uv, an editable install works too. The dev tools are a PEP 735 dependency group, not
an extra, so ask for the group by name: `pip install -e . --group dev` (pip 25.1+).

## Quick start

```python
from decimal import Decimal
from tradipy.params import Config
from tradipy.gates import position_size, spread_caps, vwap_reclaim_stop
from tradipy.quotes import Quote, spread_at_signal

cfg = Config.default()  # validated defaults, "beginner" mode (PRD §2.0)

# Spread gate caps for a $5.00 name with R = $0.15
caps = spread_caps(Decimal("5.00"), Decimal("0.15"), cfg)
print(caps.scan, caps.signal, caps.binding)  # 0.02 0.02 0.02

# Position size: 0.5% of $30k equity risked over a $0.10 stop distance
shares = position_size(Decimal("5.00"), Decimal("4.90"), cfg)
print(shares)  # 1500 — 3000 with mode="experienced"

# §3.4 VWAP-reclaim stop, returning both the level and the skip verdict.
# Destructure both: the verdict is the whole point, and dropping it once
# meant a trade the spec requires be skipped got a live stop instead.
stop, verdict = vwap_reclaim_stop(Decimal("3.83"), Decimal("3.74"), Decimal("3.80"), cfg)
print(stop, verdict)  # 3.73 None

# §20.14: a quote is only a spread if it is two-sided, fresh and uncrossed
quote = Quote(Decimal("3.82"), Decimal("3.83"), 500, 500, age_seconds=Decimal("0.5"))
print(spread_at_signal(quote, cfg))  # (Decimal('0.01'), None)
```

## Examples

More worked examples live in the test suite, which is written to be read:
[`tests/test_worked_examples.py`](tests/test_worked_examples.py) walks the PRD's own
scenarios, and [`tests/README.md`](tests/README.md) explains what each file defends against.
`python -m tradipy demo` runs the same scenarios end to end with the arithmetic shown.

> **Note on the default mode.** PRD §2.0 declares `beginner` the default, and that is what
> `Config.default()` returns. The PRD's §3 worked examples are all computed at the
> `experienced` preset (1% × $30,000), so reproducing their share counts means asking for it:
> `Config.default(mode="experienced")`. See [PLAN](docs/PLAN.md) D28.

## Configuration

There is no configuration file and there are no environment variables in the runtime path.
All tunable thresholds are registered in `tradipy.params.PARAMS`, each with a default, a
legal range, a source citation into the PRD, and (where used as a gate) a polarity. Build a
config from the defaults and override by name:

```python
cfg = Config.default(mode="experienced")

# max_spread_r is a MAXIMUM, so a smaller value is the stricter one.
stricter = cfg.with_overrides(max_spread_r="0.10", max_risk_per_trade_pct="0.005")
```

Every construction path validates individually *and* jointly, including `Config(values)`
directly. `ValueError` for an out-of-range value, an unregistered name, an unknown mode or an
incomplete mapping; `KeyError` for an unregistered name passed to `with_overrides`; and
`CouplingError` for a combination that is individually legal but jointly incoherent — a
`min_stop_distance` too tight for `max_spread_r`, a risk setting above its §7 cap, or
composite-score weights that do not sum to 1.

`PARAMS`, `MODE_PRESETS` and `HARD_CAPS` are read-only mappings. A frozen dataclass in front
of a mutable module global is not frozen, which is how a single assignment used to raise an
already-validated config's risk-per-trade past a cap the PRD calls non-bypassable.

### Environment variables

The runtime uses none. One test-only variable exists:

| Variable | Used by | Purpose |
| --- | --- | --- |
| `REGEN_REGISTRY_BASELINE` | `tests/test_parameter_registry.py` | When set, rewrites `tests/registry_baseline.json` instead of asserting against it. Prefer `uv run python scripts/regen_registry_baseline.py`. |

## Development workflow

```bash
make install     # uv sync + install pre-commit hooks
make check       # lint + format check + typecheck + test (what CI runs)
make test        # pytest
make coverage    # pytest with coverage report
make lint        # ruff check
make format      # ruff format
make format-check # ruff format --check (no rewrite)
make typecheck   # basedpyright
make clean       # remove caches and build artifacts
make help        # list all targets
```

See [`docs/development.md`](docs/development.md) for the details.

## Testing

```bash
uv run pytest
uv run pytest -m boundary      # only boundary-marked tests
uv run pytest --cov=tradipy
```

The suite uses three custom markers — `spec`, `boundary`, `polarity` — described in
[`tests/README.md`](tests/README.md). Assertions are written against the derivation of a
value, not the value itself, so a wrong rule that happens to agree at one input is still
caught.

## Linting and type checking

Ruff is the single tool for linting and formatting (replacing flake8, isort, pycodestyle,
and autoflake). BasedPyright is the type checker. Both are configured in `pyproject.toml`
and run in CI and via pre-commit.

## Release process

Semantic Versioning + [Keep a Changelog](https://keepachangelog.com/). Bump `version` in
`pyproject.toml`, add a dated section to [`CHANGELOG.md`](CHANGELOG.md), commit, tag
`vX.Y.Z`, and push tags. The release workflow builds the sdist and wheel.

## Troubleshooting

- **`uv: command not found`** — install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- **`ModuleNotFoundError: tradipy`** — run inside the project via `uv run ...`; the package
  lives under `src/` and pytest is configured with `pythonpath = ["src"]`.
- **Type checker complains about a version** — tradipy targets 3.13; run `uv python install 3.13`.
- **A registry test fails after editing the PRD** — this is usually intentional. Read the
  diff, then regenerate deliberately with `uv run python scripts/regen_registry_baseline.py`.

## License

[MIT](LICENSE). *(Placeholder — change if this project should not be MIT-licensed.)*
