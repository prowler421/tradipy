# API reference

A summary of tradipy's public surface. Each module's `__all__` is authoritative; the
docstrings in the source carry the full normative detail and PRD citations.

All monetary values are `decimal.Decimal`.

## `tradipy.rounding`

Tick arithmetic and polarity-aware threshold rounding.

| Name | Signature | Description |
| --- | --- | --- |
| `TICK_SIZE` | `Decimal` | The tick size, `$0.01` (PRD §20.13). |
| `Polarity` | `Enum` | `MINIMUM` (value must exceed the threshold) or `MAXIMUM` (value must stay under it). |
| `floor_to_tick` | `(value) -> Decimal` | Round down to the nearest whole tick. |
| `ceil_to_tick` | `(value) -> Decimal` | Round up to the nearest whole tick. |
| `is_whole_tick` | `(value) -> bool` | True if `value` is an exact tick multiple. |
| `round_threshold` | `(value, polarity) -> Decimal` | Round in the direction the polarity requires; clamps maxima to ≥ 1 tick. |

## `tradipy.params`

The parameter registry and validated configuration.

| Name | Kind | Description |
| --- | --- | --- |
| `Param` | frozen dataclass | A registered threshold: `name`, `default`, `lo`, `hi`, `unit`, `source`, optional `polarity`. `.validate(value)` raises `ValueError` if out of range. |
| `PARAMS` | `dict[str, Param]` | The registry — every tunable threshold, keyed by name. |
| `Config` | frozen dataclass | A validated parameter set. `values: Mapping[str, Decimal]`, `mode: "beginner" \| "experienced"`. |
| `Config.default(mode=...)` | classmethod | Build a validated config from the registry defaults. |
| `Config.with_overrides(**kw)` | method | Return a new config with named overrides; validates individually and jointly. |
| `Config[...]` / `.polarity(name)` | methods | Look up a value (falling back to the mode preset) / a threshold's polarity. |
| `MODE_PRESETS` | `dict` | Per-mode presets (risk, daily loss, open positions, consecutive losses). |
| `HARD_CAPS` | `dict` | Non-bypassable ceilings, independent of mode (PRD §2 / §7). |
| `CouplingError` | exception | Raised when individually-legal parameters cannot jointly hold. |
| `validate_couplings` | `(cfg) -> None` | Enforce cross-parameter coherence. |
| `signal_cap_ticks_at_min_r` | `(cfg) -> int` | Width, in ticks, of the signal-time spread cap at the tightest legal R (a documented-state helper). |
| `min_tradeable_price_from_stop_bounds` | `(cfg) -> Decimal` | Lowest entry price at which the stop floor and ceiling can both hold (a documented open finding). |
| `DISCRIMINATING_CAP_TICKS` | `int` | Aspirational minimum cap width (recorded, not enforced). |

## `tradipy.gates`

Pre-entry gates and position sizing. No threshold literal appears here; every value is read
from the registry.

| Name | Signature | Description |
| --- | --- | --- |
| `Reject` | `Enum` | Rejection reason codes (`SPREAD_TOO_WIDE`, `INSUFFICIENT_ROOM`, `TARGETS_TOO_CLOSE`, `STOP_TOO_WIDE`, `QUOTE_STALE`, `QUOTE_CROSSED`). |
| `SpreadCaps` | frozen dataclass | `scan`, `signal`, and the `binding` (tighter) cap. |
| `spread_caps` | `(price, r, cfg) -> SpreadCaps` | The scan-time and signal-time spread caps (PRD §3.1.3). |
| `check_spread` | `(spread, price, r, cfg) -> Reject \| None` | `None` if the spread passes both gates. |
| `min_separation` | `(r, spread, cfg) -> Decimal` | Minimum permissible `T2 − T1` (PRD §3.1.2). |
| `RoomRequirement` | frozen dataclass | `required`, `binding` reason, and the two unrounded terms. |
| `required_room` | `(r, spread, cfg) -> RoomRequirement` | Distance to nearest resistance a setup must have. |
| `check_room` | `(entry, resistance, r, spread, cfg) -> Reject \| None` | `None` if there is enough room. |
| `Ladder` | frozen dataclass | `t1`, `t2`, and `.ordered_above(entry)` for the §3.1.1 `entry < T1 < T2` constraint. |
| `exit_ladder` | `(entry, r, structural_target, cfg) -> Ladder` | T1 at `t1_r_multiple`·R, T2 at the structural level. |
| `apply_stop_floor_and_ceiling` | `(entry, raw_stop, cfg) -> (Decimal, Reject \| None)` | Tick round, min-stop floor, then max-stop skip test. |
| `vwap_reclaim_stop` | `(entry, dip_low, vwap, cfg) -> (Decimal, Reject \| None)` | The §3.4 stop chain; returns the level *and* the skip verdict. |
| `position_size` | `(entry, effective_stop, cfg, *, buying_power=None, adv_shares=None) -> int` | Shares to buy (PRD §2.2), floored and capped. |

### Example

```python
from decimal import Decimal
from tradipy.params import Config
from tradipy.gates import required_room, check_room

cfg = Config.default()
req = required_room(Decimal("0.15"), Decimal("0.02"), cfg)
print(req.required, req.binding)  # rounded requirement + which term bound it

verdict = check_room(Decimal("5.00"), Decimal("5.60"), Decimal("0.15"), Decimal("0.02"), cfg)
print(verdict)  # None if there is enough room, else the binding Reject code
```
