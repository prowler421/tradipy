# Changelog — PRD

Corrections and reversals to [PRD.md](PRD.md), extracted so the spec itself can state only what is true.

**Why this file exists.** Through v1.2 the PRD narrated its own corrections in place — roughly twenty passages of the form "an earlier draft required ≥ 70%," "the earlier version quoted three different entry prices," "(Removed: … was unreachable)." That was the right instinct during review: it prevented silent reversals and made the error-correction record auditable. But it worked against the document's primary job. An implementer reading §3.2 should not have to work out which rule is current and which is a retracted ancestor, in a section whose entire purpose is to be unambiguous.

**One inline note is retained deliberately.** §3.2 criterion 5 keeps its correction marker, because `≤ 70%` reads as a typo to anyone expecting `≥` and the reversal is genuinely counter-intuitive. Every other correction lives here.

**Reading this file.** Entries are grouped by the release that made the change. Each says what the rule *was*, what it *is*, and why — the "why" being the part that stops the same error recurring.

---

## Unreleased — D34, and the §6/§7 questions implementing it exposed

### Decided

| Decision | Rule | Where |
|---|---|---|
| **D34** | **The construction/calibration split extends to Phase 5, with the transport half *refused* rather than deferred.** `positions.py`, `risk.py` and `orders.py` implement §6.3's pre-trade checks, §7's rule table, §20.12's transitions and §6.1's bracket over supplied state. Everything downstream of §6.2's `OrderDraft` is absent because D30 admits no broker. The ladder does **not** move, and §12.1's Phase 3, 4 and 5 rows stay unticked. Phase 5 is blocked twice — by D30 and by §18.7's unrun viability gate — and the decision states the two separately | [PLAN.md](PLAN.md) D34 |
| **§7's rules get a fourth namespace** | A `Reject` says *this candidate is not tradeable*; a `RiskBlock` says *this account may not take this trade right now*. Mixing them would let the scanner filter a universe on `LOSS_STREAK_LOCKOUT`, which is K5's shape at one more remove — and two §7 rows' Violation Action is *"Flatten all; lock account"*, which is not a rejection of anything. `RiskDecision.reason` is `RiskBlock \| Reject \| None`, which is what §9.2's *"§7 rule name or §4.2 code"* already describes | PRD §7, §9.2; `src/tradipy/rejects.py` |
| **`ExitReason` gains §9.2's other four** | `LADDER_COMPLETE`, `STOPPED_OUT`, `EOD_FLAT` and `KILL_SWITCH`, transcribed from §9.2's `ClosedTrade.exit_reason` rather than invented — the same discipline the first two got from §20.12's state names | PRD §9.2; `src/tradipy/rejects.py` |
| **FINRA's PDT constants are not registry rows** | $25,000, the 4th-day-trade test and the 5-business-day window are law, not tunables, so they are module constants in `risk.py` — the argument `rounding.TICK_SIZE` makes from SEC Rule 612. A `Param` carries a legal range and a regulation does not have one | PRD §7; `src/tradipy/risk.py` |

### The two findings that change a verdict — §7's rules are jointly incoherent with §2's defaults, twice

Both are the **third defect class** (joint incoherence): every parameter is inside its own bounds
and defensible alone, so per-parameter validation passes both clean. Both were reproduced **by
execution** the first time §7's rules ran against §2's own worked examples, and both are **raised,
not resolved.**

**1. §7's total-risk cap makes `max_open_positions` > 1 unreachable at full size.** §7's first row
caps **total** open risk — all positions, from their current live stops, plus pending orders — at
`start_of_day_equity × max_risk_pct`, which is *the same budget* §2.2 sizes a **single** position
to. At the `experienced` preset and §3.2's own example: $30,000 × 1% = $300 of budget, and 2,500
shares × $0.12 = $300 of open risk from one position. §3.3's example adds another $300. Total $600
against a $300 cap — rejected, while `max_open_positions` (3) still reports headroom. The same
holds at `beginner`, where budget and share counts both halve.

§7.1.1 derives exactly this consequence for **scale-ins** — *"adds are only ever legal after T1,
never while the initial position is still at full risk"* — and does not extend it to new
positions, while §2 advertises up to three concurrent positions and hard-ceilings the row at 3. So
`max_open_positions` is close to inert: its value changes nothing until the earlier positions are
past T1, at which point the risk cap permits the add anyway. That is a different claim from the one
§2's *"Sensitivity: more positions = correlation risk"* makes. It also makes the
`approved_shares` question below material rather than cosmetic, because the two readings differ on
what gets written to the audit trail for a case that is not an edge case.

**Candidate resolutions, none taken:** state in §7 that the cap is per-position rather than total,
which contradicts §7.1.1's own derivation and reopens the A16 contradiction it closed; or state in
§2 that `max_open_positions` binds only after T1, making the coupling explicit; or denominate the
total-risk cap separately from the per-trade cap, which is a new parameter and a new decision.

**2. §7's daily-loss row makes §7's PDT row unreachable at §2.0's default equity.** PDT fires only
when equity is below FINRA's $25,000 floor. Reaching that from §2.0's $30,000 default needs a
$5,000 loss — 16.7% of equity — while §7's daily-loss row locks the account at `daily_loss_pct`,
whose registered **ceiling** is 5% ($1,500). So the lockout always fires first and §7's PDT row
cannot be reached at the default at any legal configuration. It is reachable only for an account
starting within `daily_loss_pct` of the floor, which §2.0's own bounds permit
(`start_of_day_equity` has `lo` = $25,000) — so this is not a dead rule, it is a rule whose
reachability depends on a parameter nothing relates to it.

Not enforced as a coupling, per convention 5 and for A25's reason: the incoherent combination *is*
the shipped default, so raising would make `Config.default` throw. `tests/test_phase5.py` pins it
in both directions, so resolving it fails the fixture deliberately.

### Spec questions — open, raised by implementing §6, §7 and §20.12

**Fifteen, plus the two findings above. No threshold moves here and no §6 or §7 rule changes.**
Each reading is localised to one function and pinned by a test;
[PHASE-5-DESIGN.md](PHASE-5-DESIGN.md) §5 carries the readings against the code. The nineteen
Phase 4 raised remain open and untouched.

**The convention, stated because two documents were using different ones:** the count is the number
of **rows in this table**, and the two joint incoherences above are counted separately because they
have their own section. [PLAN.md](PLAN.md)'s Phase 5 row said *"fourteen spec questions, two of them
joint incoherences"*, which is a third convention — total including them — and was wrong under
either reading after this table grew.

**This number has now been wrong twice in one changeset, and the second time is the instructive
one.** The first draft said twelve above a list of fourteen. Round 14's disposition then added the
`§20.12 vs §3, mid-ladder` row for H3 and left the header at fourteen — *in the paragraph that had
just finished explaining the previous instance*. That is the L1 / K6 shape for the sixth time, and
prose calling the shape out is evidently no defence against it. `tests/test_documentation.py` now
derives the row count of every spec-question table in this file and compares it against the
spelled-out number in the heading, which is the check that should have existed before either draft
— its `_REGISTRY_COUNT` regex matched only digits, so `**Fourteen**` was invisible to it.

| Where | The question | The reading taken, and why it is not a settlement |
|-------|--------------|---------------------------------------------------|
| §20.12 | **The diagram and the table disagree, and neither is complete.** The table gives `T1_FILLED → {T2_FILLED, STOPPED_OUT}` and `T2_FILLED → {TRAILING}`; the diagram's `↓` arrows put all three exit states under both. The table has no row at all for `IDLE`, `CLOSED`, `EXPIRED` or the three exit states | **The table where it has a row, the diagram where it has none** — so `IDLE → ARMED` and the three exit states `→ CLOSED` come from the diagram and nothing else does. The table's column is an enumeration and is the stricter; the table alone yields a machine that can neither start nor finish. **Cost, stated:** a §3 post-entry invalidation firing after T1 has no state to move to — `bull_flag_exit` will return `INVALIDATED` and `transition` will refuse it |
| §20.12 vs §7.2 | §7.2's kill switch has enforcement point *"Any"* and action *"market-close all positions"*, and §7's trading-hours row implies the same flattening at the close. Both need an edge to `CLOSED` from every open state; §20.12 provides one only from `TRAILING` | Reported, not patched — `reachable_exit_reasons` returns empty for `EOD_FLAT` and `KILL_SWITCH` from `PENDING_ENTRY`, `OPEN_FULL`, `T1_FILLED` and `T2_FILLED`, and a test asserts the emptiness so a later correction to §20.12 fails it |
| §20.12 vs §3, mid-ladder | **The same gap read across two phases** (round 14's H3). §3's post-entry rules — `setups.bull_flag_exit` and its siblings — return `ExitReason.INVALIDATED` on any bar after entry without consulting a state, and §20.12's table permits `T1_FILLED → STOPPED_OUT` only. So Phase 4's predicates and Phase 5's state machine share §20.12's vocabulary by construction and **still do not compose for a mid-ladder exit** | Not resolved, and re-characterised rather than re-dispositioned: this was recorded as a cost of the §20.12 reading and is better read as a boundary between two phases. Widening the table is a spec change; PHASE-5-DESIGN §6 finding 3 is the record |
| §9.2 vs §7 | `RiskDecision.approved_shares` — *"may be < TradeSignal.shares after caps"* — against §7's *"Reject order"* on every size-related breach | **Reject, never trim.** §7's rows are NON-BYPASSABLE and its Violation Action column is unambiguous; trimming would have the risk engine invent a share count no §2.2 constraint produced. `approved_shares` is the request on approval and `0` on a block |
| §7 PDT row | *"equity < $25,000"* — §7.1 defines `start_of_day_equity` and `live_equity` and assigns PDT to neither | `live_equity`. FINRA tests current account equity, and the frozen figure would let a morning loss below $25,000 pass a check whose only purpose is to prevent an illegal trade — the one direction in which being wrong is a regulatory violation rather than a missed trade |
| §6.3 vs §7 | §6.3 lists **eight** pre-trade checks; §7's enforcement column marks **eleven** rows Pre-order or stricter, including Max correlated exposure, which §6.3 omits entirely | §7's enforcement column governs and §6.3's list is treated as illustrative. A check §7 requires and §6.3 forgot is an omission, not an exemption — the reverse reading silently drops a row §7 marks bypassable-only-by-bounds |
| §3.1.1 | The 50 / 25 / 25 ladder over an **integer** share count, which §2.2 floors, so indivisible is the normal case. §3.1.1 states no rule | `floor` T1 and T2, remainder to T3, with the three summing **exactly** to the count. §21.6 makes a share with no protective leg a Sev-1, and flooring the two profit legs is the only rounding that cannot leave one uncovered. **Consequence:** a 1-share position has T1 = T2 = 0 and exits entirely on the trail; 2 shares put nothing on T2 |
| §20.13 | No row for an **entry limit price**, which is the price §6.1 actually submits. The table covers stops, targets, gate minima and gate maxima | Buy limit `ceil_to_tick`; sell stop and sell stop-limit `floor_to_tick`; target legs `ceil_to_tick`. Taken from §20.13's *governing principle* — *"no rounding decision … can make a trade look better than it is"* — rather than its table: ceiling a buy and flooring a sell are the two directions that cost money. Only the entry limit is code-originated; the other three are §20.13's own rows |
| §9.2 vs §20.12 | §9.2's `ClosedTrade.exit_reason` has **six** values; §20.12 has state names matching **three**. `LADDER_COMPLETE`, `EOD_FLAT` and `KILL_SWITCH` are not states, and §20.12's `EXPIRED` is a state with no exit reason | Both vocabularies carried, and the mapping between them made explicit rather than assumed to be the identity. `EXPIRED` having no exit reason is *consistent* — a position that expired never opened, so it produces no `ClosedTrade` — but it is stated rather than inferred |
| §7 row 2 | `daily_loss_pct` has **three** stated enforcement points: *Continuous (1 sec)*, *post-fill*, and §6.3's pre-order list. One of the three needs a feed | The pre-order one is implemented; the predicate exists for the other two and no loop calls it. **G2 narrows, it does not close.** Claiming otherwise would be the F8 shape — an unqualified claim about a check whose scope is smaller than the sentence |
| §6.5 vs §12.1 | §6.5's slippage model is in **§6**, which is Phase 5's section, while its only consumer is §8.2's fill model, which is Phase 4b's — and D22's stress requirement is a Phase 4b deliverable | Not implemented, and `impact_coefficient` stays **unregistered** despite §6.5 being the one §6 table with a Bounds column. Either §6.5 belongs in §8, or Phase 5 owns a formula with no caller — which is the fifth defect class. The boundary disagreement is the question |
| §21.5 / §7.2 | The kill switch's trigger is a file sentinel at `$XDG_STATE_HOME/tradipy/kill`, and no module in this package opens a file (D30) | The trigger arrives as `RiskState.trading_halted` / `halt_reason`, which is §10's own `daily_state` schema. So §21.5's path has a reader **nowhere**, which is a registered-but-unenforced shape outside the registry's reach |
| §7 row 4 | The loss-streak action is *"Lock new entries; **allow exits**"*, and §6.3's eight checks are written as *"before every order submission"* — which would block a protective exit | `approve()` takes the order's intent explicitly rather than inferring it from a side. Inferring is wrong in both directions: a short entry is a `SELL` and a long exit is a `SELL`. §6.3 states no such distinction, so the intent parameter is this layer's and is raised here |
| §6.7 / §21.1 | §6.7's key is `sha256(symbol\|setup_type\|**trigger_bar_timestamp**\|account_id)`, and §21.1 forbids `datetime.now()` in strategy code — which is why a `SessionBar` carries an `int` minute | `session_date` (an ISO `str` the caller supplies) plus `trigger_minute` (§20.1's ordinal). Keeps §6.7's derivation *here* — same setup, same bar, same key on a retry — while the only imported fact is which session it is, and a `str` cannot be read from a clock |
| §6.4 | *"within 30 sec"*, and *"cancel remainder only if spread widens > 2× entry spread"* — §6.4 states no ordering between the two conditions | `seconds_since_submit` supplied and the threshold applied here, the same shape `Quote.age_seconds` uses for §20.14. The spread condition is evaluated **before** the timeout, which is the stricter reading: §6.4 attaches no time bound to it, so a fill past 50% that then sees the spread double is cut immediately |

---

## Unreleased — D33, and the §3 questions implementing it exposed

### Decided

| Decision | Rule | Where |
|---|---|---|
| **D33** | **D32's construction/calibration split extends to Phase 4 (the §3 strategy engine).** `session.py` and `setups.py` implement §3.2, §3.3 and §3.4 on simulated bar series; no threshold in them is calibrated. The ladder does **not** move — `PERMITTED_ORIGINS` stays `{SIMULATED}` — and §12.1's Phase 3 and Phase 4 rows stay unticked. The cost that does *not* carry over from D32 is stated in the decision itself | [PLAN.md](PLAN.md) D33 |
| **Exit reasons are a third namespace** | A rejection declines a trade never taken; an exit closes one that was. `ExitReason` is separate from `Reject` and `SoftFlag`, and its two members (`BAILED_OUT`, `INVALIDATED`) are **transcribed from §20.12's state names** rather than invented. This is the K5 argument applied one step further out | PRD §20.12; `src/tradipy/rejects.py` |
| **§21.1's worked-example row is met from the side it names** | *"Each §3 worked example encoded as a test: **input bar series** → asserted entry, stop, R, targets, share count."* All three now start from bars (`tests/test_setups.py`, `python -m tradipy setups`). The older scalar-driven fixtures are kept: they are a different check and are what the demo's self-check exercises | PRD §21.1 |

### The finding that changes a verdict — §3.4's worked example fails §3.1.1's room gate

**This is a PRD-internal contradiction with a behaviour consequence, and it is raised rather than
resolved.** §3.1.1 defines the room gate's input as *"the **nearest** overhead level above entry
among {HOD, next whole dollar, prior leg high, measured-move projection}"*. §3.4's worked example
names the HOD (**$4.15**) as *"nearest overhead resistance"* and computes a passing room test from
it — while the next whole dollar (**$4.00**) is in §3.1.1's own set, is nearer, and is only $0.17
above the $3.83 entry against a required room of **$0.28**.

Applying §3.1.1 as enumerated, the example is **rejected** with `TARGETS_TOO_CLOSE`. Every other
line of its table reproduces exactly from the bar series — VWAP $3.80, dip depth 1.58%, the
`$3.762 → $3.76 → $3.75 → $3.73` stop chain, R $0.10, T1 $4.03, T2 $4.15, T2−T1 $0.12. Only the
resistance differs.

Three things make this worth more than a table correction:

1. **§3.2's example applies the whole-dollar candidate and §3.3's uses it as *the* resistance.**
   Only §3.4 omits it. That asymmetry is evidence of an oversight rather than a per-setup override.
2. **§3.4's sensitivity table is undermined too.** Its three rows (HOD $4.05 / $4.09 / $4.15)
   conclude that only the cost-denominated floor rejects the collapsed ladder. Under §3.1.1's set
   all three reject on the $4.00 level, which is a different reason and a different lesson.
3. **The consequence is material, not cosmetic.** On a $1–$20 universe, requiring `required_room`
   of clear space below the next whole dollar rejects a large share of VWAP Reclaim setups — the
   direction §3.1.3's own note says to accept rather than widen the gate, but a rejection rate
   nobody has measured. It is exactly the kind of joint incoherence the v1.3 defect class names:
   §3.1.1 and §3.4 are each defensible alone.

**Candidate resolutions, none taken:** amend §3.4's example and its sensitivity table to §3.1.1's
set; or state in §3.1.1 that the whole-dollar candidate applies only where a setup's structural
target is not itself a level (which would need justifying, since whole dollars are resistance
precisely on cheap stocks); or scope the candidate set per setup, which §3.4's *"HOD (or nearest
resistance)"* phrasing hints at and no section states. `tests/test_setups.py` pins the current
behaviour in both directions, and `python -m tradipy setups` prints the disagreement.

### Spec questions — open, raised by implementing §3.2, §3.3 and §3.4

**No threshold moves here and no §3 rule changes.** §20 defines flagpole geometry (§20.4) and
stops: *flag*, *consolidation candle*, *dip*, *leg* and *leg height* have no normative definition
anywhere in the PRD, so a reading had to be taken for each to make §3 executable. Every reading is
localised to one function and pinned by a test; [PHASE-4-DESIGN.md](PHASE-4-DESIGN.md) §5 carries
the same list against the code.

| Where | The question | The reading taken, and why it is not a settlement |
|-------|--------------|---------------------------------------------------|
| §2 vs §3.1.1, T3 | §2's Profit Target row says *"Target 3: HOD retest + extension"*; §3.1.1, §3.5, §15 and §20.12 all say *trail 9 EMA*. §3.4 separately uses HOD retest as **T2** | Neither is implemented — T3 is Phase 5/6 per **D18** — so nothing depends on the answer yet, which is the only reason this is recorded rather than blocking. One of the two sections is wrong about what T3 *is* |
| §3.2 / §3.3 / §3.4, bailout | Breakout-or-bailout is three rules. §3.2 requires a **conjunction** (no close above entry *and* no new high above the breakout candle); §3.3 states only the second condition; §3.4 states **none** — while §11.1 and A12 both describe it as one canonical rule | Implemented **per setup, as each states it**, and `test_vwap_reclaim_has_no_bailout_timer` asserts §3.4's silence rather than filling it in. Unifying them would be inventing a rule for whichever setups do not state it |
| §20.1 vs §3.2 / §3.4, counts | §20.1: *"pattern counts count **available bars**, not wall-clock minutes."* §3.2 writes *"3 candles (3 min)"*, equating them; §3.4 crit 2 says *"≥ 15 **minutes**"*; §3.2's halt edge case says *"within 2 min"* | Bars, because §20 governs. The parameter is named `min_bars_above_vwap` rather than `..._minutes` so the divergence from §3.4's wording is visible in the registry |
| §3.2 crit 3 | *"2–5 red/consolidation candles"* — a consolidation candle may close up, but §20.4 terminates the flagpole at *"the longest run of consecutive green candles ending immediately before the flag"* | The flag is the maximal run of **not-green** bars (`close ≤ open`). The alternative is circular: §20.4 needs the flag's start to find the flagpole, and a flag admitting green bars needs the flagpole to find its own start |
| §3.2 crit 2 | *"combined move ≥ 2%"* states no denominator, and *"total volume ≥ 2× average 1-min volume of prior 30 bars"* compares a **sum** against a **per-bar mean**, which any 3-bar pole at ordinary volume satisfies — the criterion would be inert | Move as `flagpole_height / flagpole_low`, which reproduces the example's **+7.29%** exactly where the alternatives do not. Volume as the **per-bar** comparison, the stricter reading and the same shape as crit 7. A13 shows §3.2's volume rows have needed one reversal already |
| §3.3 crit 3 | *"≥ 2 candles where high ≤ prior HOD and low ≥ VWAP"* is circular: the run's extent depends on *prior HOD* and *prior HOD* depends on where the run starts | Per bar: a consolidation bar set no new high (`high ≤ hod_through(i−1)`) and held above VWAP (`low ≥ vwap_at(i)`). The circle closes and gives the same *prior HOD* either way, because no bar in the run made a new high |
| §3.1.1 / §20.3, resistance | *"Prior leg high"* is undefined; §20.3 adds `PMH` from outside §3.1.1's enumeration; and §20.3's *"updated on every completed bar"* would put the trigger bar's **own high** in the set | `PMH` is in (§20 governs). *Prior leg high* is **omitted** — an undefined term cannot go into a gate §7 marks non-bypassable. HOD means the HOD **before** the trigger bar: the literal reading gives every breakout that closes below its high a resistance level a few ticks above entry, which would reject every §3.2 and §3.3 setup unconditionally |
| §3.3 T2 | *"Next whole dollar above T1, or prior leg extension (1× **leg height**), whichever is nearer and above T1"* — *leg height* is undefined | Whole-dollar branch only, which §3.3's own example uses. Stated because the omission can only put T2 **further** away, and a reader needs to know the direction |
| §3.4 crit 3 | *"≤ 5 consecutive candles below VWAP"* — close or wick? And depth *"≤ 2% below VWAP"* against **which** VWAP | Close-based, because the trigger is (*"closes above VWAP"*) and a reclaim defined by closes needs a dip defined by closes. Depth against VWAP as of the bar that set the dip low. The example has one VWAP value and cannot distinguish them |
| §3.4 stop vs crit 3 | Crit 3 admits a dip **2%** below VWAP; the stop is `max(dip_low, VWAP × 0.99)` — **1%** below. Whenever the dip is deeper than 1% the `max()` selects the VWAP band and puts the stop *inside the pattern*, which §2 and §3.2 both forbid in terms | Implemented as §3.4 states it. The example does exactly this ($3.74 low, $3.75 raw stop) and is rescued only by the $0.10 floor widening it to $3.73. The two numbers are also uncoupled in code: `vwap_stop_band_pct` is registered, the 2% dip depth is now registered separately, and nothing relates them |
| §20.1 gap rule | *"A gap > 2 minutes invalidates any in-progress pattern"* — missing minutes, or elapsed span? | **Missing** minutes, the literal reading. Recorded because this is the one §4.2-style ambiguity where the **stricter** reading was not taken: the span reading rejects one more minute of absence. One comparison, in `Session.pattern_intact` |
| §14.2 conviction gate | §14.2 recommends *"composite score ≥ 0.7"*, §20.10 calls the score *"directly comparable to the ≥ 0.7 conviction gate"*, `score.meets_conviction_gate` and `min_conviction_score` exist — and **no §3 criterion references it** | **Not applied.** A gate no setup criterion names would be this layer inventing a rejection. So a watchlist survivor below 0.7 can still produce a signal, which may be wrong and is at least visible |
| §14.3 vs §3.2 | §14.3 justifies its candle-quality choice as *"already used by the §3.2 breakout test"* — a body ≥ 60% of candle range. **§3.2 states no such criterion**: crit 6 is a close above the flag high and crit 7 is volume | Not implemented, because §3.2 does not state it. Either §3.2 is missing a criterion or §14.3's justification is void; both are spec calls |
| §2 vs §3, VWAP extension | §2 states a **global** rule — *"no entry if price > 3% above VWAP, or > 5% above in the first 30 min"* — and only §3.3 carries an extension test, only the 3% branch. `max_vwap_extension_open_pct` is registered and read by nothing, and *"first 30 min"* is undefined in §20 | Applied where §3.3 states it and nowhere else. Extending it to §3.2 and §3.4 would change which setups fire, which is a behaviour change and therefore a decision |
| §3.2 edge case vs §8.2 | Halt proximity is *"within **2 min** of anticipated halt/resumption"* in §3.2 and *"no entries **5 min** before known halts"* in §8.2 — and *"anticipated"* is undefined | Neither implemented: both need a halt calendar, which is Phase 2 ingestion. Recorded so the conflict is not discovered by whoever builds it |
| §3.2 edge case vs §20.11 | *"After Target 1, treat subsequent consolidation as a new flag if above VWAP"* against §20.11 rule 4, which supersedes further signals while a position is open *"except an explicit scale-in add permitted under §7.1.1"* | Neither implemented (both need position state). Is the second flag a §7.1.1 scale-in, which requires the stop already at breakeven, or a new signal §20.11 supersedes? |
| §3.3, A14 | A14 prescribes `effective_stop = max(consolidation_low − 1 tick, VWAP − 1 tick)` to reconcile a stop above VWAP with an invalidation below it — but crit 3 already requires `consolidation_low ≥ VWAP`, so that `max()` is **inert in the case A14 describes**. It binds only when the *breakout candle's* low is the lower of §3.3's two stop candidates and sits below VWAP, which A14 does not mention | Applied as A14 states it, and `test_the_hod_stop_rounds_away_from_the_position_when_a14_binds` exercises the case A14 omits. The nominal-vs-realised R mismatch A14 identifies therefore persists in the case it was written for |
| §8.2, opening auction | The row states both *"premarket signals fill at the **09:30 open** + slippage"* and, two clauses later, *"no entry may be simulated **inside the 09:30 bar** — the earliest continuous-session entry is the **09:31 bar**"* | Phase 4 refuses the session's opening bar, which follows §20.2's *"no VWAP-dependent setup can fire before 09:31"* and is the second reading. §8.2's first clause is not implemented because fills are Phase 4b's; whoever builds them meets the contradiction |
| §3.2 crit 4, §3.3 crit 3, §3.4 crit 3 | The pre-entry VWAP tests are wick-based as written (*"flag **low** remains above"*, *"**low** ≥ VWAP"*) while every post-entry VWAP rule is close-based (*"**close** below VWAP"*). §20.3 settles wick-vs-close for HOD only; §20.2 settles it for nothing | Taken as written — wicks before entry, closes after. Consistent with §20.3's split between HOD tracking and the HOD *trigger*, but nothing states it for VWAP |

---

## Unreleased — D32, and the §4.2 questions implementing it exposed

### Decided

| Decision | Rule | Where |
|---|---|---|
| **D32** | **PLAN D29 gates Phase 3's *calibration*, not its *construction*.** The §4.2 scanner is implemented on simulated data; no threshold in it is calibrated, and the Q1 row in [PHASE-3-READINESS.md](PHASE-3-READINESS.md) stays **Not met**. The data ladder does **not** move — `PERMITTED_ORIGINS` stays `{SIMULATED}` | [PLAN.md](PLAN.md) D32 |
| **§12.2 vs the readiness note** | §12.2 item 1 says *"Scanner produces **ranked** watchlist using all hard filters"* and §4.1/§4.3 make ranking a function of the §20.10 composite score; `PHASE-3-READINESS.md` said the MVP scanner needs *"only hard filters… not full soft-filter scoring."* **Resolved toward the PRD, which is normative.** The scanner ranks. Two §4.2 soft rows (`PREMARKET_THIN`, `NO_CATALYST`) are §20.10 inputs, so the soft half could not be omitted even to satisfy the narrower reading | PRD §4.1, §4.3, §12.2 |
| **Rejection codes are not one namespace** | §4.2's fourteen rows share a "Rejection Code" column, but only seven are Hard. The seven Soft codes move to a separate `SoftFlag` type; **no soft row can reject anything**. This implements round 10's **K5** rather than merely noting it | PRD §4.2; `src/tradipy/rejects.py` |

There is **no D31**. Four documents written earlier forward-reference that number as the
ladder advance to `PAPER`, so it is left reserved; see the note under the PLAN decision log.

### Spec questions — open, raised by implementing §4.2

**No threshold moves here.** Each is a place where §4.2 admits more than one reading, the
scanner had to take one to be executable, and the choice is recorded with a test pinning it so
that settling it later is a visible decision rather than an accident.

| Where | The question | The reading taken, and why it is not a settlement |
|-------|--------------|---------------------------------------------------|
| §4.2 Circuit Breakers | *"Not within 10% of LULD band"* — 10% **of** what, and **which** band? The row states neither. It could be 10% of price, or 10% of the band's own width; and "band" could mean the limit-up level a gapping long actually runs into, or both levels | 10% **of price**, measured against **both** bands. Proportional because every other §4.2 percentage is a percentage of price; both bands because the stricter of two readings cannot admit a candidate the spec meant to exclude. The required distance is a minimum over a price, so it rounds **up**. All of it lives in one function (`scanner._check_circuit_breakers`) and one registered threshold (`min_luld_distance_pct`), so settling it the other way is a localized edit |
| §4.2 Gap % vs §20.10 | Is §4.2's daily Gap % the same quantity as §20.10's `pct_change`? §4.2 says "Gap %" as a fraction; §20.10 says *"50% daily change = full marks"* in percent units. **Nothing states they are the same move** | Taken as the same, and converted (`PERCENT_PER_UNIT`). The alternative is two inputs for one move, free to disagree, with the units trap `score.py` already warns silently divides the score's largest component by 100. Pinned by `test_daily_gap_is_what_feeds_the_score` |
| §4.2 Liquidity / Spread | The row states **two** conditions — spread within the cap **and** bid size ≥ 100 — under the single code `SPREAD_TOO_WIDE`, which names only the first | Both applied, both reported under that code, with the failing condition named in the result detail. §4.2's rationale is "execution quality", which covers a bid nobody will fill in size. A second code would be a rejection reason the spec has not agreed to |
| §4.3 ranking | §4.3 says *"Return top 5 by §20.10 score"* and states **no tiebreak**. Ties are reachable, not hypothetical: `float_inverse` saturates at 0 for any float at or above the cap and `norm_rvol` at 1 above 20× | Symbol ascending. Without one the watchlist depends on the order the universe arrived in — the same market producing different answers. Pinned by a test that scans a tied universe forwards and backwards |
| §4.2 Volatility / Relative Volume, §2 ADV | Three rows name a window or a period — ATR(14) against a 30-session average, RVOL against a 30-day ADV, and §2's "(30-day)" on Average Daily Volume — that the scanner does not compute | Treated as **input contract** for Phase 2 ingestion, not as thresholds this layer applies. Only the multiple between them (`min_atr_multiple`) is registered. Registering an `atr_period` or an `adv_lookback_days` would put a row in the registry that nothing reads, which is the fifth defect class in miniature — and PLAN already tracks nine such rows |
| §4.2 Recent Halts | *"Halt in last **5 days**"* — trading sessions or calendar days? Across a weekend or a holiday they differ, and the row is a flag on elevated risk, which is a property of sessions traded rather than of the calendar | Read as **sessions**: the field is `sessions_since_halt` and the registry unit is `"sessions"`. Structurally identical to the ATR/RVOL window question above and recorded for the same reason. Nothing depends on the choice today, because the scanner receives the count rather than computing it — which is exactly why it could be got wrong upstream without anything here noticing |
| §4.2 Liquidity / Spread vs §3.1.3 | §4.2 writes the cap as an **equality**: *"Spread ≤ `min(max_spread_abs, max_spread_pct × price)` = min($0.02, 0.5%)"*. §3.1.3's formula, which the row cross-references and which the code calls, is `max(tick, floor_to_tick(min(...)))`. **The one-tick clamp widens the cap below $2.00**: at `min_price` = $1.00 the effective cap is $0.01, which is **1.00% of price** | §3.1.3 governs and the clamp is load-bearing (§20.13, A25 — an unclamped maximum flooring to $0.00 rejects every value). But §4.2's own rationale column says the row exists because *"the former '≤ 1% of price' admitted spreads costing up to 83% of R round-trip"*, and the shipped configuration admits exactly 1% of price at the bottom of the §2 range. **This is a PRD-internal tension, not a code defect**, and it lands in the same $1.00–$1.99 band that `min_tradeable_price_from_stop_bounds` already documents as empty on the stop arithmetic — which may be the resolution, or may be a coincidence worth separating. Not enforced either way |
| §2 vs §4.2, premarket gap | §2's Minimum Gap % row states a **second disjunct** — *"AND/OR ≥ 2× prior day premarket volume"* — that §4.2's Gap % row does not carry and the scanner does not implement | Not implemented, and now recorded here rather than only in [REVIEW-2026-07-28](reviews/REVIEW-2026-07-28.md), which listed it as "missing from code entirely". Implementing it needs an input (`prior_day_premarket_volume`) that §4.2 does not ask for, so the question is first whether §4.2 or §2 is the scanner's contract. §4.2 is the section §12.1 points Phase 3 at, which is why it won by default rather than by decision |
| §4.1 pipeline order | The diagram is sequential — *"Hard Filters (reject immediately) → Soft Filters (score/rank)"* — which reads as soft evaluation happening only on hard-filter survivors. The scanner evaluates all fourteen rows unconditionally, so a **rejected** candidate can carry flags | Evaluated unconditionally, for the same reason all seven hard filters are evaluated rather than stopping at the first failure: a rejection you can see one dimension of is not readable, and recalibrating against measured data has to read them. Costs nothing correctness-wise — a flag is a different type from a rejection and cannot enter `ScanResult.rejects`, which `test_enforcement.py` performs. What §4.1 unambiguously orders is the *scoring*, and scoring **is** withheld from rejects. `python -m tradipy scan` shows one such line on purpose |
| §2 price range | `min_price` and `max_price` are independent registry rows and `validate_couplings` does not check `min_price <= max_price`. `with_overrides(min_price="10.00", max_price="5.00")` constructs cleanly and yields a Price Range filter that rejects **every** candidate | **Surfaced, not enforced**, per convention 5 — adding a coupling the spec does not state is a spec decision, not a module decision. Note this is *unlike* `min_tradeable_price_from_stop_bounds`, where enforcement is impossible because the shipped defaults are themselves incoherent; here the defaults are fine and enforcing would cost one line. That makes it the easier of the two to close, and it is left open deliberately so that closing it is a recorded decision rather than a drive-by |

---

## Unreleased — spec questions from review round 10

From [claude-PHASE-3-REVIEW.md](reviews/claude-PHASE-3-REVIEW.md), the Phase 3 readiness round over
`e85a193`. **No threshold moves and no PRD rule changes here.** Three questions are recorded
unresolved, because [CLAUDE.md](../CLAUDE.md) requires a divergence between code and documented
intent to be raised rather than settled in code, and because a finding that lives only in a dated
review file is one refactor from being lost.

| Where | The question | Why it is a spec question, not a fix |
|-------|--------------|-------------------------------------|
| `scripts/spike2a/feeds.py` (**K2**) | `quote_at_or_before` derives `age_seconds` from `signal_at − captured_at` **unconditionally**, while its docstring says it does so only "when `age_seconds` is not supplied in the CSV" — and `CsvQuoteFeed` both documents and parses that column. Which age governs §20.14 on the Q4 path? | Either answer changes what a measured run computes, so neither is a docstring correction. For a historical replay the derived age is arguably right and the column vestigial; for a feed reporting its own NBBO age the supplied value is the physical one, and discarding it weakens the staleness test in the only direction that matters — which is the polarity principle `rounding.py` exists to enforce for thresholds. Reproduced: a supplied `age_seconds=999` gates `QUOTE_STALE` standalone and `PASS` after `quote_at_or_before`. Whichever is chosen needs the convention-6 test asserting which one wins |
| `docs/PHASE-2A-REPORT.md` / PLAN's defect-classes section (**K4**) | The report's one substantive Q1 finding — IBKR's "~100 market-data line cap" — is a cell from `data/spike2a/vendors.csv`, which is generated, declared `SIMULATED`, and whose numbers the generator's docstring says were chosen to exercise the pipeline's pass and fail branches. Is provenance leaking on the *prose* path a **seventh defect class**, or a second population of the sixth? | D30's stated mitigation is that any value capable of triggering a disposition must be reproducible from a provenance-marked input. This value **is** — which is exactly why nothing fired. `answers_prereg`, `banner()` and the withheld verdicts all constrain what a module prints; none constrains a human quoting a module's input with the marker left behind. That is mechanically distinct from all six recorded classes, but calling it a new class is a change to the most-cited section in the repository and is not the reviewer's call. Independent of the classification: the IBKR figure needs a vendor citation or an explicit "unsourced estimate" marker |
| PHASE-2A-SPIKE §7 (**K7**) | H7 — *"does a synthetic run count as a §7 data pull?"* — was raised by round 7, which declined to answer it because *"§7's amendment rule is the one thing in the spike that cannot be amended by the person it constrains,"* and was then decided "no" by that same party. Does that decision need a numbered PLAN decision with rejected alternatives, or a note recording that it was self-certified and by whom? | The answer is not in doubt and this round agrees with it: the alternative freezes §7 against a random number generator. What is in doubt is the route. Four documents now rely on the disposition, and `docs/PHASE-3-READINESS.md`'s review checklist asks the reviewer to accept it after the fact — which is ratification, not review. Every other behaviour-relevant call in this repository carries a D-number and its rejected alternatives; this one carries neither |

**K4's independent half is done; the classification question is not.** K4's own write-up separated
two things: whether provenance leaking on the prose path is a new defect class (a spec question,
left open above — the defect-classes section in `docs/PLAN.md` is untouched), and, independent of
that call, whether the IBKR figure should carry a citation or an "unsourced estimate" marker.
`docs/PHASE-2A-REPORT.md`'s Q1 section now states plainly that the ~100-line figure is unsourced
and names `data/spike2a/vendors.csv` as the only place it appears in this repository. **K3 is also
fixed** (not a spec question — a behaviour change to `q1_vendors.report()` plus a guarantee test;
see the root `CHANGELOG.md`): the empty-vendor-trial case no longer prints a §7 verdict or a PRD §4
rewrite implication.

---

## Unreleased — D30, the simulated-data policy

Not from a review round. Asked as a policy question — *"all project data simulated until
production-ready, then paper, then a real account"* — and answered as a decision, because it
changes what the project is permitted to do rather than what any rule computes. **No threshold
moves and no PRD rule changes.** PHASE-2A-SPIKE §7 is untouched: D30 removes its subject, not its
numbers, and H7 below is why nobody may amend it to fit.

### Decided

| ID | Decision |
|----|----------|
| **D30** | **Simulated data only**, on a `SIMULATED` → `PAPER` → `LIVE` ladder whose current rung is the first. No broker SDK, vendor client or network module may be imported in `src/`, `scripts/` or `tests/`; every dataset declares its origin in a `PROVENANCE.txt` naming each file it covers with that file's digest; undeclared data is refused rather than assumed simulated. The two IBKR collectors and `feeds.IbkrHistoricalTicksFeed` are removed. **Cost, larger than D29's:** §7 binds to measured data, so Q1–Q4 are unanswerable, Phase 3 stays gated through D29, and the risk row demanding *"real quotes, not estimates"* moves from mitigated to accepted. Full rationale and three rejected alternatives in [PLAN](PLAN.md) |

### What this does to the open questions above

**H7 is not answered, and D30 makes answering it less urgent rather than more.** The question is
whether a synthetic run counts as a data pull for §7's amendment clause. D30 does not decide it —
deliberately, since the round that raised it declined on the grounds that *"§7's amendment rule is
the one thing in the spike that cannot be amended by the person it constrains,"* and that reasoning
survives a policy change made by the same party. What D30 does is make the question harmless in
practice: `q4_spreads` can no longer print a §7 verdict over synthetic input at all, so no
synthetic run can produce the artifact that would make the clause bite. The question stays open;
the hazard it described is closed by other means.

**H2 is partly answered and should be re-read.** It asks whether §8's coverage exemption for
`scripts/spike2a/` should be narrowed, since the first defect found there changed a §7 verdict.
`provenance.py` is now spike-directory code that **is** tested, by `tests/test_enforcement.py`, and
the measurement modules cannot run without it. That is a narrowing in fact without a decision to
narrow §8, which is the shape the reviewer warned about. Whether §8 should now say so is still not
the implementer's call.

**H5 was resolved on `main` while D30 was in flight, and the two met in a merge conflict over
the same PLAN cell.** `scripts/spike2a/sample.py` now joins the window rule to the selection
rule. D30 does not change that disposition — where the join belongs is a spec-boundary question
and does not depend on where the data comes from — but it does change the module: `sample.py`
arrived reading `vix.csv` and `preopen.csv` with no provenance check, because it was written
against a tree where the gate did not exist. It is gated now, and
`test_every_spike_entry_point_gates_its_input` covers it.

**That is the shape to expect from D30 from here on.** The gate is a repository-wide invariant
added late, so every branch already in flight predates it, and the failure will always look like
this: correct code, written against a correct earlier tree, arriving without a call it had no
reason to make. The parametrized test is deliberately the enumerated kind — a new entry point
omitted from it is a hole, so adding a module to `scripts/spike2a/` means adding a row.

### The convention, and its weak point

`CLAUDE.md` gains convention 9: **all data is simulated, and nothing may reach a market.** It
appears across the documentation set and in the code, which is F8's defect class waiting to
happen. **Neither the copies nor their number is enumerated here** — F8's own disposition went
stale by being an enumeration, and the first draft of this paragraph repeated that mistake
inside the sentence warning against it, stating a count two lines after explaining why it would
not.

What is asserted instead is a property, checkable by grep at any time: **every copy that states
the lint's scope names `src/`, `scripts/` and `tests/`, and every copy that states its strength
says denylist.** Some copies state neither, because they describe the policy rather than the
mechanism, and that is fine — a copy that says less cannot drift. The difference from F8 is that
the scope is now asserted by a test (`LINTED_TREES`) as well as by prose, so a copy that drifts
disagrees with something executable.

The weak point is worth naming, as convention 8 names its own. **The import lint is a denylist**,
and a denylist is a guess about what someone will reach for next. It covers broker SDKs, the
vendors PRD §5.1 names, and the network stack — but a new vendor's client, or `subprocess` calling
`curl`, passes it. The provenance gate is the real backstop, because it constrains what may be
*read* rather than what may be *imported*; the lint is there to make the breach loud rather than
silent. Do not read a green lint as proof that nothing can reach a market.

---

## Unreleased — raised by REVIEW-2026-07-30, not yet dispositioned

Driven by [REVIEW-2026-07-30.md](reviews/REVIEW-2026-07-30.md), the third round to review code and the first to review the Phase 2a instrumentation. **No rule in the PRD changes here, and no threshold moves.** Every *code* finding is in `scripts/spike2a/` — four of the fifteen are documentation defects elsewhere — and `src/tradipy/` is behaviourally identical to v0.1.0 (`git diff 114ef86 HEAD -- src/` is two formatting reflows and one docstring). The round's own gate finding — `make check` red at `3545adf` while four documents said the guardrail was enforced — is a code defect and is recorded in the root [CHANGELOG.md](../CHANGELOG.md), not here. What is below is the part that is not the reviewer's to settle.

### Spec questions — open

| Where | The question | Why it is a spec question, not a fix |
|-------|--------------|-------------------------------------|
| PHASE-2A-SPIKE §7 (**H7**) | §7 binds every threshold "before any data was pulled" and permits amendment "only in a commit that predates the next data pull." **Synthetic data now exists and a §7 verdict has been printed over it — twice, with different answers.** Does a synthetic run count as a data pull for that clause? | **Decided — see Decided table above (H7).** Remains listed here as the record of what was asked |
| §21.1 / PHASE-2A-SPIKE §8 (**H2**) | §8 grants `scripts/spike2a/` **no test-coverage obligation**, and the first defect found there was a timestamp expression emitting `09:60`–`09:89` that silently discarded half a quote file. Should the exemption be narrowed — e.g. to "no coverage obligation, but any file the measurement reads must have a parse-rate assertion"? | The exemption is load-bearing and correct in its intent: coverage obligations are how throwaway code becomes permanent. But it was granted on the assumption that spike defects are cheap, and this one changed a §7 verdict. Narrowing it is a change to what §8 protects against; keeping it means the measurement that gates Phase 3 is the least-tested code in the repository, deliberately. Not the reviewer's call |

### Decided

| ID | Decision |
|----|----------|
| **H7** | **A provenance-marked synthetic run is not a §7 data pull.** §7's amendment clause binds thresholds chosen before measured data is pulled; a run whose `PROVENANCE.txt` declares `origin SIMULATED` is excluded by the same rule that excludes it from answering Q1–Q4. Operational enforcement: `Provenance.answers_prereg` is false for `SIMULATED`, and `q4_spreads` prints *pipeline outcome (NOT a §7 verdict)*. The clause remains checkable: the first measured pull is the first run with `origin PAPER` (or higher) after D31 |
| **H4 / H6** | **`signal_bars.csv` gains a required `signal_at` column** (ISO 8601 UTC). `scripts/spike2a/feeds.quote_at_or_before` selects the last NBBO at or before that instant and derives `age_seconds` for §20.14. Fixes Q4 attributing one session-end quote to every setup on a symbol-session (H4) and makes staleness reachable without a fake zero default (H6). Disposition: code fix + `tests/test_spike2a_q4_quote_selection.py`; no PRD rule change |
| **H5** | **`scripts/spike2a/sample.py`** joins the two halves — it restricts a pre-open file to the sessions in `windows.select_windows`'s two windows, then calls `universe.select_sample` unmodified on what remains, reporting "outside windows" as its own count rather than folding it into `Sample.rejected` or `Sample.excluded`. Of the round's three named options, this is "a new composing module," which the round itself flagged as risking being "the first step of the accretion §8 forbids". Taken anyway because §8's accretion warning is about spike code acquiring *scanning capability* it would carry into the production scanner: this module adds no filter, no threshold and no capability that `windows.py` or `universe.py` did not already have — it names and enforces an ordering between two calls a caller previously had to get right by convention. `universe.select_sample`'s signature is unchanged (round 7's first-named cost), and the join is in the repository rather than in a script that assumes it (the second-named cost). Rejected: putting the join inside `select_sample`, which would make that module the sample's definition and change a signature nothing else in this round asked to change. **A first draft of this fix had two further defects, caught on read-only review before merge**: `check_units()` was reachable only through `universe.classify`, so a malformed row landing outside the windows ran unvalidated instead of raising, exactly the "no NBBO field allowed above 1" mistake the same guard exists to catch elsewhere; and every out-of-window session was one undifferentiated count, so a genuine VIX-series gap inside a window's calendar span (a source disagreement between two input files) was indistinguishable from a session §7's rule does not select at all. Both are fixed: every parsed row is unit-checked before restriction, and out-of-window sessions are split into `span_gap` and `out_of_span` |

### Raised, and not answerable here

`tests/README.md` states **47/47** mutations caught and enumerates 22 + 13 + 11 = **46**. Review round 6's G8 reconciled `test_boundary.py`'s header to "twelve", matching the prose rather than the enumeration; one of the two is wrong and **this round cannot say which**, because mutation testing needs an environment it did not have (see the review's appendix). Resolve it by re-running the twelve rounding mutations and recording the result, not by editing whichever number is easier to reach.

---

## Unreleased — raised by REVIEW-2026-07-29, not yet dispositioned

Driven by [REVIEW-2026-07-29.md](reviews/REVIEW-2026-07-29.md), a verification round over package v0.1.0. **No rule in the PRD changes here, and no threshold moves.** The round's job was to check that v1.3.2's twelve findings were really closed — **ten** are, against file and line; F12 is correctly still open because leaving it open was its disposition; and **F8 is not closed**, its no-literal half standing unqualified in all six places it appears, `CLAUDE.md` among them — and its own findings are either small code fixes or the three spec questions below. They are recorded now, unresolved, because [CLAUDE.md](../CLAUDE.md) requires a divergence between code and PRD to be raised rather than settled in code, and because a finding that lives only in a dated review file is one refactor from being lost.

### Spec questions — open

| Section | The question | Why it is a spec question, not a fix |
|---------|--------------|-------------------------------------|
| §7 (**G2**) | `daily_loss_pct` is marked **No (NON-BYPASSABLE)** in §7's Bypassable column, has a legal range in code (D27) and a `HARD_CAPS` check — and **no enforcement point**. Nothing in the package tracks realized P&L. Should its §7 *Enforcement Point* cell be qualified, e.g. "Continuous (1 sec) — Phase 6"? | §7's form is *condition → enforcement point → action*, and this row names an enforcement point that does not exist. Qualifying the cell makes the deferral visible in the normative text that asserts the guarantee; leaving §7 alone and noting it only in `params.py` keeps an unqualified non-bypassable claim in the spec. Either way it is an edit to a row the PRD calls hard, which is not a code decision. Note the shape: F6 was a cap guarding a constant that could not vary; this is a cap guarding a value nothing reads. **Scope correction:** the review's first draft claimed this of four limits, having read §2's configurability column instead of §7's Bypassable column — `max_open_positions`, `max_consecutive_losses` and the two drawdown limits are all marked bypassable by §7 itself, so their absence from code is unremarkable |
| §21.1 (**G4**) | §21.1 enumerates the fixture types and has **no row for the enforcement fixtures** — the check for the fifth defect class, 17 functions in `tests/test_enforcement.py`, named in `CLAUDE.md` convention 6 and in the PLAN's five-class table. Should it gain one? | Because §19 already ticks a row for them (`PRD.md:1898`), the two sections disagree about what the testing strategy contains: the status table credits a fixture type the strategy table does not enumerate. That is the v1.2 class between two sections of one document. The four §21.1 rows are the checks for defect classes one through four; the fifth class's check is missing from the section that catalogues them and present in the section that scores them |
| §2 (**G9**) | `premarket_trading_enabled` (D11, A17) has no home in code because **`Param.default` is `Decimal`-typed and the registry cannot represent a boolean**. Does the registry gain a type, or does the flag live outside it? | If it lives outside, §2's "user-configurable" column means two different things depending on the row, and the registry stops being the single source of truth for tunables. If it goes in, `Config.values`, the AST lint and the frozen baseline all have to accommodate a non-`Decimal`. `impact_coefficient` (D22) and the §2.1 premarket RVOL `× 0.05` coefficient are also unregistered, but neither has this excuse — both are numbers and should be registered when §18.7's arithmetic is implemented at Phase 4b |

### Decided

| ID | Decision |
|----|----------|
| **D29** | **Phase 3 (scanner) is gated on Phase 2a**, not only Phase 2. PRD §12.1's Phase 3 dependency cell is amended from `2` to `2a (gate passed)`. §12.1 as written permitted building the scanner to §4.2's filter set before knowing the set is obtainable from any provider at any price, which is the waste §5.5 spends three paragraphs on; a negative Q1 rewrites §4 and therefore the scanner's input contract. Cost, stated because it is real: Phase 3 now sits behind a weeks-long external dependency, and if the spike stalls Phase 3 stalls. That is intended — a stalled Phase 3 is cheaper than a rewritten one. Full rationale and rejected alternatives in [PLAN](PLAN.md) |

### Convention added, and the reason

`CLAUDE.md` gains convention 8: **a finding fixable in one line, with no spec implication and no behaviour change, gets fixed in the same change and one line in the review — no CHANGELOG entry, no decision, no disposition block.** The six-round review apparatus exists for defects that recur or need a spec call. A heading reading "four" above a list of six needs neither, and this review's first two drafts gave it the same treatment as an unenforced non-bypassable risk limit. The convention names its own weak point: the triviality judgement. When unsure, disposition it — a finding that turns out to recur was never trivial.

Applied immediately to G8, which is therefore **fixed rather than logged**: all six unqualified statements of the no-literal rule now carry the lint's actual scope (`src/tradipy/*.py` non-recursive, skipping `params.py` and `__init__.py`, exempting undistinctive values, not covering `scripts/`) in `CLAUDE.md`, `CONTRIBUTING.md`, `params.py`, `api.md`, `architecture.md` and `.cursor/rules/tradipy.mdc`; `tests/README.md`'s heading reads six; `test_boundary.py:496` reads twelve.

> **Superseded two commits later, and this entry is the seventh copy of the scope it describes.** The parenthetical above — "not covering `scripts/`" — was true when written and false from `d2e94a4`, which extended the lint to walk `scripts/` recursively and updated the six live statements it had just been told about. It did not update this record of the fix, which is F8's own defect class inside F8's own disposition. Left in place with this note rather than rewritten, because the entry is history: what it got wrong is not the scope, it is that a changelog entry restating a rule *is* one of the copies. Found by review round 7.

### Corrections to the PLAN

| Change | Why |
|--------|-----|
| The closing line of the five-defect-classes section read *"The honest extrapolation is that a fifth class exists. It will not be found by tightening any of the four checks above."* Replaced with a forward-looking statement about the sixth | Stale by one round, and it contradicted a paragraph four lines above it that already recorded the fifth class as found and named its check. Exactly the v1.2 class — a claim restated in two places with one updated — in the document whose own table defines that class. Found while wiring in this review, not by the review |
| Added a subsection recording that the fifth defect class has a **second population**: a *parameter* registered and read by nothing, as against a *mechanism* built and not called | 17 of the registered thresholds — 47 at the time — have no reader outside `params.py`, and all but two of those have none at all; `select_flagpole`'s §3.2 qualification predicate has no shipped caller; `is_whole_tick` is called only from tests. `tests/test_enforcement.py` cannot see any of them, because its rule ranges over guarantees *the code makes* and these are guarantees the code has not reached. The gap looks identical from inside the check built for the first population, which is the whole point of recording it |
| New risk row: **the gap between *registered* and *enforced*** | The registry is the artifact this project points at when asked whether a rule is implemented, and it answers "registered". That is the same conflation as F4 |

### Recorded against this round itself

The review's first draft was adversarially fact-checked before it shipped, then fact-checked again after correction. Both passes were needed.

**First pass — nineteen substantive errors**, five in a finding's headline claim. G2 overstated its scope fourfold by reading §2's configurability column instead of §7's *Bypassable* column, two lines from the claim it was making. "All twelve F-findings closed" ignored that F12's disposition was to leave them open. G8 cited a `params.py` docstring that does not mention the lint, and missed five further live instances of the rule it was about. G3 undercounted the spec's reject-code namespace. §20.9 was classified absent on a standard §20.14 was simultaneously credited by. A further thirteen citations were stale `PLAN.md:` line numbers, invalidated by this round's own PLAN edit — now replaced by section names for that reason.

**Second pass — nine more, three of them created by the first pass.** The F-finding count went 12 → 11 → **10**: "eleven closed plus F12 open" accounts for all twelve and leaves no slot for F8, three lines above a table marking F8 not closed. G3's correction asserted that three enum members were code-originated; `PRD.md:241` names two of them, and `rejects.py:35-39` already marks the third exactly as the finding demanded. G8's correction credited three doc ranges to the no-literal rule that are about a different over-claim entirely, so the rule is unqualified in six of six places rather than "the rest." G4's stated *reason* was falsified by a line the review's own F7 row cites: §19 already ticks an enforcement-fixtures row, which makes the finding better — §19 and §21.1 disagree about what the testing strategy contains.

Two errors were **inherited verbatim from REVIEW-2026-07-28 and repeated under the word "confirmed"**: the non-degenerate rounding fixture is not "at the end of `test_boundary.py`", and the twelve surviving mutations are eleven according to the block's own header comment. Recorded here rather than quietly corrected, because between them these two passes are the most direct evidence yet for what Workstream 11 has asked for across six rounds. A verification round inherits the previous round's idea of where to look; a correction pass inherits the correction's. **Agents reading the same repository do not compose into a cold read, however many of them there are.**

---

## v1.3.2 — package v0.1.0

Driven by [REVIEW-2026-07-28.md](reviews/REVIEW-2026-07-28.md), the first review of the **code** rather than of this document. Three of these change trading behaviour and are recorded as decisions D26–D28 in [PLAN](PLAN.md).

The distinctive thing about this round: every finding was a place where the *document was right and the code was not*, which is the reverse of the previous four. Four review rounds hardened the prose; nothing had yet checked whether the implementation of that prose enforced it. Three of the four highest-severity findings sat directly beneath a sentence asserting the opposite, and that sentence is what stopped anyone looking.

### Strategy behaviour

| Section | Was | Is | Why |
|---------|-----|-----|-----|
| §2.0 `mode` (**D28**) | Code defaulted to `experienced` while the §2.0 row says `beginner` | Code defaults to **`beginner`**, as stated | The document's declared default won over its own worked examples, which are all computed at 1% × $30,000 and are therefore *experienced*. Two reasons: a risk system should default to the conservative preset, and the examples are illustrations while the §2.0 row is a definition. **Changes every default share count** — §3.2's Bull Flag is 1,250 shares at the default and 2,500 at the preset the tables use. The examples now say so, and `python -m tradipy demo` runs in experienced mode for exactly this reason. Rejected: amending §2.0 to `experienced`, which would have made the safer setting the one you have to ask for |
| §1, §2.0, §3.1.1, §7 `room_gate_multiple` (**D26**) | All four sections state 2.0 is legal; `validate_couplings` rejected it | 2.0 is legal, and inert | The code's justification cited §3.1.1's *"cannot go below 2.0"* — which is `≥ 2.0`, not `> 2.0` — so the cited section did not support the check, and the deviation was declared nowhere. It was also unnecessary: `min_separation` is a MINIMUM-polarity threshold over a strictly positive quantity (`sep_cost_multiple ≥ 1.0`, `est_round_trip_cost_per_share ≥ 0.001`), so it is at least one tick at every legal configuration and §3.1.2's separation term `t1_r_multiple × R + min_separation` strictly exceeds `t1_r_multiple × R`. **Not** via `min_sep_r × R > 0`, which a first draft argued in six places — §2.0 permits `min_sep_r = 0.0`, so that product is exactly zero at a legal configuration; the v1.3.1 class (a rule generalized past its justification) restated the v1.2 way (in more than one copy), inside the fix for a finding about unenforced guarantees. The `entry < T1 < T2` ordering never came from the proportional multiple. Rejected: amending four PRD sections to exclude 2.0, which would have hard-coded a bound the separation floor already makes unnecessary. The separate finding that the multiple is **inert at its 2.5 default** is unaffected and still open |
| §2 risk settings (**D27**) | §2 states three settings are user-configurable within ranges; no configuration path existed and none of the four bounds was in code | `max_risk_per_trade_pct` (0.25–2%), `daily_loss_pct` (1–5%), `max_open_positions` (1–3) and `max_consecutive_losses` (2–5) are registered parameters; `MODE_PRESETS` is an overlay bundle on top of them | §7's "non-bypassable cap" was being checked against `MODE_PRESETS`, a module constant that no supported path could change — so the guarantee was enforced against something immovable while the legal range beneath it did not exist. The check now reads the **effective** value. The §7 cap and the §2 ceiling are the same number stated twice; `test_hard_caps_match_the_registry_ceilings` holds them together and is also the alarm that fires if a registry ceiling is ever raised above a §7 cap, at which point the coupling check stops being redundant |

### Corrections to this document

| Section | Change | Why |
|---------|--------|-----|
| §3.4 sensitivity table | The `$4.05` row labelled its binding term "proportional" while showing `$0.28`, which is the *separation* term's value | At R = $0.10 the proportional term is $0.25 and does not bind. This is the same fact `test_room_gate_multiple_can_never_strictly_bind_at_defaults` pins from the other direction: at the 2.5 default the proportional term can tie the separation term but never exceed it |
| §19 status table | Three rows marked ☐ outstanding — machine-checkable example fixtures, the parameter registry check, rounding-direction assertions | All three were built and green. A status table that under-reports is not a harmless error: §19's own preamble argues that *"a self-certified checklist is not evidence"*, and a checklist that is wrong in the pessimistic direction erodes the same trust as one that is wrong in the optimistic one |
| §2.0 mode presets | Added a note that §3's worked examples are computed at the `experienced` preset | Consequence of D28. Without it the tables and `Config.default()` disagree with no explanation, which is precisely the drift this file exists to prevent |

### Thresholds the PRD states in prose but never defines

Recorded rather than fixed, because giving each a §2.0-style row is a spec edit and this round was a code review. All are now registered in `tradipy.params` with code-originated bounds, and every such bound is marked `(bounds: code)` in its `source` so a reader can tell a transcribed bound from an invented one.

| Threshold | Where the PRD states it | Registered as |
|---|---|---|
| Premarket volume floor, 100,000 shares | §2, prose only | `min_premarket_volume` |
| VWAP extension in the first 30 minutes, 5% | §2, the second branch of a two-branch rule whose first branch *was* registered | `max_vwap_extension_open_pct` |
| HOD proximity trigger, 0.5% | §2, prose only | `hod_proximity_pct` |
| Composite-score weights and normalization caps (nine values) | §20.10 code block; §20.10 calls the caps "configurable" | `score_weight_*`, `score_cap_*` |
| Catalyst midpoint, 0.5 for headline-only | §20.10 code block | `score_catalyst_headline` |
| Conviction gate, 0.7 | §14.2 | `min_conviction_score` |
| VWAP stop band, `VWAP × 0.99` | §3.4 | `vwap_stop_band_pct` (open since v0.0.1) |

Two further observations for a future spec round:

- **§2 has no Bounds column.** Roughly half of the registry's `lo`/`hi` pairs are therefore this implementation's judgement rather than specification. That is unavoidable — something has to constrain the range — but it was previously undeclared, and `params.py` claimed all bounds were transcribed from the document.
- **`score_cap_float` (§20.10) and `max_float_shares` (§2) are both 20,000,000.** §20.10 states its normalizer independently of §2's scanner ceiling, so they are two parameters rather than one restated; but they mean nearly the same thing and will drift. Pinned by `test_score_float_cap_currently_equals_the_scan_filter`.

---

## v1.3.1

Driven by the independent review in [REVIEW-v1.3.md](reviews/REVIEW-v1.3.md). One change alters trading behaviour: the spread gates now round the other way, and are clamped.

### Strategy behaviour

| Section | Was | Is | Why |
|---------|-----|-----|-----|
| §3.1.3, §20.13 | Spread gates rounded with `ceil_to_tick` | `max(tick_size, floor_to_tick(...))` on both gates | **A maximum rounded up is a maximum weakened.** §20.13's rule said gate thresholds round up "conservative in every case" — true for a floor a value must exceed, reversed for a ceiling it must stay under. §3.1.3 inherited `ceil` by analogy and admitted spreads the unrounded threshold rejected. Its own robustness tables had been computed with `floor` throughout, so the tables were right and the formula was wrong. Under `ceil` the §3.2 Bull Flag example cleared its separation floor by exactly $0.00 — a pass by coincidence; under `floor` it clears by $0.03 (D25) |
| §3.1.3 | — | One-tick clamp on both rounded maxima | `floor_to_tick(0.15 × R)` is `$0.00` for `R < $0.067`. No spread is ≤ 0, so an unclamped gate rejects every trade and reports `SPREAD_TOO_WIDE` on each — an outage indistinguishable from a working filter. Today's `min_stop_distance` keeps R above the boundary; §2.0's bounds permit values that do not (A25) |

### Rationale relocated to where it is applied

| Section | Change | Why |
|---------|--------|-----|
| §13 preamble, §3.1.2, §3.1.3, §6.5, §20.5, §20.13, §4.2 | PRD now cites the PLAN decision (D17–D22, D24) wherever it states a decided value, and carries the rejected alternative inline for every behaviour-changing one | A-ids were perfectly closed — 24 defined, 24 referenced — while 19 of 24 D-ids had no inbound reference. An implementer reading §3.1.3 saw the gates and defaults but not that lowering `sep_cost_multiple` had been considered and rejected for "preserving the ladder's appearance while still trading at negative expectancy." That is exactly the reasoning that stops a rule being tuned away by someone who meets only its inconvenient consequences |

### Corrections

| Section | Change | Why |
|---------|--------|-----|
| §9.2 | "eleven of thirteen inter-component payloads" delivered 11 types; `Alert` and `JournalEntry` added, making 13 | `NotificationSystem` and `TradeJournal` sat at the end of §9.3 arrows with untyped payloads. §21.6 already specifies `Alert` behaviour — severity routing, Sev-1 pinned until acknowledged — which is not implementable against an undefined payload |
| §21.1 | Added rounding-direction assertions and cross-parameter coupling to the registry check | `assert cap == 0.01` passes under a wrong rounding rule that happens to agree at that input. Tests must assert the derivation, not the value |
| [PLAN](PLAN.md) WS9 | "Modular architecture with interfaces and data contracts" ✓ split into contracts ✓ / interfaces ☐ | Contracts are done; no `Protocol`, ABC, or method signature exists anywhere. The tick was carried by the contracts alone |
| [PLAN](PLAN.md) WS1, sequencing table | WS1 no longer attributes 14 threshold rows to the prompt (it names 12); implementation work moved out of the workstream-numbered table | "Depends on 5" was ambiguous between Workstream 5 and Phase 5 |
| [PLAN](PLAN.md) WS11, [PROMPT-REVIEW](reviews/PROMPT-REVIEW.md) §6.2 | Fourth defect class recorded: **generalization** — a rule stated more broadly than its justification supports | Invisible to all three prior checks. The rule appeared once (registry clean), the tables applying it were arithmetically correct (fixtures clean), and the boundary case passed. Only the prose disagreed with the tables |

---

## v1.3

Driven by the independent review in [REVIEW-v1.2.md](reviews/REVIEW-v1.2.md). Two changes alter trading behaviour rather than wording: the spread gate (§3.1.3) and the correlated-exposure rule (§7.1.3).

### Strategy behaviour

| Section | Was | Is | Why |
|---------|-----|-----|-----|
| §4.2, §3.1.3 | Scanner spread filter `≤ 1% of price`; no signal-time spread test | Scan: `≤ min($0.02, 0.5% × price)`. Signal: `≤ 0.15 × R` | At 1% of price, round-trip spread cost reached 83% of R on the §3.2 example and **all three worked examples failed their own §3.1.2 separation floor** at the widest spread the filter admitted. §18.2 warns that costs above ~0.5R erase the edge; the old filter admitted trades that breached it on spread alone. The filter and the floor had never been jointly calibrated |
| §3.1.2 | Room gate and separation floor evaluated as two independent tests | Unified: `required_room = max(room_gate_multiple × R, 2R + min_separation)` | On wide-spread names the separation floor is the stricter of the two, so evaluating them separately obscured which one bound. `signals.required_room` now records the value and which term produced it |
| §7.1.3 | "Max sector exposure: > 1 position same sector" — `symbols.sector` had no provider and correlation was not modelled | `correlation_group`, assigned by shared catalyst first, sector second, ungrouped third | Sector is a weak proxy for the exposure that actually exists: co-moving low-float gappers sharing one catalyst are frequently in different sectors, and unrelated same-sector names often do not co-move. Realized correlation is deliberately *not* estimated (A24) — too little history for the estimate to mean anything |
| §6.5 | Slippage = ticks + spread | Adds a square-root impact term, `impact_coefficient × spread × sqrt(shares / bar_volume)` | The prompt's §6.8 specifies "spread **+ impact**." §18.7's viability gate is judged net of modeled slippage, so an optimistic model biases the go/no-go toward "go." Phase 4b must also report the gate at 2× calibrated slippage |
| §4.2 | Institutional Ownership `≥ 80%`, soft filter, active | Disabled by default (A22) | The premise is doubtful: ≥80% institutional ownership in a ≤20M-float, ≤$2B universe is rare, so the filter likely never fires, and where it does the causation is unclear. No source in Appendix A states the threshold. §15 separately stated it as `> 80%`; reconciled to `≥` |
| §8.2 | "Model opening auction as first regular-session bar" | Auction print excluded from the participation cap; no simulated entry inside the 09:30 bar; still counts toward VWAP and HOD (A23) | Auction volume is a cross, not participable intraday liquidity. Treating it as an ordinary bar overstates achievable fills at the open |

### Definitions that were used before being defined

| Section | Change | Why |
|---------|--------|-----|
| §20.14 | **`spread_at_signal` defined** — NBBO source, sampling at signal-bar close, validity, 2 s staleness rule, crossed-market rejection, backtest substitute | It was the binding input to the §3.1.2 separation floor (which gates every entry) and persisted in `signals`, while §20 claimed to define every term. Introduced undefined in v1.2 in the same edit that added §20.13 on the principle that terms must be defined before use |
| §20.15 | **`ATR(14)` defined** — Wilder's smoothing, true range including the gap term, daily basis for §4.2, warm-up handling | A hard-referenced scanner filter and a §14.2 alternative with no period basis or true-range convention |
| §10.1 | **`bars_5m` added** with normative aggregation semantics — session-anchored boundaries, derived from `bars_1m`, `source_bar_count`, `BAR_INCOMPLETE` below 3 | §5.1 lists 5-min bars as MVP and ORB and Five-Minute Breakout both depend on them; no table or aggregation rule existed |
| §10.1 | **`halt_events` added** | §8.4 requires "halt events per symbol per day," §4.2 has a recent-halt filter, §8.2 simulates halts — none had storage |
| §10.1 | **`news_headlines` added** with separate `published_at` and `received_at` | Catalyst is a scored filter and a §20.10 score component, but the only storage was a free-text `watchlists.catalyst`, which cannot support look-ahead control |

### Prompt requirements previously unmet

| Section | Change | Prompt |
|---------|--------|--------|
| §9.2 | Typed contracts raised from 2 to 11: `Bar`, `Quote`, `FeatureVector`, `ScanCandidate`, `TradeSignal`, `RiskDecision`, `OrderEvent`, `Fill`, `Position`, `ClosedTrade`, `BacktestResult`. §9.3 arrows annotated with the type each carries | §6.9 requires interfaces and data contracts for every component |
| §14.3 | Advantages/disadvantages per alternative and "how experienced traders read it" for all 10 discretionary elements; three elements marked as having no adequate proxy | §7.3 and §2 Core Principle |
| §13 | "Recommended Alternative" column added for all 24 assumptions | §6.13 |
| §8.2 | News look-ahead rule: backtests filter on `received_at`, never `published_at`; `news_availability_lag` default 60 s where only publication time exists | §6.8 names RVOL *and news timestamps* as the two traps; RVOL was rigorously handled and news was not |
| §5.1 | Per-feed source and latency table, including news (publisher-to-API 1–60 s, API-to-system 1–5 s) | §6.5 asks for sources **and** latency |
| §5.2 | Latency decomposed into data-to-signal, signal-to-order, **order-to-exchange**, and end-to-end | §6.2 names order-to-exchange as its own leg |
| §21.5 | Threat model, loopback-only Gateway binding, read-only client IDs, audit-trail permissions, explicit out-of-scope list | §6.2 — previously secrets handling only, labelled security |
| §11.4 | `tradipy catalyst` command added | §12.2 item 6 made catalyst confirmation the one required manual action and no command performed it, so the MVP definition was unsatisfiable |

### Corrections to self-assessment

| Section | Was | Is |
|---------|-----|-----|
| §19 | "met for the three MVP setups; deliberate deviation for the remaining ~24"; PROMPT-REVIEW cited 27 setups in three places | 3 of **14 tradeable setups**; 11 remaining. The prompt bullets **26 components**, not 27, and twelve of them are not tradeable setups — scanner filters, position management, risk rules, and operations, all fully specified elsewhere. The criterion's own "where applicable" qualifier excludes them |
| §8.3 | Trade-count sufficiency "< 100 trades in sample" | "< 100 trades for any individual setup," matching §18.7's "≥ 100 per MVP setup" — the aggregate form was a materially weaker bar |
| §8.3 | Sharpe "annualized; rf = 0" | Daily-return basis, `× sqrt(252)`, with per-trade Sharpe explicitly excluded and the reason given |
| §3.5, §15 | Five-Minute Breakout specified two incompatible ways — "same as HOD breakout, wider stops, smaller size" versus "5-min close > 20-bar high on 2× vol" | The §15 form, fully specified in §3.5 with stop and target. "Smaller size" was never a rule; §2.2 sizing already shrinks share count as R widens |
| §2, §3.4 | Max Extension from HOD delegated the consolidation test to setup-specific rules, but VWAP Reclaim had none — so the parameter resolved to nothing for that setup | §3.4 criterion 9 added; every MVP setup now has a consolidation requirement, and §2 notes that a new setup without one leaves the parameter unresolved |
| §5.3, App. C | "$14.50/month" presented as the data cost | IBKR subtotal separated from a realistic $45–$500 all-in, since §5.5 concludes an external vendor is effectively mandatory |

---

## v1.2

A cross-section consistency sweep. Every defect in this release was the same failure mode: **a threshold restated as a literal in more than one place, with only one copy updated.** The durable fix is the parameter registry (PLAN Workstream 11), not another sweep.

| Section | Was | Is |
|---------|-----|-----|
| §3.2, §3.3, §3.4 | All three setup criteria hard-coded `≥ 2 × stop_distance` | Reference `room_gate_multiple`. §2.0 and §3.1.1 had been raised to 2.5 while the criteria an engineer implements from still read 2.0, and every worked example computed at 2.5 |
| §3.1.2 | The 2.5R room gate was claimed to prevent T1 and T2 collapsing into one exit | Absolute, cost-denominated separation floor (A18). The gate did not achieve it: T1 is fixed at 2R, so 2.5R buys exactly 0.5R of separation, and R shrinks on cheap stocks where costs bite hardest. The §3.4 example passed the gate with **$0.06 of separation on a $3.83 stock** — roughly one spread plus commission — and recorded it with a ✓ |
| §21.2, §20.5, §20.12 | "Protection lives at the broker," but the T3 leg trailed a locally computed 9 EMA that cannot be a static broker order | The ratcheted level is mirrored to a resting broker-side stop, amended upward each bar close (A19). The guarantee had silently expired at `TRAILING`, while §21.6 made any unprotected position a Sev-1 |
| §2 | Max Extension from HOD required consolidation with "≥ 50% retrace" while Bull Flag criterion 3 required "≤ 50%", and specified ≥ 3 candles against the setups' ≥ 2 | Proximity trigger only; the consolidation test is owned by the setup |
| §4.3 | Carried an unnormalized composite score that summed premarket volume in shares (~10⁵) against `float_inverse` (0–1) | Points at §20.10. The duplicate is what allowed the two copies to diverge; the unnormalized version made the score effectively "premarket volume, ranked" and could not satisfy the `score ≥ 0.7` gate |
| §15 | Scaling In, Stop Loss, Position Sizing and Daily Loss Limit rows carried rules that §3, §7 and §20 had overturned | Reconciled to the current rules with section references |
| §3.4 | Invalidation "reclaim on volume < 1.5× dip average" | Removed — unreachable, since entry criterion 5 requires ≥ 2× dip average |
| §20.13 | No tick size or rounding convention, while several rules computed non-tick levels (`VWAP × 0.99`, `entry + 2R` on odd R) | $0.01 tick; stops round down, targets and gate thresholds round up. Rounding is conservative in every direction |
| §8.1, §8.2 | Three incompatible liquidity models: 1% ADV live sizing, 5% bar-volume backtest fills, and a 10% partial-fill trigger | `participation_rate` is the sole fill model; backtest sizing matches live sizing including the ADV guard |
| §21.7, §4.1 | A 200-symbol limit introduced in an ops section, contradicting §4.1's full-market scan | Two-tier topology stated explicitly: external screening tier, IBKR execution tier |
| §2.2 | "$0.005–$0.01/share round-trip" alongside a $15–30 figure for 1,500 shares that only follows from per-side costs | Per-side reading, which is correct and is the basis for `est_round_trip_cost_per_share` |
| §11.3, footer | Dashboard showed a stale account figure and Bull Flag price; footer read v1.0 | Updated to match A5 and the corrected §3.2 example |

---

## v1.1

Recomputation of every worked example, after a cold review found four arithmetic errors sitting behind a fully-ticked acceptance checklist.

| Section | Was | Is |
|---------|-----|-----|
| §3.2 example | Quoted three different entry prices — $5.20 stated, $5.21 as the trigger close, $5.12 as the actual trigger level | Single derivation from the rules; entry $5.16 |
| §3.3 example | Stop at $6.22 while the rule required the consolidation low of $6.20; T2 ($7.00) set below T1 ($7.06) | Stop $6.33 from `min(consolidation low, breakout candle low) − 1 tick`; T1 $6.78 < T2 $7.00 |
| §3.4 exits | T1 labelled HOD and T2 labelled 2R, inverting the ladder whenever HOD sat above 2R | Canonical ladder: T1 = 2R, T2 = HOD retest |
| §3.1.1 | Partial-exit schedule differed per setup — 50/25/25 in one place, 50/50 in others | One ladder governs every setup |
| §3.2 crit. 5 | Flag volume `≥ 70%` of flagpole average | `≤ 70%` — the setup's own description calls for low-volume consolidation (A13). **This is the one correction still noted inline**, because the corrected form looks like a typo |
| §3.2 crit. 6 | Trigger "above the prior red candle's high" | "Closes above the highest high of the flag" — the old wording allowed a trigger inside the flag range, colliding with the "closes back inside flag range" invalidation |
| §3.2 stop | "If VWAP is above flag low, use VWAP − 1 tick" | Removed — unreachable, since criterion 4 requires the flag low to be above VWAP |
| §3.2 false signals | Listed "volume drying up" as a false signal | Reworded to the *breakout* candle, since volume contraction within the flag is required by criterion 5 |
| §3.5 Scaling In | "Total risk ≤ 1.5× original max risk" | Total open risk from live stops ≤ the non-bypassable cap (A16). The old wording openly violated §7 |
| §6.6, §21.2 | "Cancel all open orders if reconnect not established within 10 sec" | Preserve broker-side brackets; never attempt cancels while disconnected. The old rule was both impossible (a disconnected client cannot send cancels) and unsafe |
| §6.7 | "Reject duplicate `signal_id` within 5 min," where `signal_id` was a freshly generated UUID | Deterministic `idempotency_key` from signal identity. The old check could never fire — a new UUID is unique by construction |
| §7.1 | Daily loss tested `realized + unrealized ≤ −equity × pct` with equity *including* unrealized P&L | Frozen `start_of_day_equity` denominator. The threshold previously moved as the loss accrued, so the limit could never be reached deterministically |
| §2 | Max Open Positions row said "max 3" and "max 4" in the same row | Hard ceiling 3 |
| §12.3 | "~11–12 weeks," which did not equal the sum of its own rows and omitted the §5.5 data spike | 10–15 weeks, the honest sum |
