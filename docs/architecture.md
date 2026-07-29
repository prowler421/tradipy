# Architecture

tradipy is the invariant layer of a Ross Cameron momentum trading system. It is a small,
pure library whose job is to make the rules in [`PRD.md`](PRD.md) executable and enforce them
with tests. This document explains the shape of the code and the invariants that hold it
together. `PRD.md §20` (Computation Semantics) is normative and governs on any conflict.

## Module structure

Eight library modules plus a CLI entry point, with a strict one-way dependency graph:

```
rounding.py  ◄── params.py ◄──┬── quotes.py ──┐
                              ├── score.py  ──┤
rejects.py   ◄────────────────┴── gates.py  ──┼── poc.py ◄── __main__.py
                                              │
bars.py  ─────────────────────────────────────┘
```

`rounding`, `rejects` and `bars` depend on nothing but the standard library. `params` depends
only on `rounding`; `quotes` and `gates` depend on `params` and `rejects`; `score` on
`params`. `bars` is standalone because §20.4 is pure geometry over candles — it reads no
threshold, which is also why §3.2 criterion 2 arrives as a caller-supplied predicate.

The ordering is deliberate: rounding is the most primitive concept, thresholds are defined in
terms of it, and the gates are defined in terms of thresholds. `poc` sits above all of them
and only `__main__` depends on `poc` — nothing in the library does.

`Reject` lives in its own module rather than in `gates` because two layers raise it —
`gates` for the pre-entry gates and `quotes` for §20.14 validity — and a quote is the lower
level construct. Keeping the enum in `gates` would have made `quotes` depend on `gates`,
inverting the layering for no reason. It is re-exported from `tradipy.gates`, so
`from tradipy.gates import Reject` still works.

`tradipy/__init__.py` imports the seven library modules so the names it advertises resolve as
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
reads it by name.** No numeric literal for a registered threshold may appear elsewhere; the
registry test enforces the same discipline against the PRD prose.

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
either. Every rounded threshold goes through `_rounded(cfg, value, *governed_by)`, which
reads the polarity from the parameters that govern it. Naming a `Polarity` member at the
call site gave direction two definitions that nothing reconciled, which is the v1.3.1 defect
reproduced inside the mechanism built to close it. `gates.py` no longer imports `Polarity`.

### `tradipy.poc`

Composes the gates into one `evaluate(candidate, cfg)` in the order §3.1 states them, and
carries the three §3 worked examples. It is **not** the strategy engine: it takes a candidate
that has already been found. `python -m tradipy` is the front end.

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
