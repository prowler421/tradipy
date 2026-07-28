# Architecture

tradipy is the invariant layer of a Ross Cameron momentum trading system. It is a small,
pure library whose job is to make the rules in [`PRD.md`](PRD.md) executable and enforce them
with tests. This document explains the shape of the code and the invariants that hold it
together. `PRD.md §20` (Computation Semantics) is normative and governs on any conflict.

## Module structure

The library is three modules with a strict one-way dependency graph:

```
rounding.py  ◄──  params.py  ◄──  gates.py
```

Nothing depends on `gates`; `rounding` depends on nothing but the standard library. This
ordering is deliberate — rounding is the most primitive concept, thresholds are defined in
terms of it, and gates are defined in terms of thresholds.

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
reads it by name.** No numeric literal for a registered threshold may appear elsewhere; the
registry test enforces the same discipline against the PRD prose.

`params` also holds:

- **`Config`** — a validated, frozen parameter set. Every construction path validates
  (individually *and* jointly) in `__post_init__`, which is the only place that cannot be
  routed around.
- **`MODE_PRESETS` and `HARD_CAPS`** — mode-dependent presets and the non-bypassable
  ceilings they may never exceed.
- **`validate_couplings`** — rejects combinations that are individually legal but jointly
  incoherent (the defect class that ordinary per-parameter validation cannot see).

### `tradipy.gates`

Pre-entry gates and position sizing: spread caps (`spread_caps`, `check_spread`), the
separation floor and unified room requirement (`min_separation`, `required_room`,
`check_room`), the exit ladder (`exit_ladder`), stop construction
(`apply_stop_floor_and_ceiling`, `vwap_reclaim_stop`), and sizing (`position_size`).

No numeric threshold appears as a literal in this module — every value is read from the
registry by name. That is the mechanism that makes "§20 governs" true in code rather than
aspirational.

## Design invariants

These are the properties the test suite defends. Each corresponds to a defect class found in
a PRD review round:

1. **Arithmetic** — every worked example obeys its own rules.
2. **Consistency** — a registered threshold is never restated as a divergent literal.
3. **Joint coherence** — two individually-legal parameters that cannot both hold are
   rejected (or, where the incoherent combination is the shipped default, surfaced as a
   documented open finding rather than silently enforced).
4. **Generalization** — a rounding rule holds only as broadly as its justification (a floor
   rounds up; a ceiling rounds down — they are not the same rule).

## Deliberate non-goals

tradipy is intentionally *not*:

- a strategy or execution engine (Phase 2+);
- a service or CLI (it is an importable library);
- configuration-driven at runtime (no config files, no environment variables in the runtime
  path).

Some incoherent couplings are **deliberately not enforced** because the incoherent
combination is the shipped default set — enforcing them would make `Config.default()` throw
and take the whole package with it. These are surfaced as documented findings (see
`min_tradeable_price_from_stop_bounds` and `signal_cap_ticks_at_min_r`) and pinned in tests,
because resolving them is a specification decision, not a module decision.
