# API reference

Every public name in every module's `__all__`, with the signature as it appears in the
source. Each module's `__all__` is authoritative; the docstrings carry the full normative
detail and the PRD citations, and [`PRD.md`](PRD.md) §20 governs on any conflict.

All monetary values are `decimal.Decimal`. No `float` appears anywhere a price is compared
against a tick boundary or summed into P&L (PRD §9.2).

## Package layout

Sixteen library modules and a `__main__` CLI entry point, with a strict one-way dependency
graph:

- `rounding`, `rejects`, `bars` — standard library only.
- `params` — depends on `rounding`.
- `quotes`, `gates` — depend on `params`, `rejects`, `rounding`.
- `score` — depends on `params`.
- `scanner` — depends on `params`, `rejects`, `score`, `gates`.
- `session` — depends on `bars` and `params` (PRD §20.1–§20.6 over an ordered series).
- `setups` — depends on `bars`, `session`, `params`, `rejects`, `gates` (PRD §3.2–§3.4).
- `positions` — depends on `params`, `rejects`, `rounding` (PRD §20.12's state machine, §3.1.1's
  stop management, §7.1.1's scale-in legality).
- `risk` — depends on `gates`, `params`, `positions`, `rejects`, `rounding`, `setups` (PRD §6.3's
  pre-trade checks and §7's rule table).
- `orders` — depends on `params`, `positions`, `rounding`, `setups` (PRD §6.1/§6.2/§6.4/§6.7
  order construction; **nothing that submits**).
- `daily` — depends on `params`, `rejects`, `risk`, `setups` (PRD §10's `daily_state`, §20.8's
  snapshot, §9.2's `ClosedTrade`, §7 row 4's accrual; **no store**).
- `monitor` — depends on `daily`, `params`, `positions`, `rejects`, `rounding`, `risk` (PRD §7's
  non-pre-order enforcement points and Violation Action column; **nothing that flattens**).
- `poc` — composes everything up to and including `setups` into one evaluable candidate, one
  simulated universe and the three §3 worked examples as bar series. It imports **none** of the
  five modules Phases 5 and 6 added; both phases compose at the CLI.
- `__main__` — the `python -m tradipy` front end over `poc`, `risk`/`orders` and
  `daily`/`monitor`.

`import tradipy` binds the fifteen library modules named in the package `__all__`
(`rounding`, `rejects`, `params`, `bars`, `quotes`, `score`, `gates`, `scanner`, `session`,
`setups`, `positions`, `risk`, `orders`, `daily`, `monitor`) as attributes. `tradipy.poc` is not among them and must be imported explicitly — it is the
proof-of-concept composition layer, not part of the invariant surface.

## `tradipy.rounding`

Tick arithmetic and polarity-aware threshold rounding (PRD §20.13).

```python
TICK_SIZE: Decimal  # Decimal("0.01")

class Polarity(Enum):
    MINIMUM = "minimum"   # the value must exceed the threshold
    MAXIMUM = "maximum"   # the value must stay under the threshold

def floor_to_tick(value: Decimal) -> Decimal
def ceil_to_tick(value: Decimal) -> Decimal
def round_threshold(value: Decimal, polarity: Polarity) -> Decimal
def is_whole_tick(value: Decimal) -> bool
```

- The governing principle is *rounding must never weaken a constraint*. `ceil` and `floor`
  are consequences of it; which applies is a property of the constraint, not of the call
  site.
- `round_threshold` rounds `MINIMUM` up, and rounds `MAXIMUM` down and then clamps the
  result to at least one tick. It raises `ValueError` for anything that is not a `Polarity`
  member — there is deliberately no default, because an unclassified threshold is a bug
  rather than something to guess at.
- The clamp on maxima is load-bearing. An unclamped maximum can floor to `$0.00`, which
  rejects every possible value: a silent kill switch rather than a filter.
- `is_whole_tick` exists because §20.13 requires rounding to happen once, at level
  computation, never at comparison time.

## `tradipy.rejects`

Rejection reason codes, the §4.2 soft flags that are deliberately *not* rejections, and the §3
post-entry exit reasons (PRD §3.1.2, §3.1.3, §4.2, §20.9, §20.12, §20.13, §20.14).

```python
class Reject(Enum):
    # PRD §4.2 hard filters — the scanner
    GAP_TOO_SMALL = "GAP_TOO_SMALL"  # §4.2
    RVOL_TOO_LOW = "RVOL_TOO_LOW"  # §4.2 / §20.7
    FLOAT_TOO_HIGH = "FLOAT_TOO_HIGH"  # §4.2 / D4
    PRICE_OUT_OF_RANGE = "PRICE_OUT_OF_RANGE"  # §4.2
    ADV_TOO_LOW = "ADV_TOO_LOW"  # §4.2
    NEAR_LULD = "NEAR_LULD"  # §4.2
    # PRD §3 pre-entry gates
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"  # §3.1.3 / §4.2
    INSUFFICIENT_ROOM = "INSUFFICIENT_ROOM"  # §3.1.1 / §3.1.2
    TARGETS_TOO_CLOSE = "TARGETS_TOO_CLOSE"  # §3.1.2
    STOP_TOO_WIDE = "STOP_TOO_WIDE"  # §2 / §3.2 / §20.13
    QUOTE_STALE = "QUOTE_STALE"  # §20.14
    QUOTE_CROSSED = "QUOTE_CROSSED"  # §20.14
    DATA_QUALITY_DEGRADED = "DATA_QUALITY_DEGRADED"  # §20.9 / §20.14
    # PRD §3.2 / §3.3 / §3.4 setup recognition — the one code Phase 4 adds
    SETUP_NOT_PRESENT = "SETUP_NOT_PRESENT"  # §3.2 / §3.3 / §3.4


class SoftFlag(Enum):
    PREMARKET_THIN = "PREMARKET_THIN"  # §4.2 (also a §20.10 input)
    MARKET_CAP_HIGH = "MARKET_CAP_HIGH"  # §4.2
    ATR_LOW = "ATR_LOW"  # §4.2
    NO_CATALYST = "NO_CATALYST"  # §4.2 (also a §20.10 input)
    RECENT_HALT = "RECENT_HALT"  # §4.2, "Soft (flag)"
    INST_OWN_HIGH = "INST_OWN_HIGH"  # §4.2 / A22 / D24 — disabled by default
    HIGH_SHORT_INTEREST = "HIGH_SHORT_INTEREST"  # §4.2, flag only


class ExitReason(Enum):
    BAILED_OUT = "BAILED_OUT"  # §20.12 / §3.2 / §3.3
    INVALIDATED = "INVALIDATED"  # §20.12 / §3.2 / §3.3 / §3.4
    # PRD §9.2's ClosedTrade.exit_reason — the other four (Phase 5)
    LADDER_COMPLETE = "LADDER_COMPLETE"  # §9.2 / §3.1.1 — the only non-failure exit
    STOPPED_OUT = "STOPPED_OUT"  # §9.2 / §20.12 — a state name as well
    EOD_FLAT = "EOD_FLAT"  # §9.2 / §7 trading-hours row
    KILL_SWITCH = "KILL_SWITCH"  # §9.2 / §7.2


class RiskBlock(Enum):              # PRD §7's rule table — the *account*, not the candidate
    MAX_RISK_EXCEEDED = "MAX_RISK_EXCEEDED"  # §7 row 1, NON-BYPASSABLE
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"  # §7 row 2, NON-BYPASSABLE
    MAX_POSITIONS = "MAX_POSITIONS"  # §7 row 3
    LOSS_STREAK_LOCKOUT = "LOSS_STREAK_LOCKOUT"  # §7 row 4 / §2 Three Strikes
    BUYING_POWER = "BUYING_POWER"  # §7 row 5 / §2.2
    PDT_VIOLATION = "PDT_VIOLATION"  # §7 row 6
    SESSION_DRAWDOWN = "SESSION_DRAWDOWN"  # §7 row 7 (Continuous — no caller yet)
    MULTI_DAY_DRAWDOWN = "MULTI_DAY_DRAWDOWN"  # §7 row 8 (End of day — no caller yet)
    OUTSIDE_SESSION_WINDOW = "OUTSIDE_SESSION_WINDOW"  # §7 row 9
    CORRELATED_EXPOSURE = "CORRELATED_EXPOSURE"  # §7 row 10 / §7.1.3 / D21
    TRADING_HALTED = "TRADING_HALTED"  # §7 row 11 / §7.2 / §7.1.2
    DUPLICATE_ORDER = "DUPLICATE_ORDER"  # §6.3 check 8 / §6.7
```

- The module holds both because three layers raise `Reject` — `gates` for the pre-entry
  gates, `quotes` for §20.14 validity, and `scanner` for §4.2's hard filters — and a quote is
  a lower-level construct than a gate. Keeping it in `gates` would have made `quotes` depend
  on `gates`, inverting the layering. `tradipy.gates` re-exports `Reject`, so
  `from tradipy.gates import Reject` still works.
- **`SoftFlag` is a separate enum, and that is the point.** §4.2 lists all fourteen rows
  under one "Rejection Code" column, seven Hard and seven Soft. Round 10's finding K5 is what
  that invites: a reader building from the shared column implements all fourteen as rejection
  paths, and `INST_OWN_HIGH` — which D24 keeps inert because §4.2's own note calls its
  premise doubtful — becomes a filter that discards candidates. Two unrelated types make that
  a type error. `ScanResult.reject` is `Reject | None` and cannot hold a flag;
  `test_enforcement.py` performs the violation at runtime anyway.
- Each member names the PRD section that defines the rejection, because a reason code
  invented by the implementation is a rule the specification has not agreed to.
  `STOP_TOO_WIDE` is the one exception: the PRD states the rule ("skip the trade") without
  naming a code, so the name is the implementation's and §4.2's table should adopt or
  replace it.
- `SPREAD_TOO_WIDE` covers §4.2's Liquidity/Spread row in full, which states *two* conditions
  under one code: a spread over the cap **and** a bid thinner than `min_quote_size`. A name
  nobody is bidding for in size is as unexecutable as one quoted too wide.
- `SETUP_NOT_PRESENT` is the **only** rejection code Phase 4 added: every other way a setup can
  be declined already had one, because those are §3.1's gates rather than each setup's criteria.
  `SetupOutcome.criteria` carries which part of the pattern was absent and the arithmetic behind
  it, so the single code loses no detail. Like `STOP_TOO_WIDE` it is a name the PRD does not
  state, and §4.2's table should adopt or replace it.
- **`RiskBlock` is a fourth namespace, K5's argument at one more remove.** A `Reject` says *this
  candidate is not tradeable*; a `RiskBlock` says *this account may not take this trade right now*,
  and the same candidate is fine tomorrow. Mixing them would let `scanner` filter a universe on
  `LOSS_STREAK_LOCKOUT`. There is also an asymmetry no shared enum can express: two §7 rows'
  Violation Action is *"Flatten all; lock account"*, which is not a rejection of anything.
  `RiskDecision.reason` is `RiskBlock | Reject | None`, which is what §9.2's own *"§7 rule name or
  §4.2 code"* describes — §7's two signal-time rows stay `Reject` members raised by `gates`, and
  giving them a second spelling here would be the v1.2 defect class.
- **`ExitReason` is a third namespace, on the same argument as the second.** A rejection declines
  a trade that was never taken; an exit closes one that was. Sharing a namespace would permit a
  pre-entry gate returning `BAILED_OUT` and an exit rule returning `SPREAD_TOO_WIDE`. Both member
  names are transcribed from §20.12's state machine rather than invented — the states themselves
  are Phase 5/6's, but the §3 rules that reach two of them are pure functions of the bars after
  entry, and taking §20.12's vocabulary is what lets the two halves meet later.

## `tradipy.params`

The parameter registry — the single source of truth for every tunable threshold.

```python
Mode = Literal["beginner", "experienced"]
MODES: tuple[str, ...]                             # ("beginner", "experienced")

PARAMS: Mapping[str, Param]                        # read-only; 86 entries
MODE_PRESETS: Mapping[str, Mapping[str, Decimal]]  # read-only, inner maps too
HARD_CAPS: Mapping[str, Decimal]                   # read-only
DISCRIMINATING_CAP_TICKS = 2

@dataclass(frozen=True)
class Param:
    name: str
    default: Decimal
    lo: Decimal
    hi: Decimal
    unit: str
    source: str
    polarity: Polarity | None = None

    def validate(self, value: Decimal) -> None

@dataclass(frozen=True)
class Config:
    values: Mapping[str, Decimal]
    mode: Mode = "beginner"

    def __getitem__(self, name: str) -> Decimal
    def polarity(self, name: str) -> Polarity
    def round_for(self, value: Decimal, *governed_by: str) -> Decimal

    @classmethod
    def default(cls, mode: Mode = "beginner") -> Config

    def with_overrides(self, **overrides: str | int | float | Decimal) -> Config

class CouplingError(ValueError)

def validate_couplings(cfg: Config) -> None
def signal_cap_ticks_at_min_r(cfg: Config) -> int
def min_tradeable_price_from_stop_bounds(cfg: Config) -> Decimal
```

### The registry

`PARAMS` holds **86** entries keyed by name, each carrying its default, legal range, unit,
PRD source citation, and — where it is used as a gate threshold — its polarity. A
threshold is defined there exactly once and every consumer reads it by name; no numeric
literal for a registered threshold may appear anywhere else in the package. The lint that
enforces this walks `src/tradipy/*.py` non-recursively plus `scripts/` recursively, skips
`params.py` and `__init__.py` inside `src/tradipy/` only, and exempts undistinctive values;
`tests/` is not scanned, because fixtures must state literals to assert derivations against.

`PARAMS`, `MODE_PRESETS` (including its inner preset maps) and `HARD_CAPS` are read-only
`Mapping`s. They were plain dicts read *live* by `Config.__getitem__` until v0.1.0, so a
single assignment could raise an already-validated config's risk-per-trade past the §7
non-bypassable cap with no validator re-running. A frozen dataclass in front of a mutable
module global is not frozen.

`Param.validate` raises `ValueError` when the value falls outside `[lo, hi]`; the message
names the parameter, the bounds and the PRD source.

### `Config` requires a complete mapping

`values` must contain **every** registered name and nothing else. `Config.__post_init__`
copies the mapping into a `MappingProxyType` and then validates, in this order:

1. `mode` must be in `MODES` — otherwise `ValueError`. `Literal` is a static hint with no
   runtime effect, so this is checked rather than assumed.
2. No registered name may be missing — a partial mapping raises `ValueError` naming the
   missing parameters. A `Config` without `room_gate_multiple` is not a config.
3. No unregistered name may be present — otherwise `ValueError`.
4. Every value is range-checked through `Param.validate` — otherwise `ValueError`.
5. `validate_couplings` runs last — otherwise `CouplingError` (a `ValueError` subclass).

Validation lives in `__post_init__` because that is the only construction path that cannot
be routed around. Ranges are checked *before* the couplings, because a coupling validator
reasoning about out-of-range inputs produces misleading errors.

### `Config` methods

- `Config.default(mode="beginner")` — registry defaults with the PRD §2.0 mode preset
  overlaid. Raises `ValueError` for a mode not in `MODES`. `beginner` is the default
  because §2.0 declares it; the PRD's own worked examples compute risk as 1% × $30,000,
  which is the *experienced* preset, so they pass `mode="experienced"` explicitly.
- `Config.with_overrides(**overrides)` — a new config with named overrides, each converted
  with `Decimal(str(raw))`. Raises `KeyError` for a name not in `PARAMS`. Everything else
  is validated by `__post_init__`, so overriding cannot reach a state that direct
  construction could not.
- `Config[name]` — the value. Raises `KeyError` for an unregistered name. There is no
  fallback to the mode preset: the preset is applied once, by `default()`, and the stored
  mapping is complete.
- `Config.polarity(name)` — the declared rounding direction. Raises `ValueError` when the
  parameter has no polarity, because §20.13 requires classification before a rounding
  function is chosen. Every rounding call routes through this rather than naming a
  `Polarity` member, so the registry field is the single source of truth for direction as
  well as for value.
- `Config.round_for(value, *governed_by)` — round `value` in the direction the registry
  declares for the named parameters. Raises `ValueError` when they disagree, or when any of
  them has no declared polarity, or when none is given: a threshold built from several
  parameters must have exactly one classification, and "no governing parameter" is not
  "any direction". This was `gates._rounded` until Phase 3, when `scanner` needed the same
  resolution; the alternatives were a private cross-module import or a second place naming a
  direction, and the second is the v1.3.1 defect. Direction is registry data, so resolving it
  belongs on the registry object. Carrying a polarity does **not** imply a value is rounded —
  a ratio has no tick to round to, so `min_gap_daily_pct`, `min_rvol` and
  `min_conviction_score` declare a direction and never reach this method.

### Coupling and documented-state helpers

- `validate_couplings(cfg)` raises `CouplingError` on three combinations that are legal
  per-parameter but jointly incoherent: `min_stop_distance` below `TICK_SIZE /
  max_spread_r` (the §3.1.3 signal cap would floor to `$0.00`); any of the three
  `HARD_CAPS` exceeded; and the five `score_weight_*` values not summing to exactly 1,
  which is what makes §20.10's score comparable to §14.2's gate.
- `signal_cap_ticks_at_min_r(cfg)` — how many ticks wide the §3.1.3 signal-time cap is at
  the tightest legal R. **1** at shipped defaults, i.e. the clamp floor, so for minimum-R
  trades the gate admits exactly one spread. `DISCRIMINATING_CAP_TICKS` is the width at
  which the gate would discriminate rather than admit a single value; it is recorded as an
  aspiration, not enforced.
- `min_tradeable_price_from_stop_bounds(cfg)` — `min_stop_distance / max_stop_pct`, **$2.00**
  at shipped defaults, against a `min_price` of $1.00. Below the crossover every entry is
  unconditionally `STOP_TOO_WIDE`. Deliberately *not* a `validate_couplings` check: the
  incoherent combination is the shipped default set, so raising would make
  `Config.default()` throw. Resolving it is a spec decision.

## `tradipy.bars`

Flagpole height and measured move (PRD §20.4).

```python
@dataclass(frozen=True)
class Bar:
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    @property
    def is_green(self) -> bool   # close > open; a doji is not green

def green_runs(bars: Sequence[Bar]) -> list[tuple[int, int]]
def flagpole_ending_at(bars: Sequence[Bar], end: int) -> tuple[int, int] | None
def select_flagpole(
    bars: Sequence[Bar],
    candidates: Sequence[tuple[int, int]],
    qualifies: Callable[[Sequence[Bar]], bool] | None = None,
) -> tuple[int, int] | None
def flagpole_height(pole: Sequence[Bar]) -> Decimal
def measured_move(entry: Decimal, height: Decimal) -> Decimal
def retrace_pct(flagpole_high: Decimal, flag_low: Decimal, height: Decimal) -> Decimal
```

- `Bar` carries no timestamp. §20.1 bar timing — labels, close detection, the 750 ms grace
  — is a separate subsection and needs an ingestion layer that does not exist at this
  layer.
- `green_runs` returns every *maximal* run of consecutive green bars as inclusive
  `(start, end)` index pairs, so the result is the candidate set before any §3.2
  qualification.
- `flagpole_ending_at` returns the maximal green run ending at `end`, or `None` when `end`
  is out of range or that bar is not green. §20.4's "ending immediately before the flag"
  pins one end of the run, so given a known flag start there is exactly one candidate and
  no tie is possible.
- `select_flagpole` is the search case: longest qualifying run wins, a tie on length is
  broken by greater total volume, and a tie on both returns the earlier run (§20.4 does not
  say, and deterministic beats arbitrary). `qualifies` is §3.2 criterion 2, supplied by the
  caller because its three thresholds have no registry entry — registering them here would
  be this module inventing spec. `None` applies no qualification.
- `flagpole_height` is `pole[-1].high - pole[0].low`, which is *not* `max(high) - min(low)`
  over the run; §20.4 names the first and last candles explicitly. Raises `ValueError` for
  an empty pole and for a non-positive height.
- `measured_move` returns `entry + height`, unrounded: §20.13 requires rounding once, at
  level computation, and for a target that is `gates.exit_ladder`.
- `retrace_pct` returns a fraction, not a percentage, matching every other `_pct` quantity
  in the registry. Raises `ValueError` when `height <= 0`.

## `tradipy.quotes`

NBBO quote validity and the definition of `spread_at_signal` (PRD §20.14).

```python
@dataclass(frozen=True)
class Quote:
    bid: Decimal
    ask: Decimal
    bid_size: int
    ask_size: int
    age_seconds: Decimal
    estimated: bool = False

    @property
    def spread(self) -> Decimal   # ask - bid; negative when crossed, deliberately

def check_quote(quote: Quote, cfg: Config) -> Reject | None
def spread_at_signal(quote: Quote, cfg: Config) -> tuple[Decimal | None, Reject | None]
def estimated_spread(price: Decimal, spread_pct_median: Decimal, cfg: Config) -> Decimal
```

- `age_seconds` is the quote's age **at bar close**, not at evaluation time, so a backtest
  and a live session reach the same verdict. `estimated` marks the §20.14 backtest
  substitute; those trades are reported separately in §8.3 and excluded from the §18.7
  viability gate, so the flag has to travel with the quote.
- `check_quote` returns `None` for a usable quote, else the first failure. The order is
  part of the contract:

  1. either side below `min_quote_size` → `DATA_QUALITY_DEGRADED` (a one-sided or
     odd-lot-only quote is not a spread, so this is asked first);
  2. `ask <= bid` → `QUOTE_CROSSED`, never clamped to zero, because a zero spread makes the
     §3.1.2 separation floor trivially satisfiable during exactly the dislocations that
     produce crossed quotes;
  3. `age_seconds > quote_stale_seconds` → `QUOTE_STALE`.

- `spread_at_signal` returns `(spread, None)` or `(None, reject)` — never both. An invalid
  quote's arithmetic difference is not a spread, and returning it invites a caller to gate
  on it.
- `estimated_spread` returns `max(1 tick, ceil_to_tick(spread_pct_median * price))`. §20.14
  states no rounding; rounding **up** is applied because understating a spread weakens two
  constraints at once — it lowers the §3.1.2 floor and makes the §3.1.3 gate easier to
  pass. Any `Quote` built from it must set `estimated=True`. `cfg` is accepted but unused
  today, so the tick and the rule stay together as this grows a per-symbol tick.
- Sampling — "the last NBBO quote at or before the close of the signal bar" — is a feed
  concern. This module validates whatever quote it is handed.

## `tradipy.score`

Composite score (PRD §20.10) and the §14.2 conviction gate.

```python
class Catalyst(Enum):
    CONFIRMED = "confirmed"
    HEADLINE_ONLY = "headline_only"
    NONE = "none"

    def weight(self, cfg: Config) -> Decimal

@dataclass(frozen=True)
class ScoreInputs:
    pct_change: Decimal
    rvol: Decimal
    float_shares: Decimal
    premarket_volume: Decimal
    catalyst: Catalyst

@dataclass(frozen=True)
class Score:
    total: Decimal
    pct_change: Decimal
    rvol: Decimal
    float_inverse: Decimal
    premarket_vol: Decimal
    catalyst: Decimal

def composite_score(inputs: ScoreInputs, cfg: Config) -> Score
def meets_conviction_gate(score: Score, cfg: Config) -> bool
```

- `ScoreInputs.pct_change` is in **percent units** (`7.29` for a 7.29% move), because
  §20.10's cap is written `pct_change / 50.0`. Every `_pct` parameter in the registry is a
  fraction, so this is the one place the two conventions meet, and getting it backwards
  silently divides the score's largest component by 100.
- `Catalyst.weight` returns `1` for `CONFIRMED`, `score_catalyst_headline` for
  `HEADLINE_ONLY` and `0` for `NONE`. The endpoints are structural — they are the range of
  a normalized input — so only the midpoint is a registered parameter.
- `composite_score` normalizes each input into `[0, 1]`, floored at 0 so a negative input
  cannot subtract score, and weights them by the five `score_weight_*` parameters. Every
  literal in §20.10 is registered: five weights, four caps and `score_catalyst_headline`.
- `Score` keeps the five components alongside the total. §14.4 records the objection that
  "a high score can be earned entirely on premarket volume"; returning the components is
  what lets a caller see when that has happened.
- The promised `[0, 1]` range holds only because `validate_couplings` requires the five
  weights to sum to exactly 1.
- `meets_conviction_gate` is `score.total >= min_conviction_score` (0.7 by default). No
  rounding happens: §20.13's tick rounding applies to prices, and a score is not one.

## `tradipy.gates`

Pre-entry gates and position sizing. No numeric threshold appears as a literal here; every
value is read from the registry by name, and every rounding direction from
`Config.polarity`.

```python
Reject   # re-exported from tradipy.rejects

def scan_spread_cap(price: Decimal, cfg: Config) -> Decimal

@dataclass(frozen=True)
class SpreadCaps:
    scan: Decimal
    signal: Decimal

    @property
    def binding(self) -> Decimal   # min(scan, signal)

@dataclass(frozen=True)
class RoomRequirement:
    required: Decimal
    binding: Reject                # which term set the requirement
    proportional_term: Decimal     # unrounded
    separation_term: Decimal       # unrounded

@dataclass(frozen=True)
class Ladder:
    t1: Decimal
    t2: Decimal

    def ordered_above(self, entry: Decimal) -> bool   # entry < t1 < t2

def spread_caps(price: Decimal, r: Decimal, cfg: Config) -> SpreadCaps
def check_spread(spread: Decimal, price: Decimal, r: Decimal, cfg: Config) -> Reject | None
def min_separation(r: Decimal, spread: Decimal, cfg: Config) -> Decimal
def required_room(r: Decimal, spread: Decimal, cfg: Config) -> RoomRequirement
def check_room(
    entry: Decimal, resistance: Decimal, r: Decimal, spread: Decimal, cfg: Config
) -> Reject | None
def exit_ladder(entry: Decimal, r: Decimal, structural_target: Decimal, cfg: Config) -> Ladder
def exceeds_max_stop(entry: Decimal, stop: Decimal, cfg: Config) -> bool
def apply_stop_floor_and_ceiling(
    entry: Decimal, raw_stop: Decimal, cfg: Config
) -> tuple[Decimal, Reject | None]
def vwap_reclaim_stop(
    entry: Decimal, dip_low: Decimal, vwap: Decimal, cfg: Config
) -> tuple[Decimal, Reject | None]
def position_size(
    entry: Decimal,
    effective_stop: Decimal,
    cfg: Config,
    *,
    buying_power: Decimal | None = None,
    adv_shares: Decimal | None = None,
) -> int
```

- `spread_caps` returns both §3.1.3 caps: the scan-time cap from `max_spread_abs` and
  `max_spread_pct`, and the signal-time cap from `max_spread_r`. Both are maxima, so both
  round down and are clamped to one tick. At scan time R does not exist yet, which is why
  there are two gates rather than one.
- `check_spread` applies both, against `caps.binding`. §3.1.3 states only the signal-time
  requirement while §4.2 makes the scan cap a hard filter; taking a name whose spread has
  widened past the scan cap would mean the scan filter binds only on a stale quote. On all
  three §3 worked examples the two readings agree.
- `min_separation` is `max(min_sep_r * R, sep_cost_multiple * (spread + cost))`, rounded up.
  The cost term is what binds on cheap stocks — `room_gate_multiple` alone cannot express
  that, because R shrinks with price while costs do not.
- `required_room` is `max(room_gate_multiple * R, t1_r_multiple * R + min_separation)`. The
  `binding` reason code is chosen from the **unrounded** terms and both are exposed, because
  after rounding a half-tick gap can vanish and misattribute which constraint the setup
  actually failed.
- `exit_ladder` puts T1 at exactly `t1_r_multiple` R and T2 at the structural level, both
  rounded up, away from entry, so rounding never flatters backtested R. It calls
  `ceil_to_tick` directly: §20.13 states the direction for targets as such, not by reference
  to any parameter's polarity.
- `exceeds_max_stop` is the single definition of the §20.13 ceiling, shared by
  `apply_stop_floor_and_ceiling` and `position_size`. Writing the comparison twice would
  restate a *rule* rather than a literal, which the registry lint cannot see.
- `apply_stop_floor_and_ceiling` applies tick rounding, then the minimum-stop floor, then
  the maximum-stop skip test, in that §20.13 order, so both tests operate on the level that
  will actually be sent. It returns the level in both cases; a `STOP_TOO_WIDE` verdict means
  skip the trade, never tighten the stop.
- `vwap_reclaim_stop` is the §3.4 chain and returns the level **and** the verdict. An
  earlier version returned a bare `Decimal` and discarded the verdict, leaving the ceiling
  correct but unreachable; any caller must destructure both elements.
- `position_size` risks `start_of_day_equity * max_risk_per_trade_pct` — deliberately the
  frozen start-of-day figure, so intraday gains cannot compound size within a session — over
  the stop distance, floored, then capped by `max_shares_per_order` and, when supplied, by
  `buying_power * max_bp_usage_pct / entry` and `max_pct_of_adv * adv_shares`. It raises
  `ValueError` when `effective_stop >= entry`, and — new in this version — raises
  `ValueError` when the stop distance exceeds `max_stop_pct * entry`, because §20.13
  requires skipping that trade rather than sizing it. Check the `Reject` from
  `apply_stop_floor_and_ceiling` first. A budget too small for one share still returns `0`
  rather than a rejection; that is a recorded Phase 2 gap.

## `tradipy.scanner`

PRD §4: the seven §4.2 hard filters, the seven §4.2 soft flags, and §4.3's ranked watchlist.
Same two rules as `gates` — no threshold literal, no rounding direction named at a call site.

```python
PERCENT_PER_UNIT: Decimal   # Decimal(100) — §4.2's fraction to §20.10's percent units

@dataclass(frozen=True)
class ScanCandidate:
    symbol: str
    # §4.2 hard-filter inputs — all required
    price: Decimal
    premarket_gap_pct: Decimal          # fraction, 0.04 = 4%
    daily_gap_pct: Decimal              # fraction; also what feeds §20.10
    rvol: Decimal
    float_shares: Decimal
    adv_shares: Decimal
    luld_upper: Decimal
    luld_lower: Decimal
    spread: Decimal
    bid_size: int
    # §4.3 ranking inputs — required, because §20.10 consumes them
    premarket_volume: Decimal
    catalyst: Catalyst
    # §4.2 soft-flag inputs — None means "not available", which raises no flag
    market_cap: Decimal | None = None
    atr: Decimal | None = None
    avg_atr: Decimal | None = None
    sessions_since_halt: int | None = None
    institutional_ownership_pct: Decimal | None = None
    short_interest_pct: Decimal | None = None

@dataclass(frozen=True)
class HardFilter:
    name: str          # verbatim from §4.2's Filter column
    code: Reject
    check: Callable[[ScanCandidate, Config], tuple[bool, str]]

@dataclass(frozen=True)
class SoftFilter:
    name: str
    code: SoftFlag     # note the type: a soft row cannot carry a rejection
    check: Callable[[ScanCandidate, Config], tuple[bool, str]]

HARD_FILTERS: tuple[HardFilter, ...]   # 7, in §4.2 table order
SOFT_FILTERS: tuple[SoftFilter, ...]   # 7, in §4.2 table order

@dataclass(frozen=True)
class HardResult:
    filter: str
    code: Reject
    passed: bool
    detail: str

@dataclass(frozen=True)
class SoftResult:
    filter: str
    code: SoftFlag
    raised: bool       # advisory: it rejects nothing
    detail: str

@dataclass(frozen=True)
class ScanResult:
    candidate: ScanCandidate
    hard: tuple[HardResult, ...]
    soft: tuple[SoftResult, ...]
    score: Score | None = None         # None for a rejected candidate

    @property
    def rejects(self) -> tuple[Reject, ...]   # every hard failure, §4.2 table order
    @property
    def reject(self) -> Reject | None         # the first
    @property
    def passed(self) -> bool
    @property
    def flags(self) -> tuple[SoftFlag, ...]   # never affects `passed`

@dataclass(frozen=True)
class ScanReport:
    results: tuple[ScanResult, ...]    # every candidate, in the order supplied
    watchlist: tuple[ScanResult, ...]  # survivors, ranked, cut to watchlist_size

    @property
    def survivors(self) -> tuple[ScanResult, ...]

def evaluate_candidate(candidate: ScanCandidate, cfg: Config) -> ScanResult
def scan(candidates: Iterable[ScanCandidate], cfg: Config) -> ScanReport
```

- **It sources nothing.** PRD §4.1's pipeline runs *universe → hard filters → soft filters →
  catalyst check → watchlist*; this module implements the middle and the end. The universe
  is Phase 2 ingestion and the catalyst check is the one manual step §12.2 keeps in the MVP
  loop, so both arrive as inputs. There is no feed, no file read and no network call here,
  and PLAN **D30** is why: the project is on the `SIMULATED` rung of the data ladder.
  `test_enforcement.py` enforces this with an **allowlist** of imports for this module
  specifically, rather than the repository-wide denylist — §4.2 is arithmetic over inputs and
  needs nothing but `dataclasses`, `decimal`, `collections.abc` and its own package.
- **Every hard filter is evaluated, not just up to the first failure.** `rejects` reports all
  of them so a marginal candidate can be told from one that was nowhere near — which is what
  recalibrating a threshold against measured data (Phase 2a Q1) has to read.
- **A rejected candidate has no score**, deliberately. §4.1 orders hard filters before
  scoring, and a score on a rejected name invites ranking on it.
- Ties in the watchlist are broken by symbol ascending. §4.3 states no tiebreak and ties are
  reachable — `float_inverse` saturates at 0 above the cap and `norm_rvol` at 1 above 20× —
  so without one the watchlist would depend on the order the universe arrived in.
- **§4.2 admits more than one reading in several places** — what "within 10% of LULD band"
  is 10% *of*, whether §4.2's daily Gap % and §20.10's `pct_change` are the same quantity,
  whether "last 5 days" means sessions, and others. Each is taken one way here because the
  module has to be executable, and each is raised in [CHANGELOG.md](CHANGELOG.md)'s
  spec-question table rather than decided here. That table is the authoritative list.
- **Nothing below is calibrated.** The filters are applied correctly and tested to be; PLAN
  D29 gates *calibration* on Phase 2a Q1 answered on measured data, and **D32** opened this
  phase without it. See [PHASE-3-READINESS.md](PHASE-3-READINESS.md).

## `tradipy.session`

The §20 computations that need an *ordered series* rather than one bar (PRD §20.1, §20.2,
§20.3, §20.5, §20.6).

```python
@dataclass(frozen=True)
class SessionBar:
    minute: int          # minutes from the session open; 0 is the 09:30 bar (§20.1)
    bar: Bar

@dataclass(frozen=True)
class Session:
    bars: tuple[SessionBar, ...]          # strictly increasing minutes, validated

    def bar(self, i) -> Bar
    def minute(self, i) -> int
    def ohlcv(self) -> tuple[Bar, ...]
    def through(self, i) -> Session       # the no-look-ahead primitive (§21.1)
    def vwap_at(self, i) -> Decimal       # §20.2, typical price, cumulative
    def vwap(self) -> Decimal
    def hod_through(self, i) -> Decimal   # §20.3, wicks
    def hod(self) -> Decimal
    def hod_established_by(self, i) -> bool   # §20.3's "not the opening print"
    def ema_at(self, i, cfg) -> Decimal | None    # §20.5; None until the period closes
    def gap_before(self, i) -> int        # §20.1 missing minutes
    def pattern_intact(self, start, end, cfg) -> bool

def bar_sequence(bars, *, first_minute=0) -> Session
def tighter(*levels) -> Decimal          # §20.6: max() of candidate stop prices
def wider(*levels) -> Decimal            # §20.6: min()
```

- **`minute` is an `int`, not a timestamp.** §21.1 requires an injectable clock and forbids
  `datetime.now()` in strategy code; every §20.1 rule Phase 4 needs is ordinal — *"pattern
  counts count **available bars**"*, *"a gap > 2 minutes invalidates any in-progress pattern"*.
  Timezone and DST are §21.4's and ingestion's.
- **`through(i)` is what makes §21.1's look-ahead property test two lines** rather than an
  audit: every derivation in `setups` reads the session only at or before its trigger index.
- **`ema_at` has no caller in `src/`, deliberately.** Its consumer is §3.1.1's T3 leg, which
  D18 requires be mirrored to a broker-side stop — Phase 5/6. It is implemented now because
  §21.1's unit row names *"EMA seeding"* as a computation needing a hand-computed fixture.
- **This module does not round.** VWAP, HOD and EMA are inputs to a level, not levels, and
  §20.13 puts rounding once at level computation. The enforcement suite derives the set of
  rounding modules from the source, so the distinction is checked rather than asserted.
- Premarket VWAP (§20.2's 04:00 series) is **not** implemented: D11 disables premarket entries
  and `premarket_trading_enabled` cannot be represented in the registry at all (question G9).

## `tradipy.setups`

PRD §3.2, §3.3 and §3.4 — the three MVP setups, §20.11 arbitration, and §3's post-entry rules.

```python
class SetupType(Enum):                    # §9.2 values; declaration order is §20.11 priority
    BULL_FLAG; HOD_BREAKOUT; VWAP_RECLAIM
    priority: int

@dataclass(frozen=True)
class Criterion:  name: str; code: Reject; passed: bool; detail: str

@dataclass(frozen=True)
class Resistance: level: Decimal; source: str; candidates: tuple[tuple[str, Decimal], ...]

@dataclass(frozen=True)
class Levels:     # every price §9.2's TradeSignal carries — reported on a *rejected* setup too
    entry_price; pattern_stop; stop_price; r_per_share; ladder; resistance; room
    min_separation; spread_at_signal; breakout_high; prior_hod; trigger_minute: int
    target_prices -> tuple[Decimal, Decimal]; required_room -> Decimal

@dataclass(frozen=True)
class SetupSignal: symbol; setup_type; levels: Levels; shares: int
                   direction: ClassVar[str] = "LONG"

@dataclass(frozen=True)
class SetupOutcome:
    symbol; setup_type; criteria: tuple[Criterion, ...]
    levels: Levels | None = None; signal: SetupSignal | None = None
    failures -> tuple[Criterion, ...]; reject -> Reject | None; accepted -> bool

def evaluate_bull_flag(symbol, session, i, spread, cfg, *, premarket_high=None,
                       buying_power=None, adv_shares=None) -> SetupOutcome
def evaluate_hod_breakout(...) -> SetupOutcome
def evaluate_vwap_reclaim(...) -> SetupOutcome
EVALUATORS: dict[SetupType, Callable[..., SetupOutcome]]
def evaluate_all(...) -> tuple[SetupOutcome, ...]
def arbitrate(outcomes) -> tuple[SetupSignal | None, tuple[SetupOutcome, ...]]
def nearest_resistance(entry, *, prior_hod, structural_target, premarket_high=None) -> Resistance
def whole_dollar_above(price) -> Decimal
def bull_flag_exit(session, signal, after, cfg) -> ExitReason | None
def hod_breakout_exit(session, signal, after, cfg) -> ExitReason | None
def vwap_reclaim_exit(session, signal, after, cfg) -> ExitReason | None
```

- **A `SetupOutcome` carries every criterion, and `Levels` even when it rejects.** Only the
  share count is withheld from a rejection — the same argument §4.1 makes for withholding the
  composite score. Pattern criteria short-circuit at the first structural absence (a flag's
  retrace is undefined without a flag); the §3.1 gates are all evaluated together.
- **One new rejection code**, `SETUP_NOT_PRESENT`. Everything else a setup can fail is a §3.1
  gate with a code of its own.
- **`nearest_resistance` is where two readings live.** §3.1.1's *"prior leg high"* is omitted
  because *leg* is undefined; `PMH` is included because §20.3 says so; and `HOD` means the HOD
  established **before** the trigger bar, without which §3.1.1 rejects every breakout that
  closes below its own high. See [CHANGELOG.md](CHANGELOG.md).
- **§3.4's worked example is rejected by this module**, on §3.1.1's whole-dollar candidate.
  That is a PRD-internal contradiction, raised there, and `python -m tradipy setups` prints it.
- **Nothing here is calibrated**: of Phase 4's twenty registry rows **all twenty are marked `(bounds: code)`** — eighteen cite §3.2, §3.3 or §3.4, sections with no parameter table and no Bounds column, and the other two cite §20.1 and §20.5, which have none either. See [PHASE-4-DESIGN.md](PHASE-4-DESIGN.md) and PLAN **D33**.

## `tradipy.positions`

PRD §20.12's position state machine, §3.1.1's stop management, §7.1.1's scale-in legality.

```python
class PositionState(Enum):            # §20.12's twelve states, spelled as §10 persists them
    IDLE; ARMED; PENDING_ENTRY; OPEN_FULL; T1_FILLED; T2_FILLED; TRAILING; CLOSED
    EXPIRED; STOPPED_OUT; INVALIDATED; BAILED_OUT

TERMINAL_STATES: frozenset[PositionState]   # CLOSED, EXPIRED only
OPEN_STATES: frozenset[PositionState]       # shares held — includes PENDING_ENTRY (§7 row 1)
TRANSITIONS: Mapping[PositionState, frozenset[PositionState]]   # read-only, and *total*

class IllegalTransitionError(ValueError)

def transition(state: PositionState, to: PositionState) -> PositionState
def reachable_exit_reasons(state: PositionState) -> frozenset[ExitReason]
def breakeven_stop(avg_cost: Decimal) -> Decimal
def position_risk(shares: int, current_stop: Decimal, mark: Decimal) -> Decimal
def scale_in_permitted(state: PositionState, open_risk_after: Decimal, cfg: Config) -> bool

@dataclass(frozen=True)
class LegQuantities: t1: int; t2: int; t3: int; shares: int   # sum invariant in __post_init__

def leg_quantities(shares: int, cfg: Config) -> LegQuantities
```

- **§20.12's diagram and its table disagree, and neither is complete.** The table gives six rows
  and no rule for `IDLE`, `CLOSED`, `EXPIRED` or the three exit states; the diagram adds
  `IDLE → ARMED` and routes the exit states to `CLOSED`, but also draws edges from `T1_FILLED` and
  `T2_FILLED` that the table omits. The reading is **the table where it has a row, the diagram
  where it has none** — the table's column is an enumeration and is the stricter, and the table
  alone yields a machine that can neither start nor finish. Cost, stated: a §3 invalidation firing
  after T1 has no state to move to, so `setups.bull_flag_exit` will return `INVALIDATED` and
  `transition` will refuse it. Raised in [CHANGELOG.md](CHANGELOG.md).
- `transition` refuses a **self**-transition. §20.12 lists no state as its own successor, and
  permitting one would make the audit log it requires unable to tell "no event" from "an event that
  changed nothing".
- `reachable_exit_reasons` exists to make a gap visible rather than to be convenient: §7.2's kill
  switch has enforcement point *"Any"*, and §20.12 provides an edge to `CLOSED` only from
  `TRAILING`, so `KILL_SWITCH` and `EOD_FLAT` are **unreachable** from the four other open states.
  A test asserts the emptiness, so correcting §20.12 later fails it deliberately.
- `leg_quantities` **floors** T1 and T2 and gives T3 the remainder, with the three summing exactly
  to `shares`. §3.1.1 states no rule for an indivisible count and §2.2 floors the count, so
  indivisible is the normal case; §21.6 makes an uncovered share a Sev-1, and flooring the two
  profit legs is the only allocation that cannot drop one. A 1-share position therefore exits
  entirely on the trail (`t1 == t2 == 0`), and 2 shares put nothing on T2.
- `position_risk` clamps at zero. Once the stop is at or above the mark — which is exactly what
  `breakeven_stop` does at T1 — the position cannot lose, and a negative contribution would let one
  profitable position *fund* risk on another. §7.1.1 says the tranche contributes *"~zero"*, not
  credit.

## `tradipy.risk`

PRD §6.3's pre-trade validation and §7's rule table. Nothing here senses anything.

```python
PDT_MIN_EQUITY: Decimal = Decimal(25_000)   # FINRA — law, so a constant and not a registry row
PDT_MAX_DAY_TRADES: int = 3
PDT_WINDOW_BUSINESS_DAYS: int = 5

class OrderIntent:  OPEN = "OPEN"; REDUCE = "REDUCE"

@dataclass(frozen=True)
class OpenPosition:
    symbol: str; shares: int; mark: Decimal; current_stop: Decimal
    state: PositionState; correlation_group: str
    risk -> Decimal                          # from the *current live stop* (§7.1.1)

@dataclass(frozen=True)
class RiskState:                             # §10's daily_state row + §7.1.1's positions
    start_of_day_equity: Decimal
    realized_pnl; unrealized_pnl; consecutive_losses; day_trades_in_window
    trading_halted: bool; halt_reason: str | None
    positions: tuple[OpenPosition, ...]
    session_equity_peak: Decimal | None; multi_day_peak_equity: Decimal | None
    submitted_keys: frozenset[str]
    open_positions -> tuple[OpenPosition, ...]

@dataclass(frozen=True)
class RuleOutcome: rule: str; passed: bool; detail: str; block: RiskBlock | Reject | None

@dataclass(frozen=True)
class RiskDecision:                          # §9.2's RiskDecision, minus two fields (below)
    approved: bool; reason: RiskBlock | Reject | None
    rules_evaluated: tuple[RuleOutcome, ...]
    open_risk_before: Decimal; open_risk_after: Decimal; approved_shares: int
    blocks -> tuple[RuleOutcome, ...]        # every failure, not only the reported one

def live_equity(state: RiskState) -> Decimal
def max_dollar_risk(cfg: Config) -> Decimal
def total_open_risk(state: RiskState) -> Decimal
def correlation_group(symbol, catalyst_key=None, sector=None) -> str
def daily_loss_breached(state: RiskState, cfg: Config) -> bool
def session_drawdown_breached(state: RiskState, cfg: Config) -> bool
def multi_day_drawdown_breached(state: RiskState, cfg: Config) -> bool

def approve(signal: SetupSignal, state: RiskState, cfg: Config, *,
            intent=OrderIntent.OPEN, buying_power=None, correlation=None,
            idempotency_key=None, spread_now=None) -> RiskDecision
def approve_all(signals, state, cfg, *, buying_power=None, groups=()) -> tuple[RiskDecision, ...]
```

- **Every rule is evaluated on every call**, per §9.2's *"every rule checked, for audit"*, and each
  `RuleOutcome.detail` carries the arithmetic — the same argument `scanner.HardResult` and
  `setups.Criterion` make. Evaluation does not stop at the first block; `reason` is the first
  failure and `blocks` is all of them.
- **Approval never trims.** §9.2's `approved_shares` says *"may be < TradeSignal.shares after
  caps"* and §7's Violation Action column says *"Reject order"* for every size-related breach. §7
  governs; `approved_shares` is the request on approval and `0` on a block. Raised, not settled.
- `RiskDecision` omits §9.2's `signal_id` and `evaluated_at`: the first is the caller's join key
  and the second is a `datetime` from a clock §21.1 forbids here.
- **There is no `minute` field on `RiskState`.** §7's trading-hours row is evaluated at the close
  of the trigger bar, which the signal already carries as `Levels.trigger_minute`. A second copy
  would be the v1.2 defect class, and the only way the two could differ is §6.6's disconnect
  queue — which is transport, and refused.
- **`approve_all` accrues risk sequentially.** §7 row 1 caps the *total*, so evaluating a
  watchlist's signals independently against one state would approve two orders that are each
  individually inside the cap. An approved signal is folded in as a `PENDING_ENTRY` position,
  which is what §7's *"plus pending orders"* describes.
- **The drawdown predicates have no caller.** §7 marks those rows *Continuous* and *End of day*;
  the loop that would call them and set `trading_halted` is Phase 6's. Stated because a predicate
  with no caller is the fifth defect class if it goes unrecorded.
- **This module does not round**, for the reason `Config.round_for` gives: a risk budget and a
  dollar risk total are not price levels compared against a tick. It imports `TICK_SIZE` only to
  quantize a dollar figure for display, because writing `Decimal("0.01")` locally is a second
  spelling of the price grid — and is `max_pct_of_adv`'s registered default, which the registry
  lint caught.
- **Two findings this module reproduces, raised and not resolved:** §7's total-risk cap makes
  `max_open_positions` > 1 unreachable while a position is at full risk, and §7's daily-loss row
  makes §7's PDT row unreachable at §2.0's default equity. See
  [PHASE-5-DESIGN.md](PHASE-5-DESIGN.md) §6.

## `tradipy.orders`

PRD §6.1, §6.2, §6.4 and §6.7 — order **construction**. Nothing that sends anything.

```python
class OrderSide(Enum):    BUY; SELL
class OrderType(Enum):    MARKET; LIMIT; STOP; STOP_LIMIT; BRACKET      # §6.1's five
class LegPurpose(Enum):   ENTRY; STOP; TARGET_1; TARGET_2
class PartialFillAction(Enum): WAIT; CANCEL_REMAINDER; KEEP_WORKING; COMPLETE

@dataclass(frozen=True)
class OrderLeg:            # every price validated to be a whole tick in __post_init__ (§20.13)
    side: OrderSide; order_type: OrderType; quantity: int; purpose: LegPurpose
    limit_price: Decimal | None; stop_price: Decimal | None

@dataclass(frozen=True)
class OrderDraft:
    symbol: str; setup_type: SetupType; idempotency_key: str; oca_group: str
    legs: tuple[OrderLeg, ...]; quantities: LegQuantities
    entry -> OrderLeg; protective -> OrderLeg; exit_quantity -> int

def idempotency_key(symbol, setup_type, session_date: str, trigger_minute: int,
                    account_id: str) -> str
def entry_limit_price(ask: Decimal, cfg: Config) -> Decimal
def stop_limit_price(stop: Decimal, cfg: Config) -> Decimal
def bracket(signal: SetupSignal, ask: Decimal, session_date: str, account_id: str,
            cfg: Config) -> OrderDraft
def partial_fill_action(intended: int, filled: int, entry_spread: Decimal,
                        spread_now: Decimal, seconds_since_submit: int,
                        cfg: Config) -> PartialFillAction
```

- **This module is the boundary of the package.** §6.2's lifecycle is
  `Signal → PreTradeRiskCheck → OrderDraft → Submit`, and the fourth arrow is **refused**, not
  deferred: D30 admits no broker SDK, vendor client or network module in `src/`. §6.6's recovery,
  §6.8's retry and backoff and §21.3's reconciliation all require a connection to have existed.
- **Four legs, not five.** §3.1.1's ladder has three exit tranches and T3 has no leg, because D18
  requires the ratcheted 9 EMA level to rest as a broker-side stop *amended each bar close* — an
  amendment stream, not a leg of the opening bracket. The **stop** leg covers the whole position,
  which is the only allocation under which no share is unprotected (§21.6).
- **Every draft price is a whole tick, and `OrderLeg` raises rather than rounding.** §20.13 puts
  rounding *once, at level computation*, so a second rounding point here would contradict it; the
  stop and target levels arrive already rounded from `gates`. Only the entry limit is rounded in
  this module, because `ask` is a feed input nothing upstream has touched.
- **§20.13 states no direction for an entry limit price.** Its table covers stops, targets, gate
  minima and gate maxima. The reading is `ceil_to_tick` for a buy limit and `floor_to_tick` for the
  protective sell limit, taken from §20.13's *governing principle* — *"no rounding decision can
  make a trade look better than it is"* — rather than its table: those are the two directions that
  cost money. Raised in [CHANGELOG.md](CHANGELOG.md).
- **`idempotency_key` is §6.7's whole point and half its guarantee.** §6.7: *"A UUID cannot serve
  this purpose: a freshly generated one is unique by construction, so a duplicate check against it
  can never fire."* Every input is a fact about the signal, `oca_group` is derived from the key
  rather than generated, and a field containing the `|` separator raises rather than producing a
  key two signals could share. What is **not** here is §6.7's other half — *"the DB, not process
  memory, is the arbiter"* — because there is no store; `RiskBlock.DUPLICATE_ORDER` is raised
  against a set the caller supplies.
- **§6.7's `trigger_bar_timestamp` becomes `session_date` + `trigger_minute`.** §21.1 forbids
  `datetime.now()` in strategy code, which is why a `SessionBar` carries an `int`. A `str` date
  cannot be read from a clock, and the derivation stays here.
- `partial_fill_action` is a **decision, not a wait**: §6.4's *"within 30 sec"* becomes a supplied
  `seconds_since_submit` compared against a registered threshold, the shape `Quote.age_seconds`
  already uses for §20.14. The spread condition is evaluated **before** the timeout — §6.4 states
  no ordering, and this is the stricter reading. An over-fill raises: it is a §21.3 reconciliation
  fault, and returning a plausible action for it would let a caller size a stop to shares it does
  not hold.
- **§6.5's slippage model is not here.** It is §6, so §12.1 puts it in this phase, while its only
  consumer is §8.2's fill model, which is Phase 4b's — a boundary disagreement rather than a
  choice. `impact_coefficient` therefore stays unregistered.

## `tradipy.daily`

PRD §10's `daily_state` as a value, §20.8's snapshot, §9.2's `ClosedTrade`, §7 row 4's accrual.

```python
class SessionPhase(Enum):  NO_TRADE; TRADING; LOCKED        # §20.8, §7

@dataclass(frozen=True)
class ClosedTrade:                                          # §9.2, minus four caller/clock fields
    symbol: str; setup_type: SetupType
    entry_price: Decimal; exit_price: Decimal               # volume-weighted, supplied
    shares: int; r_per_share: Decimal
    commission: Decimal; fees: Decimal
    exit_reason: ExitReason; spread_estimated: bool = False

    gross_pnl / net_pnl / r_multiple / is_loss              # properties — derived, never stored

@dataclass(frozen=True)
class DailyState:                                           # §10's row, plus what §10 cannot hold
    session_date: str; phase: SessionPhase
    start_of_day_equity: Decimal | None                     # None iff NO_TRADE (§20.8)
    realized_pnl / unrealized_pnl: Decimal
    consecutive_losses / day_trades_in_window: int
    halt_reason: RiskBlock | None
    session_equity_peak / multi_day_peak_equity: Decimal | None
    locks_next_session: bool

    trading_halted / live_equity                            # properties

DAILY_STATE_COLUMNS: Mapping[str, str]     # §10 column -> the field it is written from
CLOCK_COLUMNS: tuple[str, ...]             # ("updated_at",) — a store's, not this layer's
UNPERSISTED_FIELDS: frozenset[str]         # the four §7 inputs §10 has no column for

class SessionNotOpenError(ValueError)
class ConfirmationRequiredError(ValueError)

def open_session(session_date: str, *, carried_lock: RiskBlock | None = None) -> DailyState
def record_snapshot(state: DailyState, equity: Decimal) -> DailyState
def mark_to_market(state: DailyState, unrealized_pnl: Decimal) -> DailyState
def record_close(state, trade, *, unrealized_after: Decimal, day_trade: bool = True) -> DailyState
def roll_multi_day_peak(session_closes: Sequence[Decimal], cfg: Config) -> Decimal | None
def record_multi_day_peak(state, session_closes, cfg) -> DailyState
def lock(state: DailyState, reason: RiskBlock) -> DailyState
def clear_lock(state: DailyState, confirmation: str, expected: str) -> DailyState
def to_row(state: DailyState) -> dict[str, str | int | bool | None]
def from_row(row: Mapping[str, str | int | bool | None]) -> DailyState
def risk_state(state, positions=(), submitted_keys=frozenset()) -> RiskState
```

- **`risk_state` is the only bridge to §7's evaluator, and that is enforced.** `DailyState` and
  `RiskState` share eight fields, which is exactly the configuration the v1.2 defect class arises
  in. A test derives both field sets from the dataclasses and asserts the bridge carries every
  shared one, so a field added to either and forgotten here fails rather than silently defaulting.
- **`NO_TRADE` has no equity, and `risk_state` refuses it.** §20.8: *"it does not fall back to a
  stale or computed value, because every non-bypassable risk limit is denominated in it."* The
  only way to make that enforceable is for the fallback not to exist, so `start_of_day_equity` is
  `Decimal | None` and every mutation that needs the figure — `mark_to_market`, `record_close`,
  `record_multi_day_peak`, `lock`, `risk_state` — raises `SessionNotOpenError` before the snapshot.
  (`clear_lock` raises a plain `ValueError`: it fails on there being no lock, not on there being
  no equity.)
- **The snapshot is taken once.** §20.8 makes it *"immutable for the remainder of the session"*,
  and a second `record_snapshot` raises whatever value it carries.
- **`ClosedTrade`'s three money figures are properties.** §9.2 marks `net_pnl` *"the figure §18.7
  is judged on"* and requires `r_multiple` to be *"computed on NET P&L, not gross"* — and a
  stored field can be
  computed once, wrongly, and then agree with itself forever. Zero shares or zero R raise rather
  than producing a multiple nobody can trace.
- **`is_loss` is net and strictly negative, and a scratch resets the streak.** §7 states neither;
  both readings are in [PHASE-6-DESIGN.md](PHASE-6-DESIGN.md) §5 and raised in
  [CHANGELOG.md](CHANGELOG.md).
- **`to_row` / `from_row` are a serialisation, not a store.** §7.1.2's *arithmetic* is testable
  here — a reloaded row reproduces the same lockout — and its *durability* is not, because that
  needs a database and D30 admits none. `UNPERSISTED_FIELDS` is the enumeration of the four §7
  inputs §10 has no column for, which is finding 1 rather than an implementation note.
- Nothing here rounds: a P&L is money accumulated and an exit price is an *observed* fill, so
  §20.13's *"every price submitted to the broker"* does not reach either.

## `tradipy.monitor`

PRD §7's non-pre-order enforcement points and its Violation Action column. Decides; sends nothing.

```python
class EnforcementPoint(Enum):    # §7's third column, verbatim
    PRE_ORDER; CONTINUOUS; POST_FILL; POST_TRADE_CLOSE; END_OF_DAY; ANY

class HaltAction(Enum):          # §7's fourth column, verbatim
    REJECT_ORDER; FLATTEN_AND_LOCK_DAY; LOCK_NEW_ENTRIES
    LOCK_ACCOUNT_NEXT_DAY; FLATTEN_AND_HALT

RULES_AT: Mapping[EnforcementPoint, tuple[RiskBlock, ...]]   # PRE_ORDER absent — that is `risk`
ACTION_FOR: Mapping[RiskBlock, HaltAction]

@dataclass(frozen=True)
class MonitorDecision:
    point: EnforcementPoint
    rules_evaluated: tuple[RuleOutcome, ...]     # reuses risk.RuleOutcome, not a second audit row
    reason: RiskBlock | None                     # the FIRST breach, in §7's table order
    action: HaltAction | None                    # the STRICTEST breach — a different question
    breaches / flatten / locks                   # properties

def evaluate(state: RiskState, point, cfg, *, kill_switch: bool = False) -> MonitorDecision
def apply(state: DailyState, decision: MonitorDecision) -> DailyState
def eod_flat_due(minute: int, cfg: Config) -> bool

@dataclass(frozen=True)
class FlattenDirective:
    symbol: str; shares: int; from_state: PositionState
    exit_reason: ExitReason; to_state: PositionState | None   # None => §20.12 has no edge

    representable                                # property
    def commit(self) -> PositionState            # raises IllegalTransitionError when it cannot

def flatten_all(positions: Sequence[OpenPosition], reason: ExitReason) -> tuple[FlattenDirective, ...]
def unrepresentable(directives) -> tuple[FlattenDirective, ...]
def unrepresentable_flatten_states(reason: ExitReason) -> frozenset[PositionState]
```

- **The reason and the action answer two different questions.** If §7 row 4 (*"Lock new entries;
  allow exits"*) and row 2 (*"Flatten all; lock account for day"*) breach together, the reason is
  the earlier row in §7's table and the action is the flatten. Reporting one answer for both
  under-enforces, in the direction that leaves a position open.
- **§7 row 11's *"Any"* is unioned into every point**, derived rather than repeated, so a rule
  marked widest cannot be present at four points and missing from the fifth.
- **`evaluate` asserts its own output** against `RULES_AT`, the way `risk.approve` asserts against
  `EVALUATED_RULES` — §9.2 asks for *"every rule checked, for audit"*, and a length check passes
  with a rule missing.
- **Passing `EnforcementPoint.PRE_ORDER` raises.** Those rows are `risk.approve`'s, and a second
  implementation of §7's table is the v1.2 defect class.
- **`eod_flat_due` is not a §7 row.** §7's trading-hours row is *Pre-order* and rejects entries;
  §21.4's cutoff closes what is open. `session_flat_all_minute` is a separate registry row from
  `session_last_entry_minute` even at an equal default, coupled so the flatten cannot precede the
  last entry — see [CHANGELOG.md](CHANGELOG.md) for the half-day case where they come apart.
- **`flatten_all` never skips a position**, and marks four of §20.12's five open states
  unrecordable. That is round 14's **H3** as a blocker: of §20.12's four edges into `CLOSED` only
  one starts at an *open* state, so an account flattened by the kill switch leaves positions still
  recorded in the open state they were in. The set is derived from `positions.reachable_exit_reasons`, never re-walked here,
  and a test asserts it is **non-empty** so a §20.12 correction fails deliberately.
- **Nothing is flattened, cancelled or sent**, and there is no 1-second loop: §7's cadence is a
  clock, §21.1 forbids one here, and §6.2's `OrderDraft → Submit` arrow is refused (D30).

## `tradipy.poc`

Proof-of-concept composition: one candidate through every Phase 1 gate, plus the simulated
universe the §4 scanner demo runs over. This is not the strategy engine — finding candidates
needs a feed and bar ingestion, which PRD §12.1 scopes to Phase 2.

```python
@dataclass(frozen=True)
class Candidate:
    entry: Decimal
    raw_stop: Decimal
    structural_target: Decimal
    resistance: Decimal
    quote: Quote
    label: str = "candidate"
    section: str = ""
    expect: dict[str, object] = field(default_factory=dict)

@dataclass(frozen=True)
class GateResult:
    gate: str
    section: str
    passed: bool
    detail: str
    reject: Reject | None = None

@dataclass(frozen=True)
class Evaluation:
    candidate: Candidate
    results: list[GateResult]
    spread: Decimal | None = None
    stop: Decimal | None = None
    r: Decimal | None = None
    ladder: Ladder | None = None
    shares: int | None = None

    @property
    def reject(self) -> Reject | None   # first failing gate, in §3.1 order
    @property
    def accepted(self) -> bool

def evaluate(candidate: Candidate, cfg: Config) -> Evaluation
def worked_examples() -> list[Candidate]
def simulated_universe(cfg: Config) -> list[ScanCandidate]
```

- `simulated_universe` is fourteen synthetic candidates — seven that survive §4.2 and seven
  that each fail exactly one hard row — behind `python -m tradipy scan`. It is *constructed*,
  not read, so it needs no `PROVENANCE.txt`: PLAN D30's gate constrains what may be read, and
  nothing here reads anything. Its boundary values are derived from the registry
  (`cfg["min_rvol"] - 1`, not `4`), which is the opposite of what the fixtures in `tests/` do
  and for the opposite reason — a demo should follow the configuration, a test must be able
  to detect it changing.

Also public by use — read by the CLI and the tests, though not in `__all__`:

```python
BULL_FLAG_BARS: list[Bar]     # PRD §3.2's flagpole, flag and breakout, as 8 bars
BULL_FLAG_FLAG_START = 4      # index of the first flag bar

@dataclass(frozen=True)
class FlagGeometry:
    pole_start: int
    pole_end: int
    pole_low: Decimal
    pole_high: Decimal
    height: Decimal
    flag_high: Decimal
    flag_low: Decimal
    retrace: Decimal
    flag_volume_ratio: Decimal

def bull_flag_geometry(
    bars: list[Bar] = BULL_FLAG_BARS, flag_start: int = BULL_FLAG_FLAG_START
) -> FlagGeometry
def check_against_prd(ev: Evaluation) -> list[str]
```

- `evaluate` runs the chain in PRD §3.1 order — the quote defines the spread (§20.14), the
  spread and the stop define R, and R is the denominator of both remaining gates — and
  reports **every** gate rather than stopping at the first failure, because a candidate's
  other near-misses are the useful part of the output. Two exceptions: it returns early when
  the quote yields no spread, since every later gate consumes it and reporting them against
  a fabricated value would be worse than not reporting them; and it skips sizing when the
  stop itself was rejected, since `position_size` refuses such a stop.
- `Candidate.expect` carries values transcribed from the PRD tables and is read **only** by
  `check_against_prd`. Nothing in `evaluate` reads it — every number it reports is derived.
- `worked_examples` returns the three PRD §3 candidates. The §3.2 one derives its stop, flag
  high, flagpole height and T2 from `BULL_FLAG_BARS` via §20.4 rather than transcribing
  them, which is what §21.1 asks worked-example fixtures to do.
- `check_against_prd` returns one string per disagreement between a derived value and the
  PRD table, and `[]` when they agree or when `expect` is empty. This is the check §21.1
  calls "regression tests against spec drift"; PRD v1.0's four arithmetic errors would all
  have surfaced here.
- `bull_flag_geometry` raises `ValueError` when no green run ends at `flag_start - 1`. It
  excludes the breakout bar from the flag: §3.2 criterion 6 makes it the trigger, and
  including it would put the entry candle inside the pattern it broke out of.

## `tradipy.__main__`

The `python -m tradipy` CLI. Stdlib only — `argparse` and `decimal`. No `__all__`.

```python
def build_parser() -> argparse.ArgumentParser
def main(argv: list[str] | None = None) -> int
```

`main` returns the process exit code rather than calling `sys.exit`, so the tests can drive
it in-process. Subcommands, flags and exit codes are documented in
[`development.md`](development.md#running-the-proof-of-concept).

## Examples

Gates directly, against a config built from the registry:

```python
from decimal import Decimal

from tradipy.gates import check_room, required_room
from tradipy.params import Config

cfg = Config.default(mode="experienced")

req = required_room(Decimal("0.15"), Decimal("0.02"), cfg)
print(req.required, req.binding)
# 0.41 Reject.TARGETS_TOO_CLOSE

print(check_room(Decimal("6.48"), Decimal("7.00"), Decimal("0.15"), Decimal("0.02"), cfg))
# None  — enough room; otherwise the binding Reject code
```

The whole chain, through the PoC composition:

```python
from decimal import Decimal

from tradipy.params import Config
from tradipy.poc import Candidate, evaluate
from tradipy.quotes import Quote

cfg = Config.default(mode="experienced")
quote = Quote(
    bid=Decimal("6.47"),
    ask=Decimal("6.48"),
    bid_size=500,
    ask_size=500,
    age_seconds=Decimal(0),
)
candidate = Candidate(
    entry=Decimal("6.48"),
    raw_stop=Decimal("6.34"),
    structural_target=Decimal("7.00"),
    resistance=Decimal("7.00"),
    quote=quote,
)

ev = evaluate(candidate, cfg)
print(ev.accepted, ev.reject, ev.stop, ev.r, ev.shares)
# True None 6.34 0.14 2142

for gate in ev.results:
    print(gate.gate, gate.passed, gate.detail)
```
