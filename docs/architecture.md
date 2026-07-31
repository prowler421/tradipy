# Architecture

tradipy is the invariant layer of a Ross Cameron momentum trading system. It is a small,
pure library whose job is to make the rules in [`PRD.md`](PRD.md) executable and enforce them
with tests. This document explains the shape of the code and the invariants that hold it
together. `PRD.md §20` (Computation Semantics) is normative and governs on any conflict.

## Module structure

Fourteen library modules plus a CLI entry point, with a strict one-way dependency graph:

| Module | Imports (first-party) |
|---|---|
| `rounding`, `rejects`, `bars` | — (standard library only) |
| `params` | `rounding` |
| `quotes` | `params`, `rejects`, `rounding` |
| `score` | `params` |
| `gates` | `params`, `rejects`, `rounding` |
| `scanner` | `params`, `rejects`, `score`, `gates` |
| `session` | `bars`, `params` |
| `setups` | `bars`, `session`, `params`, `rejects`, `rounding`, `gates` |
| `positions` | `params`, `rejects`, `rounding` |
| `risk` | `gates`, `params`, `positions`, `rejects`, `rounding`, `setups` |
| `orders` | `params`, `positions`, `rounding`, `setups` |
| `poc` | all of the above |
| `__main__` | `poc`, `orders`, `params`, `positions`, `quotes`, `risk`, `rounding`, `scanner`, `score`, `setups` |

A table rather than a drawing, deliberately: an ASCII bus diagram was tried here for Phase 4's
two new rows and, on inspection, implied that `quotes` does not depend on `rejects` — its branch
was drawn off the `params` bus above the point where `rejects` merged into it, which is false
(see the row above). A bus-style junction can imply an edge that does not exist simply from where
a tap is drawn relative to a merge, which is the same failure
[PHASE-4-DESIGN.md](PHASE-4-DESIGN.md) §3 records for the diagram once drafted for that document;
a table cannot be geometrically wrong the same way.

`session` adds PRD §20.1–§20.6 over an ordered series and `setups` the three §3 setups on top of
it. `setups` is imported by `__init__` (it is public), by `poc`, and by `__main__` for one type
annotation. Both were added by **D33** and both are held to an
import allowlist, as `scanner` already was.

`rounding`, `rejects` and `bars` depend on nothing but the standard library. `params` depends
only on `rounding`; `quotes` and `gates` depend on `params`, `rejects` and `rounding`; `score` on
`params`; `scanner` on `params`, `rejects`, `score` and `gates`. `bars` is standalone because
§20.4 is pure geometry over candles — it reads no threshold, which is also why §3.2
criterion 2 arrives as a caller-supplied predicate.

The ordering is deliberate: rounding is the most primitive concept, thresholds are defined in
terms of it, and the gates are defined in terms of thresholds. `scanner` sits on top of the
library layer because §4.3 ranks with §20.10 and §4.2's spread row is §3.1.3's scan-time cap
— it reuses both rather than restating either. `poc` sits above all of them and only
`__main__` depends on `poc` — nothing in the library does.

`Reject` lives in its own module rather than in `gates` because three layers raise it —
`gates` for the pre-entry gates, `quotes` for §20.14 validity, and `scanner` for §4.2's hard
filters — and a quote is the lower level construct. Keeping the enum in `gates` would have
made `quotes` depend on `gates`, inverting the layering for no reason. It is re-exported from
`tradipy.gates`, so `from tradipy.gates import Reject` still works.

That module also holds a **second** enum, `SoftFlag`, for §4.2's seven Soft rows. §4.2 lists
all fourteen rows under one "Rejection Code" column, and round 10's finding K5 is what that
invites: a reader sizing the scanner from it builds all fourteen as rejection paths, and
`INST_OWN_HIGH` — which D24 keeps deliberately inert — becomes a filter that throws
candidates away. Two unrelated types make that a compile-time error instead. `ScanResult.reject`
is `Reject | None` and will not accept a flag.

`tradipy/__init__.py` imports the thirteen library modules so the names it advertises resolve as
attributes. It deliberately does **not** import `poc`: the composition layer is not part of
what `import tradipy` means, and `import tradipy.poc` is the honest way to reach it.

### `tradipy.rounding`

Tick arithmetic and polarity-aware threshold rounding. The governing principle is
*"rounding must never weaken a constraint."* Whether a threshold rounds up or down is a
property of the constraint, expressed as its `Polarity`:

- `Polarity.MINIMUM` — the value must exceed the threshold (room gate, separation floor,
  minimum stop distance). Rounds **up**, raising the bar.
- `Polarity.MAXIMUM` — the value must stay under the threshold (spread caps, maximum stop).
  Rounds **down**, then clamps to at least one tick.

The one-tick clamp on maxima is load-bearing: an unclamped maximum can floor to `$0.00`,
which rejects every possible value — a silent kill switch rather than a filter.

All money is `Decimal`. Binary float cannot represent `$0.01`, and almost every rule compares
a price against a tick boundary, so float would produce comparison errors that look like
logic bugs (`PRD §9.2`).

### `tradipy.params`

The parameter registry — the single source of truth for every tunable threshold. Each
`Param` carries its default, legal range, unit, PRD source citation, and (where used as a
gate) its polarity. The registry exists because the most expensive defect the PRD review
found was a single quantity expressed in more than one place, where the copies drifted apart.

The rule the module enforces: **a threshold is defined here exactly once, and every consumer
reads it by name.** No numeric literal for a registered threshold may appear elsewhere in the
package; the registry test enforces the same discipline against the PRD prose. Its scope is
stated and still narrower than the rule: `src/tradipy/*.py` non-recursively plus `scripts/`
recursively, skipping `params.py` and `__init__.py` inside `src/tradipy/` only, exempting
undistinctive values, and not covering `tests/` — where fixtures must state literals in order to
assert a derivation against them.

`params` also holds:

- **`Config`** — a validated, frozen parameter set. `__post_init__` is the only construction
  path, and it checks the mode, completeness, that no unregistered name is present, every
  value's **range**, and then the **couplings** — in that order, because a coupling validator
  reasoning about out-of-range inputs produces misleading errors. Range checking lived only
  in `with_overrides` until v0.1.0, so `Config(values)` accepted anything.
- **`MODE_PRESETS` and `HARD_CAPS`** — the §2.0 preset bundles applied on top of the registry
  defaults, and the §7 non-bypassable ceilings the effective values may never exceed. All
  three mappings are read-only: a frozen dataclass in front of a mutable module global is
  not frozen.
- **`validate_couplings`** — rejects combinations that are individually legal but jointly
  incoherent (the defect class that ordinary per-parameter validation cannot see).

### `tradipy.bars`, `tradipy.quotes`, `tradipy.score`

The three PRD §20 computations that need no market-data feed to be correct: §20.4 flagpole
geometry and the measured move, §20.14 NBBO spread and quote validity, §20.10 the normalized
composite score with §14.2's conviction gate. Each takes its inputs as values rather than
fetching them, so each is a pure function of what it is handed.

They stop where the feed begins. `bars` carries no timestamps, because §20.1 bar timing is
an ingestion concern; `quotes` validates whatever quote it is given and takes the caller's
word that §20.14's sampling rule was followed.

### `tradipy.gates`

Pre-entry gates and position sizing: spread caps (`spread_caps`, `check_spread`), the
separation floor and unified room requirement (`min_separation`, `required_room`,
`check_room`), the exit ladder (`exit_ladder`), stop construction
(`apply_stop_floor_and_ceiling`, `vwap_reclaim_stop`), and sizing (`position_size`).

No numeric threshold appears as a literal in this module — and no rounding *direction*
either. Every rounded threshold goes through `Config.round_for(value, *governed_by)`, which
reads the polarity from the parameters that govern it. Naming a `Polarity` member at the
call site gave direction two definitions that nothing reconciled, which is the v1.3.1 defect
reproduced inside the mechanism built to close it. `gates.py` no longer imports `Polarity`.
`round_for` lived here as `_rounded` until Phase 3, when `scanner` needed the same
resolution; the two ways to share it were a private cross-module import or a second module
naming directions, and direction is registry data, so it moved onto the registry object.

`scan_spread_cap(price, cfg)` is the scan-time half of §3.1.3, split out because §4.2 makes
it a hard scanner filter and at scan time no setup has formed, so no R exists to compute the
signal-time cap from. `spread_caps` delegates to it rather than deriving the same quantity
twice.

### `tradipy.scanner`

PRD §4: the seven §4.2 hard filters (`HARD_FILTERS`), the seven §4.2 soft flags
(`SOFT_FILTERS`), and §4.3's ranked watchlist (`scan`, `evaluate_candidate`). Same two rules
as `gates`: no threshold literal, no rounding direction at a call site.

It applies §4.2 to a universe it is **given**. §4.1's pipeline begins with an external
screening provider and includes a manual catalyst check; both are inputs here. There is no
feed, no file read and no network call — PLAN **D30** puts the project on the `SIMULATED`
rung of the data ladder, and the test suite backs this module with an *allowlist* of imports
rather than the repository-wide denylist, because §4.2 is arithmetic over inputs and needs
nothing else.

The hard/soft split is structural, not conventional: a `HardFilter` carries a `Reject` and a
`SoftFilter` carries a `SoftFlag`, and `ScanResult.reject` is typed `Reject | None`. Round
10's finding K5 is the failure this prevents.

Nothing here is *calibrated*. D29 gates calibration on Phase 2a Q1 answered on measured data;
**D32** opened the phase on simulated data with that explicitly outstanding. The filters are
correct applications of §4.2's thresholds, and whether those thresholds are the right numbers
— or even obtainable — is still open. See [PHASE-3-READINESS.md](PHASE-3-READINESS.md).

### `tradipy.poc`

Composes the gates into one `evaluate(candidate, cfg)` in the order §3.1 states them, carries
the three §3 worked examples, and holds `simulated_universe(cfg)` — fourteen synthetic
candidates behind `python -m tradipy scan`. It is **not** the strategy engine: it takes a
candidate that has already been found, and filters a universe it constructed rather than one
it sourced. `python -m tradipy` is the front end.

## Design invariants

These are the properties the test suite defends. Each corresponds to a defect class found in
a review round — the first four in the PRD, the fifth in the code:

1. **Arithmetic** — every worked example obeys its own rules.
2. **Consistency** — a registered threshold is never restated as a divergent literal.
3. **Joint coherence** — two individually-legal parameters that cannot both hold are
   rejected (or, where the incoherent combination is the shipped default, surfaced as a
   documented open finding rather than silently enforced).
4. **Generalization** — a rounding rule holds only as broadly as its justification (a floor
   rounds up; a ceiling rounds down — they are not the same rule).
5. **Enforcement** — every documented guarantee has a test that *performs the violation it
   forbids*. A test confirming the happy path passes whether or not the guarantee is
   enforced, which is how four of them came to be unenforced at once.

## Deliberate non-goals

tradipy is intentionally *not*:

- a strategy or execution engine (Phase 2+) — `poc.evaluate` gates a candidate, it does not
  find one;
- a service. `python -m tradipy` exists so the rules can be exercised by hand; the package is
  an importable library and the CLI is a thin presentation layer over it;
- configuration-driven at runtime (no config files, no environment variables in the runtime
  path).

Some incoherent couplings are **deliberately not enforced** because the incoherent
combination is the shipped default set — enforcing them would make `Config.default()` throw
and take the whole package with it. These are surfaced as documented findings (see
`min_tradeable_price_from_stop_bounds` and `signal_cap_ticks_at_min_r`) and pinned in tests,
because resolving them is a specification decision, not a module decision.
