# Phase 6 Design — the Full Risk Engine (§7's other five enforcement points, §10, §20.8)

> **Purpose:** the design record for PRD §12.1's **Phase 6 — full risk engine**: what "full"
> turns out to mean once §7's table is read by its *Enforcement Point* column rather than by
> its rows, the readings §7, §10 and §20.8 forced, and what building the enforcement half on
> handed-in state does and does not establish.
> **Status:** built. `src/tradipy/daily.py`, `src/tradipy/monitor.py`,
> `python -m tradipy monitor`.
> **Gate posture:** [PLAN](PLAN.md) **D35** — the pure half constructed, transport still
> refused, calibration and the §18.7 gate both still closed.
> **Last updated:** 2026-08-01.

---

## 1. What Phase 6 is

§12.1 gives Phase 6 one line — *"Full risk engine"*, complexity Medium, dependency **5** — and
for the first time in four phases **the dependency exists**: Phase 5 is built. So this is the
first phase since Phase 3 whose §12.1 precondition is met rather than argued around.

That makes the word *full* the load-bearing one, and it does not mean *more rules*. §7's table
has thirteen rows and Phase 5 transcribed all thirteen. What Phase 5 did not do is read the
table's **third column**. §7's six distinct Enforcement Point cells are *Pre-order*, *Continuous
(1 sec) + post-fill* (row 2's, which names two points in one cell), *Post-trade close*,
*Continuous* (row 7's, and the string `EnforcementPoint.CONTINUOUS` carries), *End of day* and
*Any*; `risk.approve` is the *Pre-order* one. **The other five had no code at all**, which is
why `risk.py` ships two predicates that nothing calls — `session_drawdown_breached` and
`multi_day_drawdown_breached` — and `risk.UNREACHABLE_BLOCKS` exists to say so. A third,
`daily_loss_breached`, does have a caller, and only one: row 2 is enforced at three points
across §7 and §6.3, and `approve` applies §6.3's.

Read against §7's enforcement column, §10's `daily_state` and §20.8 rather than against the
roadmap line, Phase 6 is: **the layer that turns an account's own history into the §7 verdicts
that are not about a candidate.** `risk.approve` answers *may this account take this trade*;
this layer answers *should this account still be trading at all*, and *what is the state that
question is asked against*.

Concretely it closes five gaps the package has carried:

1. **Five of §7's six enforcement points had nothing.** Rows 2 (at *post-fill* and
   *Continuous* — its *Pre-order* point was Phase 5's), 4 (Post-trade close), 7 (Continuous),
   8 (End of day) and 11 (Any) are now evaluated by `monitor.evaluate`, which also produces §7's
   **Violation Action** — *"Flatten all; lock account"* — a column no code in this package had
   ever read.
2. **§7 row 4's enforcement point is *Post-trade close*, and nothing closed a trade.**
   `consecutive_losses` was an `int` the caller supplied to `RiskState`; so were
   `realized_pnl`, `day_trades_in_window` and `session_equity_peak`. Phase 6 *computes* them,
   from §9.2's `ClosedTrade`, which had no producer either.
3. **§9.2 marks `ClosedTrade.net_pnl` *"the figure §18.7 is judged on"* and requires
   `r_multiple` to be *"computed on NET P&L, not gross"*** — and nothing computed either, so the
   arithmetic the viability gate turns on existed only as two comments in a dataclass.
4. **§20.8's `NO_TRADE`-until-snapshot rule had no representation.** `RiskState` takes
   `start_of_day_equity` as a given; §20.8 says the system stays in `NO_TRADE` until a broker
   sync succeeds and *"does not fall back to a stale or computed value, because every
   non-bypassable risk limit is denominated in it."* A layer that accepts the figure as an
   argument cannot refuse to invent it. `daily.DailyState` can.
5. **§7.1.2's restart requirement had no shape.** Phase 5 pinned it *absent*. Phase 6 builds
   the half that is arithmetic — a `daily_state` row that round-trips through §10's columns
   with the lockout intact — and refuses the half that is a store. **The half it builds is what
   makes the finding in §6 visible**, and that finding is the most consequential thing in this
   document.

### 1.1 What it is not

| Not in Phase 6 | Why, and where it goes |
|---|---|
| **The 1-second timer.** §7 row 2 says *"Continuous (1 sec)"* | A timer is a clock, and §21.1 forbids one in this layer. Phase 6 supplies the **evaluation**; the scheduler that calls it every second is ingestion's, exactly as §6.4's thirty-second window became a supplied `seconds_since_submit`. The cadence is therefore **not registered** — a threshold whose only reader would be a loop this package refuses to write is the fifth defect class |
| **The kill-switch file sentinel** at `$XDG_STATE_HOME/tradipy/kill`, and §21.5's `0700` ownership check | A file read, and no module in this package opens a file (D30). The trigger arrives as `evaluate(..., kill_switch=True)`. §21.5's path still has a reader nowhere, which Phase 5 raised and which is **not** closed here |
| **Actually flattening** — cancel orders, market-close, amend | §6.2's `OrderDraft → Submit` arrow, refused in Phase 5 and refused again. Phase 6 computes the **directive** and the §20.12 transition it implies; nothing sends anything |
| **Persisting `daily_state`** | `to_row()` / `from_row()` map §10's columns to and from a plain `dict`; there is no file, no driver, no `sqlite3`. §7.1.2's *arithmetic* becomes testable — a reloaded row reproduces the same lockout — and its *durability* does not, because durability is a store. Stated rather than implied, and pinned by a test that asserts the absence |
| **§21.3 reconciliation** | *"Broker state wins"* requires a broker. Phase 5's transport half, gated behind D31 |
| **§9.2's `Alert` contract and §21.6's alert inventory** | Deliberately out of scope. §9.2 defines the payload — `severity`, `dedupe_key`, `requires_ack` and `channels`, whose comments cite §11.2 for routing and pinning while the screen that actually specifies both is §11.3; §21.6 lists the alert conditions and the Sev-1 SLO. *(That §9.2 points at §11.2 and the behaviour lives in §11.3 is the PRD's own inconsistency, noted rather than resolved here.)* None of it is a §7 rule, and a notification layer built before anything emits into it is a mechanism wired to nothing. A `MonitorDecision` already carries the reason, the action and the arithmetic, which is what an alert would be built from |
| **§11.4's CLI journal and §9.2's `JournalEntry`** | §12.1 puts *"CLI journal"* in the **MVP Gate** row, not in Phase 6. `ClosedTrade` is here because §7 row 4 needs it; the journal that displays one is the next row of the roadmap |
| **§8.3's metrics and §18.7's gate** | Phase 4b's. Phase 6 produces the `ClosedTrade` those aggregate; aggregating them is what the gate *is*, and running it is the thing D34 and D35 both decline to do |
| **Which business days are in the PDT window, and which sessions are in the 5-day drawdown window** | §21.4's calendar. `day_trades_in_window` arrives counted, and `roll_multi_day_peak` takes the trailing session closes it is *given*. Half-days, holidays and DST are ingestion's — and §5 records what that costs, because it is not free |
| **T3's ratcheting 9 EMA trail** | Still D18, still transport. Unchanged by this phase |

---

## 2. Gate posture — the phase whose §12.1 dependency is actually met

D32 separated **construction** from **calibration**; D33 extended it to Phase 4 and priced what
did not carry; D34 extended it to Phase 5 and split the gate into two independent halves.
**D35 is the first of the four whose §12.1 dependency column is satisfied**, and that changes
which arguments have to be made and which do not.

| Gate | What it blocks | Status under D35 |
|---|---|---|
| **§12.1's stated dependency (Phase 5)** | Building at all | **Met.** `positions.py`, `risk.py` and `orders.py` are built, and this layer imports two of the three — `orders` deliberately not, because a flatten is a position event and turning one into an order is §6.2's refused arrow |
| **D30 / D31 — the data ladder** | Reading a market, and therefore acting on a flatten | **Unchanged and binding.** `PERMITTED_ORIGINS` stays `{SIMULATED}`. Phase 6 computes directives; §1.1's third row is a refusal, not a deferral |
| **§18.7 / Phase 4b — the viability gate** | *Committing capital* | **Unchanged and binding.** Not run, not passed |
| **Calibration** | Trusting any threshold | **Unchanged.** Two new registry rows, both `(bounds: code)` |
| **Construction** of pure §7/§10/§20.8 arithmetic | — | **Opened**, on the argument below |

The argument, stated so it can be attacked, and it is the *weakest* of the four because it needs
the least: **every rule in this layer refuses to trade, and none of them decides to.** D34
argued that §18.7 governs whether to trade rather than whether the arithmetic refusing a trade
is correct. Phase 6 is the pure form of that: `monitor.evaluate` can halt an account and can
never start one, `daily.record_close` accrues a loss and cannot create a position, and the
flatten directive closes exposure and cannot open any. A negative Phase 4b outcome does not
change one line of it — it changes whether anything is ever open to flatten.

What Phase 6 may claim, stated narrowly:

* §7's five non-pre-order enforcement points are applied as §7's own column writes them, and the
  mapping from row to point and from row to Violation Action is **transcribed** into
  `RULES_AT` and `ACTION_FOR` rather than distributed through control flow.
* **After this phase no `RiskBlock` member is unreachable.** `risk.UNREACHABLE_BLOCKS` is now
  empty, and a test iterates the enum and drives each of the twelve members from some code path
  — the positive assertion that replaces Phase 5's deliberate negative one.
* §10's `daily_state` round-trips, with the §7 lockout surviving the round trip.
* §20.8's refusal is enforced: a `DailyState` with no snapshot cannot produce a `RiskState` by
  any path.
* §9.2's `r_multiple` is computed on net P&L, and a trade that cannot have one — zero R, zero
  shares — raises instead of returning a number.

What it may not claim, and this list is the point of the section:

1. **No threshold is calibrated.** Both new rows are `(bounds: code)`: §7's multi-day row states
   *"Rolling 5-day"* and §21.4 states the flat-all cutoff, and neither section has a Bounds
   column.
2. **The loop is still not a loop.** §7 says *Continuous (1 sec)* and this layer is called, never
   calling. A reader who takes *"Phase 6 built"* to mean the daily-loss limit is now being
   watched every second will be wrong. G2 narrows a second time and **still does not close** —
   see §6.
3. **§7.1.2 is closed in arithmetic and open in durability**, and the gap between those two is
   §10's schema rather than this layer's code. Finding 1 is exactly that gap.
4. **Nothing flattens.** The directive names the position, the reason and the §20.12 target
   state, and for four of the five open states there **is** no target state — which is round
   14's H3, arriving as a blocker rather than a footnote. See finding 2.
5. **The ladder does not move.** `PERMITTED_ORIGINS` stays `{SIMULATED}`; advancing it is still
   **D31**, still unwritten. [PHASE-3-READINESS.md](PHASE-3-READINESS.md)'s Q1 row stays **Not
   met**, and §12.1's Phase 3, 4, 5 and 6 dependency rows all stay unticked.

---

## 3. Module design

Two modules, both pure, both added at the far end of the existing one-way graph.

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
| **`daily`** | `params`, `rejects`, `risk`, `setups` |
| **`monitor`** | `daily`, `params`, `positions`, `rejects`, `rounding`, `risk` |
| `poc` | `bars`, `gates`, `params`, `quotes`, `rejects`, `rounding`, `scanner`, `score`, `session`, `setups` — **not** the five modules Phases 5 and 6 added |
| `__main__` | `daily`, `monitor`, `orders`, `params`, `poc`, `positions`, `quotes`, `rejects`, `risk`, `rounding`, `scanner`, `score`, `setups` |

A table rather than a drawing, for the reason [PHASE-4-DESIGN](PHASE-4-DESIGN.md) §3 gives.
Four edges are worth explaining because the obvious alternative is wrong in each case:

* **`daily` imports `risk`, not the reverse.** §7's rules are evaluated against a `RiskState`,
  and `daily` builds one. Inverting it would make `risk.py` — the module that must not sense
  anything — depend on the module that models a session's history.
* **`daily` does not import `positions`, and reads the registry from exactly one function.**
  Nothing in §10's row, §20.8's snapshot or §9.2's `ClosedTrade` is a threshold — a P&L is
  arithmetic over supplied fills and an R-multiple is a ratio — so `Config` appears only in
  the two signatures §7 row 8's window reaches, `roll_multi_day_peak` and
  `record_multi_day_peak`. `OpenPosition` comes from `risk`, which is where §7's rules read it,
  rather than a second import of the state enum. `monitor` does import `rounding`, for
  `TICK_SIZE` alone: a dollar figure in an audit string is quantized to the price grid rather
  than to a locally written `Decimal("0.01")`, which is `risk.py`'s posture exactly and does
  **not** make either module a rounding consumer — `quantize` is not one of the four functions
  the enforcement suite derives that list from.
* **`monitor` imports `risk` and re-uses its three predicates rather than restating them.**
  `daily_loss_breached`, `session_drawdown_breached` and `multi_day_drawdown_breached` are §7
  rows 2, 7 and 8, they were written in Phase 5 explicitly so that *"a Phase 6 loop needs to
  call them without building a decision"*, and a second implementation of any of them would be
  the v1.2 defect class in the module written to close it. `monitor` also re-uses
  `risk.RuleOutcome`, for the same reason: an audit row is an audit row.
* **`monitor` imports `positions` and not `orders`.** A flatten is a position lifecycle event.
  Turning one into a cancel and a market order is §6.2's fourth arrow, and that arrow is
  refused.

### 3.1 `daily.py` — §10's `daily_state`, §20.8, §9.2's `ClosedTrade`, §7 row 4

```python
SessionPhase                    # NO_TRADE | TRADING | LOCKED  (§20.8, §7)
ClosedTrade(...)                # §9.2, with gross/net/r_multiple derived
DailyState(...)                 # §10's row, plus the fields §10 has no column for
UNPERSISTED_FIELDS              # exactly those fields — enumerated, not implied

open_session(session_date, *, carried_lock=None)     # §20.8 + §7 row 8's next-day lock
record_snapshot(state, equity)                       # §20.8, once and only once
mark_to_market(state, unrealized_pnl)                # §7 row 2's post-fill input
record_close(state, trade, *, unrealized_after, day_trade)   # §7 row 4's Post-trade close
roll_multi_day_peak(session_closes, cfg)             # §7 row 8's window
record_multi_day_peak(state, session_closes, cfg)    # the same, as a state transition
lock(state, reason)                                  # §7's "lock account"
clear_lock(state, confirmation, expected)            # §7.2's manual reset
to_row(state) / from_row(row)                        # §10's columns, §7.1.2
risk_state(state, positions=(), submitted_keys=frozenset())  # the bridge to §7's evaluator

SessionNotOpenError / ConfirmationRequiredError                # §20.8's refusal, §7.2's
DAILY_STATE_COLUMNS / CLOCK_COLUMNS                  # §10's columns, and the one a store owns
BRIDGE_EXCEPTIONS / bridge_fields()                  # what risk_state does *not* copy verbatim
```

Five structural choices, each with a precedent one layer down:

* **`DailyState` and `RiskState` are one definition and one derivation, not two states.**
  This is the obvious place to create the v1.2 defect class — two dataclasses carrying
  `realized_pnl` and `consecutive_losses`, updated by different code. They are not
  independent: `DailyState` is §10's *persisted row*, `RiskState` is §7's *evaluation input*,
  and `risk_state()` is the **only** function that turns one into the other. A test derives
  both field sets from the dataclasses and asserts every shared field is carried, so a field
  added to one and forgotten on the bridge fails rather than silently defaults.
* **`SessionPhase.NO_TRADE` is a phase with no equity, not an equity of zero.**
  `start_of_day_equity` is `Decimal | None`, and `risk_state()` **raises** in `NO_TRADE`.
  §20.8's sentence is *"it does not fall back to a stale or computed value"*, and the only way
  to make that enforceable is for the fallback value not to exist. A default of `Decimal(0)`
  would give every §7 threshold a denominator of zero and pass every check.
* **The lock reason is a `RiskBlock`, not a fifth enum.** §7's rule table is where these names
  come from, `RiskBlock` is already *one member per §7 row*, and inventing `HaltReason` would
  give the same fact two spellings — which is K5's argument for the fourth namespace, applied
  in reverse. `RiskState.halt_reason` is `str | None` because §10's column is a `VARCHAR(48)`;
  the bridge writes `.value`, and the typed member is what this layer holds.
* **`ClosedTrade` derives; it does not store.** `gross_pnl`, `net_pnl` and `r_multiple` are
  properties, because §9.2's own note is that the multiple is *"computed on NET P&L, not
  gross"* and a stored field can be computed once, wrongly, and then agree with itself forever.
  `trade_id`, `signal_id`, `opened_at` and `closed_at` are absent for the reason
  `RiskDecision` omits `signal_id` and `evaluated_at`: two are join keys and two are clocks.
* **`UNPERSISTED_FIELDS` is enumerated, exactly as `UNREACHABLE_BLOCKS` was.** §10's
  `daily_state` has eight columns and this layer's state has four facts §10 cannot hold. A
  field that silently fails to round-trip is worse than one that is documented as not
  round-tripping, and the difference between the two is a named set with a test on it. This is
  finding 1 and it is the reason the set exists.

`daily.py` does **not** round. A P&L is money accumulated, not a price level compared against a
tick, which is the condition `Config.round_for`'s docstring states for rounding at all; an
exit price is an *observed* fill rather than a level submitted to a broker, so §20.13 does not
reach it. Same posture as `risk.py` and `session.py`, and the enforcement suite derives the
consumer list from the source rather than trusting this paragraph.

### 3.2 `monitor.py` — §7's enforcement column, and the flatten directive

```python
EnforcementPoint                # §7's third column, transcribed
HaltAction                      # §7's fourth column, transcribed
RULES_AT                        # which §7 rows are evaluated at which point
ACTION_FOR                      # which Violation Action each row's breach produces
MonitorDecision(point, rules_evaluated, reason, action)   # .breaches/.flatten/.locks derive

evaluate(state, point, cfg, *, kill_switch=False)    # every applicable §7 row, always
apply(state, decision)                               # §7's action, folded into §10's row
eod_flat_due(minute, cfg)                            # §21.4's flat-all cutoff

FlattenDirective(symbol, shares, from_state, exit_reason, to_state)   # .representable derives
flatten_all(positions, reason)
unrepresentable(directives)                          # the ones §20.12 has no target state for
unrepresentable_flatten_states(reason)               # derived from §20.12, not written out
```

Four structural choices:

* **Every applicable rule is evaluated at every point, not just up to the first breach.** The
  same argument `risk.approve` makes from §9.2's *"every rule checked, for audit"*, and the same
  self-check: `evaluate` compares its own output against `RULES_AT` and raises if a rule was
  dropped from the loop. That assertion exists because Phase 5's first version of the equivalent
  test asserted a **length**, which passes with a rule missing.
* **The reason is §7's table order; the action is the strictest breach.** Those are two
  different questions and reporting one answer to both under-enforces. If the loss-streak row
  (*"Lock new entries; allow exits"*) and the daily-loss row (*"Flatten all; lock account for
  day"*) breach together, the reason is the earlier row in §7's table and the action is the
  flatten — never the other way round. `_SEVERITY` declares the ranking and a fixture drives
  both rules at once.
* **§21.4's flat-all cutoff is not a §7 row and is not filed as one.** §7's trading-hours row is
  marked *Pre-order* and rejects *entries*; §21.4's *"15:55 flat-all cutoff"* closes what is
  already open. Folding the second into §7's table would let a caller reading `RULES_AT` believe
  §7 states a flatten time, which it does not. `eod_flat_due` is a separate predicate and
  `session_flat_all_minute` is a separate registry row — see §5 for why they are separate
  numbers that are equal at the defaults.
* **`flatten_all` asks `positions.reachable_exit_reasons`; it does not re-derive §20.12.** That
  function already exists, already encodes the reading, and already has the test asserting the
  gap. A second walk of `TRANSITIONS` here would be two definitions of which flatten is legal,
  which is the thing the whole registry discipline is about — and it would be the second
  definition in the module whose job is to discover that the first one is empty.

`monitor.py` does not round either, for `daily.py`'s reason.

---

## 4. No clock, by construction — third time, and the seam is now visible

§21.1 forbids `datetime.now()` in strategy and risk code. Phase 4 met that with an `int` minute
on `SessionBar`, Phase 5 with four supplied time-shaped facts, and Phase 6 with four more:

| Time-shaped rule | How it is represented |
|---|---|
| §7 row 2's *"Continuous (1 sec)"* | Not represented, and that is the point. `evaluate(state, EnforcementPoint.CONTINUOUS, cfg)` is a pure function of the state it is handed; how often it is handed one is the caller's |
| §21.4's flat-all cutoff | `eod_flat_due(minute, cfg)` against `session_flat_all_minute` (385), §20.1's ordinal from the open — the same scheme `session_last_entry_minute` uses |
| §7 row 8's *"Rolling 5-day"* window | `roll_multi_day_peak(session_closes, cfg)` over the closes it is **given**, with `multi_day_dd_window_sessions` deciding how many of them count. *Which* sessions those are is §21.4's calendar |
| §10's `session_date` PK | A supplied ISO `str`, as §6.7's key already takes. A `str` cannot be read from a clock |

**Three casualties, recorded because none is fixed.**

1. **§2.0's `premarket_trading_enabled` is still unrepresentable** — G9, for the third phase
   running, and for the same reason: minute 0 *is* 09:30 by definition.
2. **§21.4's half-day contradiction is now reachable.** §7 states the entry window as *"09:30–
   15:55 ET"* absolutely; §21.4 defines the flat-all cutoff as *"`session_close − 5 min`, not a
   hard-coded time"*. On a 13:00 half-day those disagree by three hours, and the ordinal scheme
   can express only one of them at a time. Raised in [CHANGELOG.md](CHANGELOG.md); not resolved,
   because the resolution is a trading calendar and a calendar is a dependency.
3. **`updated_at`, §10's own last column, is not written.** It is a clock field on a row this
   layer produces, so `to_row()` omits it and `from_row()` ignores it — the same treatment
   `RiskDecision` gives `evaluated_at`. §10's schema declares it `TIMESTAMPTZ` and not nullable,
   so a store would have to supply it, which is the store's job and is one more thing that is
   refused here rather than stubbed.

---

## 5. Readings this layer had to take

Same treatment Phase 3 gave §4.2's ambiguities, Phase 4 gave §3's and Phase 5 gave §6's: each is
localised to one function, pinned by a test, and **raised in [CHANGELOG.md](CHANGELOG.md) rather
than settled here.** The table below and the one in that file carry the *same* readings — an
earlier draft had ten rows in each and they were not the same ten, which is the v1.2 shape in the
pair of documents whose whole job is to agree.

| § | What is not settled | Reading taken | Why this one |
|---|---|---|---|
| §7 row 4 | *"Consecutive losses"* — §7 never says whether a **loss** is gross or net, and §9.2's `ClosedTrade` carries both | **Net.** `ClosedTrade.is_loss` is `net_pnl < 0` | §9.2 already fixes the other half of this: `r_multiple` is *"computed on NET P&L, not gross"*, and §18.7 is judged net. A trade that clears $4 gross and pays $6 in commission cost the account money, and a streak rule that calls it a win is counting something the account did not experience |
| §7 row 4 | A **scratch** — `net_pnl` exactly zero. §7 says the streak counts losses and says nothing about what breaks one | **A scratch is not a loss and resets the streak to zero** | *Consecutive* means unbroken, and a trade that was not a loss breaks a run of losses. The alternative — carrying the count through a scratch — makes the rule count *"losses with non-losses interspersed"*, which is not what §2's Three Strikes Rule describes |
| §7 row 7 | Action is *"Flatten all; lock account"*, with **no duration**, where row 2's otherwise-identical action says *"for day"* | **For the day.** Rows 2 and 7 share `HaltAction.FLATTEN_AND_LOCK_DAY` | The rule is a *session* drawdown and §10 keys `daily_state` by session date, so the day is the only scope the rule's own inputs have. An indefinite lock is the stricter reading and is rejected here on the grounds that §7 states durations where it means them — row 8 says *"next day"* explicitly |
| §7 row 8 | *"Lock account next day"* — a state §10's `daily_state` has **no column for**, applied to a session this layer does not have | `DailyState.locks_next_session`, carried into the next session by `open_session(carried_lock=...)` | The action is unimplementable as a mutation of today's row, and the only alternatives are dropping it or inventing a column. Inventing one is a spec change and is raised as such; carrying it as a field of the *outgoing* state keeps the arithmetic testable in one session, which is all a pure layer can hold |
| §7 / §21.4 | §7 row 9 states the entry window as an **MVP default** of *"09:30–15:55 ET"* and defers the bounds themselves — its Bypassable cell reads *"Yes (window bounds; DST-aware per §21.4)"* — while §21.4 defines the flat-all cutoff as *"session_close − 5 min"*. On a regular session both land on minute 385 | **Two registry rows, coupled** — `session_last_entry_minute` and `session_flat_all_minute`, with `validate_couplings` requiring the flatten to be at or after the last entry | They are two rules about two different actions that are equal at one calendar's regular session. Reading them as one threshold bakes a coincidence into the registry, and the half-day case (§4) is where they come apart. The coupling is the part that is actually invariant: an entry window outlasting the flatten would open a position after the close |
| §7 row 11 | Enforcement point *"Any"* — which for a table organised by point is every point, or none | **Every point.** `RULES_AT[ANY]` is unioned into every other point's rule set, derived rather than repeated | *Any* is the widest word in the column and the row is the kill switch, so the reading that costs something if wrong is the narrow one. Deriving the union means a rule marked *Any* cannot be present at four points and missing from the fifth |
| §7 / §7.2 | When two rows breach at the same point, which Violation Action applies? §7 states no precedence | **The strictest**, ranked by what the action removes, while the *reason* stays §7's table order | Two questions, two answers. One value for both under-enforces in the direction that matters: row 4 locks entries and row 2 flattens, and reporting row 4's action alone leaves the position open |
| §7.2 | *"Requires manual reset with confirmation phrase"* — a phrase, in a layer with no UI, no config file and no secret store | `clear_lock(state, phrase, expected)` raises unless the two match; **both are supplied** | The *rule* is that a lock cannot be cleared implicitly, and that is arithmetic. Sourcing the expected phrase is §21.5's keyring, and §11.1's *"lock persists across restart … and cannot be cleared by relaunching"* is the property this makes testable. Storing a phrase here would put a secret in a package that holds none |
| §20.8 | *"remains in `NO_TRADE` state until a snapshot succeeds"* — `NO_TRADE` is named as a state and defined nowhere | `SessionPhase.NO_TRADE`, with `start_of_day_equity` **`None`** and `risk_state()` refusing | §20.8's own justification is that *"every non-bypassable risk limit is denominated in it."* A state carrying a placeholder equity satisfies the type and defeats the sentence; a state carrying `None` cannot be evaluated by mistake |
| §10 vs §9.2 | `closed_trades` has one `pnl` column; §9.2's `ClosedTrade` has `gross_pnl`, `commission`, `fees` and `net_pnl`, of which §9.2 marks `net_pnl` *"the figure §18.7 is judged on"* — and §9.2's `Fill` calls the fees *"required for net metrics (§8.3)"* | `ClosedTrade` carries §9.2's four and `to_row()` does **not** cover `closed_trades` at all | §10's schema cannot represent the distinction §18.7 is judged on, so writing a `pnl` here would mean choosing which of the two the gate later reads — the one decision §18.7 must not inherit from a persistence layer. Raised; `to_row()` is scoped to `daily_state` and says so |

---

## 6. What Phase 6 found by building — two findings that change a verdict

Every reading in §5 above is raised in [CHANGELOG.md](CHANGELOG.md)'s Unreleased table, **and
that table is the count — this section does not restate it.** Phase 5's §6 records why: the first draft of the
equivalent section carried a number that was wrong by two against the list it was summarising.

Below are the two findings that change a verdict. Both were reproduced by execution, both are
raised and not resolved, and — as with Phase 5's pair — **both were invisible to every check
that came before**, for a reason worth stating: each is about a rule's *enforcement point*
rather than its arithmetic, and every mechanical check this repository owns ranges over
arithmetic.

### Finding 1 — §7.1.2's restart guarantee is incomplete in §10's own schema

**§7.1.2 is unambiguous:** *"The non-bypassable limits are meaningless if they reset on restart.
`daily_state` (§10) persists `start_of_day_equity`, realized P&L, consecutive-loss count,
day-trade count, and lockout flags, keyed by session date."* Every one of those five is a §10
column and every one round-trips.

**Three of §7's inputs are not on that list, and §10 has no column for any of them:**

| Fact | Which §7 rule needs it | §10 column |
|---|---|---|
| `unrealized_pnl` | Row 2's numerator — §7 writes *"Realized + unrealized P&L"* | none |
| `session_equity_peak` | Row 7 — *"Peak-to-trough > session_dd_pct"* | none |
| `multi_day_peak_equity` | Row 8 — *"Rolling 5-day DD"* | none |
| `locks_next_session` | Row 8's Violation Action — *"Lock account next day"* | none |

So on the schema as written, **a restart mid-session restores the daily-loss lockout and silently
resets both drawdown rules**, and a restart overnight loses row 8's lock entirely — the one whose
whole purpose is to survive to the next day. Rows 7 and 8 are marked *Yes* under Bypassable, so
this is not a non-bypassable rule failing; it is two configurable ones that a crash disables
without saying so, plus one whose action cannot be delivered at all.

`risk.py` recorded half of this in a docstring — *"§10's `daily_state` has no drawdown fields at
all"* — as a note on two predicate arguments. Building the row is what turns it from a note into
a consequence, because the round trip is the thing that either carries a fact or drops it, and
`UNPERSISTED_FIELDS` is the enumeration of what it drops. `to_row()` covers `DAILY_STATE_COLUMNS`
exactly, and a test asserts both halves: that every column in that map is written, and that every
field outside it is in `UNPERSISTED_FIELDS`. **What is not checked, stated because an unqualified
claim about a checker is what F8 was about:** `DAILY_STATE_COLUMNS` is a hand transcription of
§10's table, and nothing compares it back to `docs/PRD.md` — so a mis-transcribed column name
would pass. `test_scanner.py` does parse §4.2 out of the PRD and compare it in both directions,
which is the shape this would need and does not yet have.

**Candidate resolutions, none taken:** add four columns to §10's `daily_state`, which is the
obvious fix and makes §7.1.2's sentence true as written; or recompute the peaks from
`closed_trades` and broker positions at startup, which §21.3 already does for `daily_state`
(*"rebuilt from broker executions, not trusted blindly"*) and which needs a broker; or state in
§7 that rows 7 and 8 are session-local and reset by design, which contradicts row 8's own
*"rolling 5-day"*.

**On G2.** The risk register's *"`daily_loss_pct` — NON-BYPASSABLE per §7, has a legal range, a
cap check and no enforcement point"* narrows a **second** time here and still does not close.
That row has three enforcement points across two sections — §7's cell names *"Continuous
(1 sec) + post-fill"* and §6.3's second check supplies the pre-order one. Phase 5 built §6.3's,
Phase 6 builds *post-fill* and the **evaluation** half of *Continuous*, and the *cadence* half is
a timer this layer refuses to own. Two of three, and the third is a scheduler. Claiming G2 closed
would be the F8 shape.

### Finding 2 — the flatten §7 requires is unrepresentable for four of five open states

**This is round 14's H3, arriving as a blocker.** That round raised it as a composition problem
between Phase 4's post-entry predicates and Phase 5's state machine, and the disposition was *no
code change — widening a normative table on this layer's authority is the thing the reading
exists to avoid.* That disposition was right and it is unchanged here. What changes is the
**cost**, because Phase 6 is the phase whose job is the flatten:

§7 has two rows whose Violation Action begins *"Flatten all"* and a third — the kill switch,
enforcement point *"Any"* — whose action is *"Cancel all open orders → market-close all
positions."* §20.12 has four edges into `CLOSED`, and **only one of them starts at an open
state**: `TRAILING`. The other three are the exit states, which a flatten has not reached. So:

| Open state | `KILL_SWITCH` / `EOD_FLAT` representable? |
|---|---|
| `PENDING_ENTRY` | **No** — successors are `OPEN_FULL`, `EXPIRED` |
| `OPEN_FULL` | **No** — successors are `T1_FILLED` and the three failure states |
| `T1_FILLED` | **No** — successors are `T2_FILLED`, `STOPPED_OUT` |
| `T2_FILLED` | **No** — successor is `TRAILING` only |
| `TRAILING` | Yes |

`flatten_all` therefore produces a directive for **every** open position — it never silently
drops one — and marks four of the five with `to_state=None`. The set is
`unrepresentable_flatten_states(reason)`, **derived from `positions.reachable_exit_reasons`**
rather than written out, so a later correction to §20.12 shrinks it and the test asserting it is
non-empty fails deliberately.

Two things this makes concrete that H3 did not:

1. **The kill switch is the rule §7 marks NON-BYPASSABLE with enforcement point *Any*, and it
   cannot be recorded for a position at full risk.** The directive can be computed and an
   operator can act on it; what cannot happen is the state machine agreeing that it happened.
   Under §20.12 as written, an account flattened by the kill switch leaves four positions still
   recorded in the open state they were in — `OPEN_FULL` among them — which is precisely the
   *"discovering an untracked broker position"* outcome §20.12's persistence sentence exists to
   prevent.
2. **`PENDING_ENTRY` has a defensible edge and it is not taken here.** §7.2's action is *"Cancel
   all open orders → market-close all positions"*, and cancelling an unfilled entry is
   §20.12's own `PENDING_ENTRY → EXPIRED`. That reading would take the count from four to three.
   It is **not** taken, for two reasons. §20.12's table gives `EXPIRED` **no row and no
   definition at all** — it appears only as a diagram arrow and as a successor of `ARMED` and
   `PENDING_ENTRY` — so reading a *cause* into it is this layer supplying one the PRD does not.
   *(The sentence `positions.py` carries about it — "the trigger never came, or the entry order
   never filled" — is that module's own gloss, and an earlier draft of this paragraph quoted it
   as §20.12's.)* And §6.4 turns a *partially* filled entry into a sized position, so
   `PENDING_ENTRY` can hold shares that a state meaning *never filled* would strand. Recorded as a candidate resolution rather than applied, because
   choosing it here is the unilateral widening H3's disposition refused.

**Candidate resolutions, none taken:** add `→ CLOSED` from every open state to §20.12, which
makes both the kill switch and the EOD flat work and is the smallest edit; or add a distinct
`FLATTENED` state with edges from every open state, which keeps `CLOSED` meaning *ladder
finished*; or read `PENDING_ENTRY → EXPIRED` as above and accept the gap for the other three.

---

## 7. Registry additions

**Two rows, taking the registry from 84 to 86, and both are `(bounds: code)`.** §7's multi-day
row states *"Rolling 5-day DD"* with no Bounds column and §21.4 states the flat-all cutoff in
prose, so neither range is spec. That is Phase 4's and Phase 5's position rather than Phase 3's.

| Row | Default | § | Polarity |
|---|---|---|---|
| `session_flat_all_minute` | 385 | §7 / §21.4 (15:55 ET) | MAXIMUM |
| `multi_day_dd_window_sessions` | 5 | §7 multi-day drawdown row | — |

`multi_day_dd_window_sessions` carries **no polarity**, and the distinction is the one the
registry already makes: a count that is a *constraint* has a direction and a count that is a
*window* does not. Compare `rvol_lookback_days` and `flagpole_vol_lookback_bars`, which have
none, against `max_open_positions` and `flag_max_candles`, which do.

**Four deliberate non-registrations**, because what is absent is as load-bearing as what is
present:

* **§7 row 2's 1-second cadence.** The loop is refused (§1.1), so the row would have no reader.
  `params.py` already declines `atr_period` and §6.8's retry constants on exactly this argument.
* **§7.2's confirmation phrase.** A secret, not a threshold — §21.5 puts credentials in an OS
  keyring and forbids them in configuration. `clear_lock` takes both sides as arguments.
* **FINRA's 5-business-day PDT window is still `risk.PDT_WINDOW_BUSINESS_DAYS`**, a module
  constant, and `multi_day_dd_window_sessions` is a registry row with the same default of 5.
  They are not the same fact: one is a regulation with no legal range and the other is §2.0-style
  tunable that §7 states as a default. Registering the first or hard-coding the second would each
  be wrong in a different direction.
* **§8.3's metrics and §18.7's gate criteria.** Phase 4b's, and the argument
  [PHASE-5-DESIGN](PHASE-5-DESIGN.md) §7 makes about `impact_coefficient` applies unchanged.

**One new coupling.** `session_flat_all_minute >= session_last_entry_minute`, in
`validate_couplings`. An entry window that outlasts the flat-all cutoff admits a position opened
after the session is required to be flat, while both parameters stay inside their own bounds and
per-parameter validation passes — third-defect-class shape, and the defaults satisfy it at
equality, which is the boundary the fixture drives.

**Baseline: unchanged, and still the same 74-entry frozen list.** Neither new default produces a
search key for the PRD-prose lint, whose key set covers sub-dollar USD values, `xR` multiples and
sub-10% fractions and neither row is any of those. For the *code* lint, `385` was already a key
(`session_last_entry_minute`) and `5` was already one (`recent_halt_lookback_days`), so the search
space does not widen either. `tests/registry_baseline.json` is byte-identical to its previous
revision, which is checkable — and this paragraph does not claim a regeneration was run, because
`scripts/regen_registry_baseline.py` shells out to `pytest`, which §9 records as uninstallable
here.

**Rounding.** Neither new module rounds, so the enforcement suite's derived rounding-consumer
list is unchanged at six files and neither `daily.py` nor `monitor.py` is subject to the
`Polarity`-import check. `monitor.py` *does* import `rounding`, for `TICK_SIZE` alone — a dollar
figure in an audit string is quantized to the price grid rather than to a locally written
`Decimal("0.01")`, which is `risk.py`'s posture exactly. `quantize` is not one of the four
functions that list is derived from, which is why importing the constant does not enlist the
module. Both new rows are a minute ordinal and a session count; neither is a
price level, so no new call reaches `Config.round_for`.

---

## 8. Test plan

| Layer | What it asserts |
|---|---|
| Worked session (`spec`) | One session end to end from §3's own examples: `open_session` refuses §7 → `record_snapshot` → a §9.2 `ClosedTrade` built from §3.2's own levels is accrued at *Post-trade close* → `evaluate(POST_FILL)` is **clear**, because one R does not breach §7 row 2 at any legal configuration → `mark_to_market` to exactly row 2's limit → `evaluate(CONTINUOUS)` returns `FLATTEN_AND_LOCK_DAY` → the lock reaches `risk.approve` through the one bridge → `flatten_all` emits one directive per open state and at least one is unrecordable. Every figure derived, none asserted against a literal. The *count* of unrecordable states is asserted separately, by the parametrised §20.12 fixture, so the end-to-end replay does not restate it |
| §7 enforcement-point coverage | A fixture per (row, point) pair in `RULES_AT`, each driving that row and only that row, **and** a two-step guard derived from the enum: `ACTION_FOR` is asserted **total over `RiskBlock`** — §7 gives every row a Violation Action — and then every row whose action is not `REJECT_ORDER` is asserted to appear at exactly the points `RULES_AT` names. Either step alone leaves a hole: the first misses a row with an action and no point, and the second cannot see a member added to the enum and to neither mapping |
| `rules_evaluated` | Asserted against `RULES_AT[point] | RULES_AT[ANY]` **as an ordered tuple**, never as a length, and `evaluate` raises if its own output disagrees. The enforcement suite performs the drop. Phase 5's equivalent fixture was `len(...) >= 10` against an actual 12 in its first draft |
| Strictness | Two rows breaching at once — loss-streak (*lock entries*) and daily loss (*flatten*) — must report the earlier row as `reason` and the **stronger** action. Both halves asserted, because a decision that gets one right and the other wrong is the one that under-enforces silently |
| §20.8 (`spec`) | A `NO_TRADE` state cannot produce a `RiskState`; a second snapshot cannot overwrite the first; a snapshot cannot be skipped by constructing a `DailyState` directly with an equity and no phase change |
| §7.1.2 round trip | `to_row` → `from_row` reproduces every column in `DAILY_STATE_COLUMNS`, derived from that map rather than listed, and a locked state reloads locked. A **second** fixture derives the complement from the **dataclass** and asserts it is exactly `UNPERSISTED_FIELDS`, so finding 1 fails the suite if someone quietly widens the row — in either direction. What neither can check is whether the map matches §10; see §6 |
| §20.12 flatten (`spec`) | `flatten_all` emits one directive per open position (count derived, not written); a representable directive transitions without raising; an unrepresentable one raises `IllegalTransitionError`; and `unrepresentable_flatten_states` is **non-empty**, so a correction to §20.12 fails it deliberately — the same shape as Phase 5's `reachable_exit_reasons` assertion |
| Reachability (`spec`) | **Every `RiskBlock` member is produced by some path.** The positive assertion that replaces `test_the_two_drawdown_blocks_are_unreachable_until_phase_6`, whose own docstring said *"when Phase 6 wires the loop, this fails"* — it does, and this is what it becomes. `risk.UNREACHABLE_BLOCKS` is now empty and a test asserts the emptiness rather than deleting the name |
| Boundary (`boundary`) | Both new thresholds named by a `@pytest.mark.boundary` block, and that coverage **derived from the source** by `test_every_phase_6_threshold_has_a_boundary_fixture`. What the derivation cannot check is stated with it: the minute at exactly `session_flat_all_minute` (§21.4's cutoff is inclusive — at 385 the flatten is due), the coupling at exact equality of the two minutes, the window at exactly its `lo` and at exactly its `hi`, each with one further session outside
it, the streak at exactly `max_consecutive_losses`, and the drawdowns at exactly their thresholds — §7 writes rows 7 and 8 with `>`, so equality must *not* breach |
| Polarity (`polarity`) | `session_flat_all_minute` read back through `eod_flat_due`, asserted against the direction the opposite polarity would have taken, never against a value |
| Enforcement | The violation each new guarantee forbids: a `DailyState` with no snapshot reaching a §7 rule; a lock cleared without the phrase; a lock lost across a round trip; a `ClosedTrade` with zero R or zero shares producing an `r_multiple`; a rule dropped from `evaluate`'s loop; a flatten directive with a `to_state` other than `CLOSED`; a §10 field added to `DailyState` and not carried by the bridge; and the D30 import allowlist extended to both new modules |
| Absence (`spec`) | The guarantee Phase 6 **cannot** make is asserted absent, not left ambiguous: neither module *calls* `open`, `connect`, `dump`, `load` or `write_text` (by AST, not by substring — this layer's docstrings describe the guarantee, and a text search reports the description as a violation), and the import allowlist above keeps `sqlite3` and `pathlib` out. So §7.1.2's durability half is pinned open exactly as Phase 5 pinned both halves |

Convention 6 is why the Reachability, Enforcement and Absence rows exist. The happy-path test
passes whether or not a guarantee is enforced, which is how four guarantees came to be unenforced at once in v0.0.1 with
three of them sitting beside a passing test.

---

## 9. What this document is not evidence of

**`make check` was not run *by the author*, and review round 15 then ran it and found it red.**
Both halves matter and the second is the useful one, so it is stated first.

The authoring environment has no network: `uv sync` cannot fetch CPython 3.13, `pip` cannot reach
an index, and the checked-in `.venv` holds macOS binaries a Linux sandbox cannot execute. So none
of the five `make check` targets was executed there — not lint, not format-check, not typecheck,
not links, not the suite.

[REVIEW-2026-08-01-round15](reviews/REVIEW-2026-08-01-round15.md) had a working toolchain and
measured the gate on both sides of this changeset. **The gate was already red, and this change
made it redder:**

| Target | Before Phase 6 | After Phase 6 | Added here |
|---|---|---|---|
| `ruff check` | 5 errors | 15 errors | **+10** |
| `ruff format --check` | 7 files | 9 files | **+2** |
| `basedpyright` | 2 errors | 10 errors | **+8** |
| `pytest` | — | 409 passed | 0 |

Every one of the eighteen this change added is behaviour-preserving and is convention 8's
category, so they are **fixed in this changeset and listed in one line each** in that round rather
than dispositioned. What is *not* convention 8's category is the row above them: the gate has been
red across at least three phases, which means **Phase 5 shipped red as well**, and the merges
happened anyway even though CI runs the gate on every pull request. That is round 15's finding and it belongs to the sixth
defect class's family — the one distinction being that this document declined to claim the gate
was green, so it is the *precondition* for that class rather than an instance of it.

**Two sentences that were here and are now known to have been too weak.** This section previously
said the gate *"was not run"* and that nothing here *"should be read as evidence that the gate is
green"*. Both were true and neither was useful: *not run* and *red, by a measured margin this
change widened* are different facts, and only a reader with a toolchain could tell them apart.
Three consecutive phases have now shipped on the first sentence.

What *was* run, stated as what it is: the package and both new modules import and execute under
the system CPython 3.10; `python -m tradipy demo`, `setups`, `scan`, `risk` and `monitor` all
exit 0; and every test function in the suite was executed directly as a function by a general
harness that collects `test_*` callables and resolves the `parametrize` and `raises` machinery
they use. That is running code, and it is a **general** substitute rather than a specific one —
it runs whatever tests exist, including ones whose subject nobody considered — which is the
distinction [REVIEW-2026-07-30](reviews/REVIEW-2026-07-30.md) drew after round 7 built a
*specific* substitute calibrated to the answer its author expected. **No substitute for `ruff`
or `basedpyright` is reported, because there is none**, and reporting a hand-built one beside a
real execution is the mistake that produced the sixth defect class's second victim.

**What this document *is* evidence of, because it was checked twice by readers who did not write
it.** [PHASE-5-DESIGN](PHASE-5-DESIGN.md) §9's argument is that a phase hiding its own error rate
makes the next one trust it more than it should, so both passes are reported.

**First pass: 30 discrepancies**, against the source and against `docs/PRD.md`. Three were HIGH
and each is worth naming, because two of the three are defect classes this repository already has
a row for. **A count wrong in one place and right in six others**: finding 2's own heading said
*three* of five open states where its table, its body, both changelogs, the PLAN, the API
reference, the test suite and the module all said four. **A fabricated PRD quotation** — a
sentence `positions.py` wrote about `EXPIRED`, quoted as §20.12's own definition, and load-bearing
in the argument for refusing a candidate resolution; §20.12 gives `EXPIRED` no row and no
definition at all. And **"three predicates that nothing calls"** where the module's own docstring,
correctly, named two. The rest were counts, dependency rows, quotations altered inside their
quotation marks, and four claims about what a test asserts that the test did not.

**Five of the thirty were gaps in the code or the tests rather than in the prose**, and they are
fixed here rather than dispositioned: `ACTION_FOR` was **not** total over `RiskBlock`, so the
coverage guard could not make the derivation this document claimed for it; `daily.py`'s
`_BRIDGE_EXCEPTIONS` was **dead**, with the test that was supposed to read it carrying its own
divergent copy — the v1.2 class inside the constant written to prevent it; `HaltAction`'s comment
attributed *"Reject order"* to §7 row 12, whose action is *"Reject **signal**"*; the D35 row had a
stray blank line above it and so was **not in the decision-log table** at all; and §5's readings
table and the CHANGELOG's carried ten rows each that were not the same ten.

**Second pass over the corrections: 10 more**, which is the finding that matters most. The largest
was the fix for one of them: *"§7's four non-pre-order enforcement points"* was corrected to five
in three files and **left in fourteen others**, one of which is a string `python -m tradipy
monitor` prints. That is the v1.2 defect class produced *by* a correction, which is the specific
risk [REVIEW-2026-07-31-round9](reviews/REVIEW-2026-07-31-round9.md) records for its own second
pass, and it is the argument for running one. All ten are fixed; a third pass was not run, and
that is this document's remaining exposure.
