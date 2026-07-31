# Phase 4 Design — The Strategy Engine (§3.2, §3.3, §3.4)

> **Purpose:** the design record for PRD §12.1's **Phase 4 — strategy engine (3 MVP setups)**:
> what it is, what it deliberately is not, the readings it had to take because §3 does not
> settle them, and what building it on simulated data does and does not establish.
> **Status:** built. `src/tradipy/session.py`, `src/tradipy/setups.py`, `python -m tradipy setups`.
> **Gate posture:** [PLAN](PLAN.md) **D33** — construction permitted, calibration still gated.
> **Last updated:** 2026-07-31

---

## 1. What Phase 4 is

§12.1 gives Phase 4 one line — *"Strategy engine (3 MVP setups)"*, depends on 3, risk
*"discretion proxies"* — so its scope is set by §3 and §20 rather than by the roadmap. Read
against those two sections, Phase 4 is the layer that turns **a bar series into a
`TradeSignal`**: it recognises the three §3 patterns, derives entry, stop, R, T1 and T2 from
them, and hands each to the gates the invariant layer already owns.

Concretely it closes the gap named in `gates.py`'s own docstrings and in
[architecture.md](architecture.md): every pre-entry gate takes `resistance`,
`structural_target`, `raw_stop`, `effective_stop` and `spread_at_signal` as **inputs**, and
before Phase 4 nothing in the package computed any of them. `poc.evaluate` supplied them by
hand from the §3 worked-example tables, which is why the demo replays *arithmetic* rather than
*setups*.

It also closes a stated PRD testing requirement rather than an aspiration. §21.1's
**worked-example fixtures** row asks for *"each §3 worked example encoded as a test: **input
bar series** → asserted entry, stop, R, targets, share count."* Until Phase 4 the suite
asserted the second half against hand-supplied scalars; there was no bar series to start from.
`tests/test_setups.py` starts from one.

### 1.1 What it is not

| Not in Phase 4 | Why, and where it goes |
|---|---|
| Ingestion, any feed, any clock | **D30.** The ladder is at `SIMULATED`; nothing in `src/` may import a broker SDK, a vendor client or a network module. A `Session` is handed to this layer, exactly as a `ScanCandidate` is handed to the scanner |
| §20.12 position state machine | Phase 5/6. The twelve states it names, the transitions and their persistence are order- and broker-shaped, and none of it is arithmetic over bars |
| T3 execution — the ratcheting 9 EMA trail | Phase 5/6, and **D18** is why: the ratcheted level has to rest as a broker-side stop amended each bar close. §20.5's EMA *computation* is here (`Session.ema_at`); the protection is not, and a local-only trail would silently void §21.2's guarantee |
| Stop-to-breakeven on T1 fill, scale-ins (§7.1.1) | Phase 5/6. Both are transitions of a position that exists |
| §7's risk rules other than the two §3 gates | §7 marks its enforcement point **pre-order**, which is Phase 5. The two §7 rows that are *signal-time* — Min R:R and Spread check — are `gates.check_room` and `gates.check_spread`, already built. `daily_loss_pct` still has no enforcement point anywhere (open question **G2**) |
| §8 fills, slippage, participation | Phase 4b. Phase 4 produces signals; §8.2's fill model consumes them |
| Premarket VWAP (§20.2's 04:00 series) | Not implemented. D11 disables premarket entries by default, and **G9** records that `premarket_trading_enabled` cannot be represented in the registry at all — so this is not merely unimplemented, it is currently unconfigurable. A `Session` is a regular-session series whose first bar is 09:30 |

---

## 2. Gate posture — what simulated-only construction establishes

D32 opened Phase 3 by separating **construction** from **calibration**: the scanner is built
and correct against §4.2, and every threshold in it stays formally uncalibrated until Phase 2a
Q1 is answered on measured data. **D33 extends that reasoning to Phase 4 and prices the part
of it that does not carry over.**

What Phase 4 may claim: the three setups apply §3.2, §3.3 and §3.4 as those sections are
written; every derived level comes from the registry and the existing gates; and **two** of the
three worked examples reproduce from a bar series exactly, with the third reproducing exactly up
to the room gate, where §5's last row and §6's finding take over.

What it may not claim, and this list is the point of the section:

1. **No threshold in it is calibrated.** Of the twenty registry rows Phase 4 adds,
   **all twenty are marked `(bounds: code)`** — eighteen cite §3.2, §3.3 or §3.4, sections with no parameter table and no Bounds column, and the other two cite §20.1 and §20.5, which have none either. Every range is therefore code-originated per convention 7 — a weaker
   position than Phase 3's, where §4.2 at least stated its defaults in a table.
2. **The patterns themselves are readings, not transcriptions.** §20 defines flagpole geometry
   and nothing else: *flag*, *consolidation candle*, *dip*, *leg* and *leg height* have no
   normative definition anywhere in the PRD. §4.2's rows were ambiguous; §3's patterns are in
   places **undefined**, which is a different and larger gap. Section 5 lists the readings that shaped the
   code; §6 counts all nineteen.
3. **D32's bet does not transfer.** D32 bet that a Q1-negative outcome would be a table edit
   because the scanner is arithmetic over a scalar `ScanCandidate`. Phase 4 consumes a *bar
   series*, and a §3 rewrite that changed a pattern's definition would change control flow, not
   a row. That exposure is accepted at **1,573 lines of module** (`session.py` 295,
   `setups.py` 1,278) and **1,036 of fixture** (`test_setups.py` 743 plus a 293-line enforcement
   block), counted with `wc -l`; it is bounded by there being no feed, no persistence and no
   order path attached to it.
4. **The ladder does not move.** `PERMITTED_ORIGINS` stays `{SIMULATED}`; advancing it is still
   **D31**, still unwritten. [PHASE-3-READINESS.md](PHASE-3-READINESS.md)'s Q1 row stays
   **Not met**, and §12.1's Phase 3 and Phase 4 dependency rows stay unticked.

---

## 3. Module design

Two modules, both pure, both added at the far end of the existing one-way dependency graph.

| Module | Imports (first-party) |
|---|---|
| `rounding`, `rejects`, `bars` | — (standard library only) |
| `params` | `rounding` |
| `quotes` | `params`, `rejects`, `rounding` |
| `score` | `params` |
| `gates` | `params`, `rejects`, `rounding` |
| `scanner` | `params`, `rejects`, `score`, `gates` |
| **`session`** | `bars`, `params` |
| **`setups`** | `bars`, `session`, `params`, `rejects`, `rounding`, `gates` |
| `poc` | all of the above |
| `__main__` | `poc`, `params`, `quotes`, `rounding`, `scanner`, `score`, `setups` |

A table rather than a drawing, deliberately: the first version of this section was a bus-style
ASCII graph whose junctions implied six edges that do not exist, and whose caption claimed a
left-to-right invariant the drawing did not honour. `session` reads `params` for `ema_period` and
`max_pattern_gap_minutes` — reading either as a literal would break convention 1. `setups` is
imported by `__init__` (it is a public module), by `poc`, and by `__main__` for one type
annotation.

### 3.1 `session.py` — §20.1, §20.2, §20.3, §20.5, §20.6

The §20 computations that need an ordered series rather than a single bar. `bars.Bar`
deliberately carries no timestamp (§20.1 needs an ingestion layer), so the series carries the
ordinal instead:

```python
SessionBar(minute: int, bar: Bar)       # minute 0 == the 09:30 bar (§20.1 labels the open)
Session(bars: tuple[SessionBar, ...])   # strictly increasing minutes, validated
```

**Why an `int` minute and not a `datetime`.** §21.1 forbids `datetime.now()` anywhere in
strategy code and requires an injectable clock; §20.1's rules that Phase 4 actually needs are
all ordinal — *"pattern counts count **available bars**, not wall-clock minutes"* and *"a gap >
2 minutes invalidates any in-progress pattern"*. An `int` expresses both, carries no timezone,
and cannot be read from a clock. DST and the UTC/`America/New_York` split are §21.4's and
ingestion's; a strategy engine that parsed timezones would be holding a concern D30 keeps out
of this layer.

Members: `vwap_at(i)` / `vwap()` (§20.2, typical price, cumulative from session start),
`hod_through(i)` / `hod()` and `hod_established_by(i)` (§20.3, wick-based, with the
*not-the-opening-print* rule), `ema_at(i, cfg)` (§20.5, seeded on the first `ema_period` closes,
`None` before that), `gap_before(i)` and `pattern_intact(a, b)` (§20.1's missing-bar rule),
`through(i)` (the truncation primitive), and `tighter()` / `wider()` (§20.6, `max()` and
`min()` over candidate stop prices, named once so the second one has a definition —
`gates.vwap_reclaim_stop` had the only `max()` and there was no `min()` at all).

`session.py` **does not round.** VWAP, HOD and EMA are computed values, not price levels
submitted to a broker, and §20.13 puts rounding *once, at level computation*. The
enforcement suite derives the set of rounding modules from the source, so this is checked
rather than asserted here.

### 3.2 `setups.py` — §3.2, §3.3, §3.4, §20.4, §20.11

One evaluator per setup, each a pure function of `(symbol, session, trigger_index, spread, cfg)`
plus the inputs §3 needs and this layer cannot derive (`premarket_high` for §20.3's `PMH`,
`buying_power` and `adv_shares` for §2.2's optional caps). Each returns a `SetupOutcome`:

```python
SetupOutcome(setup, criteria: tuple[Criterion, ...], reject: Reject | None,
             signal: SetupSignal | None)
```

Three structural choices, each with a precedent in `scanner.py`:

* **Every criterion is evaluated, not just up to the first failure.** A rejection you can only
  see one dimension of cannot be recalibrated against measured data. `Criterion` carries the
  arithmetic in a `detail` string for the same reason `HardResult` does.
* **The rejection codes are the existing ones.** `INSUFFICIENT_ROOM`, `TARGETS_TOO_CLOSE`,
  `SPREAD_TOO_WIDE`, `STOP_TOO_WIDE` come from the gates. Phase 4 adds exactly one new
  `Reject` — `SETUP_NOT_PRESENT`, for a pattern that does not exist at the trigger bar — and
  two `ExitReason` members transcribed from §20.12's state names (`BAILED_OUT`, `INVALIDATED`)
  rather than invented here.
* **Post-entry rules are predicates, not a state machine.** §3.2's breakout-or-bailout, §3.3's
  HOD-reclaim invalidation and all three setups' close-below-VWAP exit are pure functions of
  the bars after entry. They are here because they are §3 rules; the state they would be
  evaluated *in* is Phase 5/6's.

`arbitrate()` implements §20.11 rules 1 and 2 — deduplicate by symbol, and Bull Flag → HOD
Breakout → VWAP Reclaim on the same bar. Rules 3 and 4 (`SUPERSEDED` rows, open-position
suppression) need persistence and position state, so the loser list is *returned* rather than
written.

### 3.3 One refactor in `gates.py`

§3.3's T2 is *"next whole-dollar level above **T1**"*, so a setup has to know T1 before it can
name a structural target — while `exit_ladder` computes T1 and T2 together. Restating T1's
formula in `setups.py` is the v1.2 defect class, so `exit_ladder` now delegates to a new
`gates.t1_level(entry, r, cfg)`, which is the single definition. This mirrors
`scan_spread_cap` / `spread_caps` exactly, including the enforcement fixture that asserts the
delegation **structurally** — two implementations that agree today are the whole v1.2 story.

---

## 4. No look-ahead, by construction

§8.1's *"no look-ahead"* and §21.1's property test are the constraints that shape the API:

* A setup is evaluated **at an index**, and every derivation reads `session` only at or before
  it. `Session.through(i)` returns the truncated series, so the §21.1 property — *"replaying a
  bar series truncated at time t must produce identical signals to the full series evaluated
  as-of t"* — is a two-line test rather than an audit. It is written, for all three setups, at
  every legal trigger index of every fixture.
* The trigger bar is a **closed** bar (§20.1). Partial bars cannot be represented: a `Bar` is
  OHLCV with no in-progress notion, and there is no path that admits one.
* §20.2's *"no VWAP-dependent setup can fire before 09:31"* is enforced on the trigger bar's
  minute. All three setups are VWAP-dependent, so all three refuse minute 0.
* `spread_at_signal` is an input, per §20.14's sampling rule — *the last NBBO quote at or
  before the close of the signal bar*. Selecting that quote is a feed concern and stays in
  `quotes.py`'s stated scope, not here.

---

## 5. Readings this layer had to take

§3's patterns are not fully defined, and code has to be executable. Every reading below is
taken because the alternative was inventing spec or refusing to run; each is localised to one
function, pinned by a test, and **raised in [CHANGELOG.md](CHANGELOG.md) rather than settled
here.** This is the same treatment Phase 3 gave §4.2's ambiguities.

| § | What is not settled | Reading taken | Why this one |
|---|---|---|---|
| §3.2 crit 3 | *"red/consolidation candles"* — a consolidation candle may close up, but §20.4 terminates the flagpole at *"the longest run of consecutive green candles ending immediately before the flag"* | The flag is the maximal run of **not-green** bars (`close ≤ open`) immediately before the trigger | The alternative is circular: §20.4 needs the flag's start to find the flagpole, and a flag admitting green bars needs the flagpole to find its own start |
| §3.2 crit 2 | *"combined move ≥ 2%"* states no denominator | `flagpole_height / flagpole_low` | Reproduces the §3.2 worked example's **+7.29%** ($0.35 / $4.80) exactly; the other candidates (open, prior close) do not |
| §3.2 crit 4 | *"Flag low **remains** above session VWAP"* — one VWAP value or one per bar | Each flag bar's low against VWAP **as of that bar** | *"Remains"*, and it is the same test as the invalidation *"price breaks below VWAP during flag formation"*. Wick-based because §3.2 says *low* |
| §3.3 crit 3 | *"high ≤ prior HOD"* — but the extent of the consolidation and the value of *prior HOD* each depend on the other | A consolidation bar is one that **set no new high** (`high ≤ hod_through(i−1)`) and held above VWAP (`low ≥ vwap_at(i)`) | Breaks the circularity, and yields the same *prior HOD* whether it is read as of the trigger bar or as of the run's start, because no bar in the run made a new high |
| §3.4 crit 3 | *"candles below VWAP"* — close or wick | `close < vwap_at(i)` | The trigger is close-based (*"closes above VWAP"*); a reclaim defined by closes has to have a dip defined by closes |
| §3.4 crit 3 | Dip depth *"≤ 2% below VWAP"* — against which VWAP | VWAP as of the bar that set the dip low | Matches the per-bar reading above; the worked example has one VWAP value and cannot distinguish them |
| §3.4 crit 6 | *"Price still below HOD"* — HOD including the trigger bar's own wick, or before it | **Prior** HOD, `hod_through(i−1)` | The stricter of the two, and consistent with §3.3's use of *prior HOD*. Including the trigger bar lets a setup satisfy the criterion with its own wick |
| §3.4 crit 9 | *"within 0.5% of HOD"* — of HOD or of entry | `(hod − entry) / hod ≤ hod_proximity_pct` | §2's row is *"Max Extension **from** HOD"*; the extension is measured from the level it is named for |
| §3.1.1 | `resistance` is *"nearest overhead level among {HOD, next whole dollar, prior leg high, measured-move projection}"* — *prior leg high* is undefined, and §20.3 adds `PMH` to the set from outside the enumeration | The set is {HOD, next whole dollar above entry, the setup's structural target, `PMH` when supplied}; *prior leg high* is **omitted** | §20 governs, so `PMH` is in. An undefined term cannot be implemented, and inventing one would put a fabricated level into a non-bypassable gate |
| §3.3 T2 | *"next whole dollar above T1, or prior leg extension (1× leg height), whichever is nearer"* | Whole-dollar branch only | Same reason: *leg height* is undefined. §3.3's own worked example uses the whole dollar. The omission is stated rather than silently narrowed |
| §20.1 | *"a gap > 2 minutes invalidates any in-progress pattern"* — missing minutes or elapsed span | **Missing** minutes: `next.minute − prev.minute − 1 > max_pattern_gap_minutes` | The natural reading of *"a gap of 2 minutes"*. Noted because the span reading is stricter by one minute, and this is the one place Phase 4 did **not** take the stricter option — it took the literal one |
| §3.4 crit 2 | *"above VWAP for ≥ 15 **minutes**"*, and §3.2's *"3 candles (3 min)"* | Available **bars**, per §20.1 | §20 governs, and §20.1 is explicit that pattern counts are bar counts. The parameter is therefore named `min_bars_above_vwap`, not `..._minutes` |

---

## 6. Spec questions Phase 4 raises

**Nineteen**, all in [CHANGELOG.md](CHANGELOG.md)'s Unreleased table, none resolved in code, and
that table is the count — restating it here is what round 12's own fact-check caught this section
doing with the wrong number. The four that would change behaviour if settled the other way:

1. **T3 is specified twice with different values.** §2's Profit Target row says *"Target 3: HOD
   retest + extension"*; §3.1.1, §3.5, §15 and §20.12 all say *trail 9 EMA*. §3.4 separately
   uses HOD retest as **T2**. One of the two is wrong about what T3 is.
2. **Breakout-or-bailout is three rules.** §3.2 requires a conjunction (no close above entry
   **and** no new high); §3.3 states one condition; §3.4 states none — while §11.1 and A12 both
   describe it as a single canonical rule. Implemented per-setup, as written.
3. **§3.4's stop band is narrower than the dip it admits.** Crit 3 permits a dip 2% below VWAP;
   the stop is `max(dip_low, VWAP × 0.99)`. Whenever the dip is deeper than 1%, the `max()`
   selects the VWAP band and puts the stop **inside the pattern** — which §2 and §3.2 both
   forbid in terms. §3.4's own worked example does it, and is rescued only by the $0.10 floor.
4. **Is §14.2's conviction gate an entry gate?** `score.meets_conviction_gate` and
   `min_conviction_score` exist; §20.10 calls the score *"directly comparable to the ≥ 0.7
   conviction gate"*; no §3 criterion references it. Phase 4 does not apply it — a gate no
   setup criterion names would be this layer inventing a rejection.

The other fifteen are recorded with the same disposition — **raised, not resolved**. In the
table's order they are: §20.1's bars-versus-minutes reading of *"3 candles (3 min)"* and *"15
minutes"*; the flag's terminator; the flagpole move's denominator together with its volume
baseline; §3.3's circular consolidation test; the resistance set; §3.3's T2; the dip's
close-versus-wick reading together with its depth reference (one CHANGELOG.md row, two questions);
§20.1's gap reading; §14.3's candle-quality test that §3.2 does not state; §2's global
VWAP-extension rule; A14's inert branch; halt proximity at 2 min versus 5 min; §8.2's
opening-auction row contradicting itself; §3.2's multi-flag re-entry against §20.11's
supersession; and wick-versus-close for the pre-entry VWAP tests.

---

## 7. Registry additions

Twenty rows, taking the registry from 55 to 75, and **all twenty are marked `(bounds: code)`**.
Eighteen cite §3.2, §3.3 or §3.4 — sections with no parameter table and no Bounds column — and the
other two cite §20.1 and §20.5, which have no Bounds column either. So no range here is spec.

The rule applied to polarity is the one §20.13 asks for, *classify before choosing*, plus a
distinction the registry already makes implicitly: **a count that is a constraint carries a
polarity; a count that is a window does not.** `flag_max_candles` is a maximum a pattern must
stay under; `flagpole_vol_lookback_bars` is the size of a lookback and there is no direction to
declare. `max_open_positions` (MAXIMUM) and `rvol_lookback_days` (none) are the existing
precedent for each side.

Nothing here is rounded to a tick — every row is a count, a ratio or a multiple — so no new
call reaches `Config.round_for` from these. `setups.py` does round — once, for the §3.3 VWAP stop
candidate — and is therefore in the enforcement suite's derived list of rounding consumers and may
not import `Polarity`. The whole-dollar level is not rounded: a whole dollar is already a whole
tick.

Two consequences worth stating because they are the kind of thing that goes unnoticed:

* `flagpole_min_move_pct` and `max_dip_depth_pct` are both **2%**, which makes `2%` a new
  search key for the PRD-prose lint. The baseline grows by six entries — in §3.2, §3.4, §3.5,
  §15, §6.5 and §11.3, none of them a new statement in the document and three of them substring
  matches inside a larger figure; regenerated deliberately with
  `scripts/regen_registry_baseline.py` and the diff read.
* `bars.select_flagpole`'s `qualifies` predicate — built in Phase 3's window with **no shipped
  caller**, and recorded as such in [../tests/README.md](../tests/README.md) — now has one. It is
  §3.2 criterion 2, built from the four rows `bars.py` refused to invent:
  `flagpole_min_candles`, `flagpole_min_move_pct`, `flagpole_vol_multiple` and
  `flagpole_vol_lookback_bars`. Four, not three: `bars.py`'s docstring counted the thresholds and
  not the window they are measured over, and it now says so.

---

## 8. Test plan

| Layer | What it asserts |
|---|---|
| Worked examples (`spec`) | All three §3 examples from a **bar series**: entry, stop, R, T1, T2 and the verdict for each, then per setup the figures its own table states — §3.2's height, 7.29% move, 28.57% retrace, resistance, room and separation floor; §3.3's VWAP, 2.53% extension and both stop selections; §3.4's required room and its whole resistance candidate set. `shares` is asserted for the two that accept; §3.4 rejects, so §21.1's share-count clause has nothing to assert there, which is L2 rather than a gap in the fixture |
| Look-ahead property | For each setup and each legal trigger index, `evaluate(session.through(i), i) == evaluate(session, i)`. §21.1's property test |
| Boundary (`boundary`) | **Eight of the twenty** new thresholds at their own limit: flag candles at 1/2/5/6, retrace at exactly 50%, flag volume ratio at exactly 0.70 with the breakout multiple at exactly 2×, the volume lookback one bar short of evaluable, dip length at 5 and 6, and dip depth at the last admissible tick. Plus `max_vwap_extension_pct`, which is a **pre-existing** row rather than one of the twenty. **The other twelve have no boundary fixture** — stated, because the version of this row before round 12's fact-check implied all twenty did |
| Polarity (`polarity`) | The §3.3 VWAP stop candidate, read back out of `evaluate_hod_breakout` in the one case A14's `max()` actually binds, and §3.4's band — both asserted against their derivation and against the direction a ceiling would have taken, never against a value |
| Enforcement | The violation each new guarantee forbids: a partial pattern cannot produce a signal; a minute-0 trigger is refused; a gap wider than `max_pattern_gap_minutes` invalidates the pattern; `arbitrate` cannot return two signals for one symbol; a soft §4.2 flag cannot reach a setup rejection; `SETUP_NOT_PRESENT` is reachable for each setup |

Convention 6 is the reason the last row exists at all: the happy-path test passes whether or
not the guarantee is enforced, and four guarantees were unenforced at once in v0.0.1 with three
of them sitting beside a passing test.

---

## 9. What this document is not evidence of

`make check` was **not run in full** for this change: the environment that produced it has no
network, so `ruff` and `basedpyright` could not be installed from PyPI. `basedpyright` 1.39.9
was run through the bundled `dist/pyright.js` on system Node (0 errors) and the suite was run
on CPython 3.10 with two compatibility shims — but **`ruff check` and `ruff format --check`
were not run at all.** That is the same gap round 7 had, and round 7's mistake was
substituting a hand-built check and reporting it beside real executions. No substitute is
reported here. See [reviews/REVIEW-2026-07-31-round12.md](reviews/REVIEW-2026-07-31-round12.md)
§Appendix, and run the gate locally before trusting this row anywhere.
