# Changelog

All notable changes to the tradipy **package** are documented here. This file follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> The specification's own correction history is tracked separately in
> [`docs/CHANGELOG.md`](docs/CHANGELOG.md). This file tracks the code, tooling, and packaging.

## [Unreleased]

### Added — Phase 4, the §3 strategy engine (PLAN D33)

- **`src/tradipy/session.py`** — PRD §20.1, §20.2, §20.3, §20.5 and §20.6 over an ordered series:
  session VWAP on typical price, HOD on wicks with §20.3's not-the-opening-print rule, the 9 EMA
  with §20.5's seeding and its `None` before the period has closed, §20.1's missing-bar gap rule,
  and `tighter()` / `wider()` as §20.6's named definitions rather than a bare `max()` at a call
  site. A `SessionBar` carries **minutes from the session open as an `int`**, not a timestamp:
  §21.1 forbids `datetime.now()` in strategy code and every §20.1 rule Phase 4 needs is ordinal.
  `Session.through(i)` is the truncation primitive §21.1's look-ahead property test needs.
- **`src/tradipy/setups.py`** — §3.2 Bull Flag, §3.3 HOD Breakout and §3.4 VWAP Reclaim, each a
  pure function of a session and a trigger index; §20.11's arbitration (rules 1 and 2); and §3's
  post-entry rules as predicates. Returns a `SetupOutcome` carrying **every** criterion with the
  arithmetic that decided it, plus `Levels` — the derived entry, stop, R, ladder, resistance set,
  room requirement and separation floor — which are reported on a **rejected** setup as well.
  Only the share count is withheld from a rejection, on §4.1's argument for withholding the score.
  - No threshold literal and no rounding direction appears in it, and
    `test_the_setup_layer_reads_nothing_and_imports_nothing_that_could` holds both new modules to
    an import **allowlist**, as `scanner.py` already was.
  - **Nothing in it is calibrated**, and of its twenty registry rows **all twenty are marked `(bounds: code)`** — eighteen cite §3.2, §3.3 or §3.4, sections with no parameter table and no Bounds column, and the other two cite §20.1 and §20.5, which have none either. See `docs/PHASE-4-DESIGN.md` and PLAN **D33**.
- **`Reject.SETUP_NOT_PRESENT`** — the one rejection code Phase 4 adds. **`ExitReason`** is a third
  enum (`BAILED_OUT`, `INVALIDATED`), both names transcribed from §20.12's state machine: a
  rejection declines a trade never taken and an exit closes one that was.
- **`gates.t1_level(entry, r, cfg)`** — split out of `exit_ladder`, which now delegates to it,
  because §3.3's T2 is defined relative to T1 and a second derivation of `entry + t1_r_multiple × R`
  is the v1.2 defect class. Asserted structurally, like the `scan_spread_cap` delegation.
- **Twenty registry rows** for §3's inline thresholds, all `(bounds: code)`: nine for §3.2
  (`flagpole_min_candles`, `flagpole_min_move_pct`, `flagpole_vol_multiple`,
  `flagpole_vol_lookback_bars`, `flag_min_candles`, `flag_max_candles`, `max_flag_retrace_pct`,
  `max_flag_volume_ratio`, `breakout_vol_multiple`), three for §3.3 (`consolidation_min_candles`,
  `hod_breakout_vol_multiple`, `hod_reclaim_invalidation_candles`), five for §3.4
  (`min_bars_above_vwap`, `max_dip_candles`, `max_dip_depth_pct`, `reclaim_vol_multiple`,
  `hod_proximity_min_candles`) and three shared (`max_pattern_gap_minutes`, `ema_period`,
  `bailout_candles`). Registry size 55 → **75**. A count that is a *constraint* carries a polarity;
  a count that is a *window* does not — the split `max_open_positions` and `rvol_lookback_days`
  already make. `bars.select_flagpole`'s `qualifies` predicate, built in Phase 3's window with no
  shipped caller, now has one: it is §3.2 criterion 2, built from the first four rows above.
- **`python -m tradipy setups`** — replays all three §3 worked examples **from bar series** and
  self-checks every derived value against its table, which is PRD §21.1's worked-example row read
  as written. It exits 0 and reports §3.4 as **rejected**: see the note below.
- **`tests/test_setups.py`** (31 functions, 38 cases) — the three worked examples from bars, §21.1's
  look-ahead property test at every legal trigger index for all three setups, §20 computation
  fixtures, boundary cases at each new threshold's own limit, polarity assertions on the two
  VWAP-derived stop candidates, and the post-entry rules. `tests/test_enforcement.py` gains a
  Phase 4 block that performs each new guarantee's violation. Two of the 31 (added at review round
  13, `docs/reviews/REVIEW-2026-07-31-round13.md` M6/M7) close a coverage gap the first draft
  shipped with: §3.4 criterion 9 (HOD proximity consolidation) had no fixture within
  `hod_proximity_pct` of HOD at all, and `evaluate_vwap_reclaim`'s "prior HOD, not the trigger
  bar's own wick" reading had no fixture where the two disagree. Both guarantees were already
  correctly implemented; neither had a test that would have noticed if they stopped being.

### Changed

- **`tests/registry_baseline.json` regenerated: 68 → 74 entries.** `flagpole_min_move_pct` and
  `max_dip_depth_pct` are both 2%, which makes `2%` a new search key for the PRD-prose lint; the
  six new entries are §3.2, §3.4, §3.5, §15, §6.5 and §11.3, all worked examples or restatements
  already present in the document. Regenerated with `scripts/regen_registry_baseline.py` and the
  diff read.
- **`_VIX_BASELINE` named in `scripts/spike2a/synthetic_data_generator.py`.** Registering
  `min_bars_above_vwap` (15 bars) made the generator's simulated VIX level (15 index points) a
  registry-lint offender without either value moving — a units collision of the kind `TICK_SIZE`
  already has with 1%. Naming it removes the second copy the regime branch had restated, and the
  lint's `EXEMPT_ASSIGNMENTS` covers the **definition line only**. The generated data is unchanged;
  the VIX series feeds §7's window selection, so changing the number was not an option.
- **`poc.simulated_universe`: SYNC's `rvol` 9 → 8.** Registering `ema_period` (9) made the fixture's
  simulated relative volume collide with it. An arbitrary input with no meaning attached, changed
  rather than exempted; SYNC's §20.10 score moves from 0.5000 to 0.4850 and no document quoted it.

### Fixed

- **`docs/PLAN.md` understated its own test count.** The fixture-suite row read *"193 test
  functions"* where the command it cites returned **196** — written into the same changeset that
  added the tests. Review round 12's **L1**, and the fourth occurrence of round 10's K6 shape. The
  row now states 237 across twelve files, and names the 117 the coverage and mutation figures were
  measured against at v0.1.0.

### Known — raised, not fixed

- **§3.4's worked example fails §3.1.1's room gate.** §3.1.1's resistance set contains *"next whole
  dollar"*; at the example's $3.83 entry that is $4.00, nearer than the $4.15 HOD its table names,
  and $0.17 against a required $0.28. Every other line of the table reproduces exactly. Raised in
  `docs/CHANGELOG.md` with three candidate resolutions and pinned in both directions by
  `tests/test_setups.py`; `python -m tradipy setups` prints it. **Not resolved in code** — a
  PRD-internal contradiction with a behaviour consequence is a spec decision.

### Added — Phase 3, the §4.2 scanner (PLAN D32)

- **`src/tradipy/scanner.py`** — PRD §4: the seven §4.2 hard filters, the seven §4.2 soft flags,
  and §4.3's ranked watchlist. `evaluate_candidate(candidate, cfg)` returns every filter's verdict
  with the arithmetic that produced it; `scan(candidates, cfg)` returns the full audit trail plus
  the survivors ranked by §20.10 and cut to `watchlist_size`. Written fresh against the PRD, not
  grown from `scripts/spike2a/` (PHASE-2A-SPIKE §8). No threshold literal and no rounding direction
  appears in it — the same two rules `gates.py` follows.
  - **It sources nothing.** §4.1's universe is Phase 2 ingestion and its catalyst check is §12.2's
    manual step; both are inputs. `test_the_scanner_reads_nothing_and_imports_nothing_that_could`
    holds it to an import **allowlist** — the repository-wide broker/network lint is a denylist, and
    for a module that is arithmetic over inputs a positive list is available and stronger.
  - **Nothing in it is calibrated.** D29 gates calibration on Phase 2a Q1 answered on measured
    data; D32 opened construction and explicitly not that. See `docs/PHASE-3-READINESS.md`.
- **`SoftFlag`** in `rejects.py` — §4.2's seven Soft codes, as a **separate enum** from `Reject`.
  §4.2 lists all fourteen rows under one "Rejection Code" column; review round 10's **K5** is what
  that invites, and `INST_OWN_HIGH` — which D24 keeps deliberately inert — is the row it named.
  Two unrelated types make mixing them a type error. `Reject` gains the six §4.2 hard codes
  (`GAP_TOO_SMALL`, `RVOL_TOO_LOW`, `FLOAT_TOO_HIGH`, `PRICE_OUT_OF_RANGE`, `ADV_TOO_LOW`,
  `NEAR_LULD`); `SPREAD_TOO_WIDE` was already there and now covers §4.2's bid-depth condition too.
- **Eight registry rows** — seven §4.2 thresholds §2 did not already carry, plus
  `watchlist_size`, which is §4.1/§4.3 and not a filter:
  `min_luld_distance_pct`, `max_market_cap`, `min_atr_multiple`, `recent_halt_lookback_days`,
  `min_institutional_ownership_pct`, `institutional_ownership_enabled` (0 — D24),
  `min_short_interest_pct`, `watchlist_size`. Registry size 47 → **55**. `min_price`, `max_price`
  and both gap floors gain the polarity declarations they had been missing.
- **`gates.scan_spread_cap(price, cfg)`** — the scan-time half of §3.1.3, split out because §4.2
  makes it a hard scanner filter and at scan time no setup has formed, so no R exists.
  `spread_caps` delegates to it; the formula has one implementation.
- **`python -m tradipy scan`** (`--verbose`) over `poc.simulated_universe(cfg)` — fourteen
  constructed candidates, seven that survive and seven that each fail exactly one hard row, so every
  filter is visibly reachable and the watchlist truncation is visible. Constructed, not read, so no
  `PROVENANCE.txt` is involved: D30's gate constrains reads.
- **`tests/test_scanner.py`** (25 functions). `HARD_FILTERS` and `SOFT_FILTERS` are compared to
  §4.2's table **parsed out of `docs/PRD.md`** — name, code, hard/soft classification and order, in
  both directions. Review finding G3 was that nothing compared the enum to the spec's namespace
  either way. Plus a `boundary` mark per filter and a `polarity` mark proving the price range's two
  ends round in opposite directions at a config where they differ (at the shipped $1.00/$20.00 both
  are whole ticks, so a test written at the defaults would pass under any direction).
- **Guarantee tests** in `tests/test_enforcement.py`: every soft input pushed to its worst value at
  once, asserting nothing was rejected (K5, performed); `INST_OWN_HIGH` attempted at the threshold,
  above it and at 100% under the shipped config, then enabled so the first assertion is not vacuous
  (D24); the LULD distance flipped to prove it follows the registry polarity; and one candidate per
  hard row proving all seven are reachable, with a guard asserting the table of seven is complete.

### Changed

- **`gates._rounded` → `Config.round_for`.** No behaviour change. The scanner needed the same
  polarity resolution, and the two ways to share it were a private cross-module import or a second
  module naming a `Polarity` member — the second being the v1.3.1 defect, which is direction having
  two definitions. Direction is registry data, so it moved onto the registry object. It now also
  raises on an empty `governed_by`: "no governing parameter" is not "any direction".
  `test_gates_do_not_import_polarity` becomes
  `test_a_rounding_module_cannot_name_a_polarity_member`, parametrized over every module that
  rounds, with `test_every_module_that_rounds_is_in_the_polarity_check` deriving that list from the
  source so it cannot go stale.
- **`tests/registry_baseline.json` regenerated** — 68 entries before and after. The only change is
  the attribution string on the fourteen `5%` entries, which now name `min_short_interest_pct`
  alongside `max_stop_pct` and `max_vwap_extension_open_pct`. No new or removed locations.
- **`scripts/spike2a/synthetic_data_generator.py`** — the three price-tier spread multipliers move
  to named constants beside the price bands they select. `Decimal("1.5")` collided with
  `min_atr_multiple` the moment §4.2's Volatility row was registered; a spread-ladder multiplier and
  an ATR multiple are unrelated quantities sharing a number, which the lint cannot distinguish and
  is right not to try. Same rationale as `_CHEAP_PRICE_USD`, already documented there.
- Trivial (convention 8, fixed not dispositioned): three historical statements in `docs/PLAN.md` and
  `docs/CHANGELOG.md` restated the *live* registry count while describing a finding from a specific
  moment ("17 of 47 registered thresholds"). Rephrased to pin the number to its moment, so the
  count-drift check is not answering for a claim about the past.

### Fixed — review round 11 (`make check` was red)

**`make check` failed against the tree that first proposed this change**, and
`docs/PHASE-3-READINESS.md` — part of the same changeset — asserted it was green. That row is
corrected there, with why the shape of the error matters. The gate failures, all introduced by
Phase 3:

- **`ruff check`, 11 errors.** Ten `B008` in `poc._sim`, whose keyword-only defaults called
  `Decimal(...)` in the signature; the baseline is now module constants (`_SIM_*`), which reads
  better anyway. One `SIM300` in `test_scanner.py`, replaced by asserting what the conversion
  *does* — `daily_gap_pct * PERCENT_PER_UNIT == D("25.00")` — rather than the constant it is,
  which is the assertion convention 4 asks for regardless of the lint.
- **`ruff format --check`, 2 files.** `test_scanner.py`'s LULD boundary assertions and one
  set-comprehension condition in `test_enforcement.py` had been hand-wrapped. `CLAUDE.md` says
  formatting is Ruff's job; these were written to a guess at what Ruff wanted because Ruff could
  not be run. Both are now bound to locals and short enough that the question does not arise.
- **`basedpyright`, 3 errors, one cause.** `sorted(TRIPS_HARD_FILTER, key=lambda c: c.value)`
  written inline as `parametrize`'s `argvalues` let the expected `ParameterSet` type flow back
  into `sorted()`, inferring `c: ParameterSet`. Hoisted to `HARD_FILTER_CODES`, which breaks the
  inference chain. Correct at runtime throughout; a real failure of the project's toolchain.

Also from that round, non-blocking:

- **`simulated_universe`'s baseline short interest sat above `min_short_interest_pct`**, so
  `HIGH_SHORT_INTEREST` fired on all fourteen candidates and drowned out every other flag in the
  demo. The baseline now raises nothing and each survivor raises one distinct flag; `SYNGAP`
  keeps one *beside* its rejection, deliberately, so the demo shows a flag that changes nothing.
- **Soft rows are evaluated on rejected candidates too**, which is a third reading of §4.1's
  sequential pipeline diagram and was the one such reading not written down. Now on
  `evaluate_candidate` and in `docs/CHANGELOG.md`'s spec-question table.

### Fixed — from two automated checks over this change

Two reviews were run before the round above: one against `CLAUDE.md`'s conventions and review
checklist, one fact-checking `scanner.py` filter-by-filter against PRD §4. **Neither is a
committed review artifact** — they were run in-session and are not in `docs/reviews/`, which
holds independent rounds kept unedited as the record. Round 11 correctly flagged that this
section had credited them in language that implied otherwise, and that neither committed review
document mentions `scanner.py` at all. Read the findings below as this change checking its own
work under convention 8, not as an independent round; the fixes are each covered by a named
test, which is the part that is verifiable. Spec questions both raised are in
`docs/CHANGELOG.md`, not here.

- **The rounding-consumer guard was narrower than its own name.**
  `test_every_module_that_rounds_is_in_the_polarity_check` derived its list from `"round_for" in
  source`, while being named — and described here — as covering every module that rounds.
  `quotes.py` rounds §20.14's estimated spread with a bare `ceil_to_tick` and was outside it, as
  would be any future module doing the same while naming a `Polarity` member. That is the v1.3.1
  shape (a rule stated more broadly than the thing it ranges over) reproduced inside the test
  written to prevent it. Now derived by AST from **every** rounding call, and `quotes.py` is in
  `ROUNDING_CONSUMERS`.
- **"The formula has one implementation" was structural, not tested.** Nothing failed if
  `spread_caps` re-inlined the scan-cap arithmetic instead of delegating — equal outputs prove
  nothing, since two copies agree until one is edited, which is the entire v1.2 story.
  `test_the_scan_spread_cap_has_exactly_one_implementation` asserts the call by AST and the
  agreement across the §4.2 price range.
- **`Config.round_for()` with no governing parameter reported "conflicting polarities []".** There
  is no conflict; there is no classification. It now says so, and the test matches the new wording
  rather than pinning the misleading one.
- **`_rank_key`'s tiebreak rationale was half wrong, and the test did not check it.** Its docstring
  argued ties arise between *different* inputs via `float_inverse` and `norm_rvol` saturation; the
  test used three identical candidates, which tie trivially. Writing the real test showed the
  `float_inverse` half is unreachable *among survivors* — `score_cap_float` and `max_float_shares`
  are the same number, so the only float that saturates the normalizer and passes §4.2's Float
  filter is the cap exactly. Docstring corrected, and both halves are now pinned.
- **`_rank_key`'s "a rejected candidate is never ranked" guard had no test**, being unreachable
  through `scan()`. Now called directly.
- Trivial, fixed in place: `CLAUDE.md` convention 2 and both review checklists still mandated
  `_rounded`, which this change deleted, and `CLAUDE.md`'s repository-layout list omitted
  `scanner`; `CONTRIBUTING.md` the same. `params.py`'s docstrings named `gates` as the only
  polarity consumer. `PHASE-3-READINESS.md` said "the scope is 7 of §4.2's 14 rows" directly above
  a list of all 14 (the K5 distinction is *rejection paths*, not rows touched). The registry block
  comment and this file called all eight new rows §4.2 when `watchlist_size` is §4.1/§4.3.
  `test_documentation.py` — the file whose purpose is catching counts that drift — had four wrong
  ones in its own prose; the numbers are now derived there too, not written. `PLAN.md`'s
  registered-but-unread count moved 11-of-47 → **9 of 55** because the scanner gave
  `min_premarket_volume` and `rvol_lookback_days` readers, and was restated rather than left. Four
  documents said "two §4.2 readings" above a table that has grown past that; they now point at the
  table instead of counting it. `scanner.py` now names the two §4 things it deliberately does not
  do — §4.4's schedule (needs a clock, which D30 forbids it) and §4.1's "common stock" predicate
  (no security type on `ScanCandidate`) — because an omission nobody wrote down is
  indistinguishable from an oversight.

### Added

- **Simulated Q1–Q4 inputs.** `synthetic_data_generator.py` now emits `floats.csv`, `latency.csv`,
  and `vendors.csv` alongside the existing market-microstructure files; new `q1_vendors.py` applies
  §7's Q1 thresholds to the vendor matrix. All four questions remain pipeline-only on
  `SIMULATED` origin per D30.

### Fixed

- **Q4 quote selection (review H4/H6).** `signal_bars.csv` requires `signal_at`; `feeds.quote_at_or_before`
  picks the NBBO in force at that instant and derives `age_seconds` for §20.14. Stops every setup
  on a symbol-session from sharing the session's last tick. `tests/test_spike2a_q4_quote_selection.py`.
- **Q1's disposition-withholding guarantee had no test (review round 9, J2).** Q2, Q3 and Q4 each
  assert that `report()` prints `pipeline outcome (NOT a §7 verdict)` rather than a real verdict on
  `SIMULATED` input; `q1_vendors.report()` had the same `if prov.answers_prereg` branch but no test
  for it, and removing the branch entirely left the rest of the suite green.
  `test_q1_withholds_its_disposition_on_simulated_input` closes it, mirroring Q2's paired
  withheld/measured assertions.
- **`q1_vendors.report()` asserted a §7 Q1 negative from zero vendor trials (review round 10,
  K3).** On measured input with an empty or wholly-unparsable `vendors.csv`, it fell straight into
  the "no provider passes Q1" branch and printed `Implication per §6: PRD §4 is rewritten before
  Phase 3 (scanner) starts` — the spike's largest possible consequence, from a file with nothing in
  it. Q2, Q3 and Q4 each guard the empty-sample case in one line; Q1 had none. Now guarded the same
  way: zero trials prints `UNANSWERED — no vendor trials recorded, have 0` on either origin, never a
  `§7 verdict` or a PRD §4 rewrite. `test_q1_does_not_claim_a_verdict_from_zero_vendor_trials`
  reproduces the defect by mutation (removing the guard reintroduces both strings) and closes it.
  No PRD rule changes.

### Changed — all data is simulated (PLAN D30, `CLAUDE.md` convention 9)

- **`scripts/spike2a/q3_collect.py`, `scripts/spike2a/q4_collect_real_data.py` and
  `feeds.IbkrHistoricalTicksFeed` are removed.** All three imported `ib_insync` and read real
  IBKR data; `q3_collect.py` additionally placed `whatIfOrder` previews in a loop and its
  docstring named the live socket (7496) in two places, contradicting both PHASE-2A-SPIKE §3.2
  and `feeds.py`'s own comment. They were added in this same `[Unreleased]` section, which is
  where the entries below still describe them — left standing rather than rewritten, because the
  history is the point: the code was correct under §3.2 as written, since §3.2 forbade *trading*
  and reading a market is not trading. Recoverable at `3ca9e7b`, the last commit
  that contains them.
- **`scripts/spike2a/provenance.py`** — a `SIMULATED` → `PAPER` → `LIVE` ladder, a
  `PERMITTED_ORIGINS` constant holding the current rung, and `require()`, which every measurement
  module now calls before reading anything. `PROVENANCE.txt` becomes machine-readable: it declares
  an origin and names each file it covers with that file's SHA-256, so a file cannot inherit a
  neighbour's declaration and a declared file cannot be edited afterwards. Undeclared input raises
  rather than defaulting to `SIMULATED` — the file that most needs a declaration is the one
  somebody added without writing one.
- **`q4_spreads.report()` and `q3_latency.report()` take a `Provenance`**, required rather than
  defaulted. On simulated input Q4 prints `pipeline outcome (NOT a §7 verdict)` and raises no D7
  disposition, and Q3 withholds the §5.5/§4.4 disposition entirely. This is the mitigation PLAN's
  sixth defect-class row proposed and review round 7 declined to build: *"any value capable of
  triggering a D7 disposition must be reproducible from a provenance-marked input."* The marker
  had existed since the generator landed and was read by nothing, so the pipeline printed
  `§7 verdict: …` over fabricated quotes in the format it would use for measured ones.
- **Twenty-one enforcement tests, including an import lint,** in `tests/test_enforcement.py`:
  no broker SDK, vendor client or network module may be imported in `src/`, `scripts/` or
  **`tests/`** — unlike the registry lint, which exempts `tests/` because a fixture must state a
  literal, there is no analogous reason to import a broker from a test. AST-based, so a module
  named in a docstring is a string and an `import` is an import; guarded by a planted-import test
  covering module scope, aliases, submodules, function-local and constructor-local forms. Each
  guarantee was verified by removing its guard and confirming the test goes red.
- **`scripts/spike2a/sample.py` is gated too.** It arrived from `main` in the same merge that
  produced D30, written against a tree where the gate did not exist, and read `vix.csv` and
  `preopen.csv` without declaring either. It is the only entry point that reads two files, which
  is where undeclared data most easily enters — each half looks like the other call's
  responsibility. This is the shape to expect: every branch in flight predates a
  repository-wide invariant, so the failure is correct code arriving without a call it had no
  reason to make. `test_every_spike_entry_point_gates_its_input` is enumerated, so a new module
  under `scripts/spike2a/` means a new row in it.
- **`test_widening_the_permitted_origins_cannot_pass_unnoticed`** pins `PERMITTED_ORIGINS` to
  `{SIMULATED}`. It fails when that line changes, deliberately: advancing the ladder is a PLAN
  decision — and for `LIVE`, the PRD §18.8 evidence bar — so changing the line, the assertion and
  the decision together is the recorded advance, and changing the line alone is not available.

### Fixed

- **`random.seed(SEED)` moved from `__main__` into `synthetic_data_generator.main()`.** `main()`
  unconditionally wrote a `PROVENANCE.txt` asserting its output came from `random.seed(SEED)` —
  true via the command line, false for any programmatic call, and the file said so either way. A
  provenance marker that is conditionally true is the defect it exists to prevent. Output was
  unchanged **by this fix**, measured at `b70fa7a`: 156 symbol-sessions, 147 signal bars, 8,820 NBBO
  samples, Q4 reporting 1.36% aggregate with 14.29% in the cheapest decile. Those figures are
  specific to that commit and were superseded by the generator rewrite in `d03b35b` — see
  `docs/reviews/claude-PHASE-3-REVIEW.md` finding K1 for the current ones.

### Added

- **`tests/test_spike2a_instrumentation.py`** — calibrates Phase 2a instrumentation against
  the library: AST check that ``generate_signal_bars`` calls ``apply_stop_floor_and_ceiling``,
  runtime checks that ``R = entry − stop`` and rejected stops are dropped, and that ``q4_spreads``
  imports ``spread_caps`` / ``spread_at_signal`` rather than reimplementing them. Sixth
  defect-class mitigation; not full spike coverage (PHASE-2A-SPIKE §8).
- **`scripts/spike2a/`** — the Phase 2a data feasibility spike, instrumented. Throwaway
  investigative code per PHASE-2A-SPIKE.md §8: not imported by `src/tradipy/`, no coverage
  obligation, and Phase 3 gets written fresh against the PRD rather than grown from it. Seven
  modules — `prereg.py` (§7's pre-registration table, so the pass thresholds are read rather than
  re-typed), `windows.py` (the VIX window rule), `universe.py` (the §7 selection rule and its
  exclusions), `feeds.py` (the swappable NBBO fetch layer), `q4_spreads.py`, `q2_float.py`,
  `q3_latency.py` — plus `__init__.py`, and `synthetic_data_generator.py` below. Stdlib-only and
  CSV-driven, so the whole pipeline runs with no broker and no
  subscription; `ib_insync` was imported lazily inside one constructor and was deliberately not
  a package dependency. *(Superseded by D30 above, which removed that constructor and two of
  the modules, and added `provenance.py`. Left standing as the record of what shipped.)*
  Q4 computes its caps with `gates.spread_caps` and its spread with
  `quotes.spread_at_signal` rather than reimplementing either (§4.3). **No `src/tradipy/` change
  and no new dependency.**
- **`scripts/spike2a/synthetic_data_generator.py`** — fabricates `vix.csv`, `preopen.csv`,
  `signal_bars.csv` and `quotes.csv` under a fixed seed so the Q4 pipeline can be exercised before
  a vendor answers. It had no changelog entry until review round 7, which is how a 381-line module
  reached `main` unrecorded; `.gitignore`'s note on `data/spike2a/` is corrected with it, having
  described the directory's contents as "large and vendor-licensed" when everything ever written
  there was fabricated locally. Everything it writes is synthetic and it writes a `PROVENANCE.txt`
  beside the files saying so; no number computed from its output answers Q1–Q4. Four defects in it
  are fixed under *Fixed* below, one of which changed a §7 verdict.
- **`scripts/spike2a/q3_collect.py` and `scripts/spike2a/q4_collect_real_data.py`** — the two
  collectors that talk to a live IBKR paper gateway instead of reading a CSV: the first measures
  real signal-to-order latency via `whatIf` preview round-trips, the second fetches real
  historical NBBO ticks for a symbol list and date range into `quotes_real.csv`. Both merged with
  no changelog entry, which is H14 recurring in the commit after the one that found it. Neither
  is imported by `src/tradipy/`; both lazy-import `ib_insync` behind the same
  `# pyright: ignore[reportMissingImports]` pattern as `feeds.IbkrHistoricalTicksFeed`; neither
  stores an IBKR credential anywhere — see `scripts/spike2a/TEST_SETUP.md` (moved and corrected
  under *Fixed*).
- **`PreOpenFacts.check_units()`** — rejects `gap_premarket_pct`, `gap_daily_pct` or
  `missing_nbbo_pct` above `1`, because the registry stores gap thresholds as fractions and a CSV
  supplying `12` for a 12% gap compares `12 >= 0.04` — true for every row, so the gap filter stops
  rejecting anything while still reporting that it filtered. The same error on `missing_nbbo_pct`
  inverts it: every session becomes a vendor coverage failure that never happened. Called from
  `classify()` and deliberately not from `from_csv_row`, which folds `ValueError` into an
  unparsable-row count where a `UnitError` would vanish. It caught a real instance immediately —
  the synthetic fixture used to smoke-test the module had `missing_nbbo_pct=9`.
- **`scripts/spike2a/sample.py`** — joins the two halves of §7's sample definition that H5 found
  nothing composing: `windows.select_windows` (the VIX-based window rule) and
  `universe.select_sample` (the §4.2 filter rule). Restricts a pre-open file to the sessions in
  the two selected windows, then applies the filter rule to what remains, reporting sessions
  outside the windows as their own count rather than folding them into a filter rejection or a
  §7 exclusion — split further into `span_gap` (a session inside a window's calendar range but
  missing from the VIX series the window was computed from — a source disagreement) and
  `out_of_span` (genuinely not a candidate), so the two are not counted as one thing. Every parsed
  row is unit-checked regardless of which population it ends up in, since a malformed row that
  happens to fall outside the windows is otherwise never seen by `universe.classify`, the guard's
  only other caller. `windows.py` is unchanged; `universe.py`'s module docstring gains two
  sentences stating that its own CLI applies the filter rule alone, which `sample.py` and
  `scripts/spike2a/README.md` both already claimed of it. See `docs/CHANGELOG.md`'s "Decided"
  section under Unreleased for why a composing module was chosen over the other two options H5
  named, including the accretion risk the finding itself raised against this option.
  `tests/test_spike2a_sample.py` exercises the join's central guarantee — each of its three
  assertions was confirmed to fail with the corresponding guard removed, per `CLAUDE.md`
  convention 6 — even though `scripts/spike2a/` carries no coverage obligation (PHASE-2A-SPIKE.md
  §8; narrowing that exemption is H2, open).
- **Two guard tests on the registry lint's new roots** —
  `test_the_lint_scans_scripts_recursively` asserts `scripts/` is in scope and that a nested file
  is reached; `test_the_lint_catches_a_planted_literal` asserts the detection half fires on a file
  in a subdirectory. Two tests because the roots can be right while the offender construction
  drops every hit, which is the failure mode the `normalize()` blind spot actually had.
- **`tests/test_documentation.py`** — asserts that counts stated in prose match the code:
  registered parameters, frozen-baseline entries, library-module count, the re-exported count in
  `__all__`, every `Reject` member being documented, and every declared pytest marker being both
  documented and applied. The v1.2 defect class (a quantity stated twice, one copy updated) was
  solved for thresholds by the registry and unsolved for the documentation's own numbers; it had
  recurred by v0.1.0 in `tests/README.md`. Verified by injecting three mutations and confirming
  each fails.
- **`scripts/check_links.py`** plus `make links`, a `check-links` pre-commit hook and a CI step —
  validates every relative Markdown link and heading anchor in the repository. Stdlib-only and
  offline by design. It found a broken citation in this file on its first run.
- **Two agent skills**, `.claude/skills/guarantee-test/` and `.claude/skills/review-round/`,
  with mirrored Cursor rules in `.cursor/rules/`. They encode convention 6 (write the test that
  performs the violation a guarantee forbids) and the review procedure including the mandatory
  adversarial fact-check.
- **`docs/README.md`** — documentation index, stating which documents are authoritative and how
  the two changelogs differ.
- **`.python-version`** pinning 3.13, and **`.github/dependabot.yml`** for GitHub Actions only —
  deliberately not for pip/uv, since the runtime is stdlib-only and `uv.lock` exists precisely
  so pins do not move on their own.
- **Coverage floor** of 95% (`fail_under`), below the ~99% measured, so the gate fails on
  collapse rather than on the next honest commit. The floor is not the claim.

### Changed

- **Release workflow** — runs ``make check`` before ``uv build`` so tagged releases cannot ship
  without the same gate CI uses.
- **Pre-commit** — ``ruff-check`` hook renamed to ``lint`` (explicit scope: ``src tests scripts``,
  matching ``make lint`` and CI).
- **Root ``README.md``** — review-round and defect-class counts aligned with ``docs/README.md``
  and PLAN Workstream 11 (six rounds, six classes).
- **``.cursor/rules/tradipy.mdc``** — deduplicated against ``CLAUDE.md``; canonical detail lives
  in ``CLAUDE.md``, the rule file keeps only always-on constraints.
- **``CONTRIBUTING.md``** — points assistant conventions to ``CLAUDE.md``.
- **`[tool.ruff.lint.isort] known-first-party` gains `"scripts"`** (`pyproject.toml`). Ruff's
  default `src` is `[".", "src"]`; this project overrides it to `["src", "tests"]`, dropping `.`,
  so `scripts.spike2a.*` resolved as third-party and isort wanted a section break before
  `tradipy.*`. Every spike module importing from both — which is every module that reads a
  registered threshold — tripped `I001`. Declared here rather than by adding a `src` root, because
  the declaration does not depend on filesystem detection and matches how `tradipy` is already
  declared.
- **The registry lint now scans `scripts/` recursively**, not `src/tradipy/*.py` alone
  (`test_parameter_registry.lint_roots()`). PHASE-2A-SPIKE.md §8 called this a prerequisite rather
  than an improvement: the spike's central task is measuring whether `max_spread_r` is calibrated,
  its code lives in `scripts/spike2a/`, and until now the only thing keeping a second definition of
  `max_spread_r` out of the code that measures `max_spread_r` was a sentence in a document.
  Verified by mutation — `Decimal("0.15")` planted in `scripts/spike2a/q4_spreads.py` fails with a
  message naming `max_spread_r`. Two related changes: the `params.py`/`__init__.py` filename
  exemption now applies **inside `src/tradipy/` only**, because exempting a filename exempts
  whatever anyone later puts in it; and offenders are labelled by repo-relative path rather than
  bare filename, since `scripts/` has subdirectories and two files called `sample.py` would
  otherwise report identically. The six live statements of convention 1's scope (`CLAUDE.md`,
  `CONTRIBUTING.md`, `params.py`, `api.md`, `architecture.md`, `.cursor/rules/tradipy.mdc`) are
  updated to match, per the rule F8 established — **and a seventh, `docs/CHANGELOG.md`'s record of
  the F8 fix, was missed and is annotated there rather than rewritten.**
- **`docs/` reorganized**: the five review documents moved to `docs/reviews/`. They are the only
  part of the documentation set that grows by one file per round. All 120 relative links updated
  and verified by the new link checker; review filenames left as they are, because
  `REVIEW-v1.2` versus `REVIEW-2026-07-28` tells a reader whether a round examined the
  specification or the code.
- **`make check` now includes `make links`**, and `make docs` shows the index rather than a bare
  directory listing.
- **`CLAUDE.md` convention 1 and five other statements of the no-literal rule** now carry the
  registry lint's actual scope. The unqualified form was finding F8, reported closed and not
  closed. *(This entry read "…exempting undistinctive values, `scripts/` not scanned" until review
  round 7. The scope was extended to `scripts/` by the entry two items above, in the same
  `[Unreleased]` section — so the file asserted both. The scope is now stated in one place per
  document and described here by reference rather than restated.)*
- **`CLAUDE.md` gains convention 8**: a finding fixable in one line, with no spec implication and
  no behaviour change, gets fixed in the same change rather than dispositioned. Six rounds of
  review machinery exist for defects that recur or need a spec call.
- **`docs/development.md`** documents the manual mutation protocol. It is *not* automated, and
  says so — a mutation harness whose own correctness is undemonstrated is a mechanism built and
  not wired.

### Removed

- **Makefile** — dropped dead ``mutants`` phony target (mutation protocol remains manual per
  ``docs/development.md``; no recipe ever existed).

### Fixed

Driven by [`docs/reviews/REVIEW-2026-07-30.md`](docs/reviews/REVIEW-2026-07-30.md) except where
noted. **`make check` was red at `3545adf`** while four documents said the guardrail it trips was
enforced and three of them that the tree was clean; everything below is in `scripts/spike2a/`, and
**no `src/tradipy/` behaviour changes.**

- **The registry lint was failing on five literals** in `synthetic_data_generator.py` —
  `Decimal("3")` and `Decimal("0.7")` (read as `sep_cost_multiple` and `min_conviction_score`) in
  `MarketRegime` fields no caller read; `Decimal("5")` (`min_rvol`) as a price band; and
  `Decimal("0.01")` twice, which was a genuine second definition of the tick. The dead fields
  (`vix_mean`, `vix_std`, `volume_ratio`) and the unused `regime` parameter of
  `generate_preopen_facts` are removed, the price bands are `int` dollars as in `prereg.py`, and
  the tick comes from `rounding.TICK_SIZE` with `ceil_to_tick` — the direction
  `quotes.estimated_spread` already uses, because understating a spread weakens both constraints
  that consume it. Ruff had twelve findings in the same file: two unused imports and one
  placeholder-free f-string (`F401`×2, `F541`), one `zip()` without `strict=` (`B905`), and **seven
  `B007`s** — loop control variables unpacked and never used — plus two lines over the 100-character
  limit. The `B007`s were found by running real `ruff`, *after* review round 7 reported the other
  five from a hand-built AST check that had no `B007` rule; they are fixed by underscore-prefixing
  the five pre-open facts a signal bar does not use, dropping a redundant `enumerate`, and marking
  `_r` unused in the quote generator, where reading R would manufacture the correlation Q4 exists to
  measure. *(This entry claimed `ruff format --check` still failed on this file. It did not — the
  claim was produced by running `ruff format --check --isolated` against a copy outside the repo,
  which drops `pyproject.toml`'s `line-length = 100` and reformats against ruff's default of 88.
  Checked in place, the file was already correctly formatted. Corrected here rather than restated
  elsewhere, since the file this mistake describes is the file the mistake was made in.)*
- **`signal_bars.r` was computed by hand** — `price × 0.97` and friends — in a module whose own
  docstring said it used the library's stop functions, and which imported
  `gates.apply_stop_floor_and_ceiling` without calling it. R is the denominator of the §3.1.3
  signal-time cap, so every cap in a Q4 run was derived from a stop the shipped rule would not
  place: all 154 R values were off the tick grid and 7 were below `min_stop_distance`. The stop now
  goes through the library, entry and price are tick-aligned, and bars the library rejects are
  dropped — six of the 154 raw stops were `STOP_TOO_WIDE` under the shipped rule, so six bars existed
  that the rule would never have produced. Across the other 148 the hand-rolled R was 0.014% to 7.7%
  low, median 1.4%. **This changed the answer** — on the same generator the §7 Q4 verdict moved from
  INERT to CALIBRATED, with the cheapest decile at 14.29% on VWAP Reclaim, which is A21's stated
  worst case. Both verdicts are statements about the generator, which is the point of the next item.
- **Half of every generated quote file was silently discarded.** The sample timestamp was
  `f"09:{30+minute:02d}"` over 60 minutes, so rows 30–59 of each bar were `09:60`–`09:89`;
  `datetime.fromisoformat` rejected 4,620 of 9,240 rows and `CsvQuoteFeed.unparsed` counted them —
  a counter that existed for exactly this purpose and that **no caller read**. Fixed with `divmod`;
  `q4_spreads.main` now prints the unparsed share, and `CsvQuoteFeed` gained `rows_read` so it can
  be reported as a share rather than a bare count.
- **`verdict()`'s fall-through message could state a falsehood** (H15). With a low aggregate held out
  of INERT by one hot decile — again, A21's case — it reported `aggregate 1.36% inside the 2%-30% dead
  band` for a rate below 2%. It now names the clause that decided the verdict and the worst decile.
- **Provenance** (H7's code half; the §7 amendment question it raises stays open in
  `docs/CHANGELOG.md`). The generator writes `data/spike2a/PROVENANCE.txt` naming itself, its seed
  and its windows, because four plausible CSVs and a documented command are otherwise indistinguishable
  from a vendor extract. Its windows now come from `windows.select_windows` over the VIX series it
  writes, not from calendar recency: the §7 rule selected two windows containing 77 of its 156 rows,
  with the quiet window empty, so every downstream number described a sample §7 would not have drawn.
- `prereg.py`'s list of numeric coincidences with registered defaults named one on **20**, which no
  constant in the module has, and omitted the two on **5**. Recomputed, and the same list in
  `docs/PHASE-2A-SPIKE.md` §8 corrected with it.
- Two `### Changed` headings in this `[Unreleased]` section (H14), with six `Added` items under the
  first of them, and this section's own statement of the registry lint's scope contradicting an entry
  nine bullets above it (H11).
- **`scripts/spike2a/README.md`** (H8) now leads with the generator, marks its four output files
  synthetic, and says which two documented inputs — `floats.csv`, `latency.csv` — have no generator
  and why, so a clean clone no longer has five run commands that all fail with `FileNotFoundError`.
  It also records that `universe.py` does not filter to the selected windows.
- **Four documentation counts that had drifted** (H12), none of them covered by
  `tests/test_documentation.py`: `docs/development.md` said six test files in two places where there
  are seven, `docs/README.md` said six documents where there are seven plus the index, and neither
  `CLAUDE.md`'s nor `docs/development.md`'s layout block mentioned `scripts/spike2a/` or `data/`.
  Extending the doc-count test to cover them is recommended and not done here.
- **`q4_collect_real_data.py` wrote `age_seconds: "0"` for every real tick** — the same defect
  H6 found in the synthetic path, in the collector merged the same day H6 was written. A written
  `0` asserts every quote was fresh at the signal instant, which this collector cannot know (it
  has no signal instant), and makes the one §20.14 staleness branch that could fire on real data
  unreachable. `age_seconds` is optional in the schema; the column is no longer written.
- **`SPIKE2A_TEST_SETUP.md`**, merged at the repository root with no changelog entry, reported a
  synthetic Q4 run — `154 signal bars, 0.00%, INERT` — as "already ran and analyzed" with no
  synthetic label, over the same hand-derived R the fix above corrects (the current number is
  `CALIBRATED`, `2/147`, cheapest decile `14.29%`). That is H7 in a new document the same day H7
  was fixed in the old one. It also instructed running `q4_spreads.py` against the synthetic
  `quotes.csv` immediately after collecting real data into `quotes_real.csv`, which would silently
  re-measure the synthetic sample and label it real. Moved to
  `scripts/spike2a/TEST_SETUP.md`, rewritten to state plainly what is real and what is fabricated,
  and corrected to note that no generator produces a real `signal_bars.csv`.
- *(Round 6)* `tests/README.md` heading read "Four open spec discrepancies" above a list of six.
- *(Round 6)* `tests/test_boundary.py` said eleven surviving rounding mutations where
  `tests/README.md`, this file and `docs/reviews/REVIEW-2026-07-28.md` all say twelve. **Round 7
  notes the enumeration in `tests/README.md` lists eleven, not twelve** — see `docs/CHANGELOG.md`.
- *(Round 6)* A stale citation in this file pointing at the pre-move review path.

## [0.1.0] - 2026-07-29

Driven by [`docs/reviews/REVIEW-2026-07-28.md`](docs/reviews/REVIEW-2026-07-28.md), the first review of the
**code** rather than of the specification. It found four guarantees the documentation asserts
and the code did not enforce, all reproduced by execution. **Three of the four fixes change
behaviour**, and one changes it for every caller: `Config.default()` is now `beginner` mode.

### Fixed — four unenforced guarantees

- **`MODE_PRESETS` was a mutable module dict read live by `Config.__getitem__`.** One
  assignment raised an already-validated config's `max_risk_per_trade_pct` to 50%, past a cap
  PRD §7 calls non-bypassable, with no validator re-running. `PARAMS`, `MODE_PRESETS`,
  `HARD_CAPS` and the inner preset dicts are now `MappingProxyType`, and the preset is
  resolved into `Config.values` at construction rather than read on every lookup.
- **The registry lint was blind to 7 of 29 parameters.** Its search set was built from
  `Decimal.normalize()`, which renders trailing-zero values in scientific notation —
  `Decimal("30000")` became `3E+4`, a string that cannot occur in source. Six hardcoded
  thresholds injected into `gates.py` passed it clean, `start_of_day_equity` among them. The
  lint now parses an AST instead of matching a regex, which also fixes two further holes it
  had: it follows the `D = Decimal` alias, and it no longer reports literals *described* in
  docstrings.
- **`Config(values)` never range-validated.** `Config({**defaults, "max_spread_r": 99})` was
  accepted, taking the §3.1.3 signal-time spread cap to $14.85 on a $0.15 R — the gate off,
  silently, on a config reporting itself validated. `__post_init__` now validates every value
  against its `Param` bounds before checking couplings, and rejects unregistered names.
- **Rounding polarity was decided at the call site, not by the registry.** `gates.py` named
  `Polarity` members directly and `Config.polarity()` had zero callers, so flipping a
  registry declaration broke no test. Every rounded threshold now routes through
  `_rounded(cfg, value, *governed_by)`, which reads the direction from the parameters that
  govern it; `gates.py` no longer imports `Polarity` at all.

### Changed — behaviour

- **`Config.default()` defaults to `beginner`** (D28), as PRD §2.0 declares. This halves
  `max_risk_per_trade_pct` (1.0% -> 0.5%), lowers `daily_loss_pct` (3% -> 2%),
  `max_open_positions` (3 -> 1) and `max_consecutive_losses` (3 -> 2). The PRD's worked
  examples are computed at the *experienced* preset and now say so explicitly.
- **`room_gate_multiple = 2.0` is legal again** (D26). `validate_couplings` rejected it while
  PRD §1, §2.0, §3.1.1 and §7 all state it is legal, citing a section that says
  "cannot go below 2.0" — which is `>=`, not `>`. The check is removed: `min_separation` is a
  MINIMUM-polarity threshold over a strictly positive quantity (`sep_cost_multiple >= 1.0`,
  `est_round_trip_cost_per_share >= 0.001`), so it is at least one tick at every legal
  configuration and §3.1.2's separation term guarantees `entry < T1 < T2` whatever the
  proportional multiple is. At 2.0 the term is inert, not unsafe. (**Not** via
  `min_sep_r * R > 0`, which a first draft of this entry argued in six places — §2.0 permits
  `min_sep_r = 0.0`, so that product is exactly zero at a legal configuration.)
- **The three §2 risk settings are configurable** (D27). `max_risk_per_trade_pct`,
  `daily_loss_pct`, `max_open_positions` and `max_consecutive_losses` are registered
  parameters with the ranges §2 states (0.25–2%, 1–5%, 1–3, 2–5). `MODE_PRESETS` is now an
  overlay bundle applied on top of the registry defaults, which is what §2.0 calls it.
  `validate_couplings` checks the **effective** value against `HARD_CAPS` rather than the
  preset, which is a constant and could never have violated it.
- **`position_size` refuses a stop the §20.13 ceiling rejects**, raising `ValueError`. It
  never consulted `max_stop_pct`, so honouring the ceiling was a convention rather than an
  invariant; any path deriving a stop without `apply_stop_floor_and_ceiling` could size a
  trade the spec requires be skipped.
- **`Config` rejects an unknown `mode` at runtime.** `Literal` is a static hint, and the
  failure was previously a bare `KeyError: 'typo'` escaping from inside `validate_couplings`.

### Added — PRD §20 computations

The three subsections that need no market-data feed to be correct. All were fully specified
and entirely absent; §20.14 had a registered parameter and two `Reject` members that no code
returned.

- **`tradipy.quotes` (§20.14)** — `Quote`, `check_quote`, `spread_at_signal`,
  `estimated_spread`. Spread is `ask - bid` from the NBBO; odd-lot or one-sided quotes are
  `DATA_QUALITY_DEGRADED`, `ask <= bid` is `QUOTE_CROSSED` and is never clamped to zero, and
  a quote older than `quote_stale_seconds` at bar close is `QUOTE_STALE`.
- **`tradipy.bars` (§20.4)** — `Bar`, `green_runs`, `flagpole_ending_at`, `select_flagpole`,
  `flagpole_height`, `measured_move`, `retrace_pct`. §3.2 criterion 2's three thresholds have
  no registry entry, so `select_flagpole` takes the qualification test as a caller-supplied
  predicate rather than inventing them.
- **`tradipy.score` (§20.10, §14.2)** — `Catalyst`, `ScoreInputs`, `Score`,
  `composite_score`, `meets_conviction_gate`. §20.10's promise that the score lands in [0, 1]
  holds only if the five weights sum to 1, which is now a coupling check.
- **`tradipy.rejects`** — the `Reject` enum, moved out of `gates` so `quotes` does not have to
  depend on it. Re-exported from `tradipy.gates`, so existing imports still work. Gained
  `DATA_QUALITY_DEGRADED`.

### Added — a runnable proof of concept

- **`python -m tradipy demo`** replays the three PRD §3 worked examples through every gate,
  printing each verdict and its arithmetic, and self-checks every derived value against the
  tables. Exit 1 on disagreement. §3.2's stop, flag high, flagpole height and T2 are derived
  from a bar series via §20.4 rather than transcribed, which is what §21.1 asks
  worked-example fixtures to do.
- **`python -m tradipy evaluate --entry ... --stop ... --resistance ...`** runs one candidate
  of your own through the same chain. Exit 0 accept, 3 reject. Optional `--rvol` and friends
  add the §20.10 score. Stdlib `argparse` only — still no runtime dependencies.
- **`tradipy.poc`** — the composition layer both use. Explicitly *not* the strategy engine: it
  takes a candidate that has already been found.

### Added — registry and tests

- 18 new registered parameters: the four §2 risk settings; §2's `min_premarket_volume`,
  `max_vwap_extension_open_pct` and `hod_proximity_pct` (all previously prose-only); §20.10's
  five weights, four normalization caps and catalyst midpoint; and §14.2's
  `min_conviction_score`. 29 -> 47.
- Every `Param.source` now declares whether its bounds were **transcribed** from a PRD table
  or **originated here**. Roughly half were originated — §2, §3.1.1, §3.4, §20.10 and §20.14
  state defaults with no bounds column — while `params.py` claimed all of them came from the
  document. `test_code_originated_bounds_are_declared_as_such` enforces the distinction.
- `tests/test_enforcement.py` — the fifth defect class, **unenforced guarantee**: a rule that
  is stated, has a mechanism, is believed to be enforced, and is not. Invisible to all four
  earlier checks by construction.
- `tests/test_computations.py` and `tests/test_poc.py`.
- The suite is 153 cases (was 63) at 99% line and branch coverage (was 91%) *as measured at this
  release; nine test functions have been added since and review round 7 could not reproduce either
  figure — see `docs/reviews/REVIEW-2026-07-30.md`*, verified against
  47 mutations, 47 caught. Twelve of those forty-seven survived a release candidate — every
  rounding direction and truncation outside the five gate thresholds was unenforced, because
  all three §3 worked examples are numerically degenerate. See `tests/README.md`.

### Fixed — documentation

- `docs/architecture.md` claimed every construction path validated individually *and*
  jointly. It did not; see above.
- `README.md`'s override example was labelled `tighter` and was in fact looser
  (`max_spread_r` is a MAXIMUM defaulting to 0.15, so 0.20 admits more), with a second
  override that restated the default and changed nothing.
- `docs/PLAN.md` (WS11, sequencing, risk table) and `docs/PRD.md` §19 marked the parameter
  registry, the §21.1 fixture suite and the rounding-direction assertions as outstanding.
  All were built and green.
- `docs/PRD.md` §3.4's sensitivity table labelled the `$4.05` row's binding term
  "proportional" while showing the separation term's value.
- `CHANGELOG.md` claimed BasedPyright was pinned to a minor series; the specifier is
  `>=1.39,<2`. The guarantee holds via `uv.lock` and CI's `--frozen`, and now says so.
- `scripts/regen_registry_baseline.py` printed "Done. Review the diff" even when pytest
  failed and no baseline had been written.

### Tooling, packaging and documentation

Merged into this release rather than kept as a separate one: it was sitting under
`[Unreleased]` and was never tagged.

- `uv`-based project management: dev dependency group (PEP 735), `pyproject.toml` metadata
  (authors, license, classifiers, URLs), and a committed `uv.lock`.
- Ruff (lint + format) and BasedPyright configuration in `pyproject.toml`.
- Coverage configuration and `pytest-cov` in the dev group.
- `Makefile` with developer targets (`install`, `sync`, `test`, `coverage`, `lint`,
  `format`, `format-check`, `typecheck`, `check`, `clean`, `docs`, `precommit`, `release`).
- Pre-commit hooks (`.pre-commit-config.yaml`) for whitespace, Ruff, and BasedPyright.
- GitHub Actions CI (lint, format check, type check, tests + coverage) and a tag-driven
  release workflow.
- Documentation: top-level `README.md`, `CONTRIBUTING.md`, `LICENSE` (MIT, placeholder),
  and `docs/architecture.md`, `docs/development.md`, `docs/api.md`.
- `CLAUDE.md` and `.cursor/rules/` to keep AI-assisted contributions consistent with the
  project's invariants.
- Editor configuration (`.editorconfig`). VS Code settings stay local: `.vscode/` is
  git-ignored deliberately, so editor preferences are per-developer.
- `scripts/regen_registry_baseline.py` — a documented wrapper for regenerating the
  parameter-registry prose baseline.

- Minimum Python raised to 3.13.
- `tradipy/__init__.py` now imports its submodules, so the names it advertises in `__all__`
  resolve as attributes (`tradipy.gates` previously raised `AttributeError`).
- `Ladder` is exported from `tradipy.gates`; it is the return type of `exit_ladder` and was
  reachable but undeclared.
- Ruff is pinned to a minor series (`>=0.16,<0.17`) and BasedPyright to a major one
  (`>=1.39,<2`). Reproducibility across the pair comes from the committed `uv.lock` and CI's
  `uv sync --frozen`, not from the specifiers — an earlier entry here claimed both were
  pinned to a minor series, which was true of only one.
- The `PARAMS` registry is fenced with `# fmt: off` / `# fmt: on`. It transcribes the PRD's
  §2 / §2.0 tables and is reviewed against them row by row; the formatter would expand each
  row carrying a `polarity=` keyword into an eight-line block.
- The PRD's `×`, `–`, and `−` glyphs are allow-listed via Ruff's `allowed-confusables` rather
  than switching off RUF001-003, so an accidental homoglyph is still caught. Rewriting them to
  ASCII would break the PRD literal scan in `tests/test_parameter_registry.py`.
- `make check` now includes the formatting check, matching CI exactly.
- `license` is declared as a PEP 639 SPDX expression (`License-Expression: MIT` in the built
  metadata) instead of the deprecated `{ file = ... }` table.
- `pre-commit-hooks` updated to v6.0.0.
- Both workflows declare `permissions: contents: read`; the release workflow refuses to build
  when the pushed tag disagrees with `version` in `pyproject.toml`.

- The `trailing-whitespace` hook ran without `--markdown-linebreak-ext=md` and so stripped the
  hard line breaks from `docs/PRD.md`'s header, reflowing the normative document.
- `scripts/regen_registry_baseline.py` inherited environment: it replaced the child
  environment with two variables, dropping `HOME`, `TMPDIR`, and `VIRTUAL_ENV`.
- Documented installs referenced a `dev` extra that does not exist now that dev tools are a
  PEP 735 group; `pip install -e . --group dev` is the pip path.

### Migrating from 0.0.1

- `Config.default()` now returns a **beginner** config. Pass `mode="experienced"` to keep
  0.0.1's behaviour; every share count halves otherwise.
- `Config(values)` now rejects out-of-range values, unregistered names and unknown modes.
  A dict that used to construct may now raise `ValueError`.
- `position_size` raises `ValueError` when the stop exceeds `max_stop_pct × entry`. Check the
  `Reject` from `apply_stop_floor_and_ceiling` before sizing.
- `PARAMS`, `MODE_PRESETS` and `HARD_CAPS` are read-only. Code that mutated them — which was
  never supported and is what this release closes — now raises `TypeError`.
- `Reject` moved to `tradipy.rejects` and is re-exported from `tradipy.gates`; both import
  paths work.

## [0.0.1] - 2026-07-28

### Added

- Initial invariant layer: parameter registry (`params.py`), polarity-aware tick rounding
  (`rounding.py`), and pre-entry gates with position sizing (`gates.py`).
- Test suite defending four defect classes (worked examples, registry consistency, boundary
  and polarity invariants), verified by mutation testing.

[Unreleased]: https://github.com/prowler421/tradipy/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/prowler421/tradipy/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/prowler421/tradipy/releases/tag/v0.0.1
