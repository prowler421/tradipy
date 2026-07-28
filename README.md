# tradipy

The **invariant layer** of a Ross Cameron momentum day-trading system. tradipy takes the
rules established over four review rounds of [`docs/PRD.md`](docs/PRD.md) and makes them
executable and tested, rather than prose. It is deliberately *not* the strategy engine — it
is the layer that guarantees the strategy engine cannot violate its own specification.

- **Status:** Phase 1 (invariant fixtures). Alpha.
- **Runtime dependencies:** none. Standard library only (`Decimal`, `dataclasses`, `enum`).
- **Python:** 3.13+.

## Why it exists

Each of four review rounds of the PRD found a distinct defect class that the check built for
the previous round could not see — an arithmetic error, a threshold restated inconsistently,
two individually-legal parameters that could not both hold, and a rounding rule stated more
broadly than its justification. Prose review caught all four; nothing stops a fifth landing
silently. This package encodes the rules so they are enforced by tests, not vigilance.

## Architecture

Three small, pure modules, with a strict one-way dependency: `rounding` ← `params` ← `gates`.

| Module | Responsibility |
| --- | --- |
| `tradipy.rounding` | Tick arithmetic and polarity-aware threshold rounding. *Rounding must never weaken a constraint.* |
| `tradipy.params` | The parameter registry — the single source of truth for every threshold, its legal range, source, and polarity. Plus mode presets, hard caps, and the coupling validator. |
| `tradipy.gates` | Pre-entry gates and sizing: spread caps, separation floor, room requirement, exit ladder, stop construction, position size. No threshold literal appears here — every value is read from the registry by name. |

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

cfg = Config.default()  # validated defaults, "experienced" mode

# Spread gate caps for a $5.00 name with R = $0.15
caps = spread_caps(Decimal("5.00"), Decimal("0.15"), cfg)
print(caps.scan, caps.signal, caps.binding)

# Position size: 1% of $30k equity risked over a $0.10 stop distance
shares = position_size(Decimal("5.00"), Decimal("4.90"), cfg)
print(shares)  # 3000

# §3.4 VWAP-reclaim stop, returning both the level and the skip verdict
stop, verdict = vwap_reclaim_stop(Decimal("3.80"), Decimal("3.50"), Decimal("3.80"), cfg)
print(stop, verdict)
```

## Examples

More worked examples live in the test suite, which is written to be read:
[`tests/test_worked_examples.py`](tests/test_worked_examples.py) walks the PRD's own
scenarios, and [`tests/README.md`](tests/README.md) explains what each file defends against.

## Configuration

There is no configuration file and there are no environment variables in the runtime path.
All tunable thresholds are registered in `tradipy.params.PARAMS`, each with a default, a
legal range, a source citation into the PRD, and (where used as a gate) a polarity. Build a
config from the defaults and override by name:

```python
cfg = Config.default(mode="beginner")
tighter = cfg.with_overrides(max_spread_r="0.20", room_gate_multiple="2.5")
```

Overrides are validated individually *and* jointly — `with_overrides` raises `ValueError`
for an out-of-range value and `CouplingError` for a combination that is individually legal
but jointly incoherent.

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
