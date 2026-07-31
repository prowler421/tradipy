# Phase 5 Design — Pre-Order Risk and Order Construction (§6, §7, §20.12)

> **Purpose:** the design record for PRD §12.1's **Phase 5 — execution + pre-trade risk**:
> what it is, what it deliberately is not, why the half of it that §12.1 names first is
> *forbidden* rather than merely deferred, the readings §6 and §7 forced, and what building it
> on handed-in state does and does not establish.
> **Status:** built. `src/tradipy/risk.py`, `src/tradipy/orders.py`,
> `src/tradipy/positions.py`, `python -m tradipy risk`.
> **Gate posture:** [PLAN](PLAN.md) **D34** — the pure half constructed, the transport half
> refused, calibration and the §18.7 gate both still closed.
> **Last updated:** 2026-08-01 — amended after review round 14 (H3's re-characterisation, H6's fix).

---

## 1. What Phase 5 is

§12.1 gives Phase 5 one line — *"Execution + pre-trade risk"*, complexity High, dependencies
**"4b (gate passed), IBKR paper"**, risk *"order routing"*. That dependency column is the whole
problem, and it is a different problem from the one D32 and D33 solved:

* **Phase 4b does not exist**, so the §18.7 Viability Gate has not been run, let alone passed.
* **"IBKR paper" is not deferred, it is forbidden.** `CLAUDE.md` convention 9 / **D30** admits
  no broker SDK, vendor client or network module anywhere in `src/`, `scripts/` or `tests/`.

So Phase 5 cannot be built as §12.1 describes it, and the interesting question is what is left
when the forbidden part is removed. Read against §6, §7 and §20.12 rather than against the
roadmap line, the answer is substantial and it is the same shape as every layer before it:
**Phase 5 is the layer that turns a `SetupSignal` into an approved `OrderDraft`, or into the
reason there is not one.**

Concretely it closes three gaps the package has carried since v0.0.1:

1. **§7's rule table had two enforcement points in code and eleven in the document.** It has
   thirteen rows. The two signal-time ones — Min R:R and Spread check — are `gates.check_room`
   and `gates.check_spread`. The other eleven are marked **Pre-order**, **Continuous**,
   **Post-trade close**, **End of day** or **Any**, and nothing in the package evaluated one of
   them. `daily_loss_pct` is
   the one the risk register names: NON-BYPASSABLE per §7, with a legal range, a hard cap and
   *no enforcement point anywhere* (open question **G2**).
2. **§6.3's eight pre-trade checks were prose.** Every one is a predicate over a proposed
   order, a risk state and a config. None needs a broker if the state is handed in — which is
   exactly how a `Session` reaches `setups` and a `ScanCandidate` reaches `scanner`.
3. **§20.12's state machine had a vocabulary and no machine.** `ExitReason`'s docstring already
   says its members exist so that *"a Phase 5 state machine consuming these does not have to
   reconcile a second vocabulary."* This is that consumer.

### 1.1 What it is not

| Not in Phase 5 | Why, and where it goes |
|---|---|
| **Submit, acknowledge, cancel, amend** — everything in §6.2 downstream of `OrderDraft` | **D30, and this is a refusal rather than a deferral.** §6.2's lifecycle arrow `OrderDraft → Submit` is the exact boundary; this layer builds the draft and stops. The ladder is at `SIMULATED`, advancing it is still **D31**, still unwritten |
| §6.6 connection-failure recovery, §6.8 retry and backoff, §21.2 resting brackets, §21.3 reconciliation | All four require a connection to *have* failed. Phase 5's transport half, gated behind D31 |
| Persistence — §10's `daily_state`, `idempotency_keys`, `orders`, `positions` tables | No DB dependency, per `CLAUDE.md`'s standard on dependencies. **The consequence is stated rather than papered over:** §6.7's guarantee is *"the DB — not process memory — is the arbiter, so protection survives a crash mid-submission."* This layer computes the key and **cannot make that guarantee**. §7.1.2's *"the non-bypassable limits are meaningless if they reset on restart"* is likewise unclosed |
| §20.8's start-of-day equity **snapshot** | Needs a broker sync at 09:30. `start_of_day_equity` is already a registry row, so the *value* is supplied and the *snapshot mechanism* is Phase 2 ingestion's. §20.8's `NO_TRADE`-until-snapshot rule has no representation here |
| §7's **Continuous** rows as a loop — daily loss at 1 s, session drawdown, multi-day drawdown | The **predicates** are here (`daily_loss_breached`, `session_drawdown_breached`, `multi_day_drawdown_breached`); the 1-second loop that calls them and sets `trading_halted` is Phase 6. Same treatment §3's post-entry rules got in Phase 4 — rules as predicates, without the state they would be evaluated in |
| §6.5's slippage model (`base_ticks`, `spread_fraction`, the square-root impact term) | **Phase 4b**, and this is a §12.1-versus-§6 boundary disagreement rather than a choice — see §6 question 10. Its only consumer is §8.2's fill model, D22's stress requirement is a Phase 4b deliverable, and [PHASE-4-DESIGN](PHASE-4-DESIGN.md) §1.1 already assigned it there. `impact_coefficient` therefore stays **unregistered**: a registry row wired to nothing is the fifth defect class in miniature, which `params.py` says in terms about `atr_period` |
| §7's kill-switch **sentinel** at `$XDG_STATE_HOME/tradipy/kill` | A file read, and no module in this package opens a file. The *trigger* arrives as `RiskState.trading_halted` / `halt_reason`, which is §10's own `daily_state` schema. So §21.5's path has a reader nowhere, which is question 11 |
| T3's ratcheting 9 EMA trail | Still not built, and **D18** is still why: the ratcheted level has to rest as a broker-side stop amended each bar close. `positions.py` models the `TRAILING` **state** and `session.ema_at` computes the level; the protection is transport's |
| §18.7's viability gate | Phase 4b. Phase 5 produces an approved draft; nothing here says the strategy has an edge, and §2 below is the whole point |

---

## 2. Gate posture — the doubly-gated phase

D32 opened Phase 3 by separating **construction** from **calibration**. D33 extended that to
Phase 4 and priced the part that did not carry over. **D34 extends it again, and this time the
gate has two independent halves that must be distinguished, because conflating them is how a
phase gets declared open on an argument that only covers one of them.**

| Gate | What it blocks | Status under D34 |
|---|---|---|
| **D30 / D31 — the data ladder** | Reading a market, and therefore *submitting to one* | **Unchanged and binding.** `PERMITTED_ORIGINS` stays `{SIMULATED}`. The transport half of Phase 5 is not built, and §1.1's first row is a refusal |
| **§18.7 / Phase 4b — the viability gate** | *Committing capital* | **Unchanged and binding.** Not run, not passed. Nothing below claims otherwise |
| **Calibration** | Trusting any threshold | **Unchanged.** Nine new registry rows, all `(bounds: code)` |
| **Construction** of pure §6/§7/§20.12 arithmetic | — | **Opened**, on the argument below |

The argument, stated so it can be attacked: **§18.7's gate governs whether to trade, not
whether the arithmetic that would refuse a trade is correct.** A pre-order risk engine's job is
to *decline* orders, and every §7 rule it applies is a rule about the account rather than about
the edge. A negative Phase 4b outcome does not change one line of §7 — it changes whether
anything ever calls it. That is a materially weaker exposure than D33's, where a §3 rewrite
would have changed control flow.

What Phase 5 may claim, stated narrowly because the first draft of this paragraph overstated it
in two places: §6.3's eight checks and **nine of** §7's eleven non-signal-time rows are applied as
those sections write them; §20.12's transition table is transcribed rather than invented; every
threshold comes from the registry; and the **two** §3 worked examples that produce a signal now run
end to end from bars to an `OrderDraft` or to the `RiskDecision` explaining why not.

The two §7 rows that are *not* applied are rows 7 and 8, the drawdowns: their predicates exist and
**nothing calls them**, because §7 marks their enforcement point *Continuous* and *End of day*.
`RiskBlock.SESSION_DRAWDOWN` and `RiskBlock.MULTI_DAY_DRAWDOWN` are therefore produced by no code
path, which `risk.UNREACHABLE_BLOCKS` enumerates and a test asserts — an unreachable reason code is
normally a defect, so the two that are unreachable on purpose need the opposite assertion or the
next reader cannot tell a deliberate gap from an accidental one. §3.4 produces neither a draft nor
a decision: §3.1.1's room gate rejected it before a `SetupSignal` existed (Phase 4's L2).

What it may not claim, and this list is the point of the section:

1. **No threshold is calibrated.** All nine new rows are `(bounds: code)` per convention 7:
   §6.1, §6.3, §6.4 and §7 have no Bounds column, and §3.1.1's ladder table has none either.
   This is Phase 4's position, not Phase 3's.
2. **The refused half is the half §12.1 names.** §12.1's Phase 5 risk column says *"order
   routing"*, and order routing is precisely what is absent. A reader who takes "Phase 5 is
   built" from the sequencing table and not from this document will be wrong about the part
   that matters most.
3. **Two guarantees are computed and cannot be enforced.** §6.7's idempotency key is derived
   correctly and there is no store to make it *the arbiter*; §7.1.2's restart-survival
   requirement has no persistence. Both are stated in §1.1 and pinned by tests that assert the
   absence rather than the presence.
4. **Three findings, all raised and none resolved** — the disposition §3.4's room-gate failure
   got in Phase 4, and §6 carries all three. Two are §7 rules unreachable at §2's shipped
   defaults, found by running the rules rather than reading them: `max_open_positions` > 1
   against §7's total-risk cap, and §7's PDT row against §7's daily-loss row. The third came from
   review round 14 and is a boundary rather than a threshold: **Phase 4's post-entry predicates
   and this layer's §20.12 machine do not compose for a mid-ladder exit.**
5. **The ladder does not move.** `PERMITTED_ORIGINS` stays `{SIMULATED}`; advancing it is still
   **D31**, still unwritten. [PHASE-3-READINESS.md](PHASE-3-READINESS.md)'s Q1 row stays
   **Not met**, and §12.1's Phase 3, 4 and 5 dependency rows all stay unticked.

---

## 3. Module design

Three modules, all pure, all added at the far end of the existing one-way dependency graph.

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
| **`positions`** | `params`, `rejects`, `rounding` |
| **`risk`** | `gates`, `params`, `positions`, `rejects`, `rounding`, `setups` |
| **`orders`** | `params`, `positions`, `rounding`, `setups` |
| `poc` | `bars`, `gates`, `params`, `quotes`, `rejects`, `rounding`, `scanner`, `score`, `session`, `setups` — **not** the three new ones |
| `__main__` | `poc`, `orders`, `params`, `positions`, `quotes`, `risk`, `rounding`, `scanner`, `score`, `setups` |

A table rather than a drawing, for the reason [PHASE-4-DESIGN](PHASE-4-DESIGN.md) §3 gives.
Three edges are worth explaining because the obvious alternative is wrong in each case:

* **`risk` imports `gates`, not the reverse.** §7's Min R:R and Spread check rows are the
  gates, and §7 marks their enforcement point *pre-order* as well as signal-time, so the risk
  engine has to apply them. Restating either would be the v1.2 defect class.
* **`risk` imports `positions` and not `orders`.** §7's max-risk cap is computed from *open
  positions*' live stops (§7.1.1); nothing in it needs an order draft. Approval happens before
  a draft exists, which is also §6.2's ordering — `PreTradeRiskCheck` precedes `OrderDraft`.
* **`risk` and `orders` both import `setups`, and `poc` imports none of the three.** A
  `RiskDecision` judges a `SetupSignal` and an `OrderDraft` is built from one, so both need the
  type; §6.7's key additionally needs `SetupType`, whose string values are §9.2's and are half of
  that key. `poc` is untouched because Phase 5 composes at the CLI rather than in `poc` — the
  §3 examples it already builds are the input, and `__main__` is where they meet `risk`. The
  dependency table above says so explicitly, because "`poc` imports all of the above" was true
  through Phase 4 and is the kind of sentence that stays after it stops being true.

### 3.1 `positions.py` — §20.12, §3.1.1 stop management, §7.1.1

The state machine, as a transition **table** and a pure transition function. Twelve states,
transcribed from §20.12; the transition set is transcribed too, with one reading recorded in §5
because §20.12's diagram and its table disagree.

```python
PositionState          # 12 members, §20.12
TRANSITIONS            # Mapping[PositionState, frozenset[PositionState]]
transition(state, to)  # -> PositionState, raises IllegalTransition
```

Also here, because each is a property of a position rather than of an order:

* `breakeven_stop(avg_cost)` — §3.1.1's *"on T1 fill, move the stop on the remaining 50% to
  breakeven"*. One line, and it is the line that makes §7.1.1's scale-in argument true.
* `scale_in_permitted(state, open_risk_after, cfg)` — §7.1.1, which turns out to be a **consequence**
  rather than a rule: an add is legal only if total open risk still satisfies the cap
  afterwards, and the only way to create that headroom is T1. The function therefore reads the
  state as well as the arithmetic, and `T1_FILLED` is not sufficient on its own.
* `leg_quantities(shares, cfg)` — §3.1.1's 50/25/25 split over an integer share count, with the
  invariant that the three legs sum **exactly** to `shares`. §3.1.1 states no rule for
  indivisible counts; the reading is in §5 and the invariant has a breaking test.

`positions.py` rounds (the breakeven stop is a price submitted to a broker), so it is in the
enforcement suite's derived list of rounding consumers and may not import `Polarity`.

### 3.2 `risk.py` — §6.3, §7, §7.1–§7.1.3

One `approve()` entry point returning §9.2's `RiskDecision`. **Three** §7 rows are separately
named predicates — `daily_loss_breached`, `session_drawdown_breached` and
`multi_day_drawdown_breached` — because those are the rows §7 marks *Continuous* or *End of day*
and a Phase 6 loop needs to call them without building a decision. The other eight are evaluated
inline in `approve()`; extracting them would create call sites nothing else uses. State arrives as
frozen values:

```python
OpenPosition(symbol, shares, mark, current_stop, state, correlation_group)
RiskState(start_of_day_equity, realized_pnl, unrealized_pnl, consecutive_losses,
          day_trades_in_window, trading_halted, halt_reason, positions,
          session_equity_peak, multi_day_peak_equity, submitted_keys)
RiskDecision(approved, reason, rules_evaluated, open_risk_before, open_risk_after,
             approved_shares)
EVALUATED_RULES      # every rule `approve` must produce, in §7's table order
UNREACHABLE_BLOCKS   # the two §7 rows with a predicate and no block path
```

`RiskState` has **no `minute` field** and that is deliberate — see §4. `mark` rather than
`avg_cost`, because the same field carries the entry limit while a position is `PENDING_ENTRY`,
which §7's *"plus pending orders"* requires.

Four structural choices, each with a precedent one layer down:

* **Every rule is evaluated, not just up to the first block.** `rules_evaluated` is §9.2's own
  field — *"every rule checked, for audit"* — and the reason is `scanner.HardResult`'s and
  `setups.Criterion`'s: a rejection you can see one dimension of cannot be recalibrated against
  measured data. Each entry carries the arithmetic in a `detail` string.
* **§7's rules get a fourth namespace, `RiskBlock`.** This is the K5 argument at one more
  remove. A `Reject` says *this candidate is not tradeable*; a `RiskBlock` says *this account
  may not take this trade right now*, and the same candidate is fine tomorrow. Mixing them
  would let a scanner filter on `LOSS_STREAK_LOCKOUT`, which is exactly the shape K5 caught.
  There is also a concrete asymmetry: two §7 rows' Violation Action is *"Flatten all; lock
  account"*, which is not a rejection of anything. `RiskDecision.reason` is
  `RiskBlock | Reject | None`, which is what §9.2's *"§7 rule name or §4.2 code"* already says.
* **`total_open_risk` is computed from current live stops, never from entry risk.** §7.1.1 is
  explicit, and the distinction is the whole mechanism: it is what makes an add legal after T1
  and what makes §6's finding 2 fall out.
* **Approval never trims.** §9.2's `approved_shares` says *"may be < TradeSignal.shares after
  caps"* and §7's table says *"Reject order"* for every size-related breach. §7 governs;
  `approved_shares` is the requested count on approval and `0` on a block. Raised as question 3.

`risk.py` does **not** round. A risk budget is `equity × pct` and total open risk is
`shares × (entry − stop)`; neither is a price level compared against a tick, which is the
condition `Config.round_for`'s docstring states for rounding at all. Same posture as
`session.py`, and the enforcement suite derives the list rather than trusting this paragraph. It
imports `rounding` all the same, for `TICK_SIZE` — a dollar figure in an audit string is
quantized to the price grid rather than to a `Decimal("0.01")` written locally, which is
`max_pct_of_adv`'s registered default and which the registry lint caught on the first run.

### 3.3 `orders.py` — §6.1, §6.2, §6.4, §6.7

The bracket draft, and nothing that sends it.

```python
OrderSide, OrderType, LegPurpose        # §6.1's five types, §9.2's side strings
OrderLeg(side, order_type, quantity, purpose, limit_price=None, stop_price=None)
OrderDraft(symbol, setup_type, idempotency_key, oca_group, legs, quantities)
idempotency_key(symbol, setup_type, session_date, trigger_minute, account_id)
entry_limit_price(ask, cfg) / stop_limit_price(stop, cfg)
bracket(signal, ask, session_date, account_id, cfg)
partial_fill_action(intended, filled, entry_spread, spread_now, seconds_since_submit, cfg)
```

* **Four legs, one OCA group.** §6.1's Bracket/OCO row is *"entry + stop + target as atomic
  group"* and §3.1.1's ladder has two targets, so the draft is entry + stop + T1 + T2. T3 has
  no leg: §3.1.1 trails it and D18 keeps the trail out of this phase.
* **Every price on the draft is a whole tick, enforced here rather than assumed.** §20.13's
  universal requirement is *"every price submitted to the broker must be a whole tick"*, and an
  `OrderDraft` is the thing submitted. So this is the last place the requirement can bind, and
  it binds regardless of what the caller passed — a sub-penny ask produces a tick-aligned
  limit. The four directions and the one §20.13 does not state are in §5.
* **The idempotency key is `hashlib.sha256`, and that is the whole of §6.7 this layer can
  honour.** §6.7's *point* is that the key is derived from signal identity rather than from a
  UUID, and that half is here and tested by attempting the collision §6.7 forbids. The
  persistence half is not — see §1.1.
* **`partial_fill_action` is a decision, not a wait.** §6.4's *"within 30 sec"* becomes a
  supplied `seconds_since_submit` compared against a registered threshold, exactly as
  `Quote.age_seconds` carries §20.14's staleness into `quotes.py`. The clock stays outside.

---

## 4. No clock, by construction

§21.1 forbids `datetime.now()` in strategy code and requires an injectable clock. Phase 4 met
that with an `int` minute on `SessionBar`; Phase 5 needs four more time-shaped facts and meets
it the same way, which is worth enumerating because a risk engine is the layer most likely to
reach for a wall clock:

| Time-shaped rule | How it is represented |
|---|---|
| §7's trading-hours lockout, 09:30–15:55 ET | `Levels.trigger_minute` — the signal's own bar, ordinal from the open — against `session_last_entry_minute` (385). **Not a field on `RiskState`:** one fact, one source, and the only way the two could differ is §6.6's disconnect queue, which is transport. The early edge needs no threshold because minute 0 **is** 09:30 — but that is a fact about `SessionBar`, which validates it, and `Levels.trigger_minute` is a *copy* of that ordinal, so it re-imposes the floor itself. It did not until review found that a negative minute cleared this row |
| §7's PDT rolling 5-business-day window | `day_trades_in_window`, an `int` — §10's `daily_state` column. Which days are in the window is ingestion's arithmetic, not a risk rule |
| §6.4's 30-second partial-fill window | `seconds_since_submit: int`, supplied |
| §6.7's `trigger_bar_timestamp` in the dedupe key | `session_date: str` (ISO, supplied) plus `trigger_minute: int`. A `str` cannot be read from a clock |

DST, the UTC/`America/New_York` split and business-day arithmetic are §21.4's and ingestion's.
A risk engine that parsed a timezone would be holding a concern D30 keeps out of this layer.

**One casualty, recorded because it is not fixed:** §2.0's `premarket_trading_enabled` is still
unrepresentable — **G9** — and the ordinal-minute scheme makes it unrepresentable *twice*,
because minute 0 is 09:30 by definition and there is no way to express a 04:00 window at all.
D11 disables premarket entries by default, so the shipped behaviour is right by accident rather
than by configuration.

---

## 5. Readings this layer had to take

Same treatment as Phase 3 gave §4.2's ambiguities and Phase 4 gave §3's: each is localised to
one function, pinned by a test, and **raised in [CHANGELOG.md](CHANGELOG.md) rather than settled
here.**

| § | What is not settled | Reading taken | Why this one |
|---|---|---|---|
| §20.12 | The **diagram and the table disagree.** The table gives `T1_FILLED → {T2_FILLED, STOPPED_OUT}` and `T2_FILLED → {TRAILING}`; the diagram's `↓` arrows put `STOPPED_OUT / INVALIDATED / BAILED_OUT` under both. The table has no row at all for `IDLE`, `CLOSED`, `EXPIRED` or the three exit states | **The table where it has a row; the diagram where it has none** — so `IDLE → ARMED` and the three exit states `→ CLOSED` come from the diagram, and nothing else does | The table's column is titled *"Permitted transitions"*, which is an enumeration and is the stricter of the two. Without the diagram's two edge sets the machine can neither start nor finish, so it cannot be the table alone |
| §7 PDT row | *"equity < $25,000"* — §7.1 defines `start_of_day_equity` and `live_equity` and assigns PDT to neither | `live_equity` | FINRA's test is on current account equity. The frozen figure would let a morning loss below $25,000 pass a check whose only purpose is to prevent an illegal trade — the one direction in which being wrong is a regulatory violation rather than a missed trade |
| §9.2 vs §7 | `RiskDecision.approved_shares` — *"may be < TradeSignal.shares after caps"* — against §7's *"Reject order"* on every size-related breach | **Reject, never trim.** `approved_shares` is the request on approval, `0` on a block | §7's rows are marked NON-BYPASSABLE and its Violation Action column is unambiguous. Trimming would have the risk engine invent a share count no §2.2 constraint produced |
| §3.1.1 | The 50 / 25 / 25 ladder over an **integer** share count. §3.1.1 states no rule, and `shares` is `floor`ed by §2.2 | `floor` T1 and T2, remainder to T3, with the three summing **exactly** to `shares` | The binding requirement is that no share is left without a protective leg — §21.6 makes an unprotected position a Sev-1. Flooring the two profit legs is the only allocation that cannot leave one uncovered. **Consequence:** a 1-share position has T1 = T2 = 0 and exits entirely on the trail |
| §20.13 | No row for an **entry limit price**, which is the price §6.1 actually submits | Buy limit `ceil_to_tick`, and the protective sell **limit** `floor_to_tick`. Those are the only two directions this layer chooses: the stop price and both target limits arrive already rounded from `gates` — §20.13 puts rounding *once, at level computation* — and `OrderLeg` only **validates** them | §20.13's governing principle is *"no rounding decision can make a trade look better than it is."* Ceiling a buy and flooring a sell are the two directions that cost money. An earlier version of this cell claimed four directions, two of which Phase 5 code never takes |
| §7 hours row | *"09:30–15:55 ET"*, in a layer with no clock | One MAXIMUM row, `session_last_entry_minute` = 385, ordinal from the open | §21.1 forbids a clock and §20.1 already counts ordinals. 15:55 is 385 minutes after 09:30; §21.4's DST handling is ingestion's |
| §7.1.3 | `correlation_group` assignment needs `news_headlines` (rule 1) and a screening vendor's sector (rule 2) | The **assignment** is first-match-wins over caller-supplied strings; the **enforcement** is *"> 1 position sharing a group"* | The rule is arithmetic over supplied strings; sourcing either input is a feed, and D30 keeps feeds out. Same split as `spread_at_signal` |
| §7 loss-streak row | Action is *"Lock new entries; **allow exits**"*, and §6.3's eight checks would block every order including a protective one | The pre-order gate is applied to **entry** drafts only, and `approve()` takes that intent explicitly rather than inferring it from `OrderLeg.side` | Inferring from side is wrong in both directions: a short entry is a sell and a long exit is a sell. An explicit intent cannot be got wrong silently |
| §6.4 | *"within 30 sec"* — a wait, in a layer with no clock | `seconds_since_submit: int` supplied, threshold applied here | Gives §6.4's figure a reader without importing a clock. Identical shape to `Quote.age_seconds` |
| §6.3 vs §7 | §6.3 lists **eight** pre-trade checks; §7's table marks **eleven** rows Pre-order or stricter, including Max correlated exposure, which §6.3 omits | §7's enforcement column governs; §6.3's list is treated as illustrative | §20 governs on computation and §7 is the rule table with the enforcement column. A check §7 requires and §6.3 forgot is an omission, not an exemption. Recorded because the reverse reading would silently drop a NON-BYPASSABLE row |

---

## 6. Spec questions Phase 5 raises

All in [CHANGELOG.md](CHANGELOG.md)'s Unreleased table, none resolved in code, **and that table is
the count — this section does not restate it.** That is not fastidiousness: the first draft of this
section carried a number that was wrong by two against the list it was summarising, which is the
L1 / K6 shape for the fifth time and was written into the same changeset that built the list.
Round 12 required exactly this of [PHASE-4-DESIGN](PHASE-4-DESIGN.md) §6.

Below are the three findings that change a verdict — two from building, one from review round 14,
which is [REVIEW-2026-08-01-round14.md](reviews/REVIEW-2026-08-01-round14.md) and is the first cold
read of this phase. The nineteen Phase 4 raised remain open and untouched.

### Finding 1 — `max_open_positions` > 1 is unreachable at full size

**Reproduced by execution and raised, not resolved.** §2 offers three concurrent positions in
`experienced` mode and hard-ceilings the row at 3; §7's first row makes **total open risk across
all positions**, measured from current live stops, exceed `start_of_day_equity × max_risk_pct` a
NON-BYPASSABLE rejection. §2.2 sizes each position to `floor(max_dollar_risk / stop_distance)`,
i.e. to approximately the *whole* budget.

At the shipped `experienced` preset, using §3.2's own worked example: budget
`$30,000 × 1% = $300`; 2,500 shares × $0.12 = **$300** of open risk from one position. §3.3's
example adds 2,000 × $0.15 = **$300**. Total $600 against a $300 cap — **rejected**. The same
arithmetic holds at `beginner`, where the budget halves and so does every share count.

So a second position is rejected whenever the first is still at full risk, at every legal
configuration. §7.1.1 derives exactly this for **scale-ins** — *"adds are only ever legal after
T1, never while the initial position is still at full risk"* — and does not extend it to new
positions, while §2 advertises a concurrency that inherits the same constraint. Two consequences
make this worth more than a footnote:

1. **`max_open_positions` is not the binding limit it reads as.** Its value changes nothing
   until the earlier positions are past T1, at which point the risk cap permits the add anyway.
   The parameter is close to inert, which is a different claim from the one §2's *"Sensitivity:
   more positions = correlation risk"* makes.
2. **It makes question 3 material.** Under §9.2's trimming reading the second position is
   *sized down* to whatever headroom remains — zero — and under §7's reading it is rejected. The
   two differ in what gets written to the audit trail for a case that is not an edge case.

**Candidate resolutions, none taken:** state in §7 that the cap is per-position rather than
total (which contradicts §7.1.1's own derivation and reopens the A16 contradiction it closed);
or state in §2 that `max_open_positions` binds only after T1, making the coupling explicit; or
denominate the total-risk cap separately from the per-trade cap, which is a new parameter and a
new decision. `tests/test_enforcement.py` and `tests/test_phase5.py` pin the current behaviour and
`python -m tradipy risk` prints it.

### Finding 3 — Phase 4 and Phase 5 do not compose mid-ladder

**Raised by review round 14 as H3, and it is the finding this document originally understated.**
The §20.12 reading in §5 was recorded as a *cost of the reading* — a position past T1 cannot be
marked `INVALIDATED` or `BAILED_OUT`, only `STOPPED_OUT`. Read across the two phases it is more
than that: `setups.bull_flag_exit` and its two siblings are §3 rules that fire on any bar after
entry, they return `ExitReason.INVALIDATED` without consulting a state, and `positions.transition`
will **refuse** that transition once T1 has filled. So Phase 4's post-entry predicates and Phase 5's
state machine agree on the vocabulary — which is why `ExitReason`'s members were transcribed from
§20.12 in the first place — and **do not compose for a mid-ladder exit.**

The same shape covers §7.2's kill switch, whose enforcement point is *"Any"*: §20.12 supplies an
edge to `CLOSED` only from `TRAILING`, so `KILL_SWITCH` and `EOD_FLAT` are unreachable from the four
other open states. `reachable_exit_reasons` returns the empty set there and a test asserts the
emptiness, so a later correction to §20.12 fails it.

**No code change.** Adding the edges would make both work and would also widen a normative table on
this layer's authority, which is the thing the reading exists to avoid. What changes here is the
*characterisation*: this is a boundary between two phases that a reader would reasonably assume is
covered, not a footnote on a transition table.

### Finding 2 — §7's PDT row is unreachable at §2.0's default equity

**Also reproduced by execution, also raised, not resolved, and also the third defect class.** §7's
PDT row fires only when equity is below FINRA's $25,000 floor. Reaching that from §2.0's $30,000
default requires a $5,000 loss — 16.7% of equity — while §7's daily-loss row locks the account at
`daily_loss_pct`, whose registered **ceiling** is 5% ($1,500). The lockout therefore always fires
first, and §7's PDT row cannot be reached at the shipped default at any legal configuration.

It is reachable only for an account starting within `daily_loss_pct` of the floor, which §2.0's own
bounds permit — `start_of_day_equity` has `lo` = $25,000. So this is not a dead rule; it is a rule
whose *reachability* depends on a parameter nothing relates to it, which is A25's shape with a
different pair.

Not enforced as a coupling, per convention 5 and A25's precedent: the incoherent combination is the
shipped default, so raising would make `Config.default` throw and take every call path with it.
`tests/test_phase5.py` pins it in both directions.

**Both findings were invisible to every check that came before.** The registry lint sees one
threshold per rule and both rules read theirs by name. The boundary fixtures vary a parameter while
holding the inputs fixed, which is round 12's §5.2 heuristic and is exactly what misses these: each
one needs *two* parameters read together, and one of them (`start_of_day_equity`) is not a gate
threshold at all. What found them was running §7's rules against §2's own worked examples — which
is the argument for building rather than designing, in the same form D33 made it.

**On G2.** The risk register's *"`daily_loss_pct` — NON-BYPASSABLE per §7, has a legal range, a
cap check and no enforcement point"* **narrows** here rather than closing: the pre-order half is
built and tested, the post-fill and 1-second-continuous halves are not. Claiming G2 closed would
be the F8 shape — an unqualified claim about a check whose scope is smaller than the sentence.

---

## 7. Registry additions

Nine rows, taking the registry from 75 to 84, and **all nine are `(bounds: code)`**. §6.1, §6.3,
§6.4 and §7 have no Bounds column, and §3.1.1's ladder table has none either — so no range here
is spec. That is Phase 4's position rather than Phase 3's.

| Row | Default | § | Polarity |
|---|---|---|---|
| `max_correlated_positions` | 1 | §7 / §7.1.3 | MAXIMUM |
| `session_last_entry_minute` | 385 | §7 trading-hours (15:55 ET) | MAXIMUM |
| `entry_limit_offset_ticks` | 1 | §6.1 | — |
| `stop_limit_offset_ticks` | 2 | §6.1 | — |
| `t1_scale_out_pct` | 0.50 | §3.1.1 | — |
| `t2_scale_out_pct` | 0.25 | §3.1.1 | — |
| `min_partial_fill_pct` | 0.50 | §6.4 | MINIMUM |
| `partial_fill_timeout_seconds` | 30 | §6.4 | MAXIMUM |
| `partial_fill_spread_widening_multiple` | 2.0 | §6.4 | MAXIMUM |

**Three deliberate non-registrations**, because what is absent is as load-bearing as what is
present:

* **FINRA's PDT constants are module constants, not registry rows.** `PDT_MIN_EQUITY` ($25,000),
  `PDT_MAX_DAY_TRADES` (3) and `PDT_WINDOW_BUSINESS_DAYS` (5) are *law*, not tunables — the same
  argument `rounding.TICK_SIZE` makes from SEC Rule 612 and `setups._ONE_DOLLAR` makes about the
  price grid. A registry row implies a legal range, and there is no legal range for a
  regulation.
* **§6.8's retry count, backoff and rate limit, and §6.6's 60-second signal expiry, are not
  registered.** All four are transport rules, transport is refused, and a registered threshold
  with no reader is the fifth defect class. `params.py` already declines `atr_period` on exactly
  this argument.
* **§6.5's `impact_coefficient` is not registered**, despite §6.5 being the one §6 table that
  *does* have a Bounds column (0.0–5.0). Its consumer is Phase 4b's. Registering it now would
  buy a spec-stated bound at the cost of a row wired to nothing.

**One new coupling.** `t1_scale_out_pct + t2_scale_out_pct < 1`, in `validate_couplings`.
§3.1.1's T3 leg is the remainder, and at a sum of 1 or more it is empty — which silently deletes
the ratcheting trail that §21.2 makes the protection of the final tranche, while every
per-parameter bound still passes. Third-defect-class shape, and the defaults satisfy it at 0.75.

**Rounding.** `positions.py` and `orders.py` both round and are therefore in the enforcement
suite's derived consumer list; neither may import `Polarity`. `risk.py` does not round, for the
reason in §3.2. None of the nine rows above is itself tick-rounded — they are counts, ratios,
minutes and multiples — so no new call reaches `Config.round_for` from them; the rounding in the
two new modules is of *price levels*, which take `ceil_to_tick` / `floor_to_tick` directly on the
`gates.t1_level` precedent.

**Baseline: unchanged, and still the same 74-entry frozen list.** `0.25` and `385` are new search keys for the *code*
lint — the one that walks `src/` and `scripts/` for a registered default written as a literal —
and **not** for the PRD-prose lint, whose key set formats a small fraction as a percentage
(`"25%"`) and produced no new key for either. So the frozen baseline needed no regeneration and
`tests/registry_baseline.json` is byte-identical to its previous revision, which is checkable and
is the reason this paragraph does not claim a regen was run. An earlier version of it said the
baseline *was* regenerated and attributed both values to the prose lint; neither was true, and
`scripts/regen_registry_baseline.py` shells out to `pytest`, which §9 records as uninstallable
here.

The phrasing above is *"74-entry frozen list"* rather than the bare noun form, because
`tests/test_documentation.py` reads *`<number>` + "entries"* as a claim about the **registry** and
this paragraph is about the baseline. Not a false positive worth suppressing: the registry size and
the baseline size are two different two-digit numbers one paragraph apart in a document whose
subject is both, which is exactly the configuration the v1.2 class arises in. This document and
PHASE-4-DESIGN were outside that guard's scope until Phase 5 added them, and this was the first
thing it caught — including, on the next run, in the sentence written to explain it.

---

## 8. Test plan

| Layer | What it asserts |
|---|---|
| Worked examples (`spec`) | Each of the three §3 signals through `approve()` and `bracket()`: the §3.2 and §3.3 examples approve on a flat risk state and produce four-leg drafts whose leg quantities sum to the share count and whose prices are whole ticks; §3.4 never reaches the risk engine because §3.1.1 already rejected it, which is asserted rather than skipped |
| §7 rule coverage | A fixture per §7 row **that has a block path** — nine of the eleven — each driving that row and only that row. Two rows have none and cannot: rows 7 and 8's enforcement point is Phase 6's loop, so their fixtures test the *predicate* and a separate one asserts the two `RiskBlock` members are unreachable. Row 12 (Min R:R) is re-applied pre-order and **inert by construction**, so it has no block fixture either and `approve`'s docstring says why. Two of the nine need help to be reachable at all, and the fixtures say so rather than working around it: `MAX_POSITIONS` needs a position already at breakeven (otherwise row 1 fires first) and `PDT_VIOLATION` needs an account started near FINRA's floor (finding 2) |
| `rules_evaluated` | Asserted against `risk.EVALUATED_RULES` **as an ordered tuple**, not as a length. The first version of this was `len(...) >= 10` against an actual 12, which passes with a rule missing — the fifth defect class, in the fixture written to prevent it. `approve` now raises if its own output disagrees, and the enforcement suite performs the drop |
| Boundary (`boundary`) | **All nine** new thresholds named by a `@pytest.mark.boundary` block, and that coverage is *derived from the source* by `test_every_phase_5_threshold_has_a_boundary_fixture` rather than counted by a reader — the same argument `test_every_module_that_rounds_is_in_the_polarity_check` makes about a hand-maintained list. **What the derivation cannot check is stated with it:** it verifies the name appears, not that the fixture exercises the *limit*; that is a review judgement and this enumeration is where it is recorded — the minute at exactly 385, the ladder split where `shares` is indivisible by four, `min_partial_fill_pct` at exactly 50%, the correlation cap at exactly its maximum, both §6.1 offsets at their `lo` **and** `hi` (and at zero, where an offset applied in the wrong direction becomes invisible), the partial-fill timeout at exactly its value, and the widening multiple at exactly 2× — which §6.4 writes as *"> 2×"*, so the boundary keeps working. **The first draft of this row said six of nine and named two things that are not new registry rows** — `max_risk_per_trade_pct`, which is pre-existing, and FINRA's day-trade count, which is a module constant. That is the shape round 12 caught in [PHASE-4-DESIGN](PHASE-4-DESIGN.md) §8; three fixtures were added rather than the claim lowered |
| Non-registry boundaries | Listed separately so they are not double-counted above: total open risk at exactly the cap (permitted — §7 says *"> "*) and `day_trades_in_window` at 2 / 3, which is FINRA's constant rather than a tunable |
| Polarity (`polarity`) | `session_last_entry_minute` and `min_partial_fill_pct` read back through their comparisons, asserted against the direction the opposite polarity would have taken, never against a value |
| §20.12 (`spec`) | Every edge in `TRANSITIONS` is walked, and every edge **not** in it raises. The second half is the one that matters: a state machine that permits everything passes the first |
| Enforcement | The violation each new guarantee forbids: leg quantities that do not sum to `shares`; a draft price that is not a whole tick; a `RiskBlock` reaching a `Reject` slot and the reverse; every §20.12 transition the table omits, including each self-transition; a second position at full risk being approved; a scale-in from any state before T1; an approval on a halted account; two trigger bars producing one idempotency key; a `|` embedded in a key field; a trigger minute before the open; and a rule dropped from `approve`'s loop. `positions.py` and `orders.py` are in the derived rounding-consumer list and so inherit the `Polarity`-import check; `risk.py` is deliberately **not**, because it does not round |
| Absence (`spec`) | The two guarantees Phase 5 **cannot** make are asserted absent rather than left ambiguous: nothing persists, and `RiskState` has no load path. A guarantee documented as unclosed and quietly closed later is as much a drift as the reverse — the sixth defect class from the other side |
| Joint incoherence | Both §6 findings, pinned in **both** directions: the block happens, *and* the arithmetic that causes it is asserted, so resolving either question in either direction fails a fixture deliberately rather than silently changing behaviour |

Convention 6 is why the last three rows exist. The happy-path test passes whether or not a
guarantee is enforced, which is how four guarantees came to be unenforced at once in v0.0.1 with
three of them sitting beside a passing test.

---

## 9. What this document is not evidence of

`make check` was **not run**. The environment that produced this change has no network: `uv
sync` cannot fetch CPython 3.13, and `ruff`, `basedpyright` and `pytest` are not installed and
cannot be installed. So **none of the five `make check` targets was executed** — not lint, not
format-check, not typecheck, not links, not the suite.

What *was* run, stated as what it is: the package and the new modules import and execute under
the system CPython 3.10, `python -m tradipy demo`, `setups`, `scan` and `risk` all exit 0, and every
fixture in the suite was executed directly as a function. That is running code, not running the
gate. **No substitute for `make check` is reported**, because round 7's mistake was building one
and presenting it beside real executions, and [PHASE-4-DESIGN](PHASE-4-DESIGN.md) §9 had the
same gap one round later. In particular **`ruff format --check` was not run**, so the formatting
of the three new modules is unverified; line length was checked by hand against the 100-column
setting and nothing else was.

**What this document *is* evidence of, because it was checked by a reader who did not write it.**
An adversarial fact-check of every claim above against the source found **24** discrepancies, and
they are worth characterising rather than just counting: nineteen were prose — six wrong
constructor signatures, three wrong dependency-table rows, a "one enforcement point" that should
have read two, a regenerated baseline that was not regenerated, a rounding claim naming four
directions where the code takes two, and stale counts in five other documents. **Five were real
gaps in the code or the tests**, and they are fixed here rather than dispositioned:
`Levels.trigger_minute` accepted a negative ordinal and reached §6.7's key; `rules_evaluated` was
asserted by *length*, which passes with a rule missing; §7's two drawdown rows were claimed applied
when nothing calls them; the boundary-coverage claim was counted by a reader rather than derived;
and the design documents were outside `test_documentation.py`'s scope entirely, so none of their
counts was mechanically checked. The last of those is the one that matters most, because it is why
the other four could be written at all — and the guard, once added, failed on its first two runs,
the second time on the sentence written to explain the first.
