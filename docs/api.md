# API reference

Every public name in every module's `__all__`, with the signature as it appears in the
source. Each module's `__all__` is authoritative; the docstrings carry the full normative
detail and the PRD citations, and [`PRD.md`](PRD.md) §20 governs on any conflict.

All monetary values are `decimal.Decimal`. No `float` appears anywhere a price is compared
against a tick boundary or summed into P&L (PRD §9.2).

## Package layout

Eight library modules and a `__main__` CLI entry point, with a strict one-way dependency
graph:

- `rounding`, `rejects`, `bars` — standard library only.
- `params` — depends on `rounding`.
- `quotes`, `gates` — depend on `params`, `rejects`, `rounding`.
- `score` — depends on `params`.
- `poc` — composes all of the above into one evaluable candidate.
- `__main__` — the `python -m tradipy` front end over `poc`.

`import tradipy` binds the seven library modules named in the package `__all__`
(`rounding`, `rejects`, `params`, `bars`, `quotes`, `score`, `gates`) as attributes.
`tradipy.poc` is not among them and must be imported explicitly — it is the proof-of-concept
composition layer, not part of the invariant surface.

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

Rejection reason codes (PRD §3.1.2, §3.1.3, §4.2, §20.9, §20.13, §20.14).

```python
class Reject(Enum):
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"              # §3.1.3
    INSUFFICIENT_ROOM = "INSUFFICIENT_ROOM"          # §3.1.1 / §3.1.2
    TARGETS_TOO_CLOSE = "TARGETS_TOO_CLOSE"          # §3.1.2
    STOP_TOO_WIDE = "STOP_TOO_WIDE"                  # §2 / §3.2 / §20.13
    QUOTE_STALE = "QUOTE_STALE"                      # §20.14
    QUOTE_CROSSED = "QUOTE_CROSSED"                  # §20.14
    DATA_QUALITY_DEGRADED = "DATA_QUALITY_DEGRADED"  # §20.9 / §20.14
```

- The enum lives in its own module because two layers raise it — `gates` for the pre-entry
  gates and `quotes` for §20.14 validity — and a quote is a lower-level construct than a
  gate. Keeping it in `gates` would have made `quotes` depend on `gates`, inverting the
  layering. `tradipy.gates` re-exports `Reject`, so `from tradipy.gates import Reject`
  still works.
- Each member names the PRD section that defines the rejection, because a reason code
  invented by the implementation is a rule the specification has not agreed to.
  `STOP_TOO_WIDE` is the one exception: the PRD states the rule ("skip the trade") without
  naming a code, so the name is the implementation's and §4.2's table should adopt or
  replace it.

## `tradipy.params`

The parameter registry — the single source of truth for every tunable threshold.

```python
Mode = Literal["beginner", "experienced"]
MODES: tuple[str, ...]                             # ("beginner", "experienced")

PARAMS: Mapping[str, Param]                        # read-only; 47 entries
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

    @classmethod
    def default(cls, mode: Mode = "beginner") -> Config

    def with_overrides(self, **overrides: str | int | float | Decimal) -> Config

class CouplingError(ValueError)

def validate_couplings(cfg: Config) -> None
def signal_cap_ticks_at_min_r(cfg: Config) -> int
def min_tradeable_price_from_stop_bounds(cfg: Config) -> Decimal
```

### The registry

`PARAMS` holds **47** entries keyed by name, each carrying its default, legal range, unit,
PRD source citation, and — where it is used as a gate threshold — its polarity. A
threshold is defined there exactly once and every consumer reads it by name; no numeric
literal for a registered threshold may appear anywhere else in the package. The lint that
enforces this walks `src/tradipy/*.py` non-recursively, skips `params.py` and `__init__.py`,
and exempts undistinctive values; `scripts/` is not scanned.

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
  function is chosen. `tradipy.gates` routes every rounding call through this rather than
  naming a `Polarity` member, so the registry field is the single source of truth for
  direction as well as for value.

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

## `tradipy.poc`

Proof-of-concept composition: one candidate through every Phase 1 gate. This is not the
strategy engine — finding candidates needs a scanner, a feed and bar ingestion, all of which
PRD §12.1 scopes to later phases.

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
```

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
    bid=Decimal("6.47"), ask=Decimal("6.48"), bid_size=500, ask_size=500,
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
