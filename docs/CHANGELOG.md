# Changelog — PRD

Corrections and reversals to [PRD.md](PRD.md), extracted so the spec itself can state only what is true.

**Why this file exists.** Through v1.2 the PRD narrated its own corrections in place — roughly twenty passages of the form "an earlier draft required ≥ 70%," "the earlier version quoted three different entry prices," "(Removed: … was unreachable)." That was the right instinct during review: it prevented silent reversals and made the error-correction record auditable. But it worked against the document's primary job. An implementer reading §3.2 should not have to work out which rule is current and which is a retracted ancestor, in a section whose entire purpose is to be unambiguous.

**One inline note is retained deliberately.** §3.2 criterion 5 keeps its correction marker, because `≤ 70%` reads as a typo to anyone expecting `≥` and the reversal is genuinely counter-intuitive. Every other correction lives here.

**Reading this file.** Entries are grouped by the release that made the change. Each says what the rule *was*, what it *is*, and why — the "why" being the part that stops the same error recurring.

---

## v1.3.1

Driven by the independent review in [REVIEW-v1.3.md](REVIEW-v1.3.md). One change alters trading behaviour: the spread gates now round the other way, and are clamped.

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
| [PLAN](PLAN.md) WS11, [PROMPT-REVIEW](PROMPT-REVIEW.md) §6.2 | Fourth defect class recorded: **generalization** — a rule stated more broadly than its justification supports | Invisible to all three prior checks. The rule appeared once (registry clean), the tables applying it were arithmetically correct (fixtures clean), and the boundary case passed. Only the prose disagreed with the tables |

---

## v1.3

Driven by the independent review in [REVIEW-v1.2.md](REVIEW-v1.2.md). Two changes alter trading behaviour rather than wording: the spread gate (§3.1.3) and the correlated-exposure rule (§7.1.3).

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
