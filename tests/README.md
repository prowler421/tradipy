# Invariant fixture suite

This was the first code in the project, and it is deliberately not the strategy engine.
PRD §21.1 and PLAN Workstream 11 call for it because five review rounds have each found a
defect class invisible to the check designed for the previous one. These fixtures make the
rules executable.

**The fifth class was found in the code, not in the document** — see
`test_enforcement.py`. Four guarantees the documentation asserted had a mechanism built for
them and nothing calling it, `Config.polarity()` most starkly: documented as the thing that
decides rounding direction, zero callers, and flipping a registry declaration broke no test.
The rule that falls out is the one every file here now follows: **for each documented
guarantee, write the test that performs the violation it forbids.** A test confirming the
happy path passes whether or not the guarantee holds, which is why three of the four had a
passing test sitting immediately next to the hole.

## Running

```bash
uv sync        # or, with pip: pip install -e . --group dev   (pip 25.1+)
uv run pytest
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
| `test_enforcement.py` | **Unenforced guarantee** — a rule that is stated, has a mechanism, is believed to be enforced, and is not | v0.0.1 code review: four at once. A mutable `MODE_PRESETS` read live past a "non-bypassable" cap; a registry lint blind to 7 of 29 parameters; `Config(values)` skipping range validation under a docstring reading *"every construction path validates; there is no other"*; and rounding direction decided at the call site |
| `test_computations.py` | The three PRD §20 rules that need no feed — §20.4 flagpole geometry, §20.10 composite score, §20.14 quote validity | All three were fully specified and entirely absent. §20.14 had a registered parameter and two `Reject` members that no code returned |
| `test_poc.py` | A self-checking demo that has stopped checking | `python -m tradipy demo` is what people will run instead of reading the code, so its self-check needs its own test — including `test_demo_self_check_would_catch_spec_drift`, which asserts the check can still fail |

Assertions are written against the **derivation**, not the value. `assert cap == Decimal("0.01")`
passes under a wrong rounding rule that happens to agree at that input;
`assert cap == floor_to_tick(x) and cap <= x` does not. That distinction is the only reason the
v1.3.1 class is now catchable.

## Verified by mutation

The suite was checked by breaking the spec on purpose, each mutation applied to an isolated
copy of the tree. **47/47 caught** at v0.1.0 — 22 new below, 13 carried from earlier rounds,
and 12 that survived a release candidate and drove the fixture that now catches them:

| Mutation | Tests failed |
|---|---|
| `MAXIMUM` rounds `ceil` instead of `floor` (the v1.3.1 defect) | 4 |
| One-tick clamp removed (the A25 outage) | 2 |
| Polarity forced to `MAXIMUM` at every `_rounded` call site (the v0.0.1 defect) | 10 |
| `MODE_PRESETS` unfrozen | 1 |
| Range validation removed from `__post_init__` | 2 |
| `mode` default back to `experienced` | 1 |
| Runtime `mode` check removed | 1 |
| §7 cap check reads the preset instead of the effective value | 1 |
| Composite-score weight-sum coupling dropped | 1 |
| `position_size` ignores `max_stop_pct` | 1 |
| 1%-of-ADV cap dropped from sizing | 1 |
| §20.14 staleness never fires | 2 |
| §20.14 crossed quote admitted | 3 |
| §20.14 odd-lot check dropped | 4 |
| §20.4 height uses run extremes instead of first-low/last-high | 1 |
| §20.4 tie-break ignores volume | 1 |
| §20.10 normalization cap removed | 1 |
| §20.10 negative inputs not floored at zero | 1 |
| §20.10 `float_inverse` unfloored | 1 |
| PoC skips the room gate | 1 |
| PoC self-check made vacuous | 2 |
| Registry lint blinded again (`normalize()` + a hardcoded threshold) | 1 |

Every mutation from earlier rounds is still caught, at counts re-measured against this suite
rather than carried over: `max_spread_r` loosened 0.15 → 0.30 (5), `sep_cost_multiple`
weakened 3.0 → 1.0 (9), `min_sep_r` 0.5 → 0.0 (3), `est_round_trip_cost_per_share`
understated (9), separation floor rounding down (9), sizing budget doubled (14), T1 no longer
exactly 2R (11), `required_room` ignoring the separation term (7), max-stop ceiling deleted
(6), `vwap_reclaim_stop` discarding its verdict (1), `Config.values` copy made conditional
(1), `validate_couplings` removed from `__post_init__` (3), binding reason chosen from
rounded terms (2).

And the twelve rounding-and-truncation mutations that **survived the entire suite at
v0.1.0-rc** and are now caught — the exit ladder rounding targets down (1), the raw stop and
the min-stop floor rounding up (1 each), the VWAP band rounding up (1), `position_size`
rounding or ceiling instead of flooring (1 each), the buying-power and ADV caps rounding (1
each), `measured_move` rounding (1), `select_flagpole`'s tie going to the latest run (1), and
`t1_r_multiple`'s lower bound back at 1.0 (1). They survived because all three §3 worked
examples are numerically degenerate: every level is already a whole tick and all three risk
divisions are exact, so ceil, floor and round agree on every one. See the non-degenerate
fixture at the end of `test_boundary.py`.

**Two rows are worth reading twice.**

The **max-stop ceiling**: before `vwap_reclaim_stop` returned its verdict, deleting the
ceiling killed *zero* tests, because its only caller discarded the result. A mutation this
table would have scored as caught was in fact unreachable — mutation testing cannot see a
gate whose verdict no caller consumes, and the score reports that as coverage.

The **registry lint** row is the same lesson one level up, and it took two attempts to write.
The first mutation of it *survived*, and the survival was the mutation's fault rather than
the suite's: it removed `str(value)` from the search set but left `str(int(value))`, which
still matched. Only re-creating the original bug exactly — a search set built from
`normalize()` alone — reproduced the blindness, and then
`test_lint_search_terms_contain_no_scientific_notation` caught it. **A mutation that is not
faithful to the defect proves nothing in either direction**, and a surviving mutant is a
claim about the suite that has to be checked before it is believed.

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
threshold as a literal. Each entry is `name|literal|section`, and `name` may list several
parameters joined by `+` — `max_pct_of_adv`, `vwap_stop_band_pct` and
`max_risk_per_trade_pct` are all 1%, and attributing the hit to whichever one happened to be
registered last sent readers to the wrong place to look. Most are legitimate — worked examples must state numbers — so the lint
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

Three more of the same shape were registered in v0.1.0 and want §2.0 rows too:
`min_premarket_volume` (100,000 shares), `max_vwap_extension_open_pct` (5%, the first-30-min
branch of a two-branch §2 rule whose *other* branch was already registered), and
`hod_proximity_pct` (0.5%). §20.10's nine score parameters and §14.2's `min_conviction_score`
are stated in a code block rather than a definition table, which is the same gap in a
different dress.

### Two further findings from v0.1.0

4. **§2 has no Bounds column, so roughly half the registry's ranges are invented here.**
   `params.py` claimed all values *and bounds* were transcribed from the cited PRD tables.
   True of §2.0, §3.1.2 and §3.1.3, which have a Bounds column; false of §2, §3.1.1, §3.4,
   §20.10 and §20.14, which state defaults only. Every such row now marks itself
   `(bounds: code)`, and the distinction is enforced — a transcribed bound is a spec fact, an
   originated one is this module's judgement and can be revised without a spec decision.
   → `test_code_originated_bounds_are_declared_as_such`

5. **`score_cap_float` (§20.10) and `max_float_shares` (§2) are both 20,000,000.** §20.10
   states its normalizer independently of §2's scanner ceiling, so they are two parameters
   rather than one restated — but they mean nearly the same thing. Lowering §2's float
   ceiling without the normalizer would silently give at-ceiling names a non-zero float
   score. Pinned so the divergence has to be a decision.
   → `test_score_float_cap_currently_equals_the_scan_filter`

### Thresholds the code deliberately does not invent

PRD §3.2 criterion 2 states three thresholds — at least 3 candles, combined move ≥ 2%, total
volume ≥ 2× the prior 30 bars' average — and none has a registry entry. `bars.select_flagpole`
therefore takes the qualification test as a **caller-supplied predicate** rather than either
registering values the PRD never defined or writing them as literals. §3.2's criteria 3, 5
and 7 (retrace ≤ 50%, flag volume ≤ 70%, breakout volume ≥ 2×) are in the same position.
These are setup rules rather than §20 computation semantics, so they belong to whatever
implements §3.2 — but they need §2.0 rows before it does.
