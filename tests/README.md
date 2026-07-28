# Invariant fixture suite

This is the first code in the project, and it is deliberately not the strategy engine.
PRD §21.1 and PLAN Workstream 11 call for it because four review rounds of `docs/PRD.md`
each found a defect class invisible to the check designed for the previous one. Prose review
found all four; nothing stops a fifth from landing silently. These fixtures make the rules
executable.

## Running

```bash
pip install -e ".[dev]"      # or: uv pip install -e ".[dev]"
pytest
```

Everything is `Decimal`. Binary float cannot represent `$0.01`, and almost every rule here
compares a price against a tick boundary, so float would produce comparison errors that look
like logic bugs (PRD §9.2).

## What each file defends

| File | Defect class it catches | Origin |
|---|---|---|
| `test_worked_examples.py` | **Arithmetic** — an example that violates its own rules | v1.0 shipped four: a stop at $6.22 where the rule required $6.20, a T2 below T1, three different entry prices in one example |
| `test_parameter_registry.py` | **Consistency** — a threshold restated as a literal, one copy updated | v1.2: `room_gate_multiple` raised to 2.5 in two sections while all three setup criteria still read `2 ×` |
| `test_boundary.py` (boundary marks) | **Joint incoherence** — two individually-legal parameters that cannot both hold | v1.3: the §4.2 spread filter admitted 1% of price while §3.1.2's floor consumed spread as input; every example failed its own gate at the widest spread admitted |
| `test_boundary.py` (polarity marks) | **Generalization** — a rule stated more broadly than its justification supports | v1.3.1: "gate thresholds round up" is true for a floor, false for a ceiling; §3.1.3's spread cap inherited `ceil` by analogy and became more permissive |

Assertions are written against the **derivation**, not the value. `assert cap == Decimal("0.01")`
passes under a wrong rounding rule that happens to agree at that input;
`assert cap == floor_to_tick(x) and cap <= x` does not. That distinction is the only reason the
v1.3.1 class is now catchable.

## Verified by mutation

The suite was checked by breaking the spec on purpose, each mutation applied to an isolated
copy of the tree. **15/15 caught:**

| Mutation | Tests failed |
|---|---|
| `MAXIMUM` rounds `ceil` instead of `floor` (the v1.3.1 defect) | 2 |
| One-tick clamp removed (the A25 outage) | 2 |
| `max_spread_r` loosened 0.15 → 0.30 | 4 |
| `sep_cost_multiple` weakened 3.0 → 1.0 | 7 |
| `min_sep_r` 0.5 → 0.0 (drop the R term) | 2 |
| `est_round_trip_cost_per_share` 0.015 → 0.001 (understate costs) | 6 |
| Separation floor rounds down instead of up | 5 |
| Sizing budget doubled | 4 |
| T1 no longer exactly 2R | 6 |
| `required_room` ignores the separation term | 4 |
| Max-stop ceiling deleted | 3 |
| `vwap_reclaim_stop` discards the ceiling verdict | 1 |
| `Config.values` copy made conditional (proxy back door) | 1 |
| `validate_couplings` removed from `__post_init__` | 3 |
| Binding reason chosen from rounded terms | 2 |

The bottom five were added after review. The **max-stop ceiling** row is the one worth
reading twice: before `vwap_reclaim_stop` returned its verdict, deleting the ceiling killed
*zero* tests, because its only caller discarded the result. A mutation this table would have
scored as caught was in fact unreachable — mutation testing cannot see a gate whose verdict
no caller consumes, and the score reports that as coverage.

**Copy `docs/` into the mutant tree, not just `src/` and `tests/`.** Two registry tests read
`docs/PRD.md` and fail on its absence, which silently inflates every row by 2 and makes
mutations look caught when they were not.

**The mutation check paid for itself twice.** Replacing `required_room` with its proportional
term alone initially passed the *entire* suite, because all three worked examples clear the
separation term with margin — the gate was untested at the point where it binds. Later, the
`Config.values` mutation exposed a test that mutated the shared module-level `CFG`: with the
freeze removed it corrupted `min_stop_distance` for three unrelated tests, so one mutation
appeared to kill four. A test asserting that mutation is impossible must not be the thing
performing it on shared state. A fixture that catches no mutation is decoration; re-run this
after adding any.

Run it with a script that copies the tree per mutation. Do not mutate in place: several
mutations are byte-identical in length (`"0.15"` → `"0.50"`), so Python's `.pyc` cache treats
the restored file as unchanged and you get phantom failures.

## The registry baseline

`registry_baseline.json` freezes the 68 places where `docs/PRD.md` restates a registered
threshold as a literal. Most are legitimate — worked examples must state numbers — so the lint
fails on *new* occurrences rather than demanding zero. Demanding zero would be unachievable
and would get switched off.

Regenerate deliberately, and read the diff:

```bash
REGEN_REGISTRY_BASELINE=1 pytest tests/test_parameter_registry.py
```

Six restatements of `max_spread_abs` and six of `max_spread_pct` currently sit across §3.2,
§3.3, §3.4, §4.2, §13 and §15. Each is a future divergence point; the baseline is what makes
the seventh visible.

## Four open spec discrepancies these tests pin

None is a code bug — each follows from defaults that were individually reasonable, set in
different revisions. All are recorded as tests that fail once resolved, so they cannot be
closed silently in either direction.

0. **`room_gate_multiple` is inert at its default.** The unified requirement takes
   `max(2.5R, 2R + min_separation)`, and `min_separation` is floored at `min_sep_r × R` = 0.5R
   *by construction*. Since 2.5 = `t1_r_multiple` + `min_sep_r` = 2.0 + 0.5 exactly, the
   proportional term can never *exceed* the separation term — only tie it. So the §3.1.1 room
   gate does no work at 2.5, and `INSUFFICIENT_ROOM` is emitted only on ties, never because
   the proportional constraint was stricter. §3.1.2 calls `min_sep_r` *"redundant with a 2.5
   room gate"*; the dominance runs the other way. Resolve by raising `room_gate_multiple`
   above 2.5 or deleting it and letting §3.1.2 stand alone.
   → `test_room_gate_multiple_can_never_strictly_bind_at_defaults`

1. **A25's recommended validator rejects the PRD's own defaults.** Its prose locates the
   outage boundary at `tick / max_spread_r` = $0.0667, but its recommended config-load check
   is `2 × tick / max_spread_r` = $0.1333, against a shipped `min_stop_distance` of $0.10.
   Factor 1 is enforced here; closing the gap needs a spec decision — raise
   `min_stop_distance` to $0.14, raise `max_spread_r` to 0.20, or amend A25 to factor 1. All
   three change trading behaviour.
   → `test_a25_recommended_validator_would_reject_the_shipped_defaults`

2. **The scan-cap clamp changes what `max_spread_pct` means below $2.00.** At the 0.5%
   default, `floor_to_tick(0.005 × price)` is $0.00 under $2.00, so the clamp raises it to one
   tick — 1.00% of price at $1.00, double what the parameter declares. In absolute terms it is
   maximally strict: only 1-tick spreads pass across the whole $1.00–$1.99 band, which §2
   includes in the tradeable universe. Expectancy is protected by the signal-time `0.15 × R`
   gate, so this is a truthfulness gap rather than a live risk — but the band is *de facto*
   excluded by a clamp added for an unrelated reason. Phase 2a (A21) should quantify it.
   → `test_scan_cap_clamp_binds_below_two_dollars`

3. **The stop bounds empty the bottom of the price band.** `min_stop_distance / max_stop_pct`
   = $0.10 / 5% = **$2.00**, but `min_price` defaults to $1.00. Below the crossover the
   minimum-stop floor widens every stop to $0.10, which the maximum-stop ceiling then
   rejects, so *every* entry in $1.00–$1.99 is unconditionally `STOP_TOO_WIDE` regardless of
   setup quality, spread or R. Structurally this is finding 2 reached by an independent
   mechanism and strictly stronger: the clamp makes that band maximally strict, this makes it
   empty. **Not enforced in `validate_couplings`** — the incoherent combination is the
   shipped default set, so raising would make `Config.default()` throw and take every call
   path with it. That is precisely the defect in A25's recommended validator (finding 1), and
   enforcing this one would repeat it. Resolve by raising `min_price` to $2.00, making
   `max_stop_pct` price-dependent, or lowering `min_stop_distance` below $0.05 — which A25's
   coupling then rejects, so the three constraints need deciding together.
   → `test_stop_bounds_empty_the_bottom_of_the_price_band`,
   `params.min_tradeable_price_from_stop_bounds`

`gates.vwap_reclaim_stop` also surfaced a smaller one: §3.4 writes the stop band as
`VWAP × 0.99`, a 1% threshold with no name, no bounds, and no row in any definition table,
sitting directly on the MVP path. It is registered here as `vwap_stop_band_pct`; the PRD should
give it a §2.0 row.
