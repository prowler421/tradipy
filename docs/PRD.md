# Ross Cameron Momentum Trading System — Product Requirements Document

**Version:** 1.3.1  
**Status:** Phase 1 draft — **pending independent verification** (PLAN Workstream 11)  
**Date:** 2026-07-28  
**Revision history:** [CHANGELOG.md](CHANGELOG.md) — this document states current rules only; superseded rules and the reasoning behind each reversal live there  
**Market:** US Equities  
**Broker:** Interactive Brokers (IBKR)  
**Language:** Python  

---

## 1. Executive Summary

This PRD specifies a production-ready quantitative trading platform that reverse-engineers Ross Cameron's discretionary momentum day-trading methodology into deterministic, testable rules. The system targets small-cap US equities with news catalysts, high relative volume, and low float — the "stocks in play" framework taught by Warrior Trading.

**Core philosophy:** A day trader is two things — a hunter of volatility and a manager of risk. Stock selection and risk management are primary; pattern execution is secondary.

**Phase 1 deliverable:** This document. No code is included.

**MVP gate:** Paper-trade ready system with scanner + 3 setups (Bull Flag, HOD Breakout, VWAP Reclaim) + full risk controls + basic CLI journal.

**Key constraints:**
- All subjective decisions converted to explicit rules or documented assumptions
- Minimum 2:1 reward-to-risk on every trade, enforced as the §3.1.1 room gate and **non-bypassable** (configurable upward only, 2.0–3.0)
- Daily loss limit and max risk-per-trade are non-bypassable hard rules, both denominated in **start-of-day equity** (§7.1)
- US equities only via IBKR official API
- Regular session only by default; premarket trading is opt-in and off in the MVP (D11)

> **Assumed account size: $30,000** (raised from $25,000 — see A5/D10). At exactly the $25,000 PDT minimum, the first losing trade drops equity below the threshold and the PDT rule locks the account long before the 3% daily loss limit is ever reached. A $30,000 assumption leaves ~16% of headroom before PDT restriction bites.

> ### Read §18 before building anything
>
> Sections 2–17 specify *how* to trade this methodology deterministically. **[§18](#18-strategy-viability--open-risks) asks whether it is worth trading at all**, and it is the only section that can prevent a real loss. It argues that the central premise (A2) is asserted rather than demonstrated, that the source's performance claims are unaudited marketing, that costs plausibly exceed the theoretical edge, and that **no capital should move until net-of-cost expectancy clears the out-of-sample gate in §18.7.**
>
> It is placed at §18 because it depends on the cost and slippage models defined earlier. It is signposted here because a reader under time pressure would otherwise reach it last, if at all.

---

## 2. Quantitative Thresholds

Every threshold below includes: proposed default, confidence rating, Ross source, sensitivity note, and user-configurable flag.

| Parameter | Proposed Default | Confidence | Ross Source | Sensitivity | User-Configurable |
|-----------|------------------|------------|-------------|-------------|-------------------|
| **Minimum Gap %** | ≥ 4% premarket gap from prior close; OR ≥ 10% daily change | High (10% daily); Medium (4% premarket) | Stock Selection PDF: "up at least 10% on the day"; book mentions 4–5% premarket gaps | High — lowering gap threshold increases candidate count but dilutes quality | Yes |
| **Relative Volume (RVOL)** | ≥ 5× 30-day average daily volume | Medium | Warrior "Stock Selection" PDF cites "at least a Relative Volume Ratio of 5," but the governing architect prompt's §7.4 states Ross rarely gives an exact multiple and treats 5× as a community proxy — hence Medium, not High. Source example uses a **50-day** ADV lookback; see A8 / D2 for the 30-day divergence | High — 3× captures more names; 10× misses early movers | Yes |
| **Float** | ≤ 20M shares (prefer ≤ 10M) | High | Stock Selection PDF + "20-20 rule" ($20 price, 20M float) | Medium — lower float = more volatility but less liquidity | Yes |
| **Price Range** | $1.00 – $20.00 (ideal $2 – $10) | High | Stock Selection PDF: "$1.00 and $20.00" | Medium — exceptions allowed for "obvious" leading gainer | Yes |
| **Average Daily Volume** | ≥ 500,000 shares/day (30-day) | Medium | Community/education material; not explicitly stated by Ross | Medium — ensures exit liquidity on low-float names | Yes |
| **Premarket Volume** | ≥ 100,000 shares premarket AND/OR ≥ 2× prior day premarket volume | Medium | Implied by premarket scanning workflow; no exact number in source | Medium — filters illiquid premarket gappers | Yes |
| **Max Extension from VWAP** | No entry if price > 3% above VWAP (regular session) OR > 5% above VWAP (first 30 min) | Low | Ross avoids chasing; no exact % in source — community proxy | High — tighter = fewer entries; looser = more chase risk | Yes |
| **Max Extension from HOD** | No entry within 0.5% of HOD unless the setup's own consolidation requirement is satisfied — Bull Flag §3.2 crit. 3 (2–5 flag candles, retrace ≤ 50% of flagpole), HOD Breakout §3.3 crit. 3 (≥ 2 candles, high ≤ prior HOD, low ≥ VWAP), or VWAP Reclaim §3.4 crit. 9 (≥ 2 candles since dip low, high ≤ HOD). **This row defines only the 0.5% proximity trigger; the consolidation test is owned by the setup.** Every MVP setup now has one — a post-MVP setup added without one leaves this parameter unresolved and must define it | Medium | Implied by bull flag / pullback entry logic | Medium | Yes (proximity % only) |
| **Stop Distance** | Pattern-derived level (setup-specific), then **widened** to a $0.10 minimum distance if narrower. If the resulting distance exceeds 5% of entry, **skip the trade** (do not tighten — tightening puts the stop inside the pattern) | High | Bull flag: "max loss at low of pullback"; book uses $0.10–$0.50 typical | High — directly affects position size | Yes |
| **Profit Target / R-Multiple** | Target 1: 2R (minimum); Target 2: measured move (flagpole height); Target 3: HOD retest + extension | High | Stock Selection PDF: "2:1 Profit to Loss ratio" | High — 1.5R reduces expectancy; 3R reduces win rate | Yes |
| **Max Risk Per Trade** | 1% of account equity (default); hard cap 2% | High | Book: 1–2% depending on experience level | Critical — linear impact on drawdown | Yes (within 0.25%–2% bounds) |
| **Daily Loss Limit** | 3% of account equity (hard stop); beginner mode: 2% | High | Book: $200–$1,000 or 2–5% by experience | Critical — prevents catastrophic days | Yes (within 1%–5% bounds; cannot disable) |
| **Max Open Positions** | 1 concurrent position (default); 3 in experienced mode | Medium | Ross typically focuses on 1–2 leading gainers | Medium — more positions = correlation risk (§7.1.3) | Yes, **hard ceiling 3** |
| **Max Consecutive Losses** | 3 losses → lock new entries for remainder of session | High | Book: "Three Strikes Rule" | Medium — 2 is conservative; 5 allows revenge trading | Yes (2–5) |

### 2.0 Previously Undefined Parameters

These were referenced in Sections 6, 7 and 2.2 without ever being given a default or bounds, which would have blocked implementation:

| Parameter | Default | Bounds | Used by |
|-----------|---------|--------|---------|
| `start_of_day_equity` (assumed) | $30,000 | ≥ $25,000 for PDT mode | Sizing, all risk limits (A5) |
| `session_dd_pct` | 4% of start-of-day equity | 2–10% | Session drawdown rule (§7) |
| `multi_day_dd_pct` | 8% rolling 5-day | 5–20% | Multi-day drawdown rule (§7) |
| `max_bp_usage_pct` | 50% | 10–100% | Position sizing constraint (§2.2) |
| `max_shares_per_order` | 10,000 | 100–100,000 | Position sizing constraint |
| `max_pct_of_adv` | 1% of 30-day ADV | 0.1–5% | Liquidity guard (§2.2, §18.3) |
| `room_gate_multiple` | 2.5 | 2.0–3.0, cannot go below 2.0 | Pre-entry room gate (§3.1.1) |
| `min_stop_distance` | $0.10 | $0.01–$1.00 | Stop floor |
| `max_stop_pct` | 5% of entry | 1–10% | Skip-trade ceiling |
| `max_spread_abs` | $0.02 | $0.01–$0.10 | Scanner spread cap, absolute (§4.2) |
| `max_spread_pct` | 0.5% of price | 0.1–2.0% | Scanner spread cap, relative (§4.2) |
| `max_spread_r` | 0.15 × R | 0.05–0.50 | **Pre-entry** spread gate, R-denominated (§3.1.3) |
| `sep_cost_multiple` | 3.0 | 1.0–10.0 | T2−T1 separation floor (§3.1.2) |
| `est_round_trip_cost_per_share` | $0.015 | $0.001–$0.10 | Separation floor + cost modelling (§3.1.2) |
| `min_sep_r` | 0.5 | 0.0–2.0 | Separation floor, R component (§3.1.2) |
| `bar_close_grace_ms` | 750 ms | 100–5,000 | Bar close detection (§20.1) |
| `premarket_trading_enabled` | **false** | — | Session gating (D11, A17) |
| `mode` | `beginner` | `beginner` \| `experienced` | Preset bundle, below |

**Mode presets** (referenced throughout but never defined):

| Setting | `beginner` | `experienced` |
|---------|-----------|---------------|
| `max_risk_per_trade_pct` | 0.5% | 1.0% (hard cap 2.0%) |
| `daily_loss_pct` | 2% | 3% |
| `max_open_positions` | 1 | 3 (hard ceiling 3) |
| `max_consecutive_losses` | 2 | 3 |

> **The §3 worked examples are computed at the `experienced` preset.** Every one of them
> states risk as 1% × $30,000 — that is `experienced`, while the declared default above is
> `beginner`. The default is deliberately the safer of the two, so reproducing the §3 tables
> means asking for the other one: `Config.default(mode="experienced")`, or
> `python -m tradipy demo`, which does exactly that and says so in its header. At the
> `beginner` default every share count in §3 halves. Decided as [PLAN](PLAN.md) **D28**.

### 2.1 RVOL Calculation Specification

```
RVOL = current_session_volume / avg_daily_volume_30d

For premarket:
  RVOL_premarket = premarket_volume / avg_premarket_volume_30d
  (fallback: premarket_volume / (avg_daily_volume_30d × 0.05) if no premarket history)

Computed on 1-minute bars; updated every minute during premarket and regular session.
Use volume as-of signal time only (no look-ahead).
```

### 2.2 Position Sizing Formula

```
shares = floor(max_dollar_risk / effective_stop_distance)
max_dollar_risk = start_of_day_equity × max_risk_per_trade_pct

effective_stop_distance = entry_price − effective_stop
  where effective_stop = the level that will trigger FIRST
  (e.g. max(pattern_stop, VWAP − 1 tick) for VWAP-invalidated setups — see A14)

Constraints:
  - shares × entry_price ≤ available_buying_power × max_bp_usage_pct (default 50%)
  - shares ≤ max_shares_per_order (default 10,000)
  - shares ≤ max_pct_of_adv × avg_daily_volume_30d (default 1%) — liquidity guard so
    the position can realistically be exited (new; see §18.3)
  - Round down to nearest whole share

Note: sizing uses start_of_day_equity, NOT live equity, so intraday gains cannot
compound position size within the same session.
```

**Worked example:** start-of-day equity $30,000, risk 1% ($300), entry $4.50, effective stop $4.30 (distance $0.20):
- Shares = floor(300 / 0.20) = **1,500**
- Position value = 1,500 × $4.50 = **$6,750** (within 50% BP cap)
- Max loss if stopped = 1,500 × $0.20 = **$300** = 1.0% of start-of-day equity ✓

**Commissions are not included in R.** IBKR per-share pricing plus regulatory fees typically runs **~$0.005–$0.01 per share per side**, i.e. **$0.01–$0.02 round-trip**. On the example above (1,500 shares) that is ~$15–30 against a $300 risk unit — a 5–10% drag on every R. This per-side figure is the basis for `est_round_trip_cost_per_share` = $0.015 in §3.1.2. Backtest and journal metrics must be reported **net** (§8.3, §18.2).

---

## 3. Trading Setups & Rules

> **Read §20 (Computation Semantics) first.** Every term used below — VWAP, HOD, flagpole height, 9 EMA, "tighter", RVOL as-of time, bar timing — is defined normatively there, and §20 governs on any conflict. The rules in this section are not implementable without it.

### 3.1 Setup Inventory

| Setup | Confidence | MVP | Primary Timeframe |
|-------|------------|-----|-------------------|
| Gap Scanner (filter, not trade setup) | High | Yes | Pre-market |
| Bull Flag | High | Yes | 1-min, 5-min |
| High-of-Day Breakout | High | Yes | 1-min |
| VWAP Reclaim | Medium-High | Yes | 1-min |
| Opening Range Breakout (ORB) | Medium | No | 5-min |
| Flat-Top Breakout | Medium | No | 1-min, 5-min |
| ABCD Pattern | Medium | No | 1-min, 5-min |
| Micro Pullback | Medium | No | 1-min |
| First 1-Min Candle New High | Medium | No | 1-min |
| Five-Minute Breakout | Medium | No | 5-min |
| Pullback Entry (generic) | Medium | No | 1-min |
| Momentum Continuation | Medium | No | 1-min |
| Premarket Gapper | Medium | No | Pre-market |
| Whole-Dollar Breakout | Low-Medium | No | 1-min |
| Halt Breakout | Low | No | 1-min |
| Scaling Into Winners | High (management) | Partial | — |
| Scaling Out | High (management) | Partial | — |
| ABCD (target projection) | Medium | No | — |

---

### 3.1.1 Canonical Exit Ladder (applies to all setups)

**One ladder governs every setup**, and target *ordering* is enforced rather than assumed:

| Leg | Size | Level |
|-----|------|-------|
| **T1** | 50% | Exactly **2R** from entry (R = entry − stop) |
| **T2** | 25% | Nearest **structural** target above T1 (setup-specific: measured move, HOD, or next whole dollar) |
| **T3** | 25% | Trail 9 EMA (1-min); exit on close below the EMA. The ratcheted level rests as a broker-side stop, amended each bar close (§20.5, §21.2) |

**Ordering constraint (hard):** `entry < T1 < T2`. This is guaranteed by the pre-entry room gate below rather than checked afterwards.

**Pre-entry room gate (replaces the old tautological "R:R ≥ 2:1 to first target" criterion):** let `resistance` be the *nearest* overhead level above entry among {HOD, next whole dollar, prior leg high, measured-move projection}. Require:

```
(resistance − entry) ≥ room_gate_multiple × stop_distance
room_gate_multiple: default 2.5, configurable 2.0–3.0, cannot be set below 2.0
```

If the nearest resistance is closer than that, the trade has insufficient room and is **rejected pre-entry**. This is a real gate — unlike "R:R ≥ 2:1 to T1," which could never fail because T1 is *defined* as 2R.

The default of **2.5** rather than 2.0 exists so T1 (at 2R) and T2 (at the structural level) are separated by a meaningful margin. At exactly 2.0 the two legs can land within a cent or two of each other, which after slippage and commissions is a single exit wearing two labels (A15).

> **This is not the whole gate.** The multiple above is the *proportional* term only. It is insufficient on its own — see §3.1.2, which shows why, adds a cost-denominated floor, and combines both into the single `required_room` test that is actually enforced. Implement §3.1.2, not this formula in isolation.

**Stop management:** on T1 fill, move the stop on the remaining 50% to breakeven (entry). This is what makes scaling in compatible with the non-bypassable per-trade risk cap (§7).

---

### 3.1.2 T2−T1 Separation Floor (absolute, cost-denominated)

The `room_gate_multiple` of 2.5 was introduced (A15) so that T1 and T2 would not "collapse into one exit after costs." **It does not achieve that**, and the failure is structural rather than a tuning error: T1 is fixed at 2R, so a 2.5R gate buys exactly 0.5R of separation — and R itself shrinks on cheap stocks, which is precisely where costs bite hardest. The §3.4 worked example cleared the 2.5R gate with T1 and T2 **$0.06 apart on a $3.83 stock**, which is roughly one spread plus round-trip commission. Two exits, one economic event.

Separation must therefore be constrained in **absolute, cost-denominated terms**, not as a multiple of R:

```
round_trip_cost_per_share = spread_at_signal + est_round_trip_cost_per_share

min_separation = max(
    min_sep_r × R,                                    # 0.5R — already implied by the room gate
    sep_cost_multiple × round_trip_cost_per_share     # the binding constraint on cheap stocks
)

require:  (T2 − T1) ≥ ceil_to_tick(min_separation)
```

| Parameter | Default | Bounds | Note |
|-----------|---------|--------|------|
| `sep_cost_multiple` | 3.0 | 1.0–10.0 | T2 must clear T1 by 3× the cost of taking the extra exit |
| `est_round_trip_cost_per_share` | $0.015 | $0.001–$0.10 | IBKR per-share + SEC/TAF, both sides (§2.2). **Calibrate from real fills in Phase 4b** — this is an estimate, not a measurement |
| `min_sep_r` | 0.5 | 0.0–2.0 | Redundant with a 2.5 room gate; retained so the constraint is self-contained |

**Enforcement:** pre-entry, alongside the room gate. A setup that passes the room gate but fails the separation floor is rejected with `TARGETS_TOO_CLOSE` — it is not silently collapsed into a single target, because a 50/50 ladder has different expectancy than the specified 50/25/25 and would quietly change the strategy being measured.

**Why not simply raise `room_gate_multiple`?** Because the required multiple is price-dependent. On the §3.4 example, forcing $0.075 of separation would need a gate of ~2.75R; on a $15 stock with a $0.40 stop the same dollar separation is 0.19R and the 2.5R gate is already generous. One multiplier cannot serve both. Recorded as **A18**; decided as [PLAN](PLAN.md) **D17**, which records what the earlier 2.5R gate was believed to accomplish and why it did not.

**Unified room requirement.** The room gate and the separation floor are two constraints on the same quantity — the distance from entry to the nearest overhead resistance — and on wide-spread names the separation floor is the *stricter* of the two. Evaluating them independently obscures which one binds. They are therefore combined into a single pre-entry test:

```
required_room = max(
    room_gate_multiple × R,          # §3.1.1 — proportional
    2 × R + min_separation           # §3.1.2 — T1 sits at 2R, T2 must clear it by the floor
)

require:  (resistance − entry) ≥ ceil_to_tick(required_room)
```

Rejection code is `INSUFFICIENT_ROOM` when the first term binds, `TARGETS_TOO_CLOSE` when the second does; `signals` records which (§10).

---

### 3.1.3 Spread Gate (pre-entry, R-denominated)

The separation floor above takes `spread_at_signal` as an input, which makes the scanner's spread filter part of the strategy's economics rather than a hygiene check. §4.2 originally admitted any spread up to **1% of price**, and at that limit the arithmetic does not work:

| Setup | Price | Spread at 1% (`floor_to_tick`) | Round-trip spread cost | R | Cost as % of R |
|-------|-------|------------------------------|----------------------|---|---------------|
| §3.2 Bull Flag | $5.16 | $0.05 | $0.10 | $0.12 | **83%** |
| §3.3 HOD Breakout | $6.48 | $0.06 | $0.12 | $0.15 | **80%** |
| §3.4 VWAP Reclaim | $3.83 | $0.03 | $0.06 | $0.10 | **60%** |

§18.2 observes that "a gross +0.5R edge can turn negative once round-trip slippage and fees exceed ~0.5R." A 1%-of-price spread filter **admits trades that breach that threshold on spread alone**, before slippage or commission. All three worked examples also fail their own §3.1.2 separation floor at that spread. The filter and the floor were never jointly calibrated; this section does it.

Two gates, because the binding quantity changes between scan time and signal time. **Both are maximums, so both round *down* per §20.13** — rounding a ceiling up would admit spreads the unrounded threshold rejects:

```
# Scan time (R is not yet known — the setup does not exist)
max_spread_scan = max(tick_size,
                      floor_to_tick(min(max_spread_abs, max_spread_pct × price)))

# Signal time (R is known — this is the gate that matters)
max_spread_signal = max(tick_size, floor_to_tick(max_spread_r × R))

require:  spread_at_signal ≤ max_spread_signal
```

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `max_spread_abs` | $0.02 | Two ticks. A percentage-of-price cap scales the wrong way: 1% of $20 is ten ticks, which no momentum setup can absorb |
| `max_spread_pct` | 0.5% | Binds below ~$4, where two ticks is already a large fraction of price |
| `max_spread_r` | 0.15 | Round-trip spread crossing ≤ 30% of R. Not comfortable — but it is the level at which the §18.2 erosion threshold is not breached by spread alone |

**Why the one-tick clamp is load-bearing.** `floor_to_tick(max_spread_r × R)` returns `$0.00` whenever `R < tick_size / max_spread_r`, which at the defaults is **R below $0.067**. No spread can be less than or equal to zero, so an unclamped gate would reject *every trade* — silently, with a plausible-looking `SPREAD_TOO_WIDE` on each. Today's `min_stop_distance` of $0.10 keeps R above that boundary, but §2.0 permits `min_stop_distance` down to $0.01, so the failure is reachable by a legal configuration change and not by any bug. Recorded as **A25**; the parameter-registry check (§21.1) must treat this as a coupling, not two independent bounds.

Rejection code `SPREAD_TOO_WIDE` at both points. Failing at signal time is expected and common: spreads widen precisely during the momentum bursts that produce triggers, and a trade whose spread has blown out is one the system should decline rather than pay for.

> **This changes trading behaviour** — decided as [PLAN](PLAN.md) **D20**. The system now declines trades it previously took, and the rejection rate is expected to be material on sub-$4 names, where two ticks is already 0.5% of price. That is the intended effect, not a regression.
>
> **The rejected alternative matters more than the chosen one.** Lowering `sep_cost_multiple` would have made the §3.1.2 floor easy to clear and left the ladder looking healthy — while continuing to trade at negative expectancy, since the friction that the floor exists to measure would still have been there. It is the cheaper-looking fix and the wrong one. If the `SPREAD_TOO_WIDE` rate proves uncomfortably high in Phase 4b, **the correct response is to conclude the strategy cannot be traded on those names, not to widen the gate.** Any change to `max_spread_r`, `max_spread_abs`, `max_spread_pct`, or `sep_cost_multiple` must be justified against measured net expectancy, not against rejection count.

**Robustness invariant (testable).** Every worked example in §3 must satisfy the §3.1.2 separation floor **at the widest spread its own filters admit**, not merely at an assumed $0.01. Recomputed at the tightened caps:

| Setup | Widest admitted spread (`floor_to_tick`) | Separation floor at that spread | Actual T2−T1 | Margin | Result |
|-------|----------------------------------------|-------------------------------|-------------|--------|--------|
| §3.2 Bull Flag | $0.01 (0.15 × $0.12 = $0.018 → **$0.01**) | $0.08 | $0.11 | $0.03 | PASS |
| §3.3 HOD Breakout | $0.02 (0.15 × $0.15 = $0.0225 → **$0.02**) | $0.11 | $0.22 | $0.11 | PASS |
| §3.4 VWAP Reclaim | $0.01 (0.15 × $0.10 = $0.015 → **$0.01**) | $0.08 | $0.12 | $0.04 | PASS |

Under the old 1% filter all three failed. The **margin** column is reported deliberately: had these gates rounded up instead of down, Bull Flag would have passed at exactly `$0.11 ≥ $0.11` — zero margin, which is not a pass so much as a coincidence, and which would make the CI fixture below flip on any parameter nudge without distinguishing a meaningful change from rounding jitter. A boundary fixture that passes with zero margin is reporting a problem, not a success.

This invariant is encoded as a fixture in §21.1 so a future loosening of any of the four parameters breaks CI rather than silently reintroducing negative-expectancy trades. Recorded as **A21**.

---

### 3.2 MVP Setup 1: Bull Flag

**Description:** Continuation pattern after strong upward move (flagpole), brief low-volume consolidation (flag), then breakout to new high.

#### Entry Criteria (all required)
1. Stock passes scanner hard filters (Section 4)
2. Flagpole: ≥ 3 consecutive green 1-min candles with combined move ≥ 2% and total volume ≥ 2× average 1-min volume of prior 30 bars
3. Flag: 2–5 red/consolidation candles; pullback retraces ≤ 50% of flagpole height (see §20.4 for the definition of flagpole height)
4. Flag low remains above session VWAP (§20.2). Premarket entries are **disabled by default** in the MVP (D11); when premarket trading is explicitly enabled, premarket VWAP applies instead
5. Flag volume: average volume of flag candles **≤ 70%** of flagpole average volume — the flag must show volume *contraction*. (Corrected: an earlier draft required ≥ 70%, which contradicted this setup's own "low-volume consolidation" description. See A13)
6. **Trigger:** first 1-min candle that **closes above the highest high of the flag** — not merely above the prior red candle's high, which would allow a trigger inside the flag range
7. Breakout candle volume ≥ 2× average flag candle volume
8. **Room gate:** nearest overhead resistance ≥ `required_room` — the unified test in §3.1.2, which takes the greater of `room_gate_multiple × stop_distance` (default 2.5) and `2R + min_separation`. Ordering `entry < T1 < T2` follows from it
9. **Spread gate:** `spread_at_signal ≤ max_spread_r × R` (§3.1.3, §20.14)

#### Optional Confirmations
- Daily chart shows stock near/at all-time low (turnaround story — lower risk)
- Stock is top 1–3 leading percentage gainer
- Level 2 shows ask-side absorption (future; not MVP)

#### Stop Placement
- Hard stop at **low of flag consolidation** (lowest low of flag candles), minus 1 tick
- Minimum stop distance: $0.10. Maximum stop distance: 5% of entry price — if the flag low is further than 5% away, **skip the trade** (do not tighten the stop; tightening would place it inside the pattern and guarantee a noise stop-out)
- No VWAP branch applies here: criterion 4 requires the flag low to be above VWAP, so VWAP can never be the tighter level

#### Exit Criteria
Per the canonical ladder (§3.1.1):
- **T1 (50%):** 2R from entry → on fill, move stop to breakeven on the remainder
- **T2 (25%):** measured move = entry + flagpole height (§20.4)
- **T3 (25%):** trail 9 EMA (1-min); exit on close below the EMA
- **Breakout or bailout:** exit full position if, within 3 candles (3 min) of entry, price has not closed above the entry price *and* has not made a new high above the breakout candle high ("no upward movement" is defined here explicitly)
- **Invalidation:** close below VWAP after entry → exit immediately

#### Invalidation Rules
- Pullback exceeds 50% of flagpole height
- Price breaks below VWAP during flag formation
- Flag extends beyond 5 candles without a valid trigger
- After entry: breakout candle closes back below the flag high (now redundant with the corrected criterion 6 trigger, but retained as a post-entry check)

#### Edge Cases
- **Multi-flag:** After Target 1, treat subsequent consolidation as new flag if above VWAP
- **Halt during flag:** Remove from watchlist; re-evaluate on resumption with new HOD logic
- **Low float halts:** Do not enter within 2 min of anticipated halt/resumption

#### False-Signal Patterns
- **Breakout** candle on weak volume (< 2× flag average) — note this is about the *breakout*, not the flag. Volume contraction *within* the flag is desirable (criterion 5); it is the failure to expand on the breakout that signals a false move
- Session RVOL declining through the flag *and* the breakout (interest leaving the name entirely)
- Flag below a declining 9 EMA with no volume on breakout
- "Obvious" stock already up > 100% with no fresh catalyst

#### Worked Example (every line derives from the rules above)

| Step | Derivation | Value |
|------|-----------|-------|
| Flagpole | 4 green 1-min candles, $4.80 → $5.15 | height = **$0.35** (+7.29%) |
| Flag | 3 red candles; flag high $5.12, flag low $5.05 | retrace = (5.15 − 5.05)/0.35 = **28.6%** ≤ 50% ✓ |
| Flag volume | avg flag vol / avg flagpole vol = 0.55 | **≤ 0.70** ✓ (contraction) |
| Trigger (crit. 6) | first close above flag high $5.12 | breakout candle closes **$5.16** |
| Breakout volume | 3.0× avg flag candle volume | ≥ 2× ✓ |
| **Entry** | breakout candle close | **$5.16** |
| Stop | flag low $5.05 − 1 tick | **$5.04** |
| R (stop distance) | 5.16 − 5.04 | **$0.12** (≥ $0.10 min ✓; ≤ 5% = $0.258 ✓) |
| Spread gate (§3.1.3) | scan: min($0.02, 0.5% × $5.16 = $0.026) = $0.02; signal: 0.15 × $0.12 = $0.018 → **$0.01** | observed $0.01 ✓ |
| Nearest resistance | measured move $5.51 (below next whole dollar $6.00) | gap = $0.35 |
| Separation floor (§3.1.2) | max(0.5 × $0.12, 3 × ($0.01 + $0.015)) = $0.075 → $0.08 | required **$0.08** |
| Required room (§3.1.2, unified) | max(2.5 × $0.12 = $0.30, 2 × $0.12 + $0.08 = $0.32) | **$0.32** |
| Room test | $0.35 ≥ $0.32 | **PASS** ✓ |
| T1 (50%) | entry + 2R | **$5.40** |
| T2 (25%) | entry + flagpole height | **$5.51** |
| Ordering | $5.16 < $5.40 < $5.51 | ✓ |
| T2 − T1 | $5.51 − $5.40 | **$0.11** ≥ $0.08 ✓ |
| Shares | floor(risk $300 / $0.12), risk = 1% × $30,000 | **2,500** |
| Position value | 2,500 × $5.16 | $12,900 (within 50% BP cap ✓) |
| Max loss if stopped | 2,500 × $0.12 | **$300** = 1.0% of equity ✓ |

---

### 3.3 MVP Setup 2: High-of-Day Breakout

**Description:** Entry on first candle making a new high of day after consolidation or pullback, confirming continued momentum.

#### Entry Criteria (all required)
1. Stock passes scanner hard filters
2. Stock has established HOD at least once prior (not opening print)
3. Consolidation: ≥ 2 candles where high ≤ prior HOD and low ≥ VWAP
4. **Trigger:** 1-min candle closes above prior HOD (close-based, not wick — see §20.3)
5. Breakout volume ≥ 1.5× average volume of consolidation candles
6. Price ≤ 3% above VWAP at entry
7. **Room gate:** nearest overhead resistance ≥ `required_room` (§3.1.2 unified test)
8. **Spread gate:** `spread_at_signal ≤ max_spread_r × R` (§3.1.3, §20.14)

#### Stop Placement
- Low of consolidation range OR low of breakout candle (**whichever is lower**), minus 1 tick
- Minimum stop distance $0.10; maximum 5% of entry — if exceeded, skip the trade

#### Exit Criteria
Per the canonical ladder (§3.1.1):
- **T1 (50%):** 2R → move stop to breakeven on remainder
- **T2 (25%):** next whole-dollar level above T1, or prior leg extension (1× leg height), whichever is nearer *and above T1*
- **T3 (25%):** trail 9 EMA (1-min)
- **Breakout or bailout:** 3 candles after entry with no new high above the breakout candle high → exit

#### Invalidation
- Close back below prior HOD within 2 candles of breakout
- Close below VWAP

#### Worked Example

| Step | Derivation | Value |
|------|-----------|-------|
| Prior HOD | established 10:15 AM | $6.45 |
| VWAP at entry | — | $6.32 |
| Consolidation | 3 candles, $6.34–$6.42 (high ≤ HOD ✓; low ≥ VWAP ✓) | low = $6.34 |
| **Trigger / entry** | 1-min close above HOD $6.45, at 10:28 AM | **$6.48** |
| Breakout volume | 1.9× consolidation average | ≥ 1.5× ✓ |
| Extension (crit. 6) | 6.48 / 6.32 − 1 = **2.53%** | ≤ 3% ✓ |
| Stop | min(consolidation low $6.34, breakout candle low $6.44) − 1 tick | **$6.33** |
| R | 6.48 − 6.33 | **$0.15** (≥ $0.10 ✓; ≤ 5% = $0.324 ✓) |
| Spread gate (§3.1.3) | scan: min($0.02, 0.5% × $6.48 = $0.032) = $0.02; signal: 0.15 × $0.15 = $0.0225 → **$0.02** | observed $0.01 ✓ |
| Nearest resistance | next whole dollar $7.00 | gap = $0.52 |
| Separation floor (§3.1.2) | max(0.5 × $0.15, 3 × ($0.01 + $0.015)) = $0.075 → $0.08 | required **$0.08** |
| Required room (§3.1.2, unified) | max(2.5 × $0.15 = $0.375, 2 × $0.15 + $0.08 = $0.38) | **$0.38** |
| Room test | $0.52 ≥ $0.38 | **PASS** ✓ |
| T1 (50%) | entry + 2R | **$6.78** |
| T2 (25%) | whole dollar $7.00 (> T1 ✓) | **$7.00** |
| Ordering | $6.48 < $6.78 < $7.00 | ✓ |
| T2 − T1 | $7.00 − $6.78 | **$0.22** ≥ $0.08 ✓ |
| Worst-case check (§3.1.3) | at the widest admitted spread $0.02: floor = max($0.075, 3 × $0.035 = $0.105) → $0.11 | $0.22 ≥ $0.11 ✓ |
| Shares | floor($300 / $0.15) | **2,000** |
| Position value | 2,000 × $6.48 | $12,960 (within BP cap ✓) |
| Max loss if stopped | 2,000 × $0.15 | **$300** = 1.0% of equity ✓ |

> **Tension worth noting (A14):** criterion 3 puts the consolidation low *above* VWAP, and the stop sits at that low — while the invalidation rule exits on a close *below* VWAP. When the consolidation low is only slightly above VWAP, the VWAP invalidation fires before the stop is reached, so realized risk is smaller than nominal R. **Resolution:** size using `effective_stop = max(consolidation_low − 1 tick, VWAP − 1 tick)`, i.e. whichever level triggers first.

---

### 3.4 MVP Setup 3: VWAP Reclaim

**Description:** Stock dips below VWAP during pullback, then reclaims VWAP with volume — indicating buyers defending average cost basis.

#### Entry Criteria (all required)
1. Stock passes scanner hard filters
2. Stock was above VWAP for ≥ 15 minutes prior to dip
3. Dip below VWAP: ≤ 5 consecutive candles below VWAP; dip depth ≤ 2% below VWAP
4. **Trigger:** 1-min candle closes above VWAP after dip
5. Reclaim candle volume ≥ 2× average volume of dip candles
6. Price still below HOD (not chasing extended move)
7. **Room gate:** HOD (or nearest resistance) ≥ `required_room` (§3.1.2 unified test)
8. **Spread gate:** `spread_at_signal ≤ max_spread_r × R` (§3.1.3, §20.14)
9. **Consolidation / HOD proximity:** if entry is within 0.5% of HOD, require ≥ 2 candles since the dip low with high ≤ HOD — the VWAP Reclaim's consolidation requirement, added so the §2 "Max Extension from HOD" row resolves for this setup rather than delegating to a rule that does not exist here

#### Stop Placement
- `raw_stop = round_down_to_tick(max(dip_low, VWAP × 0.99)) − 1 tick` — for a long, "tighter" means the **higher** of the two candidate levels, i.e. the smaller stop distance (§20.6). Tick rounding per §20.13
- Then apply the **$0.10 minimum stop distance**, which widens the stop if `entry − raw_stop < $0.10`
- Maximum 5% of entry; if exceeded, skip

#### Exit Criteria
Per the canonical ladder (§3.1.1):
- **T1 (50%):** 2R → move stop to breakeven on remainder
- **T2 (25%):** HOD retest (guaranteed above T1 by the room gate)
- **T3 (25%):** trail 9 EMA (1-min)
- Exit remainder immediately on a close back below VWAP

#### Invalidation
- Dip lasts > 5 candles or exceeds 2% below VWAP — the setup is abandoned; no entry
- Post-entry: close back below VWAP → exit remainder (see Exit Criteria)

#### Worked Example

| Step | Derivation | Value |
|------|-----------|-------|
| VWAP | — | $3.80 |
| Above VWAP prior to dip | 18 min | ≥ 15 min ✓ |
| Dip | 4 candles below VWAP; low $3.74 | ≤ 5 candles ✓ |
| Dip depth | (3.80 − 3.74)/3.80 = **1.58%** | ≤ 2% ✓ |
| **Trigger / entry** | 1-min close back above VWAP | **$3.83** |
| Reclaim volume | 2.4× dip average | ≥ 2× ✓ |
| raw_stop | max($3.74, $3.80 × 0.99 = $3.762) − 1 tick = $3.76 − 0.01 | $3.75 |
| Min-stop check | 3.83 − 3.75 = $0.08 **< $0.10 floor** → widen | **stop = $3.73** |
| R | 3.83 − 3.73 | **$0.10** |
| Spread gate (§3.1.3) | scan: min($0.02, 0.5% × $3.83 = $0.019) = $0.01; signal: 0.15 × $0.10 = $0.015 → **$0.01** | observed $0.01 ✓ |
| HOD | nearest overhead resistance | $4.15 |
| Separation floor (§3.1.2) | max(0.5 × $0.10, 3 × ($0.01 + $0.015)) = $0.075 → $0.08 | required **$0.08** |
| Required room (§3.1.2, unified) | max(2.5 × $0.10 = $0.25, 2 × $0.10 + $0.08 = $0.28) | **$0.28** |
| Room test | (4.15 − 3.83) = $0.32 ≥ $0.28 | **PASS** ✓ |
| T1 (50%) | entry + 2R | **$4.03** |
| T2 (25%) | HOD retest (> T1 ✓) | **$4.15** |
| Ordering | $3.83 < $4.03 < $4.15 | ✓ |
| T2 − T1 | $4.15 − $4.03 | **$0.12** ≥ $0.08 ✓ |
| Shares | floor($300 / $0.10) | **3,000** |
| Position value | 3,000 × $3.83 | $11,490 (within BP cap ✓) |
| Max loss if stopped | 3,000 × $0.10 | **$300** = 1.0% of equity ✓ |

> **This example is the reason §3.1.2 exists.** Its history is worth keeping because it shows which term of the unified room requirement binds where — the proportional term at low HOD, the cost-denominated term just above it:
>
> | HOD | Room available | Binding term | Required | Outcome |
> |-----|---------------|-------------|----------|---------|
> | $4.05 | $0.22 | separation (2R + $0.08 = $0.28) | $0.28 | Rejected — insufficient room (what A15 fixed) |
> | $4.09 | $0.26 | separation (2R + $0.08 = $0.28) | $0.28 | Rejected — T1 and T2 collapse into one economic exit |
> | $4.15 | $0.32 | — | $0.28 | **Traded** |
>
> The v1.1 revision claimed the 2.5R gate solved the collapse problem. It did not: at HOD $4.09 the trade passed the gate and still produced a six-cent ladder on a $3.83 stock, and the example table recorded that separation with a ✓. Only the absolute, cost-denominated floor rejects it — and only the §3.1.3 spread gate keeps that floor honest, since at the old 1%-of-price spread allowance this trade fails even at HOD $4.15.

---

### 3.5 Additional Setups (Post-MVP)

#### Opening Range Breakout (ORB)
- **Range:** First 5 or 15 minutes (configurable; default 5 min)
- **Entry:** 1-min close above OR high (long only for MVP)
- **Stop:** OR low − 1 tick
- **Target:** OR height projected from breakout
- **Confidence:** Medium — Ross uses ORB but timeframe varies

#### Flat-Top Breakout
- **Entry:** Close above horizontal resistance (≥ 3 touches within 0.3%) on volume ≥ 2× 10-bar average
- **Stop:** Below resistance zone (now support) or pattern low
- **Target:** Measured move = pattern height

#### ABCD Pattern
- **A→B:** Initial impulse leg
- **B→C:** Pullback 38.2%–61.8% of A-B (Fibonacci)
- **C→D:** Entry at C completion; target D = C + (B − A)
- Used primarily as target-setting overlay on bull flags

#### Micro Pullback
- **Entry:** 1 red candle in strong uptrend (≥ 5 green of 6 prior), entry on next candle new high
- **Stop:** Low of red candle
- **Max pullback:** 1–2 candles, ≤ 30% of prior leg

#### First 1-Min Candle New High
- **Entry:** First 1-min candle of regular session making new high with RVOL ≥ 5×
- **Stop:** Low of that candle
- **Note:** High risk at open; requires wide spread check

#### Five-Minute Breakout
- **Entry:** 5-min close above the highest high of the prior 20 completed 5-min bars, on volume ≥ 2× the 20-bar average 5-min volume. Bars per `bars_5m` aggregation semantics (§10.1); reject windows with `source_bar_count < 3`
- **Stop:** low of the breakout 5-min bar − 1 tick, subject to the $0.10 floor and 5% ceiling
- **Target:** canonical ladder (§3.1.1), with the unified room and separation gates (§3.1.2) computed on the wider 5-min R
- **Size:** no special rule — §2.2 sizing already shrinks share count automatically as R widens

#### Halt Breakout
- **Entry:** First 1-min close above halt resumption high
- **Stop:** Low of resumption candle
- **Special:** Slippage model must account for gap; post-MVP only

#### Whole-Dollar Breakout
- **Entry:** Close above whole dollar ($5, $6, etc.) on volume spike
- **Stop:** Below whole dollar level
- **Confidence:** Low-Medium — psychological level, Ross mentions but less formal

#### Scaling Into Winners
- **Rule:** Add 25–50% of original size on the first 1-min new high **after T1 has filled** and the remaining tranche's stop has moved to breakeven
- **Constraint:** total open risk measured from *current live stops* must remain ≤ `start_of_day_equity × max_risk_pct` (§7.1.1). Never add to losers

#### Scaling Out
- **Rule:** the canonical ladder in §3.1.1 — 50% at T1 (2R), 25% at T2 (structural), 25% trailed on the 9 EMA. This applies to *all* setups; per-setup variants have been removed

---

## 4. Scanner Specification

> **§20 (Computation Semantics) governs this section too.** RVOL and its as-of semantics (§20.7), corporate-action adjustment (§20.9), and the composite score (§20.10) are defined there normatively. Where the prose below and §20 disagree, §20 wins.

### 4.1 Scanner Pipeline

**Universe sourcing (see §5.5):** full-market screening is *not* performed through IBKR. The candidate list is produced by an external screening provider; IBKR market-data subscriptions are taken only on the narrowed watchlist, within the line budget in §21.7. "Universe" below means the provider's screenable universe, not a set of IBKR-subscribed symbols.

```
Universe (US equities, common stock — external screening provider)
  → Hard Filters (reject immediately)
  → Soft Filters (score/rank)
  → Catalyst Check (manual or NLP-assisted)
  → Watchlist (top 3–5 by composite score)
```

### 4.2 Filter Definitions

| Filter | Default Threshold | Hard/Soft | Rejection Code | Rationale |
|--------|-------------------|-----------|----------------|-----------|
| Gap % | ≥ 4% premarket OR ≥ 10% daily | Hard | `GAP_TOO_SMALL` | Ross requires stocks already moving |
| Relative Volume | ≥ 5× 30-day ADV | Hard | `RVOL_TOO_LOW` | Confirms unusual interest |
| Float | ≤ 20M shares | Hard | `FLOAT_TOO_HIGH` | Supply/demand imbalance |
| Price Range | $1.00 – $20.00 | Hard | `PRICE_OUT_OF_RANGE` | Retail accessibility + volatility |
| Average Daily Volume | ≥ 500K shares/day | Hard | `ADV_TOO_LOW` | Exit liquidity |
| Premarket Volume | ≥ 100K shares (premarket session) | Soft | `PREMARKET_THIN` | Early interest signal |
| Market Cap | ≤ $2B | Soft | `MARKET_CAP_HIGH` | Small-cap focus |
| Volatility (ATR) | ATR(14) ≥ 1.5× 30-day avg ATR | Soft | `ATR_LOW` | Needs intraday movement |
| News / Catalyst | Headline present (manual/NLP) | Soft | `NO_CATALYST` | Ross requires catalyst |
| Recent Halts | Halt in last 5 days | Soft (flag) | `RECENT_HALT` | Elevated risk/opportunity |
| Circuit Breakers | Not within 10% of LULD band | Hard | `NEAR_LULD` | Avoid forced halts |
| Liquidity / Spread | Spread ≤ `min(max_spread_abs, max_spread_pct × price)` = min($0.02, 0.5%) AND bid size ≥ 100 shares. **Re-tested at signal time against R** (§3.1.3) | Hard | `SPREAD_TOO_WIDE` | Execution quality. The former "≤ 1% of price" admitted spreads costing up to 83% of R round-trip (§3.1.3) |
| Institutional Ownership | ≥ 80% | Soft (**disabled by default**) | `INST_OWN_HIGH` | See note below — retained but inert |
| Short Interest | ≥ 5% (flag only, not reject) | Soft | `HIGH_SHORT_INTEREST` | Potential squeeze fuel |

**Note on Institutional Ownership.** This filter is **off by default** and should be treated as unvalidated. Two problems: its direction was stated inconsistently (`≥ 80%` here, `> 80%` in §15 — now reconciled to `≥`), and more seriously, its *premise* is doubtful. Institutional ownership at or above 80% in a universe capped at 20M float and $2B market cap is rare; on most qualifying names the filter would never fire, and where it does fire the causation is unclear — high institutional ownership on a micro-float gapper may indicate a recent placement rather than reduced effective float. No source in Appendix A states this threshold. Enable only after the Phase 2a spike (§5.5) confirms the data exists and Phase 4b shows it discriminates. Recorded as **A22**; decided as [PLAN](PLAN.md) **D24**, where the rejected alternative was deleting the filter outright — it is kept off-by-default so the hypothesis can be tested rather than silently lost.

### 4.3 Composite Scoring (Soft Filter Ranking)

**The normative formula is §20.10** and is deliberately not restated here — duplicating it is what allowed two copies to diverge (see CHANGELOG v1.2).

Return top 5 by §20.10 score for the watchlist. User reviews top 2–3 "most obvious."

### 4.4 Scan Schedule

| Window | Frequency | Action |
|--------|-----------|--------|
| 4:00–9:30 AM ET | Every 60 sec | Premarket gap scan |
| 9:30–10:30 AM ET | Every 30 sec | Opening momentum scan |
| 10:30 AM–3:30 PM ET | Every 60 sec | Intraday refresh |
| 3:30–4:00 PM ET | Every 120 sec | Late-day (reduced) |

---

## 5. Market Data Requirements

### 5.1 Real-Time Data

| Data Type | Required | MVP | Use |
|-----------|----------|-----|-----|
| Level I (NBBO) | Yes | Yes | Quotes, spread check |
| Time & Sales | Yes | Yes | Volume confirmation, RVOL |
| Level II / Depth | Optional | No | Tape reading, halt resumption |
| Halt / LULD Status | Yes | Yes | Circuit breaker filter |
| News feed | Yes | Headline API + manual confirmation | Catalyst verification — see source/latency table below |
| 1-min bars | Yes | Yes | Pattern detection |
| 5-min bars | Yes | Yes | ORB, higher TF context |
| Daily bars | Yes | Yes | RVOL, ATR, daily chart |
| Premarket / After-hours | Yes | Yes | Gap scanning |
| Corporate actions | Yes | Yes | Split adjustment |
| Trading calendar | Yes | Yes | Session boundaries |

**Sources and latency per feed:**

| Feed | Candidate source | Expected latency | Notes |
|------|-----------------|-----------------|-------|
| L1 / NBBO, T&S | IBKR consolidated (§5.3) | 100–300 ms | Execution tier only; §21.7 line budget applies |
| 1-min / 5-min bars | IBKR `reqRealTimeBars` (5 s) aggregated locally | ≤ 1 s after minute close | 5-min derived from 1-min per §10.1, never fetched separately |
| Halt / LULD status | IBKR + Nasdaq Trade Halts feed | 1–30 s, **unreliable** | Halts are commonly reported late. Never treat absence of a halt record as evidence of no halt |
| Screening universe | External vendor (Polygon / Benzinga Pro / equivalent) | 1–15 s | Not IBKR — see §5.5. Vendor choice is a Phase 2a deliverable |
| **News headlines** | Vendor headline API (Benzinga, Polygon news, or equivalent) | **Publisher-to-API 1–60 s; API-to-system 1–5 s** | Both timestamps persisted separately (`published_at`, `received_at`, §10). Backtests filter on `received_at` only (§8.2). Free RSS sources are **not** acceptable: latency is minutes and unbounded, which on a catalyst-driven strategy means trading news the market already priced |
| Float / short interest | Vendor fundamentals; Finviz fallback (A10) | Daily, often stale | The weakest input in the system; primary Phase 2a question |
| Corporate actions | Vendor + IBKR contract details | Daily, pre-open | Must land before the first scan (§20.9) |

### 5.2 Data Quality Requirements

- **Latency budget**, decomposed into the three legs the prompt's §6.2 names separately. *These are budgets to measure against in Phase 2a, not guarantees* — IBKR routes through TWS/IB Gateway and is not a low-latency broker, and the `ib_insync`/Python path adds overhead:

| Leg | Definition | MVP budget | Measurement |
|-----|-----------|-----------|-------------|
| Data-to-signal | Bar close → signal emitted | ≤ 500 ms | Instrumented in-process; reported in §21.6 metrics |
| Signal-to-order | Signal emitted → order submitted to the API | ≤ 100 ms | In-process |
| **Order-to-exchange** | API submission → broker acknowledgement | **≤ 500 ms**, alert above 2 s | Measured as submit-to-`Acknowledged` round trip. This is the only leg the system cannot control or fully observe: IBKR does not expose exchange arrival time, so the acknowledgement round trip is an upper bound, not the true figure. Budgeted and monitored anyway, because a degrading broker path is invisible otherwise |
| **End-to-end** | Bar close → acknowledgement | **≤ 1.1 s** | The figure that actually matters for slippage; the sum is what Phase 2a must validate |

  Design signals around 1-min bar closes rather than sub-second reaction, so the strategy tolerates realistic latency (see §5.5).
- **Bar alignment:** 1-min bars aligned to exchange session boundaries
- **Split adjustment:** Apply split factors to historical volume and price before RVOL/ATR calculation
- **Missing ticks:** Forward-fill NBBO for ≤ 5 sec gaps; flag symbol as `DATA_QUALITY_DEGRADED` if > 5 sec
- **Premarket volume:** Use IBKR premarket session volume; if unavailable, estimate from T&S count
- **Halt resumption gaps:** Mark bar as `HALT_GAP` — exclude from pattern detection for 1 bar after resumption

### 5.3 IBKR Market Data Subscriptions

**Assumption:** Non-professional retail account on IBKR Pro.

| Subscription | Monthly Cost (Non-Pro) | Required For | MVP |
|--------------|------------------------|--------------|-----|
| US Securities Snapshot and Futures Value Bundle | ~$10 (waived if ≥ $30 commissions) | NYSE, NASDAQ, AMEX consolidated L1 | Yes |
| US Equity and Options Add-On Streaming Bundle | ~$4.50 | Streaming real-time (vs snapshot) | Yes |
| NASDAQ TotalView (Level II) | ~$14 | Depth of book | No (Phase 8+) |
| NYSE OpenBook | ~$5 | NYSE depth | No |
| Cboe One / IEX (free non-consolidated) | Free | Supplementary quotes | Optional |

**IBKR subscriptions alone: ~$14.50/month** (often waived with active trading commissions).

**This is not the data cost.** §5.5 concludes that full-universe screening through IBKR is likely infeasible and that an external provider is effectively mandatory. Quoting $14.50 as the data budget while the design depends on a vendor understates it structurally. Indicative all-in ranges, to be replaced by real quotes in the Phase 2a spike:

| Component | Indicative monthly | Note |
|-----------|-------------------|------|
| IBKR L1 bundles (above) | ~$14.50 | Execution tier only |
| Screening / scanner feed | **$30–$200** | Polygon Starter–Developer, Benzinga Pro, or equivalent. Wide range because requirements depend on whether real-time full-market screening or delayed-plus-narrowing is sufficient |
| News headline API | **$0–$180** | Bundled with some screening vendors; standalone Benzinga is at the top of the range |
| Float / short interest | **$0–$100** | May be bundled; free sources are unreliable (A10) |
| **Realistic MVP total** | **~$45–$500/month** | The spread is itself a Phase 2a finding: if the answer is $500, the strategy needs materially higher expectancy to clear its fixed costs |

**Verify at subscription time** — IBKR and vendor pricing both change periodically. A fixed data cost of even $100/month against a $30,000 account is a 4%/year drag before a single trade, which belongs in the §18.7 viability arithmetic rather than in a footnote.

### 5.4 Historical Data

- 30 days minimum of 1-min and daily bars per symbol (RVOL, ATR)
- 1 year daily bars for ATR baseline (optional enhancement)
- Prior day OHLC for gap calculation
- Storage: TimescaleDB hypertable or Parquet files partitioned by date

### 5.5 Data & Scanning Feasibility Risks

The scanner design (Section 4) assumes real-time, full-universe screening on gap %, RVOL, and float. This is the weakest feasibility assumption in the PRD and is easy to underestimate:

- **IBKR is not a market scanner.** The IBKR API was built for order management, not for streaming quotes across thousands of symbols. Real-time L1 subscriptions are capped (roughly ~100 concurrent market-data lines on a standard account) and the built-in scanner (`reqScannerSubscription`) offers a limited set of predefined filters that do not map cleanly onto "RVOL ≥ 5× AND float ≤ 20M AND gap ≥ 4%." Screening the whole universe every 30–60 seconds through IBKR alone is likely **not achievable**. Expect to need a dedicated screening/market-data source (e.g. Polygon, a market-data vendor, or a paid scanner) to *produce the candidate list*, with IBKR subscribed only to the narrowed watchlist for execution-grade quotes.
- **Float and short-interest data are not reliably available from IBKR.** Assumption A10 (Finviz scrape or IBKR fundamentals) means the single most important scanner filter may run on stale, missing, or inconsistent data for exactly the small-cap names the strategy targets. Split/reverse-split events (common in this universe) corrupt float and historical-volume figures if not adjusted.
- **Premarket volume is inconsistent** across feeds; the fallback estimate in §5.2 is a crutch, not a solution, and directly affects the premarket RVOL used for early entries.

**Recommended action — Phase 2a data spike (V7).** Before building the execution engine, run a short, focused spike that answers concretely: (1) can we obtain a real-time candidate list matching Section 4 filters within budget, and from which provider; (2) how fresh and accurate is float/short-interest data on a sample of recent gappers; (3) what is the *measured* data-to-signal and signal-to-order latency on paper. Treat unresolved answers here as a gate on Phase 5, not a detail to discover mid-build.

---

## 6. Execution Engine

### 6.1 Order Types Supported

| Type | Use Case |
|------|----------|
| Market | Emergency exit, halt resumption (with slippage cap) |
| Limit | Primary entry/exit; price = ask + 1 tick (buy) or bid − 1 tick (sell) |
| Stop | Hard stop placement immediately after fill |
| Stop-Limit | Stop with limit offset (default: stop − 2 ticks for sells) |
| Bracket/OCO | Entry + stop + target as atomic group |

### 6.2 Order Lifecycle

```
Signal → PreTradeRiskCheck → OrderDraft → Submit → Acknowledged → PartialFill* → Filled → PostFillReconcile
                                      ↓ reject                    ↓ cancel
                                   Rejected                     Cancelled
```

### 6.3 Pre-Trade Risk Validation

Before every order submission, verify:
1. Max risk per trade not exceeded (including open position + pending orders)
2. Daily loss limit not breached
3. Max open positions not exceeded
4. Loss-streak lockout not active
5. PDT compliance (≥ $25K equity or ≤ 3 day trades in 5 days for accounts < $25K)
6. Trading hours lockout not active
7. Symbol passes spread/liquidity check
8. No duplicate order for same signal_id

### 6.4 Partial Fill Handling

- Track cumulative filled quantity vs intended quantity
- Adjust stop/target quantities to match filled amount
- If partial fill < 50% of intended within 30 sec, cancel remainder and size stop to filled amount
- If partial fill ≥ 50%, cancel remainder only if spread widens > 2× entry spread

### 6.5 Slippage Assumptions

The prompt (§6.8) specifies "spread **+ impact**." Earlier revisions modelled ticks and spread only, which understates cost precisely where it matters: a 3,000-share order on a thin gapper does not fill at the touch. Since §18.7's viability gate is judged *net of modeled slippage*, an optimistic model biases the go/no-go decision toward "go."

```
slippage_per_share = base_ticks × tick_size
                   + spread_fraction × spread_at_signal
                   + impact
```

**Base and spread terms:**

| Scenario | `base_ticks` | `spread_fraction` |
|----------|-------------|------------------|
| Normal L1 entry | 1 | 0.50 |
| Low float (< 5M shares) | 2 | 1.00 |
| Market order exit | 2 | 1.00 |
| Stop triggered (adverse) | 2 | 1.00 |
| Halt resumption | Gap to limit price; reject if > 3% (post-MVP setup) | — |

**Impact term (new).** A square-root model, standard for equities and conservative at the order sizes this system produces:

```
impact = impact_coefficient × spread_at_signal × sqrt(order_shares / bar_volume)
```

| Parameter | Default | Bounds | Note |
|-----------|---------|--------|------|
| `impact_coefficient` | 1.0 | 0.0–5.0 | **Unvalidated.** Calibrate against real paper fills in Phase 4b (V2) |

At the §8.2 participation cap of 5% of bar volume, `sqrt(0.05) ≈ 0.224`, so impact adds ~22% of one spread — small at the cap and growing as participation rises. It is deliberately expressed as a multiple of *spread* rather than of price, so it scales with the same liquidity signal the §3.1.3 gate uses.

**Stress requirement.** Phase 4b must report the viability gate at `1×` and `2×` the calibrated slippage (V2). A strategy that only clears the gate at 1× has no margin against a model that §18.2 already describes as optimistic. Decided as [PLAN](PLAN.md) **D22**: the model previously had ticks and spread but no impact term, and because §18.7's viability gate is judged net of modeled slippage, an optimistic model biases the go/no-go decision toward "go" — the one direction in which an error costs real money.

### 6.6 Connection Failure Recovery

**See §21.2 for the full policy.** Summary:

- Protective stops and targets live at the broker as native **bracket/OCA** orders from the moment of entry fill, so protection survives client crash, disconnect, or reboot.
- On disconnect: stop generating signals, alert, and **do not attempt to cancel anything** — a disconnected client cannot send cancels, and cancelling brackets would strip protection from an open position.
- On reconnect: enter `RECONCILING` and complete §21.3 reconciliation before accepting new signals.
- Signals queued during a disconnect expire after 60 sec and are discarded, never replayed against a stale bar.

### 6.7 Duplicate Order Protection

Deduplication uses a key derived deterministically from signal identity. A UUID cannot serve this purpose: a freshly generated one is unique by construction, so a duplicate check against it can never fire.

```
idempotency_key = sha256(f"{symbol}|{setup_type}|{trigger_bar_timestamp}|{account_id}")
```

- Derived from **signal identity**, not from a random value, so the same setup on the same bar produces the same key on a retry, a restart, or a duplicate event delivery.
- Persisted **before** order submission in `idempotency_keys` (§10) with a unique constraint; the DB — not process memory — is the arbiter, so protection survives a crash mid-submission.
- Sent to IBKR as the order reference for cross-system tracing.
- `signal_id` (UUID) remains as the internal join key; it is not a deduplication mechanism.
- Executions deduplicated separately by IBKR `exec_id` (§21.3), which can legitimately repeat across reconnect replays.

### 6.8 Retry & Backoff

- Rejected orders (non-risk): retry up to 2 times with 500ms backoff
- Risk rejections: no retry; log and alert
- Rate limit: max 10 orders/minute per symbol

---

## 7. Risk Management Engine

All rules below are **hard rules** unless marked advisory. Rules marked **NON-BYPASSABLE** cannot be disabled in any configuration.

| Rule | Condition | Enforcement Point | Violation Action | Bypassable |
|------|-----------|-------------------|------------------|------------|
| Max risk per trade | **Total open risk** (all positions, measured from current live stops, plus pending orders) > `start_of_day_equity × max_risk_pct` | Pre-order | Reject order | No (**NON-BYPASSABLE**) |
| Daily loss limit | Realized + unrealized P&L ≤ −`start_of_day_equity` × daily_loss_pct | Continuous (1 sec) + post-fill | Flatten all; lock account for day | No (**NON-BYPASSABLE**) |
| Max open positions | Open positions ≥ max | Pre-order | Reject order | Configurable max only |
| Loss-streak lockout | Consecutive losses ≥ max_consecutive_losses | Post-trade close | Lock new entries; allow exits | Yes (2–5 range) |
| Max buying power | Order value > BP × max_bp_pct | Pre-order | Reject order | Yes |
| PDT check | Order would open the **4th** day trade in a rolling 5-business-day window AND equity < $25,000 (i.e. `day_trades_in_window ≥ 3` when the new one would be the 4th) | Pre-order | Reject order | No |
| Max drawdown (session) | Peak-to-trough > session_dd_pct | Continuous | Flatten all; lock account | Yes |
| Max drawdown (multi-day) | Rolling 5-day DD > multi_day_dd_pct | End of day | Lock account next day | Yes |
| Trading hours lockout | Outside the **enabled session windows**. MVP default: regular session only, 09:30–15:55 ET. Premarket (04:00–09:30) is a separate opt-in window, **disabled by default** (D11); when disabled, premarket signals are logged but never routed | Pre-order | Reject order | Yes (window bounds; DST-aware per §21.4) |
| Max correlated exposure | > 1 position sharing a **correlation group** (§7.1.3) | Pre-order | Reject order | Yes |
| Emergency kill switch | User/API trigger | Any | Flatten all; halt all trading | No |
| Min R:R ratio | Nearest overhead resistance < `required_room` at signal time (§3.1.2 unified test: the greater of `room_gate_multiple × stop_distance` and `2R + min_separation`) | Pre-order | Reject signal | **No — cannot be disabled.** `room_gate_multiple` configurable in 2.0–3.0; cannot be set below 2.0 (matches the §1 constraint). The separation term cannot be disabled at all |
| Spread check | `spread_at_signal > max_spread_r × R` (§3.1.3) — the R-denominated gate, not the scanner's price-denominated one | Pre-order | Reject order | Bounds only (0.05–0.50); cannot be disabled, because §3.1.2's separation floor consumes the same quantity |

### 7.1 Dynamic Position Sizing

See Section 2.2 for the formula.

**Equity definitions.** These must stay distinct: denominating the daily-loss threshold in an equity figure that itself includes unrealized P&L makes the threshold move as the loss accrues, so the limit can never be reached deterministically.

| Term | Definition | Used for |
|------|-----------|----------|
| `start_of_day_equity` | Account net liquidation value at 09:30 ET, snapshotted once per session and **never updated intraday** | Denominator for the daily loss limit, max risk per trade, and drawdown rules |
| `live_equity` | `start_of_day_equity` + realized P&L + unrealized P&L | Reporting, buying-power checks, and the P&L numerator |

**Position sizing uses `start_of_day_equity`**, so intraday P&L swings cannot inflate size after a winning trade (a common blow-up path).

### 7.1.1 Scaling In vs the Non-Bypassable Risk Cap

§3.5 permits adding to winners, which appeared to contradict the non-bypassable per-trade cap. The rules are reconciled as follows:

- The cap applies to **total open risk**, computed from the *current live stop* of every open position — not from the original entry risk.
- An add is permitted **only if**, after the add, total open risk still satisfies `≤ start_of_day_equity × max_risk_pct`.
- Because the stop moves to breakeven when T1 fills (§3.1.1), the original tranche contributes ~zero risk at that point, which is precisely what creates headroom for the add.
- **Consequence:** adds are only ever legal *after* T1, never while the initial position is still at full risk. This is stricter than the old "total risk ≤ 1.5× original max risk" wording, which openly violated the cap. Recorded as **A16**.

### 7.1.2 Risk State Persistence

The non-bypassable limits are meaningless if they reset on restart. `daily_state` (§10) persists `start_of_day_equity`, realized P&L, consecutive-loss count, day-trade count, and lockout flags, keyed by session date. On startup the risk engine **loads this state before accepting any signal**, and reconciles it against broker-reported positions and executions (§21.3).

### 7.1.3 Correlated Exposure

The rule was previously "> 1 position in the same sector," with `symbols.sector` having no provider and correlation not modelled at all. Sector is a **weak proxy** for the exposure that actually exists here, and the PRD should say so rather than imply coverage.

**The real exposure is co-movement, not sector.** Two low-float gappers running on the same catalyst — a sector-wide FDA headline, a short-squeeze sympathy move, a themed retail rotation — are effectively one position, and they are frequently in *different* GICS sectors. Conversely two unrelated healthcare names sharing a sector code may have no co-movement at all. A sector filter blocks the second case and misses the first.

`correlation_group` is therefore assigned per symbol per session, by the first matching rule:

| # | Rule | Source |
|---|------|--------|
| 1 | Shared catalyst — same confirmed headline or same event keyword cluster within the session | `news_headlines` (§10), set at catalyst confirmation (§11.4) |
| 2 | Sector | `symbols.sector`, populated from the screening vendor (§5.3) — **not IBKR**, which does not reliably supply it |
| 3 | Ungrouped | Symbol is its own group |

Rule 1 dominates deliberately: it is the exposure that matters and the one a sector code cannot see.

**Honest limitation.** No realized-correlation estimate is computed. Measuring intraday correlation on names with a few days of relevant history is not statistically meaningful, and a spurious estimate would be worse than an admitted proxy. With `max_open_positions` defaulting to 1 (beginner) and hard-capped at 3, the practical exposure to this gap is small — but it *is* a gap, and it grows immediately if the position cap is ever raised. Recorded as **A24**; decided as [PLAN](PLAN.md) **D21**. **This changes trading behaviour** wherever two watchlist names share a headline — the second is declined, where earlier revisions would have taken both.

### 7.2 Emergency Kill Switch

- Trigger: UI button, API endpoint, or file sentinel at `$XDG_STATE_HOME/tradipy/kill` (see §21.5 — **not** `/tmp`, which is world-writable)
- Action: Cancel all open orders → market-close all positions → set `trading_halted = true`
- Requires manual reset with confirmation phrase

---

## 8. Backtesting Framework

### 8.1 Design Principles

- **No look-ahead:** RVOL, VWAP, indicators computed on data available at signal bar close only
- **Realistic fills:** exactly one participation model governs, defined in §8.2. A second fill rule anywhere in the spec is a defect, not a refinement — two thresholds leave a band of order sizes where one says "fill fully" and the other says "cap it"
- **Backtest sizing must match live sizing:** the simulator applies the full §2.2 constraint set, including the 1%-of-ADV liquidity guard. Sizing (position-level, vs 30-day ADV) and fills (bar-level, vs bar volume) are distinct constraints and both apply. Omitting the sizing cap would let the backtest take positions the live system would refuse, biasing results optimistic in exactly the direction §18.2 warns about
- **Conservative bias:** When uncertain, assume worse fill (higher buy, lower sell)

### 8.2 Realism Requirements

| Requirement | Implementation Design |
|-------------|----------------------|
| Partial fills | **Sole fill model.** Fill qty = min(order_qty, bar_volume × `participation_rate`); default `participation_rate` = 5%. Any order exceeding 5% of the signal bar's volume is partially filled by construction — no separate trigger threshold exists |
| Order sizing in backtest | Identical to live: §2.2 formula plus BP, `max_shares_per_order`, and `max_pct_of_adv` (1% of 30-day ADV) caps |
| Slippage | Per Section 6.5 model applied to every simulated fill |
| Halt/LULD simulation | Use historical halt timestamps; no entries 5 min before known halts; resumption at next trade price + slippage |
| Look-ahead bias (features) | Enforce `as_of_time` on all feature queries; unit test with shifted data |
| **Look-ahead bias (news)** | The prompt names news timestamps alongside RVOL as the two specific traps; RVOL was rigorously handled in §20.7 and news was not. **Rule:** a headline is available to the backtest only at `news_headlines.received_at`, never `published_at`. Where only `published_at` exists (common in historical archives), apply `news_availability_lag` — default **60 seconds**, bounds 0–600 — and mark those trades `NEWS_LAG_ESTIMATED`. Publisher timestamps routinely precede retail availability, and a catalyst filter that fires on publication time buys the news before anyone could have read it |
| Premarket / opening auction | Premarket signals fill at the 09:30 open + slippage. The opening auction is **not** modelled as an ordinary bar: the 09:30 print is an auction cross, not a continuous-trading price, and its volume is not tradeable intraday liquidity. Requirements: (a) the 09:30 bar's volume is **excluded** from the §8.2 participation cap, since auction volume cannot be participated in after the cross; (b) no entry may be simulated *inside* the 09:30 bar — the earliest continuous-session entry is the 09:31 bar; (c) the auction print still counts toward session VWAP (§20.2) and HOD (§20.3). Imbalance feeds are out of scope for the MVP and recorded as **A23** |
| Corporate actions | Adjust historical prices/volumes for splits before any calculation |
| Walk-forward | Train params on 60-day window, test on next 20-day; roll forward |
| Monte Carlo | Bootstrap trade sequence 10,000 times; report 95th percentile max drawdown |

### 8.3 Required Metrics

| Metric | Definition |
|--------|------------|
| Expectancy | (win_rate × avg_win) − (loss_rate × avg_loss). **Reported net** of commissions, regulatory fees and modeled slippage; the gross figure may also be shown but the viability gate (§18.7) is judged on net |
| Sharpe Ratio | Computed on **daily** returns (aggregate all trades into a daily P&L series, including flat days), annualized by `× sqrt(252)`, `rf = 0`. Per-trade Sharpe is **not** reported: trade counts vary with opportunity, so a per-trade figure is not comparable across periods or setups and cannot be annualized without assuming a trade frequency. Daily-return Sharpe is also the only variant comparable to published benchmarks |
| Profit Factor | Gross profit / gross loss |
| Max Drawdown | Peak-to-trough equity decline |
| Win Rate | Winning trades / total trades |
| Avg Winner / Loser | Mean P&L of wins and losses |
| Holding Time Distribution | Histogram of trade duration |
| Risk-Adjusted Return | Return / max drawdown |
| Trade Count Sufficiency | Flag if **< 100 trades for any individual setup**, reported per setup rather than in aggregate — matching the §18.7 gate. An aggregate count hides the case the gate cares about: 250 Bull Flag trades and 12 VWAP Reclaims is not a validated VWAP Reclaim |
| Cost Drag | Total commissions + fees + slippage as a % of gross P&L, and as a fraction of average R (§2.2 notes ~5–10% of R at typical size) |

### 8.4 Data Requirements for Backtest

- 1-min OHLCV bars, split-adjusted, 2+ years
- Halt events per symbol per day
- News timestamps (for catalyst filter validation)
- NBBO snapshot at bar close (optional; improves slippage model)

---

## 9. System Architecture

### 9.1 Component Overview

| Component | Responsibility | Inputs | Outputs |
|-----------|---------------|--------|---------|
| **MarketDataIngestion** | IBKR connection, bar/tick aggregation | IBKR API streams | Normalized bars, quotes, halts |
| **FeatureStore** | VWAP, RVOL, EMA, ATR, pattern features | Bars, quotes | Feature vectors per symbol/time |
| **Scanner** | Universe filter and ranking | Features, config | Watchlist with scores |
| **StrategyEngine** | Pattern detection and signal generation | Watchlist, features | TradeSignal objects |
| **RiskEngine** | Pre/post trade risk enforcement | Signals, positions, config | Approved/rejected signals |
| **ExecutionEngine** | Order management via IBKR | Approved signals | Orders, fills |
| **PortfolioManager** | Position tracking, P&L | Fills, market prices | Positions, equity |
| **TradeJournal** | Record signals, trades, notes | All events | Journal entries |
| **Analytics** | Performance statistics, equity curve, per-setup expectancy, cost-drag attribution (§8.3) | Closed trades, executions, daily state | Metrics, `performance_snapshots`, viability-gate report (§18.7) |
| **Backtester** | Historical simulation | Historical data, config | Performance report |
| **Database** | Persistence and migrations for all §10 tables; enforces the uniqueness constraints the risk and idempotency rules depend on | All component writes | Durable state, query interface |
| **Configuration** | Strategy params, risk limits | YAML/DB | Config objects |
| **LoggingAudit** | Structured logs, audit trail | All events | Log streams, DB |
| **Monitoring** | Health checks, alerts | Component heartbeats | Alerts |
| **NotificationSystem** | Email/push/desktop alerts | Risk events, signals | Notifications |

### 9.2 Data Contracts

Every arrow in the §9.3 event flow carries one of the **thirteen** types below. Earlier revisions typed only `TradeSignal` and `OrderEvent`, leaving the other eleven as prose — which is how `spread_at_signal` came to gate every entry without ever being given a type or a definition.

The last two, `Alert` and `JournalEntry`, were added after a count in this paragraph claimed thirteen while eleven were defined: `NotificationSystem` and `TradeJournal` both sat at the end of §9.3 arrows carrying untyped payloads. `Alert` in particular needed a contract rather than an exemption, because §21.6 already specifies its behaviour — severity routing, Sev-1 pinning until acknowledged — which is not implementable against an undefined payload.

Field types are indicative Python; `Decimal` is used wherever a value is compared against a tick boundary or accumulated into P&L, and `float` only where the value is a ratio or score that is never rounded to a price.

#### Bar
```python
@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime      # labels the bar OPEN, UTC (§20.1)
    timeframe: str           # "1m" | "5m"
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    vwap_session: Decimal | None   # cumulative session VWAP at bar close (§20.2)
    session: str             # "premarket" | "regular" | "afterhours"
    is_revised: bool         # True if this replaced an earlier delivery (§20.1)
    has_halt_gap: bool       # first bar after resumption (§5.2)
```

#### Quote
```python
@dataclass(frozen=True)
class Quote:
    symbol: str
    timestamp: datetime      # NBBO quote time, UTC
    bid: Decimal
    ask: Decimal
    bid_size: int
    ask_size: int

    @property
    def spread(self) -> Decimal:     # §20.14
        return self.ask - self.bid

    @property
    def is_valid(self) -> bool:      # §20.14 validity + crossed-market rules
        return (self.ask > self.bid
                and self.bid_size >= 100
                and self.ask_size >= 100)
```

#### FeatureVector
```python
@dataclass(frozen=True)
class FeatureVector:
    symbol: str
    as_of: datetime          # close of the bar these were computed on (§20.7)
    vwap: Decimal | None     # None before 09:31 (§20.2)
    hod: Decimal
    premarket_high: Decimal | None
    ema_9: Decimal | None    # None until 9 bars closed (§20.5)
    rvol: float
    atr_14_daily: Decimal | None     # None if <14 sessions history (§20.15)
    adv_30d: int
    spread: Decimal | None           # from the as-of NBBO quote (§20.14)
    spread_is_stale: bool
    flagpole_height: Decimal | None  # §20.4, when a flagpole is present
```

#### ScanCandidate
```python
@dataclass(frozen=True)
class ScanCandidate:
    symbol: str
    scan_time: datetime
    score: float                     # 0–1, §20.10
    rank: int
    passed_hard_filters: bool
    rejection_codes: list[str]       # §4.2 codes; empty iff passed
    catalyst_state: str              # "confirmed" | "headline_only" | "none"
    features: FeatureVector
```

#### TradeSignal
```python
@dataclass(frozen=True)
class TradeSignal:
    signal_id: str           # UUID — join key only, NOT a dedupe key (§6.7)
    idempotency_key: str     # sha256, §6.7 — this is the dedupe key
    symbol: str
    setup_type: str          # "BULL_FLAG" | "HOD_BREAKOUT" | "VWAP_RECLAIM"
    direction: str           # "LONG" (MVP: long only)
    trigger_bar_ts: datetime
    entry_price: Decimal     # limit price
    stop_price: Decimal      # effective stop (§20.6, A14)
    target_prices: list[Decimal]     # ordered [T1, T2]; T3 is trailed
    shares: int
    r_per_share: Decimal
    required_room: Decimal   # §3.1.2 unified gate value it was judged against
    min_separation: Decimal  # §3.1.2 floor
    spread_at_signal: Decimal        # §20.14
    confidence: str          # HIGH | MEDIUM | LOW
    features: FeatureVector
```

#### RiskDecision
```python
@dataclass(frozen=True)
class RiskDecision:
    signal_id: str
    approved: bool
    reject_reason: str | None        # §7 rule name or §4.2 code
    rules_evaluated: list[str]       # every rule checked, for audit
    open_risk_before: Decimal        # total open risk from live stops (§7.1.1)
    open_risk_after: Decimal
    approved_shares: int             # may be < TradeSignal.shares after caps
    evaluated_at: datetime
```

#### OrderEvent
```python
@dataclass(frozen=True)
class OrderEvent:
    order_id: str
    signal_id: str
    symbol: str
    side: str                # "BUY" | "SELL"
    order_type: str          # §6.1
    quantity: int
    limit_price: Decimal | None
    stop_price: Decimal | None
    status: str              # PENDING, SUBMITTED, FILLED, CANCELLED, REJECTED
    filled_qty: int
    avg_fill_price: Decimal | None
    bracket_group_id: str | None     # OCA group (§21.2)
    timestamp: datetime
```

#### Fill
```python
@dataclass(frozen=True)
class Fill:
    exec_id: str             # IBKR-assigned; the dedupe key (§21.3)
    order_id: str
    symbol: str
    side: str
    fill_price: Decimal
    fill_qty: int
    commission: Decimal
    fees: Decimal            # SEC/TAF — required for net metrics (§8.3)
    timestamp: datetime
```

#### Position
```python
@dataclass
class Position:
    position_id: str
    signal_id: str
    symbol: str
    state: str               # §20.12 state machine
    quantity: int            # remaining, after partial exits
    original_quantity: int
    avg_cost: Decimal
    current_stop: Decimal
    broker_stop_order_id: str | None  # None is a Sev-1 (§21.6)
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    adopted: bool            # adopted by reconciliation (§21.3)
    opened_at: datetime
    closed_at: datetime | None
```

#### ClosedTrade
```python
@dataclass(frozen=True)
class ClosedTrade:
    trade_id: str
    signal_id: str
    symbol: str
    setup_type: str
    entry_price: Decimal         # volume-weighted across entry fills
    exit_price: Decimal          # volume-weighted across all exit legs
    shares: int
    gross_pnl: Decimal
    commission: Decimal
    fees: Decimal
    net_pnl: Decimal             # the figure §18.7 is judged on
    r_multiple: Decimal          # computed on NET P&L, not gross
    exit_reason: str             # LADDER_COMPLETE | STOPPED_OUT | INVALIDATED
                                 # | BAILED_OUT | EOD_FLAT | KILL_SWITCH
    spread_estimated: bool       # §20.14 — excluded from the gate if True
    opened_at: datetime
    closed_at: datetime
```

#### BacktestResult
```python
@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    config_hash: str         # ties results to exact parameters (§21.5)
    start: date
    end: date
    setups: list[str]
    trades: list[ClosedTrade]
    metrics_net: dict        # §8.3, net of commissions/fees/slippage
    metrics_gross: dict      # shown alongside; never the gate basis
    spread_estimated_trades: int     # excluded from the gate (§20.14)
    viability_gate: dict     # per-criterion pass/fail (§18.7)
```

#### Alert
```python
@dataclass(frozen=True)
class Alert:
    alert_id: str
    raised_at: datetime
    severity: str                # "sev1" | "sev2" | "info" — §21.6
    category: str                # "unprotected_position" | "kill_switch" |
                                 # "risk_breach" | "data_gap" | "signal" | "fill"
    symbol: str | None
    message: str
    dedupe_key: str              # identical keys collapse; a flapping condition
                                 # must not generate one alert per bar
    requires_ack: bool           # True for every sev1 (§11.2 pins until acked)
    acknowledged_at: datetime | None
    channels: list[str]          # "desktop" | "email" | "push" — routed by §11.2
```

#### JournalEntry
```python
@dataclass(frozen=True)
class JournalEntry:
    entry_id: str
    trade_id: str                # FK to the ClosedTrade / Position
    written_at: datetime
    setup: str
    entry_snapshot: dict         # FeatureVector at signal, frozen for review
    decision_trace: list[str]    # ordered gate outcomes, incl. rejection codes
    outcome_r: Decimal | None    # None while the position is open
    user_note: str | None        # the only user-authored field
```

### 9.3 Event Flow

Every arrow is annotated with the §9.2 type it carries:

```
IBKR ──Bar, Quote──▶ MarketDataIngestion ──Bar, Quote──▶ FeatureStore
                                                              │
                                                        FeatureVector
                                                              ▼
                                                          Scanner
                                                              │
                                                       ScanCandidate
                                                              ▼
                                                      StrategyEngine
                                                              │
                                                         TradeSignal
                                                              ▼
                                                   RiskEngine (pre-trade)
                                                              │
                                                        RiskDecision
                                                              ▼
                                    ExecutionEngine ──OrderEvent──▶ IBKR
                                              ▲                       │
                                              └────────Fill───────────┘
                                                              │
                                                              ▼
                                              PortfolioManager ──Position, JournalEntry──▶ TradeJournal
                                                              │
                                                        ClosedTrade
                                                              ▼
                                                          Analytics

RiskEngine, ExecutionEngine, Monitoring ──Alert──▶ NotificationSystem ──Alert──▶ UI / email / push
```

`Backtester` consumes historical `Bar`/`Quote` and emits `BacktestResult`, driving the same `StrategyEngine` and `RiskEngine` instances as live — which is what makes §8.1's "backtest sizing must match live sizing" enforceable by construction rather than by discipline.

### 9.4 Technology Stack (Recommended)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.11+ | Per PDF requirement |
| IBKR | ib_insync | Async event model, active community |
| Database | PostgreSQL + TimescaleDB | Time-series bars; production grade |
| MVP Database | SQLite | Local dev simplicity |
| Config | YAML + pydantic validation | Type-safe, readable |
| Logging | structlog → JSON | Structured audit trail |
| Task queue | asyncio (MVP); Redis (prod) | Event-driven architecture |
| Packaging | pyproject.toml + uv | Match sibling project conventions |

---

## 10. Database Design

### 10.1 Schema

#### `symbols`
| Column | Type | Notes |
|--------|------|-------|
| symbol | VARCHAR(16) PK | |
| float_shares | BIGINT | Updated daily; provider per A10 |
| avg_daily_volume_30d | BIGINT | |
| sector | VARCHAR(64) NULL | From the screening vendor (§5.3), not IBKR. NULL is expected and handled — see §7.1.3 rule 3 |
| correlation_group | VARCHAR(64) NULL | Session-scoped grouping key (§7.1.3); catalyst cluster takes precedence over sector |
| last_updated | TIMESTAMP | |

#### `bars_1m` (TimescaleDB hypertable)
| Column | Type | Notes |
|--------|------|-------|
| symbol | VARCHAR(16) | PK part |
| timestamp | TIMESTAMPTZ | PK part |
| open, high, low, close | DECIMAL | |
| volume | BIGINT | |
| vwap | DECIMAL | Computed |
| session | VARCHAR(16) | premarket, regular, afterhours |

#### `bars_5m` (TimescaleDB continuous aggregate)
*Required by §5.1 (5-min bars listed as MVP), ORB, and the Five-Minute Breakout; previously absent despite three sections depending on it.*

| Column | Type | Notes |
|--------|------|-------|
| symbol | VARCHAR(16) | PK part |
| timestamp | TIMESTAMPTZ | PK part; labels the bar **open**, aligned to 09:30 (§20.1) |
| open, high, low, close | DECIMAL | |
| volume | BIGINT | |
| session | VARCHAR(16) | |
| source_bar_count | SMALLINT | How many 1-min bars aggregated; < 5 means gaps |

**Aggregation semantics (normative).** 5-min bars are derived from `bars_1m`, never fetched independently, so the two can never disagree:

- **Boundaries** are anchored to the regular-session open (09:30, 09:35, …), *not* to wall-clock multiples of five. Premarket 5-min bars anchor to 04:00.
- `open` = open of the first available 1-min bar in the window; `close` = close of the last; `high`/`low` = extremes across available bars; `volume` = sum.
- **Missing minutes do not shift boundaries.** A window with fewer than five 1-min bars still produces one 5-min bar, with `source_bar_count` recording the shortfall. A window with **zero** bars produces no row (consistent with §20.1's "no trades, no bar").
- A 5-min bar is **closed** only when the 1-min bar covering its final minute has closed (§20.1 grace period applies once, at the 1-min level).
- Any setup evaluating 5-min bars must reject windows where `source_bar_count < 3` as `BAR_INCOMPLETE` — a 5-min "breakout" built from two prints is noise.

#### `halt_events`
*Required by §8.4 ("halt events per symbol per day"), the §4.2 recent-halt filter, and §8.2 halt simulation; previously had no home.*

| Column | Type | Notes |
|--------|------|-------|
| halt_id | UUID PK | |
| symbol | VARCHAR(16) | Indexed with `halted_at` |
| halted_at | TIMESTAMPTZ | |
| resumed_at | TIMESTAMPTZ NULL | NULL while still halted |
| halt_code | VARCHAR(16) | LUDP (LULD pause), T1/T2 (news), M (market-wide), etc. |
| resumption_price | DECIMAL NULL | First trade price after resumption |
| source | VARCHAR(32) | Feed that reported it; halts are frequently reported late or not at all |

#### `news_headlines`
*Catalyst is a scored input to §20.10 and a §4.2 filter, yet the only prior storage was a free-text `watchlists.catalyst` column — which cannot support the look-ahead controls in §8.2.*

| Column | Type | Notes |
|--------|------|-------|
| headline_id | UUID PK | |
| symbol | VARCHAR(16) | |
| **published_at** | TIMESTAMPTZ | Publisher's stated time |
| **received_at** | TIMESTAMPTZ | When *this system* received it. **Backtests filter on `received_at`, never `published_at`** (§8.2) |
| headline | TEXT | |
| source | VARCHAR(64) | |
| url | TEXT NULL | |
| confirmed_by_user | BOOLEAN NULL | Set by `tradipy catalyst` (§11.4); NULL = not reviewed |
| confirmed_at | TIMESTAMPTZ NULL | |

#### `signals`
*Missing from v1.0 despite `orders.signal_id` and `closed_trades.signal_id` being declared foreign keys — there was no table to reference.*

| Column | Type | Notes |
|--------|------|-------|
| signal_id | UUID PK | |
| symbol | VARCHAR(16) | |
| setup_type | VARCHAR(32) | BULL_FLAG, HOD_BREAKOUT, VWAP_RECLAIM |
| trigger_bar_ts | TIMESTAMPTZ | Bar that produced the trigger (§20.1) |
| status | VARCHAR(16) | GENERATED, APPROVED, REJECTED, SUPERSEDED, EXPIRED, FILLED |
| reject_reason | VARCHAR(48) NULL | Risk or filter code |
| superseded_by | UUID NULL | Winning signal when arbitration applies (§20.11) |
| entry_price | DECIMAL | Intended |
| stop_price | DECIMAL | Effective stop (§20.6, A14) |
| target_prices | JSONB | Ordered ladder [T1, T2] |
| shares | INT | |
| room_gate_multiple | DECIMAL | Value at signal time |
| required_room | DECIMAL | §3.1.2 unified gate value; records which term bound |
| min_separation | DECIMAL | §3.1.2 floor the signal was judged against, in dollars |
| spread_at_signal | DECIMAL | §20.14. Input to `min_separation` and the §3.1.3 gate; also the calibration record for `est_round_trip_cost_per_share` (A18) |
| spread_estimated | BOOLEAN | True when NBBO was unavailable and §20.14's backtest substitute was used; excluded from the §18.7 gate |
| features | JSONB | RVOL, VWAP, HOD, flagpole height as-of signal |
| created_at | TIMESTAMPTZ | |
| **UNIQUE** | (symbol, setup_type, trigger_bar_ts) | Prevents duplicate signals per bar |

#### `daily_state`
*Required so the non-bypassable risk limits survive a restart (§7.1.2).*

| Column | Type | Notes |
|--------|------|-------|
| session_date | DATE PK | |
| start_of_day_equity | DECIMAL | Immutable snapshot (§20.8) |
| realized_pnl | DECIMAL | |
| consecutive_losses | INT | |
| day_trades_in_window | INT | Rolling 5 business days (PDT) |
| trading_halted | BOOLEAN | Kill switch / daily-loss lockout |
| halt_reason | VARCHAR(48) NULL | |
| updated_at | TIMESTAMPTZ | |

#### `idempotency_keys`
| Column | Type | Notes |
|--------|------|-------|
| idempotency_key | CHAR(64) PK | sha256 per §6.7 |
| signal_id | UUID FK | |
| order_id | UUID NULL | Populated after submission |
| created_at | TIMESTAMPTZ | Written **before** broker submission |

#### `orders`
| Column | Type | Notes |
|--------|------|-------|
| order_id | UUID PK | |
| signal_id | UUID FK | |
| symbol | VARCHAR(16) | |
| side | VARCHAR(4) | |
| order_type | VARCHAR(16) | |
| quantity | INT | |
| limit_price | DECIMAL | |
| stop_price | DECIMAL | |
| status | VARCHAR(16) | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

#### `executions`
| Column | Type | Notes |
|--------|------|-------|
| execution_id | UUID PK | |
| order_id | UUID FK | |
| **exec_id** | **VARCHAR(64) UNIQUE** | **IBKR-assigned; idempotent dedupe across reconnect replays (§21.3)** |
| fill_price | DECIMAL | |
| fill_qty | INT | |
| commission | DECIMAL | |
| fees | DECIMAL | Regulatory (SEC/TAF) — needed for net-of-cost metrics (§8.3) |
| timestamp | TIMESTAMPTZ | |

#### `positions`
| Column | Type | Notes |
|--------|------|-------|
| position_id | UUID PK | |
| signal_id | UUID FK | |
| symbol | VARCHAR(16) | |
| quantity | INT | |
| avg_cost | DECIMAL | |
| **state** | **VARCHAR(20)** | **Position state machine (§20.12): OPEN_FULL, T1_FILLED, TRAILING, …** |
| current_stop | DECIMAL | Live stop; moves to breakeven at T1 (§3.1.1) |
| broker_stop_order_id | VARCHAR(32) NULL | Broker-side bracket leg; NULL is a Sev-1 (§21.6) |
| unrealized_pnl | DECIMAL | |
| adopted | BOOLEAN | Set when reconciliation adopts an untracked broker position (§21.3) |
| opened_at | TIMESTAMPTZ | |
| closed_at | TIMESTAMPTZ NULL | |

#### `closed_trades`
| Column | Type | Notes |
|--------|------|-------|
| trade_id | UUID PK | |
| signal_id | UUID | |
| symbol | VARCHAR(16) | |
| setup_type | VARCHAR(32) | |
| entry_price | DECIMAL | |
| exit_price | DECIMAL | |
| shares | INT | |
| pnl | DECIMAL | |
| r_multiple | DECIMAL | |
| opened_at | TIMESTAMPTZ | |
| closed_at | TIMESTAMPTZ | |

#### `journal_entries`
| Column | Type | Notes |
|--------|------|-------|
| entry_id | UUID PK | |
| trade_id | UUID FK NULL | |
| entry_type | VARCHAR(16) | signal, trade, note, risk_event |
| content | TEXT | |
| metadata | JSONB | |
| timestamp | TIMESTAMPTZ | |

#### `watchlists`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| date | DATE | |
| symbol | VARCHAR(16) | |
| score | DECIMAL | |
| rank | INT | |
| catalyst | TEXT | |
| filters_passed | JSONB | |

#### `strategy_config`
| Column | Type | Notes |
|--------|------|-------|
| config_id | UUID PK | |
| name | VARCHAR(64) | |
| parameters | JSONB | |
| active | BOOLEAN | |
| created_at | TIMESTAMPTZ | |

#### `performance_snapshots`
| Column | Type | Notes |
|--------|------|-------|
| snapshot_id | UUID PK | |
| date | DATE | |
| equity | DECIMAL | |
| daily_pnl | DECIMAL | |
| win_rate_30d | DECIMAL | |
| max_drawdown | DECIMAL | |
| metrics | JSONB | |

#### `audit_log`
| Column | Type | Notes |
|--------|------|-------|
| log_id | UUID PK | |
| event_type | VARCHAR(32) | |
| component | VARCHAR(32) | |
| payload | JSONB | |
| timestamp | TIMESTAMPTZ | |

---

## 11. User Interface

### 11.1 User Journeys (Functional Flow)

The interface exists to serve these flows; the layouts in §11.3 follow from them.

**Primary journey — scanner to journal (one trade, MVP path):**

| # | Step | Actor | System behaviour | Artifacts |
|---|------|-------|-----------------|-----------|
| 1 | Session start | System | 09:30 broker sync → `start_of_day_equity` snapshot (§20.8). No trading until it succeeds | `daily_state` row |
| 2 | Scan | System | External provider screens the universe; hard filters reject with codes, soft filters score (§20.10); top 5 to watchlist | `watchlists` rows |
| 3 | Catalyst confirmation | **User** | Reviews top 2–3 headlines and confirms or rejects each. **The one required manual step in the MVP** (§12.2 item 6); unconfirmed symbols score 0.5 or 0.0 and typically fall out of the top ranks | `watchlists.catalyst` |
| 4 | Setup identification | System | Strategy engine evaluates the 3 MVP setups on closed 1-min bars; arbitrates collisions by §20.11 priority | `signals` row (`GENERATED` / `SUPERSEDED`) |
| 5 | Pre-trade gating | System | Room gate (§3.1.1), separation floor (§3.1.2), then all §7 risk rules. Rejections carry a reason code | `signals.status`, `signals.reject_reason` |
| 6 | Entry | System | Limit order + native bracket (stop, T1, T2) submitted atomically; idempotency key written **before** submission (§6.7) | `orders`, `idempotency_keys`, `executions` |
| 7 | Management | System | T1 fill → stop to breakeven; T2 fill → `TRAILING` with broker-mirrored 9 EMA stop (§21.2); breakout-or-bailout timer runs from entry | `positions.state` transitions |
| 8 | Exit | System | Ladder completes, stop fills, or invalidation fires | `closed_trades` with `r_multiple` |
| 9 | Journal | **User** | Reviews auto-logged trade; optionally adds a note | `journal_entries` |
| 10 | Session end | System | 15:55 flat-all (§21.4); daily snapshot written | `performance_snapshots` |

**Secondary journeys:**

| Journey | Trigger | Flow |
|---------|---------|------|
| Risk lockout | Daily loss limit, loss streak, or drawdown breach | System flattens and locks → user sees reason in risk panel → lock persists across restart (§7.1.2) and cannot be cleared by relaunching |
| Emergency stop | User pulls the kill switch | Cancel orders → market-close all → `trading_halted` → manual reset requires a confirmation phrase (§7.2) |
| Crash recovery | Process restart, mid-session | Load `daily_state` → reconcile against broker (§21.3) → adopt untracked positions for review → ensure every position has a live protective stop → only then resume signals |
| Backtest / validation | User runs Phase 4b validation | Select range and setups → run → review net expectancy, win rate, drawdown, cost drag → compare against the §18.7 viability gate |
| Parameter change | User edits a threshold | Bounds-validated at load (§21.5); non-bypassable limits rejected outside legal range; change hashed into `audit_log` so any trade traces to the exact config that produced it |
| Post-session review | End of day | Statistics screen: equity curve, per-setup expectancy, cost drag, rejection-reason histogram |

### 11.2 Framework Recommendation

**PySide6 (Qt for Python)** — native desktop, excellent table/widget support, embeds pyqtgraph for charts. Alternative: Tauri + Python backend (more complex setup).

### 11.3 Screen Layouts

#### Trading Dashboard (Primary)
```
+-------------------------------------------------------------+
| [Account: $30,000] [Daily P&L: +$120] [Risk: 1%/3%] [KILL]  |
+-------------------------------------------------------------+
|  WATCHLIST (Top 5)    |  CHART (1-min + VWAP + 9 EMA)        |
|  Symbol | Chg | RVOL   |                                     |
|  XYZ    | +42%| 12x    |                                     |
|  ABC    | +18%|  8x    |                                     |
+-------------------------------------------------------------+
|  ACTIVE SIGNALS       |  ORDERS & POSITIONS                  |
|  Bull Flag XYZ $5.16  |  Pos | Symbol | P&L | Stop | Target  |
+-------------------------------------------------------------+
|  RISK PANEL: Daily loss used 40% | Streak: 0 | Positions: 1  |
+-------------------------------------------------------------+
```

*(Account figure matches A5/D10; the signal price matches the corrected §3.2 worked example.)*

#### Statistics / Equity Curve
- Equity curve with drawdown shading; per-setup breakdown
- Metrics table per §8.3, reported **net** of commissions, fees and slippage, with the gross figure shown alongside
- Cost-drag panel: total frictions as a % of gross P&L and as a fraction of average R
- Holding-time histogram; trade-count sufficiency warning below 100 trades per setup
- Viability-gate status (§18.7): pass/fail per criterion, not a single aggregate number

#### Notifications / Alerts
- Live alert feed with severity; Sev-1 items (unprotected position, kill switch, risk breach) pinned until acknowledged
- Per-channel routing (desktop, email, push) configurable by severity
- Alert inventory per §21.6, each showing last-fired time so a silent channel is visibly silent rather than assumed healthy

#### Scanner View
- Filter configuration panel (all Section 4 thresholds)
- Live scan results table with rejection reason codes
- Catalyst verification checkbox per symbol

#### Backtesting Interface
- Date range selector, setup toggles, parameter overrides
- Run backtest → equity curve, metrics table, trade list
- Walk-forward and Monte Carlo report tabs

#### Trade Journal
- Chronological log of signals, entries, exits, risk events
- Manual note entry per trade
- Filter by setup type, date, P&L

#### Settings / Parameter Editor
- All Section 2 thresholds with validation bounds
- Risk limits (non-bypassable limits shown as locked)
- IBKR connection settings

### 11.4 MVP UI

CLI-only for MVP:

| Command | Purpose |
|---------|---------|
| `tradipy scan` | Run scanner, print ranked watchlist with scores and rejection codes |
| `tradipy catalyst` | **Catalyst confirmation** — the one required manual step (§11.1 step 3, §12.2 item 6). Lists each watchlist symbol with its headline(s) and prompts `confirm / reject / skip`; writes `watchlists.catalyst` and the `catalyst_confirmed` score component (§20.10). Non-interactive form: `tradipy catalyst --set SYMBOL=confirmed`. Symbols left unconfirmed score 0.0 and are not traded |
| `tradipy trade --paper` | Enable strategy engine in paper mode |
| `tradipy status` | Positions, P&L, risk utilization |
| `tradipy journal` | View/add journal entries |

Without `tradipy catalyst` the MVP definition is unsatisfiable: §12.2 item 6 requires a full session with no manual intervention *except* catalyst confirmation, and there was previously no command that performed it.

Desktop GUI deferred to Phase 8.

---

## 12. Development Roadmap & MVP

### 12.1 Phase Map

| Phase | Scope | Complexity | Dependencies | Risk |
|-------|-------|------------|--------------|------|
| 0 | Research + thresholds | Low | — | Source ambiguity |
| 1 | Architecture, config, data contracts | Medium | 0 | — |
| 2 | Market data ingestion + quality checks | High | 1, IBKR account | IBKR API complexity |
| **2a** | **Data feasibility spike (§5.5)** — can we source a real-time candidate list matching §4 filters, how reliable is float data, what is measured latency | Medium | 2 | **May prove IBKR-only scanning infeasible and require a data vendor** |
| 3 | Scanner (hard filters) | Medium | **2a (gate passed)** | Float data availability — resolved by 2a before this phase starts (D29) |
| 4 | Strategy engine (3 MVP setups) | High | 3 | Discretion proxies |
| **4b** | **Lightweight strategy validation** — historical replay of the 3 MVP setups with modeled slippage/fees; produce expectancy, win rate, drawdown | Medium | 4, historical data | **Setups may show no edge** |
| **Viability Gate** | Section 18.7 go/no-go: positive net expectancy over ≥100 trades/setup, out-of-sample. **If failed, stop or iterate — do not build execution** | — | 4b | — |
| 5 | Execution + pre-trade risk | High | 4b (gate passed), IBKR paper | Order routing |
| 6 | Full risk engine | Medium | 5 | — |
| **MVP Gate** | Paper trade: scan + 3 setups + risk + CLI journal | — | 6 | — |
| 7 | Full backtesting with realism (halts, Monte Carlo, walk-forward) | Very High | 4b, historical data | Halt simulation |
| 8 | Desktop GUI (PySide6) | High | MVP | — |
| 9 | Parameter optimization / walk-forward | High | 7 | Overfitting |
| 10 | Production hardening, monitoring | Medium | 8 | — |

**Sequencing note (revised from the prompt's Phase order):** The architect prompt places all backtesting at Phase 7, *after* the paper-trading MVP gate. That is risky — it commits significant effort to an execution stack before any evidence the setups have an edge. This roadmap therefore splits backtesting in two: a **lightweight validation (Phase 4b)** that must pass the **Viability Gate (Section 18.7)** *before* the execution engine is built, and the **full realism backtester (Phase 7)** — Monte Carlo, halt simulation, walk-forward optimization — which remains later. Phase 4b needs only historical bars and the Section 8 no-look-ahead/slippage rules, not the live order stack, so it is cheap to run early and is the single highest-value de-risking step in the plan.

### 12.2 MVP Definition

**MVP is complete when:**
1. Scanner produces ranked watchlist using all hard filters
2. Bull Flag, HOD Breakout, and VWAP Reclaim generate signals with full rule compliance
3. Risk engine enforces all non-bypassable rules in paper trading
4. Orders route to IBKR paper account with bracket stops
5. CLI journal records all signals and trades
6. User can paper trade a full session without manual intervention (except catalyst confirmation)

**Prerequisite before MVP go-live:** the Phase 4b lightweight validation must pass the Section 18.7 Viability Gate. Paper trading a system with no demonstrated edge only defers the question.

**Explicitly NOT in MVP:**
- Desktop GUI
- Full realism backtester (Phase 7) — the lightweight Phase 4b validation *is* required, however
- Level II data
- Halt breakout setup
- News NLP automation
- Multi-setup concurrent positions

### 12.3 Estimated Timeline (Single Developer)

| Phase | Duration |
|-------|----------|
| 1–2 | 3–4 weeks |
| **2a — data feasibility spike (§5.5)** | **1–2 weeks** (was unbudgeted) |
| 3–4 | 3–4 weeks |
| 4b — lightweight validation + viability gate | 1–2 weeks |
| 5–6 | 2–3 weeks |
| **MVP total** | **10–15 weeks** (arithmetic sum of the above) |
| 7–10 | +16–20 weeks |

*The total is the arithmetic sum of its rows. It excludes any vendor-integration work the §5.5 spike may prove necessary, and excludes iteration time if the Viability Gate fails.*

---

## 13. Assumptions Register

Per the architect prompt §6.13, each assumption states the consequence if wrong **and a recommended alternative**. The alternatives column was previously present inline for only about four of twenty entries.

**On registers and where rationale lives.** Three identifier registers run through these documents: **A-ids** (assumptions, below), **V-ids** (validation requirements, §15), and **D-ids** (decisions, in [PLAN.md](PLAN.md)). The first two are defined and referenced within the PRD, so they stay closed by construction. D-ids were not: nineteen of twenty-four had no inbound reference from this document, which meant an implementer reading only the PRD saw the rule and none of the reasoning — including, for every behaviour-changing decision, the alternative that was considered and rejected. That reasoning is what prevents a rule from being tuned away later by someone who encounters only its inconvenient consequences.

The convention is now: **wherever this document states a decided value, it cites the D-id and carries enough of the rationale to be actionable in place.** The PLAN remains the authority on how a decision was reached; the PRD must not require a reader to go there to avoid making a mistake. Decisions that change trading behaviour — D17 (§3.1.2), D18 (§20.5/§21.2), D19 (§20.13), D20 (§3.1.3), D21 (§7.1.3), D22 (§6.5), D24 (§4.2) — are marked as such at the point of use.

| ID | Assumption | Consequence if Wrong | Recommended Alternative |
|----|------------|---------------------|------------------------|
| A1 | Ross's 5× RVOL / 10% daily / $1–$20 / ≤20M float remain valid criteria | Scanner may miss or include wrong stocks | Re-fit each threshold against Phase 4b outcome data; treat the source values as priors, not constants. Widen float to ≤50M before widening price |
| A2 | 2:1 R:R minimum produces positive expectancy at ~50% win rate | Whole system may have no edge (V1, V3) | Measure realized win rate per setup at 2R; if below ~40%, test a 1.5R T1 with a correspondingly higher required win rate, or abandon the setup. Do **not** lower R:R to rescue a failing win rate without re-testing |
| A3 | Manual catalyst verification acceptable for MVP | False positives from pump-and-dump increase | Keyword NLP over `news_headlines` as a *pre-filter* that ranks rather than decides, keeping the human confirmation step (§11.4). Full automation only after loss attribution shows catalyst quality is not a loss driver (V6) |
| A4 | Long-only for MVP (Ross primarily trades long) | Forgoes the short side, which on failed gappers is often the higher-probability trade | Add short setups post-MVP with a separate locate/borrow-availability gate; do not reuse long sizing logic, since borrow cost and hard-to-borrow status change the economics |
| A5 | **$30,000** account assumed for sizing examples — deliberately above the $25,000 PDT minimum | At exactly $25K, the first loss triggers PDT restriction before the daily loss limit binds | Implement a sub-PDT mode enforcing ≤ 3 day trades per rolling 5 days, or use a cash account with T+1 settlement tracking. Both are strictly better than trading at $25K with no PDT headroom |
| A6 | ib_insync remains maintained and compatible with IBKR API | May need migration mid-project | Isolate all broker calls behind a single adapter interface so the native `ibapi` is a drop-in replacement. Cost of the abstraction now is far below the cost of a scattered migration later |
| A7 | 3% above VWAP extension limit approximates Ross's "don't chase" rule | May enter too early or too late vs discretionary trader | ATR-normalised extension (§14.3, Alt B): `> 2 × ATR(14) from VWAP = skip`. Adapts to the name's own volatility; adopt once §20.15 ATR is available and validated |
| A8 | 30-day RVOL lookback chosen for faster regime adaptation (the architect prompt's own §7.4 example cites 50-day ADV) | Different lookback changes the candidate set | Run both 30-day and 50-day in Phase 4b as a parameter sweep and select on out-of-sample expectancy, not on which produces more candidates |
| A9 | Non-professional IBKR data pricing (~$14.50/mo, plus screening vendor per §5.3) | Professional classification increases costs ~10× | Confirm non-pro status in writing before Phase 2. If classified professional, the free Cboe One / IEX tier plus a vendor feed is likely cheaper than IBKR consolidated |
| A10 | Float data from IBKR fundamental data or Finviz scrape | Stale/missing float → the single most important filter runs on bad data | Paid vendor float (Polygon, Benzinga, Nasdaq Data Link) — this is a primary question for the Phase 2a spike (V7). Interim: cross-check two free sources and reject on disagreement > 20% rather than trusting either |
| A11 | Top 2–3 "most obvious" gappers outperform lower-ranked | Trades a suboptimal symbol vs Ross | Log outcomes by rank in Phase 4b. If rank does not predict expectancy, drop the top-N restriction and let the risk engine's position cap do the selecting |
| A12 | Breakout-or-bailout (3 candles) approximates Ross's patience threshold | May exit winners early or hold losers too long | Sweep 2–5 candles in Phase 4b; consider a volume-conditioned variant (extend the timer while breakout volume persists) rather than a fixed bar count |
| A13 | Bull-flag volume should **contract** in the flag (≤ 70% of flagpole average) | If contraction is the wrong read, the filter rejects valid high-volume consolidations | Threshold is configurable; test 50%, 70%, 90% and no-filter as a four-way sweep |
| A14 | For VWAP-invalidated setups, the **effective** stop is `max(pattern_stop, VWAP − 1 tick)` | Sizing overstates risk-per-share; realized R differs from nominal R | Alternative: drop the VWAP invalidation for setups whose pattern stop already sits above VWAP, removing the double trigger rather than reconciling it. Simpler, at the cost of slower exits on failed reclaims |
| A15 | Room gate requires resistance ≥ **2.5R** so T1 and T2 are meaningfully separated | Superseded in part by A18 — the multiple alone does not achieve separation | The unified requirement in §3.1.2 (`max(2.5R, 2R + min_separation)`) is the recommended form. Retained here because the proportional term still binds on wide-R setups |
| A16 | Adds are legal only after T1 fills and the stop moves to breakeven | Stricter than Ross, who may add before the first target; reduces upside participation | Alternative: permit a pre-T1 add sized so total open risk stays under the cap (a smaller add than 25–50%). More faithful to the source, materially more complex to enforce; defer until the base ladder is validated |
| A17 | Premarket trading disabled by default in MVP (D11) | Forgoes premarket gap continuation entries | Enable premarket as an explicit opt-in window with its own VWAP anchor (§20.2) and a wider spread allowance, only after regular-session expectancy is proven |
| A18 | T2 must clear T1 by an **absolute, cost-denominated** floor (§3.1.2), not by a multiple of R | If `est_round_trip_cost_per_share` is too high the gate rejects viable trades; too low and the ladder degrades to an effective 75/25 after costs | Calibrate against real fills in Phase 4b using `signals.spread_at_signal` and `executions.commission`/`fees`. If the rejection rate exceeds ~40% of otherwise-valid setups, prefer reducing `sep_cost_multiple` to 2.0 over abandoning the floor |
| A19 | A resting broker-side stop is always present, including during `TRAILING`, amended upward each bar close (§21.2) | Repeated amendment failure protects at a stale level, giving back more than the live EMA would | The alternative — a purely local trail — voids the §21.2 guarantee whenever the client dies, which is strictly worse. If amendment proves unreliable, replace the EMA trail with a static trailing-percentage order native to IBKR, accepting a cruder trail for a broker-enforced one |
| A20 | Tick size is $0.01 for the entire tradeable universe, and all rounding is conservative (§20.13) | Holds while the §2 price floor stays at $1.00 | If the floor is ever lowered below $1.00, implement sub-penny tick rules per SEC Rule 612 before any level is computed. Simpler alternative: keep the $1.00 floor permanently |
| A21 | Spread caps of min($0.02, 0.5% of price) at scan and 0.15 × R at signal make the §3.1.2 floor achievable (§3.1.3) | Too tight and the system rarely trades; too loose and costs exceed the edge, as the former 1%-of-price cap did | Measure the realized spread distribution on qualifying names during the Phase 2a spike, then set `max_spread_r` to the level that retains ~70% of otherwise-valid signals. Prefer trading less to trading at negative expectancy |
| A22 | The ≥80% institutional-ownership filter is unvalidated and **off by default** (§4.2) | If enabled on a false premise it silently shrinks the candidate set for no benefit | Leave disabled. Remove the filter entirely if Phase 4b shows no expectancy difference between high- and low-ownership names |
| A23 | The opening auction is modelled as a non-participable print: excluded from the fill cap, no entries inside the 09:30 bar (§8.2) | Backtests that fill inside the auction overstate achievable liquidity at the open | Obtain imbalance feed data and model the cross explicitly — expensive and out of MVP scope. Interim alternative: exclude the first 5 minutes from backtests entirely and measure how much of the strategy's return depended on them |
| A24 | Shared catalyst, then sector, is an adequate proxy for correlated exposure; realized correlation is not modelled (§7.1.3) | Two co-moving names are treated as independent positions, so true exposure is up to `max_open_positions` × nominal risk rather than the cap | Adequate while `max_open_positions ≤ 3`. If the cap is ever raised, compute rolling intraday return correlation over the session and group above a 0.7 threshold — but only once enough same-session history exists for the estimate to mean anything |
| A25 | The one-tick clamp on the §3.1.3 spread gates is sufficient protection for the `min_stop_distance` ↔ `max_spread_r` coupling | Below `R = tick_size / max_spread_r` ($0.067 at defaults) the signal-time gate would floor to $0.00 and reject every trade. The clamp converts a total silent outage into a merely permissive gate on very tight stops — it does not make those trades economically sound, since a 1-tick spread against a sub-$0.07 R is still ~30% of R round-trip | Enforce the coupling directly: require `min_stop_distance ≥ 2 × tick_size / max_spread_r` as a config-load validation rather than relying on the clamp, so an unsound combination fails at startup instead of trading. Deferred because it adds a cross-parameter validator before there is a config loader to put it in |

---

## 14. Strategy Validation & Discretion Analysis

### 14.1 Source Review Summary

**Consistently taught principles (High confidence):**
- Trade stocks already moving (not hoping they will move)
- 5× RVOL minimum, 10% daily change, $1–$20 price, low float
- News catalyst required
- 2:1 reward-to-risk minimum
- Daily max loss is inviolable
- VWAP as primary intraday reference
- Bull flag as core pattern
- Focus on top 2–3 leading percentage gainers

**Isolated examples (not strict rules):**
- Specific stocks (AVTX, GME) with exceptional moves
- GameStop exception to float rule due to unique catalyst
- Anticipating breakouts (early entry before confirmation)

### 14.2 Discretion Register

| Element | Why Subjective | Deterministic Alternative A | Alternative B | Recommended | AI Candidate |
|---------|---------------|----------------------------|---------------|-------------|--------------|
| Reading momentum/tape | Requires real-time order flow interpretation | Breakout volume ≥ 2× average | Bid/ask size ratio > 2 at entry | Alt A for MVP | Yes |
| Healthy pullback | Visual assessment of candle quality | Pullback ≤ 50% of flagpole | Pullback ≤ 61.8% Fibonacci | Alt A | Yes |
| Candle quality | Marubozu vs doji judgment | Breakout body ≥ 60% of candle range | Close in top 25% of range | Alt A | Yes |
| Market sentiment | Broad market context | SPY above VWAP = risk-on | SPY 5-min trend positive | Alt A (soft filter) | Yes |
| Volume strength | "Heavy" vs "light" volume | Absolute: vol ≥ 2× 20-bar avg | Relative: z-score ≥ 1.5 | Alt A | No |
| "Too obvious" / crowded | Fear of late entry | Skip if up > 100% without fresh catalyst today | Skip if float rotation > 5× | Alt A | Yes |
| Clean charts | Visual clutter assessment | Max 3 direction changes in 20 bars | No HOD break in last 10 bars before setup | Alt A | Yes |
| Conviction / setup quality | Holistic gut feel | Composite score ≥ 0.7 | Require 2+ optional confirmations | Alt A | Yes |
| Extended move | "Too far" judgment | > 3% above VWAP = skip | > 2× ATR(14) from VWAP = skip (§20.15) | Alt A | No |
| Skip valid setup | Contextual pass | Auto-skip if daily loss > 50% utilized | Auto-skip if 2 consecutive losses | Alt A | No |

### 14.3 Trade-offs and Discretionary Reading

The architect prompt's §7.3 and §2 Core Principle require, for each discretionary element, the **advantages and disadvantages of each alternative** and **how experienced traders typically interpret it**. §14.2 gave neither; both are below.

The "how traders read it" column is characterisation from the sources in Appendix A, not measurement. It is included because it identifies *what the proxy is trying to approximate*, which is the only way to tell whether a proxy is failing by being too loose or too tight.

| Element | Alt A — advantages / disadvantages | Alt B — advantages / disadvantages | How experienced traders read it |
|---------|-----------------------------------|-----------------------------------|--------------------------------|
| Reading momentum/tape | **+** Computable from bars alone; no L2 subscription. **−** Volume is a lagging, one-bar summary; misses the ask-side absorption that actually signals buyer commitment | **+** Closer to what a tape reader sees. **−** Requires L2 (~$14/mo, Phase 8+), and size can be spoofed or pulled in the sub-second window before the fill | As *pressure*, not volume: whether offers are being lifted faster than they refresh. Neither proxy captures rate; both capture aggregate |
| Healthy pullback | **+** Matches the source's stated 50% rule; simple. **−** A hard boundary makes a 51% retrace fail identically to a 90% one | **+** 61.8% Fib admits deeper but still-valid flags, raising candidate count. **−** Deeper retraces have materially lower follow-through; loosens the setup's identity toward "any dip" | Depth *and shape* jointly: a shallow drift on falling volume is healthy, a sharp 40% flush on rising volume is not. Both proxies see depth only — which is why the §3.2 crit. 5 volume-contraction test carries most of the weight |
| Candle quality | **+** Body/range ratio is a direct measure of conviction within the bar. **−** Penalises bars with a long lower wick that were bought back aggressively — often the strongest bars | **+** Close-in-top-quartile handles the bought-back case correctly. **−** Admits small-bodied bars with a long upper wick, i.e. rejection | Directionally the same thing: did the bar close where buyers wanted it. Alt B is arguably the better proxy; Alt A is recommended only because it is already used by the §3.2 breakout test and a second convention would fragment the spec |
| Market sentiment | **+** One binary, cheap, no extra data. **−** SPY is a poor proxy for small-cap risk appetite; low-float gappers routinely run on red SPY days | **+** Trend is less noisy than a single level. **−** Same wrong-index problem, with added lag | Via small-cap tape specifically: are *other* gappers holding their highs today. IWM or a breadth measure over qualifying names would be a better proxy than SPY; neither alternative offers it (**gap acknowledged**) |
| Volume strength | **+** Absolute multiple is interpretable and matches source language. **−** A fixed 2× multiple means different things at different times of day; 2× at 09:35 is unremarkable, 2× at 14:00 is significant | **+** Z-score normalises for time-of-day and regime. **−** Needs a stable variance estimate that thin names do not provide; unstable on exactly the universe in scope | Relative to *what this stock has been doing in the last few minutes*, not to a daily average. Alt B is closer in principle and fails in practice on low float |
| "Too obvious" / crowded | **+** Cheap, and up-100%-without-catalyst is a genuine late-stage marker. **−** Arbitrary threshold; a stock up 300% on a real catalyst is excluded while one up 80% on nothing passes | **+** Float rotation directly measures how much of the float has already changed hands. **−** Depends on float data that A10 flags as unreliable for this universe | As exhaustion: whether the move has already paid everyone who was going to buy. Float rotation is the better proxy and is gated on data quality, not on logic |
| Clean charts | **+** Direction-change count is computable and roughly tracks choppiness. **−** No trader has ever counted direction changes; it is a proxy for a gestalt, and a weak one | **+** "No recent HOD break" at least encodes a real structural idea. **−** Excludes valid continuation setups that broke HOD ten bars ago | As predictability of structure — whether levels are respected. This is the **weakest proxy in the register** and both alternatives are admitted approximations |
| Conviction / setup quality | **+** Single 0–1 number, comparable and rankable (§20.10). **−** Composes five inputs whose weights are guesses; a high score can be earned entirely on premarket volume | **+** Requiring 2+ confirmations is transparent about what qualified the trade. **−** Discrete and coarse; no ranking between qualifying setups | As a *bet size* signal, not a binary. Neither alternative varies size with conviction, because §7 caps risk uniformly — a deliberate simplification (**gap acknowledged**) |
| Extended move | **+** 3% above VWAP is fixed and easy to reason about. **−** A fixed percentage ignores the stock's own volatility; 3% is enormous on a quiet name and trivial on one running 40% | **+** ATR-normalised adapts to the name. **−** Requires §20.15 ATR to be defined and available; adds a warm-up dependency | Relative to the day's range and the pace of the move. Alt B is the better proxy; Alt A is recommended for the MVP only because it has no data dependency. **Revisit in Phase 4b** |
| Skip valid setup | **+** Ties the skip to an objective risk state already tracked. **−** Mechanical: skips a good setup because of unrelated earlier losses | **+** Loss-streak trigger is closer to the psychological reason the rule exists. **−** Overlaps the §7 loss-streak lockout, creating two rules for one behaviour | As state management, not signal quality — a trader stepping away rather than judging the chart. Both proxies encode the intent adequately |

**Elements with no adequate proxy** — recorded rather than papered over: market sentiment (wrong index), clean charts (no real proxy), and conviction-scaled sizing (deliberately not implemented). These are the three most likely places for the §18.4 discretion gap to be real.

---

## 15. Validation Matrix

| Strategy Concept | Ross Teaching | Deterministic Rule | Conf. | Assumptions | Alternatives |
|------------------|---------------|-------------------|-------|-------------|--------------|
| Relative Volume | ≥ 5× average volume | RVOL ≥ 5× 30-day ADV at signal time on 1-min bars | Medium | 5× is a community proxy (Ross rarely states an exact multiple, per the architect prompt's §7.4); source example uses **50-day** ADV, PRD assumes 30-day (A8) | 3× or 10×; z-score; 50-day lookback |
| Daily % Change | Already up 10% | daily_change ≥ 10% OR premarket_gap ≥ 4% | High | Continuation exception for prior-day movers | 8% threshold |
| Price Range | $1–$20 | $1.00 ≤ price ≤ $20.00 | High | Exceptions for obvious leaders | $2–$50 |
| Float | Low float preferred | float ≤ 20M shares (prefer ≤ 10M) | High | 20-20 rule | ≤ 50M |
| News Catalyst | Must have headline | Manual confirm OR NLP keyword match (soft) | Medium | MVP manual | Benzinga API auto |
| Gap Scanner | Premarket gappers | gap ≥ 4% from prior close in premarket | Medium | 4% is book premarket proxy | 10% daily only |
| Bull Flag | Flagpole + pullback + breakout | Section 3.2 rules | High | 50% max retrace | 61.8% Fib retrace |
| HOD Breakout | First candle new high | Close > prior HOD on volume ≥ 1.5× consolidation avg | High | HOD tracked on highs, trigger confirmed on **close** — resolved in §20.3 | Wick break (rejected) |
| VWAP Reclaim | Buyers defend VWAP | Close above VWAP after ≤ 5 bar dip ≤ 2% depth | Medium | Dip depth limit | No depth limit |
| ORB | Opening range break | 5-min close above OR high; stop at OR low | Medium | 5-min OR chosen | 15-min OR |
| Flat-Top Breakout | Horizontal resistance break | ≥ 3 touches within 0.3%; close above on 2× vol | Medium | Touch count | 2 touches |
| ABCD | Fibonacci measured move | C at 38.2–61.8% retrace; D = C + (B−A) | Medium | Standard Fib levels | Fixed 50% retrace |
| Micro Pullback | 1 red in uptrend | 1 red candle; entry on next new high; stop at red low | Medium | Single candle only | 2 red candles |
| 1-Min New High | First candle new high | First 1-min bar new HOD with RVOL ≥ 5× | Medium | Open volatility | Skip first 5 min |
| 5-Min Breakout | Higher TF breakout | 5-min close > 20-bar high on 2× 20-bar avg volume; stop at breakout bar low (§3.5) | Medium | 5-min bars derived from 1-min per §10.1 aggregation semantics | 15-min TF |
| Scaling In | Add to winners | Add 25–50% of original size on first new high **after T1 fills and the stop is at breakeven**; total open risk from live stops must stay ≤ `start_of_day_equity × max_risk_pct` (§7.1.1) | High | Adds are illegal while the initial tranche is at full risk (A16) | Fixed add size |
| Scaling Out | Partial profits | Canonical ladder §3.1.1: 50% at T1 (2R), 25% at T2 (structural), 25% trailed on 9 EMA — subject to the §3.1.2 separation floor | High | One ladder for all setups (D12) | All-out at 2R |
| Stop Loss | Low of pattern | Setup-specific pattern level (§3.2–3.4), then widened to the $0.10 floor; sizing uses `effective_stop` = whichever level triggers first (§2.2, A14); skip the trade if distance > 5% of entry | High | Bull Flag has no VWAP stop branch — its flag low is above VWAP by construction (§3.2) | ATR-based stop |
| Profit Target | 2:1 minimum | T1 = 2R; T2 = nearest structural level above T1; T3 = trail 9 EMA (§3.1.1) | High | Separation floor §3.1.2 applies | Fixed $ targets |
| Position Sizing | Risk-based | `shares = floor(start_of_day_equity × risk% / effective_stop_distance)`, capped by BP, `max_shares_per_order`, and 1% of 30-day ADV (§2.2) | High | Frozen start-of-day denominator, not live equity (D16) | Fixed share count |
| Daily Loss Limit | Stop when max loss hit | Flatten all when realized + unrealized ≤ −`start_of_day_equity` × `daily_loss_pct`; lock account (§7.1) | High | Beginner 2% / experienced 3%; frozen denominator (D16) | Fixed $ amount |
| Max Losses | Three strikes | Lock entries after 3 consecutive losses | High | — | 2 or 5 losses |
| Risk Management | Cap losses | All Section 7 rules enforced pre-order | High | — | — |
| Trade Journal | Record trades | Auto-log all signals/fills; manual notes | High | — | — |
| Statistics | Track performance | Daily snapshot: equity, win rate, PF, DD | High | — | — |
| Halt Breakout | Trade resumption | Post-MVP: entry on close above resumption high | Low | Complex slippage | Skip halts entirely |
| Premarket Gappers | Scan premarket | Premarket scan 4:00–9:30; gap ≥ 4% + vol | Medium | — | Regular hours only |
| Momentum Continuation | Second day mover | Prior day +10% AND holding prior close ± 5% | Medium | Continuation exception | — |
| Whole-Dollar Break | Psychological levels | Close above whole $ on 2× vol | Low | — | — |
| Pullback Entry | Generic pullback | ≥ 3 green, 1–3 red, ≤ 50% retrace, new high entry | Medium | Overlaps bull flag | — |
| Low Float Momentum | Float + volume | float ≤ 20M AND RVOL ≥ 5× (scanner filter) | High | — | — |
| Relative Volume (scanner) | Volume in play | RVOL ≥ 5× as hard scanner filter | High | — | — |
| High-of-Day | New high entry | HOD breakout rules Section 3.3 | High | — | — |
| News Catalysts | Breaking news | Headline required; manual MVP | Medium | — | NLP auto |
| Circuit Breakers | Avoid LULD | Reject if within 10% of LULD band | Medium | LULD data from IBKR | — |
| Liquidity | Adequate volume | ADV ≥ 500K; spread ≤ min($0.02, 0.5% of price) at scan and ≤ 0.15 × R at signal (§3.1.3) | Medium | The former "spread ≤ 1%" admitted round-trip spread costs up to 83% of R | ATR-relative spread cap |
| Short Interest | Squeeze potential | Flag if ≥ 5%; no reject | Low | — | — |
| Institutional Ownership | Effective float | Soft flag if **≥ 80%** — **disabled by default**, premise unvalidated (§4.2 note, A22) | Low | Rarely fires in a ≤20M-float universe; unsourced | Remove entirely if Phase 4b shows no discrimination |

---

## 16. Confidence Report

### High Confidence (implement objectively)
- Scanner hard filters as mechanisms (gap, float, price, ADV) — the *existence* of each filter is well-grounded; specific cut-offs vary (see Medium)
- Bull flag pattern rules
- HOD breakout rules
- 2:1 R:R enforcement
- Position sizing formula
- Daily loss limit and max risk per trade
- VWAP calculation and reclaim (with dip depth assumption)
- Scaling out schedule
- Three-strikes rule

### Medium Confidence (reasonable assumptions)
- RVOL multiple (5×) and lookback (30-day) — 5× is a community proxy, not an exact Ross figure; source example uses 50-day
- VWAP extension limit (3%)
- Premarket gap threshold (4%)
- ORB timeframe (5 min)
- Catalyst automation (NLP keyword)
- "Obvious" stock ranking via pct_change
- Breakout-or-bailout (3 candles)
- Max extension from HOD without consolidation

### Low Confidence (heavy discretion; approximate)
- Halt breakout trading
- Whole-dollar breakout as standalone setup
- Tape reading / Level II interpretation
- "Clean chart" assessment
- Conviction scoring
- Anticipating breakouts (early entry)
- Exact premarket volume threshold

---

## 17. Known Limitations

| Limitation | Why It Exists | Performance Impact | Mitigation | Future AI |
|------------|---------------|-------------------|------------|-----------|
| Tape reading | Ross uses L2 and time & sales for entry timing | May enter late or on false breakouts | Volume spike confirmation; breakout-or-bailout | Yes |
| Catalyst quality assessment | Distinguishing real news from pump | Losses on junk catalysts | Manual verification MVP; keyword NLP v2 | Yes |
| "Obvious" stock selection | Discretionary ranking of top gappers | May trade suboptimal symbol vs Ross | Rank by pct_change × RVOL composite | Yes |
| Anticipating breakouts | Ross sometimes enters before confirmation | Better cost basis but higher false rate | MVP requires close confirmation only | Yes |
| Halt/resumption trading | Extreme slippage and gap risk | High variance; hard to backtest | Defer to post-MVP | Yes |
| Market context (SPY) | Ross considers broad market | Long on weak market days underperform | SPY > VWAP soft filter | No |
| Pattern quality scoring | Visual chart assessment | Mixed-quality setups pass filters | Composite score + min confirmations | Yes |

---

## 18. Strategy Viability & Open Risks

This section responds to the architect prompt's directive to "challenge assumptions" and "identify hidden complexities and risks." Everything above specifies *how* to trade the methodology deterministically; this section is a deliberate counterweight that asks *whether* it is worth trading at all. Nothing here has been empirically validated — it is a register of the assumptions and structural risks that must be tested before any capital, paper or real, is committed.

### 18.1 The central unproven premise

The economic foundation of the entire system is assumption **A2**: that a 2:1 reward-to-risk minimum produces positive expectancy at roughly a 50% win rate. This is asserted, not demonstrated. Two cautions:

- At a 50% win rate and a *realized* 2:1 payoff, gross expectancy is +0.5R per trade — attractive on paper. But mechanically enforcing a 2:1 target tends to *lower* the win rate: more distant targets are hit less often, and fixed stops at pattern lows are hit frequently on noisy low-float names. The true win rate at a 2:1 target is an empirical unknown and could easily fall below the ~40% breakeven point (where 0.4 × 2R − 0.6 × 1R = +0.2R gross, still positive, but fragile once costs are added).
- The 2:1 figure is a risk-management convention, not evidence of edge. Positive expectancy must come from the *entry signal's* directional accuracy, which this PRD assumes rather than measures.

### 18.2 Cost and slippage erosion

Theoretical edge on sub-$20, low-float names is unusually exposed to frictions the backtest must model honestly (see Section 8):

- **Slippage dominates.** The Section 6.5 model (1–2 ticks + 50–100% of spread) is optimistic for thin names during fast momentum bursts and halt resumptions, where realized slippage of several percent is common. On a strategy targeting ~$0.20 moves, a few cents of slippage per side is a large fraction of expected R.
- **Commissions and regulatory fees** (SEC/TAF, plus IBKR per-share pricing) are small individually but compound across a high-frequency intraday style with scaling in/out (each partial is a fill).
- A plausible erosion example: a gross +0.5R/trade edge can turn negative once round-trip slippage + fees exceed ~0.5R, which on tight stops is not a high bar. This must be quantified, not assumed away.

### 18.3 Structural risks of the low-float universe

- **Halts and LULD** interrupt exits and create gap risk that the MVP explicitly defers (halt breakout is post-MVP), yet halts can occur *while holding* any position, not only when trading resumptions.
- **Liquidity is state-dependent:** the spread and depth that pass the scanner filter at signal time can evaporate at the moment of exit, precisely when a stop is triggered.
- **Adverse selection / pump-and-dump:** many low-float gappers are promotional. Manual catalyst verification (A3) is the only defense in the MVP and is itself discretionary and error-prone.
- **Regime dependence:** the strategy needs a daily supply of qualifying gappers. In quiet small-cap tapes, the scanner returns few or no candidates and realized performance may bear little resemblance to backtests run over hot periods. Backtests must span at least one full boom/quiet cycle.

### 18.4 The discretion gap

The system replaces Ross Cameron's real-time judgment (tape reading, "clean chart," conviction, "too obvious") with deterministic proxies (Sections 14, 17). It is plausible that a meaningful part of the discretionary trader's edge *lives in exactly the judgment we removed.* The automated system should therefore be treated as a distinct strategy whose expectancy is unknown, not as a faithful clone with known results.

### 18.5 Source-quality caveat

The methodology's public performance claims originate substantially from a trading-education business (Warrior Trading). Such figures are marketing materials: not independently audited, and subject to survivorship and selection bias (winning examples are more visible than losing ones). Taught results must not be treated as expected results for this system.

### 18.6 Open risks register

| ID | Open risk | Why it threatens viability | How to resolve before risking capital |
|----|-----------|----------------------------|----------------------------------------|
| V1 | Expectancy unproven (A2) | Whole system may have no edge | Backtest ≥ 100 trades per MVP setup; report expectancy net of modeled costs |
| V2 | Slippage worse than modeled | Erases edge on thin names | Calibrate slippage model against real paper fills; stress-test ±2× |
| V3 | Win rate below breakeven at 2:1 | Negative net expectancy | Measure realized win rate per setup in backtest and paper |
| V4 | Regime dependence | Backtest over-fit to hot periods | Walk-forward across boom and quiet tapes; out-of-sample gate |
| V5 | Discretion proxies underperform | Automated ≠ discretionary edge | Compare proxy signals to manually-tagged setups on a sample |
| V6 | Catalyst/pump false positives | Cluster of avoidable losses | Track loss attribution to catalyst quality; tighten filter |
| V7 | Data/scan feasibility (see §5.5) | Signals miss or arrive late | Phase 2a data spike before committing to execution build |

### 18.7 Viability gate (go / no-go before real capital)

No real money should be committed until, at minimum: backtest and paper trading each show **positive expectancy net of modeled slippage and fees** over **≥ 100 trades per MVP setup**; results hold **out-of-sample** (walk-forward) and across at least one quiet-market period; and Monte Carlo 95th-percentile max drawdown stays within the account's risk tolerance. Failing any of these, the correct decision is to iterate on the signal or stop — not to trade a specified-but-unvalidated system.

---

## 19. Acceptance Criteria Checklist

**Self-assessment only.** These boxes were ticked by the document's author. A cold review in v1.1 found four arithmetic errors inside the §3 worked examples and roughly a dozen internal contradictions — all of which had been sitting behind a fully-checked list. The lesson is recorded rather than hidden: **a self-certified checklist is not evidence.** Final sign-off requires PLAN Workstream 11 by someone other than the author.

| Verification status | |
|---|---|
| Author self-assessment | ✓ complete (below) |
| Independent review | ☐ **outstanding** |
| Worked examples recomputed | ✓ v1.1 (four arithmetic errors fixed) |
| Cross-section consistency sweep | ✓ v1.2 (see note below) |
| Independent review of v1.2 | ✓ [REVIEW-v1.2.md](REVIEW-v1.2.md) — 23 defects; addressed in v1.3 |
| Spread/separation joint calibration | ✓ v1.3 (§3.1.3), with the worst-case invariant now a fixture |
| Independent review of v1.3 | ✓ [REVIEW-v1.3.md](REVIEW-v1.3.md) — 6 defects, one blocking (rounding direction); addressed in v1.3.1 |
| Independent review of v1.3.1 | ☐ **outstanding** — no round has yet been run by a reader with no prior context |
| Machine-checkable example fixtures | ✓ built and green (`tests/test_worked_examples.py`, `tests/test_poc.py`; §3.2 driven from a bar series via §20.4) |
| Parameter registry check | ✓ built and green (`tests/test_parameter_registry.py`, `tradipy.params`) |
| Rounding-direction assertions | ✓ built and green (`tests/test_boundary.py` polarity marks; direction is read from the registry, not named at the call site) |
| Independent review of the **code** | ✓ [REVIEW-2026-07-28.md](REVIEW-2026-07-28.md) — four unenforced guarantees, all reproduced by execution; fixed in package v0.1.0. See [CHANGELOG](CHANGELOG.md) v1.3.2 |
| Enforcement fixtures (fifth defect class) | ✓ `tests/test_enforcement.py` — for each documented guarantee, the test that performs the violation it forbids |

**Four defect classes, not one.** The self-assessment below has been wrong in a different way each round, and the pattern is worth stating plainly because it bears on how much the checkmarks are worth:

| Round | Class | Why the previous fix could not see it |
|-------|-------|---------------------------------------|
| v1.1 | **Arithmetic** — examples violating their own rules | — |
| v1.2 | **Consistency** — a threshold restated in two places, one updated | Recomputing the examples against the *new* value confirmed the examples and never asked whether the document agreed with itself |
| v1.3 | **Joint incoherence** — two individually-correct parameters that cannot both hold | Every value appeared exactly once, so a parameter registry passes it clean |
| v1.3.1 | **Generalization** — a rule stated more broadly than its justification supports | The rule appeared once, the tables applying it were arithmetically correct, and the boundary fixture passed. Only the prose and the tables disagreed — and prose comparison is the one check that does not mechanize |

The durable fixes are the §21.1 fixture suite and the parameter registry, which is why they appear above as outstanding rather than complete. They close the four classes that have occurred; they are not an argument that a fifth does not exist. The full correction record is in [CHANGELOG.md](CHANGELOG.md), and PLAN Workstream 11 carries the checks.

- [x] ~~Every setup in Section 4 has fully specified entry, exit, stop, target, and invalidation rules~~ — **met for 3 of 14 tradeable setups; deliberate deviation for the remaining 11.** Post-MVP setups in §3.5 carry entry, stop and target but no invalidation rules, worked examples, or false-signal patterns. This is a considered choice, not an oversight: see PROMPT-REVIEW §3.6 on why the prompt's demand for full depth across every listed component produces uniform shallowness. Ticking this box unqualified would be exactly the presence-over-correctness failure that §19's preamble warns about

  > **On the denominator.** The prompt's §4 bullets **26 items** and calls them "components," not setups. Twelve are not tradeable setups at all — Gap scanner, Relative volume, Low float momentum, News catalysts (scanner filters); Scaling into winners, Scaling out (position management); Risk management, Daily loss limits, Maximum number of losses, Position sizing (risk rules); Trade journaling, Statistics (operations). The criterion's own "where applicable" qualifier excludes them: there is no stop placement for Statistics. The correct denominator is the **14 tradeable setups** in §3.1, and all twelve non-setup components *are* fully specified elsewhere (§4.2, §3.1.1, §7, §8.3, §10). Earlier revisions of this document cited 27 setups and "~24 remaining"; both were wrong.
- [x] Section 3 thresholds populated with proposed defaults, confidence ratings, and source notes
- [x] Every identified discretionary element has at least one recommended deterministic implementation and a documented alternative
- [x] Validation Matrix covers all major components and contains no empty "Deterministic Rule" cells
- [x] Risk rules specify enforcement point and violation action; daily loss limit and max risk-per-trade are hard (non-bypassable)
- [x] Backtest design explicitly addresses the realism items in Section 6.8
- [x] MVP scope defined: scanner + 3 highest-confidence setups + risk + basic CLI journal
- [x] All assumptions listed in Section 13 with consequences
- [x] A software engineer unfamiliar with Ross Cameron can begin MVP implementation without clarifying questions on trading logic

---

## 20. Computation Semantics (Normative)

**This section governs.** Every indicator, level, and derived term used in Sections 3, 4, and 7 is defined here. Where prose elsewhere in this document conflicts with this section, this section wins. Nothing in this section is optional or illustrative — it is the contract between the spec and the code.

### 20.1 Bar Timing and Labeling

| Rule | Specification |
|------|--------------|
| Bar timestamp | Labels the bar's **open** (a bar stamped 10:31:00 covers 10:31:00.000–10:31:59.999) |
| Signal evaluation | Only on **closed** bars. In-progress (partial) bars never trigger entries |
| Bar close detection | A 1-min bar is considered closed when either the next bar's first tick arrives or `bar_open + 60s + grace_period` elapses (`grace_period` default 750ms) |
| Late / revised bars | IBKR may revise a bar after delivery. A revision arriving **after** a signal has fired on that bar does not retroactively cancel the signal; it is logged as `BAR_REVISED` for audit. Revisions arriving before evaluation replace the bar |
| Missing bars | A session minute with no trades yields no bar. Pattern counts ("3 consecutive candles") count **available bars**, not wall-clock minutes; a gap > 2 minutes invalidates any in-progress pattern |
| Timezone | All bar timestamps stored UTC, evaluated in `America/New_York` (DST-aware, §21.4) |

### 20.2 VWAP

```
VWAP_t = Σ(typical_price_i × volume_i) / Σ(volume_i)   for i in [session_start, t]
typical_price_i = (high_i + low_i + close_i) / 3
```

| Question | Answer |
|----------|--------|
| Session start | **09:30:00 ET.** VWAP resets at the regular-session open |
| Does it include premarket volume? | **No.** Regular-session VWAP excludes 04:00–09:30 entirely |
| Premarket VWAP | A *separate* series anchored at 04:00 ET, used only when premarket trading is enabled (D11, off by default) |
| Bar source | 1-min bars; typical price as above (not close-only) |
| Value used at signal time | VWAP as of the **close of the signal bar** — never a partial-bar value |
| Before first bar closes | VWAP is undefined until the 09:30 bar closes; no VWAP-dependent setup can fire before 09:31 |

### 20.3 High of Day (HOD)

| Question | Answer |
|----------|--------|
| Definition | Highest **traded price** of the regular session so far |
| Wick or close? | HOD is tracked on **highs** (wicks). But the *breakout trigger* requires a **close** above it — resolving the "wick break vs close" alternative left open in §15 in favour of close-confirmation |
| Premarket high included? | **No** for regular-session HOD. Premarket high is tracked separately as `PMH` and used as an additional resistance level in the room gate |
| Updated | On every completed bar |
| "Not the opening print" (§3.3 crit. 2) | The 09:30 bar's high does not by itself establish a tradeable HOD; at least one *subsequent* bar must set a higher high |

### 20.4 Flagpole Height and Measured Move

```
flagpole_low    = LOW of the first candle in the flagpole sequence
flagpole_high   = HIGH of the last candle before the flag begins
flagpole_height = flagpole_high − flagpole_low
measured_move   = entry_price + flagpole_height
retrace_pct     = (flagpole_high − flag_low) / flagpole_height
```

Flagpole detection: the longest run of consecutive green candles (close > open) ending immediately before the flag, subject to §3.2 criterion 2. Ties broken by taking the **longest** qualifying run; if two runs tie in length, take the one with greater volume.

### 20.5 EMA

```
EMA_9(t) = close_t × k + EMA_9(t−1) × (1 − k),  k = 2/(9+1) = 0.2
```

- **Seeding:** simple average of the first 9 available regular-session 1-min closes. The EMA is not valid (and no EMA-dependent trail is active) until 9 bars have closed.
- Premarket bars are **excluded** from the regular-session EMA.
- Trail evaluation is **close-only** — an intrabar dip below the EMA does not trigger.
- The trailing stop **ratchets**: it only ever moves up, never down.
- The ratcheted level is **mirrored to a resting broker-side stop order** and amended on each bar close (§21.2). The EMA is computed locally; the protection is not. A position in `TRAILING` with no live broker stop is a Sev-1 (§21.6), identical to any other unprotected position. Decided as [PLAN](PLAN.md) **D18** — the rejected alternative was to accept the exposure and document it, which would have made §21.2's "protection lives at the broker" guarantee silently expire at exactly the state where a position is most likely to be left unattended.

### 20.6 "Tighter" and "Wider"

For a long position: **tighter** = higher stop price = smaller `stop_distance`; **wider** = lower stop price = larger distance. Where a rule says "whichever is tighter," take `max()` of the candidate stop prices; "wider" takes `min()`. The $0.10 minimum-distance floor is applied **after** this selection and can only widen the result (§2, §3.4).

### 20.7 RVOL and As-Of Semantics

```
RVOL_t = cumulative_session_volume(session_start → t) / avg_daily_volume_30d
```

- Only volume **through the close of the signal bar** may be used. No forward volume, no full-day totals — enforced by an `as_of_time` parameter on every feature query and unit-tested with shifted data (§8.2).
- `avg_daily_volume_30d` is computed from the 30 completed sessions **before** the current one, split-adjusted (§20.9).
- Premarket RVOL uses the separate premarket baseline in §2.1.

### 20.8 Start-of-Day Equity

Snapshot of broker net liquidation value taken at the **first successful broker sync at or after 09:30:00 ET**, persisted to `daily_state`, and immutable for the remainder of the session. If the broker is unreachable at 09:30, the system remains in `NO_TRADE` state until a snapshot succeeds — it does not fall back to a stale or computed value, because every non-bypassable risk limit is denominated in it.

### 20.9 Corporate Actions

Split and reverse-split factors are applied to **all** historical prices and volumes before any indicator computation (RVOL, ATR, ADV, EMA). A symbol with a corporate action effective within the lookback window and no adjustment factor available is marked `DATA_QUALITY_DEGRADED` and excluded from the scanner that session.

### 20.10 Composite Score (normalized)

Inputs of different magnitude must be normalized before summing, and the result must land in 0–1 so it is directly comparable to the `score ≥ 0.7` conviction gate in §14.2:

```
score = 0.30 × norm_pct_change
      + 0.30 × norm_rvol
      + 0.20 × float_inverse
      + 0.10 × norm_premarket_vol
      + 0.10 × catalyst_confirmed

norm_pct_change     = min(pct_change / 50.0, 1.0)        # 50% daily change = full marks
norm_rvol           = min(rvol / 20.0, 1.0)              # 20× RVOL = full marks
float_inverse       = max(0, (20e6 − float) / 20e6)      # already 0–1
norm_premarket_vol  = min(premarket_volume / 1e6, 1.0)   # 1M shares = full marks
catalyst_confirmed  = 1.0 confirmed | 0.5 headline only | 0.0 none

⇒ score ∈ [0, 1], directly comparable to the ≥ 0.7 conviction gate (§14.2)
```

Normalization caps are configurable and should be revisited against real scanner output in Phase 3.

### 20.11 Signal Arbitration (multiple setups, same symbol)

A bull-flag breakout is frequently *also* a HOD breakout, so more than one setup can fire on the same bar. §12.2 forbids concurrent multi-setup positions but did not say which wins. Rules:

1. **Deduplicate by symbol.** At most one open position per symbol regardless of setup count.
2. **Priority order** when several fire on the same bar: Bull Flag → HOD Breakout → VWAP Reclaim (descending source confidence, §16).
3. Losing signals are recorded in `signals` with status `SUPERSEDED` and the winning `signal_id` referenced, so the journal and backtest can measure what was skipped.
4. While a position is open in a symbol, further signals on that symbol are `SUPERSEDED` — except an explicit scale-in add permitted under §7.1.1.

### 20.12 Position State Machine

`OrderEvent.status` covers order state but not *position* lifecycle, which is what the multi-target ladder and partial-fill quantity adjustments actually require:

```
IDLE → ARMED → PENDING_ENTRY → OPEN_FULL → T1_FILLED → T2_FILLED → TRAILING → CLOSED
                     ↓              ↓            ↓           ↓           ↓
                  EXPIRED       STOPPED_OUT / INVALIDATED / BAILED_OUT → CLOSED
```

| State | Meaning | Permitted transitions |
|-------|---------|----------------------|
| `ARMED` | Setup recognized, awaiting trigger bar | → `PENDING_ENTRY`, `EXPIRED` |
| `PENDING_ENTRY` | Entry order live, unfilled or partially filled | → `OPEN_FULL`, `EXPIRED` |
| `OPEN_FULL` | Position open, stop at pattern level, full R at risk | → `T1_FILLED`, `STOPPED_OUT`, `INVALIDATED`, `BAILED_OUT` |
| `T1_FILLED` | 50% out; stop moved to breakeven; scale-in now legal | → `T2_FILLED`, `STOPPED_OUT` |
| `T2_FILLED` | 75% out | → `TRAILING` |
| `TRAILING` | Final 25% on ratcheting 9 EMA stop, mirrored to a resting broker-side stop amended each bar close (§21.2) | → `CLOSED`, `STOPPED_OUT` |

Every transition is persisted (`positions.state`) and emitted to the audit log, so a restart can resume mid-position (§21.3) rather than discovering an untracked broker position.

### 20.13 Tick Size and Price Rounding

Several rules compute price levels that are not whole ticks — `VWAP × 0.99`, `entry + 2R` on an odd R, measured moves, and the §3.1.2 separation floor. Without a rounding convention these are ambiguous, and the direction of rounding is not cosmetic: rounding a stop the wrong way tightens it into noise, and rounding a target the wrong way flatters backtested R.

| Rule | Specification |
|------|--------------|
| Tick size | **$0.01** for all tradeable symbols. SEC Rule 612 mandates $0.01 increments at or above $1.00, and the §2 price filter floors the universe at $1.00, so sub-penny increments never arise. Sub-$1.00 names are excluded by `PRICE_OUT_OF_RANGE` before any level is computed |
| Universal requirement | Every price submitted to the broker or compared against a bar must be a whole tick. Rounding happens **once**, at level computation, never at comparison time |
| **Stops (long)** | Round **down** (away from the position) → `floor_to_tick`. A wider stop reduces share count at fixed dollar risk, so this never increases risk and never creates a noise stop-out that the unrounded level would have survived |
| **Targets (long)** | Round **up** (away from entry) → `ceil_to_tick`. Makes targets marginally harder to reach, so backtests are not flattered by rounding |
| **Gate thresholds — MINIMUM** (value must **exceed** the threshold) | Round **up** → `ceil_to_tick`. Raising a floor makes it harder to clear, so the requirement is never weakened. Applies to the §3.1.1 room gate, the §3.1.2 separation floor, and `min_stop_distance` |
| **Gate thresholds — MAXIMUM** (value must **stay under** the threshold) | Round **down** → `max(tick_size, floor_to_tick(threshold))`. **The opposite direction from a minimum**, for the same reason: lowering a ceiling makes it harder to clear. Rounding a maximum *up* admits values the unrounded threshold would have rejected. Applies to the §3.1.3 spread gates and any future cap of this shape |
| Clamp on rounded maxima | A maximum that floors to `$0.00` rejects every possible value, which is a silent kill switch rather than a filter. Every rounded maximum is therefore clamped to at least one tick — see §3.1.3 and A25 for the specific coupling this protects against |
| Ordering | Tick rounding is applied **before** the $0.10 minimum-stop floor and before the 5% maximum-stop skip test, so both tests operate on the level that will actually be sent |
| Worked reference | §3.4: `VWAP × 0.99 = $3.762` → `floor_to_tick` → `$3.76` → `− 1 tick` → `$3.75`. The $0.10 floor then widens it to `$3.73` |

**Read the rationale, not the direction.** The governing principle is *"rounding must never weaken a constraint"*; `ceil` and `floor` are consequences of it, and which one applies depends on the polarity of the constraint. This distinction was missed once: §3.1.3's spread gate is a **maximum**, and an earlier draft applied `ceil_to_tick` to it by analogy with the minimum-gate row above, which made the gate more permissive while the surrounding prose claimed conservatism. Any new threshold must be classified as a minimum or a maximum **before** a rounding function is chosen.

With both polarities specified, rounding can only widen stops, raise targets, raise floors, and lower ceilings. No rounding decision anywhere in the system can make a trade look better than it is — but that claim is only true because the polarity split above exists, so it must be re-checked whenever a threshold is added. Decided as [PLAN](PLAN.md) **D19**, amended by **D25** (the polarity split).

### 20.14 Spread and `spread_at_signal`

`spread_at_signal` is the binding input to the §3.1.2 separation floor and the §3.1.3 spread gate, both of which reject entries. It was previously used in three places and defined in none.

| Question | Answer |
|----------|--------|
| Definition | `spread = NBBO_ask − NBBO_bid`, from the **consolidated National Best Bid and Offer**. Never last-trade-derived, and never a single-venue book |
| Sampling point | The **last NBBO quote at or before the close of the signal bar**, matching the as-of discipline in §20.7. Not the quote at order-submission time — that is unknown when the gate runs, and using it would make the gate non-reproducible in backtest |
| Quote validity | Both sides must be present with `bid_size ≥ 100` and `ask_size ≥ 100`. A one-sided or odd-lot-only quote is not a spread; treat as `DATA_QUALITY_DEGRADED` and reject the signal |
| Staleness | A quote older than **2 seconds** at bar close is stale. Reject the signal with `QUOTE_STALE` rather than gating on a stale value — the §5.2 forward-fill allowance (≤ 5 s) governs *display*, not risk gates |
| Crossed / locked markets | `ask ≤ bid` is rejected outright (`QUOTE_CROSSED`), never clamped to zero. A zero spread would make the separation floor trivially satisfiable, which is the exact opposite of correct during the dislocations that produce crossed quotes |
| Backtest substitute | If NBBO history is unavailable for a session, use `est_spread = max(1 tick, spread_pct_median × price)` from the same symbol's available quote days and mark the trade `SPREAD_ESTIMATED`. Estimated-spread trades are **reported separately** in §8.3 and excluded from the §18.7 viability gate, because the gate's whole purpose is to measure net-of-cost expectancy |
| Persistence | Recorded in `signals.spread_at_signal` (§10) for every signal including rejections, so `est_round_trip_cost_per_share` can be calibrated against realised spreads in Phase 4b (A18) |

### 20.15 ATR

Referenced by the §4.2 volatility filter and offered as a §14.2 alternative for the extension test, previously with no period basis or true-range convention.

```
TR_i  = max(high_i − low_i,
            |high_i − prev_close_i|,
            |low_i  − prev_close_i|)

ATR_14 = Wilder's smoothing of TR over 14 periods:
         ATR_1  = mean(TR_1 … TR_14)                     # seed
         ATR_t  = (ATR_{t−1} × 13 + TR_t) / 14
```

| Question | Answer |
|----------|--------|
| Period basis | **Daily bars** for the §4.2 scanner filter (`ATR(14) ≥ 1.5 × 30-day avg ATR` compares a 14-day ATR against the mean of the trailing 30 daily ATR readings). **1-minute bars** for any intraday use, stated explicitly at the point of use — the two are not interchangeable and must never be compared to each other |
| Smoothing | **Wilder's**, not a simple moving average. The two differ materially at n=14 and the choice must not be left to the library default |
| True range | Includes the gap term against the prior close, as above. A high−low-only variant systematically understates volatility in a gapping universe, which is precisely this one |
| Session scope | Daily ATR uses regular-session OHLC only; premarket is excluded, consistent with §20.2 and §20.3 |
| Warm-up | Undefined until 14 completed periods plus one prior close exist. A symbol with insufficient history fails the §4.2 volatility filter as `ATR_INSUFFICIENT_HISTORY` rather than passing by default |
| Corporate actions | Split-adjusted before computation (§20.9) |

---

## 21. Non-Functional Requirements & Operations

### 21.1 Testing Strategy

| Layer | Requirement |
|-------|-------------|
| Unit | Every §20 computation (VWAP, EMA seeding, RVOL as-of, flagpole height, sizing, room gate) with hand-computed fixtures |
| **Worked-example fixtures** | Each §3 worked example encoded as a test: input bar series → asserted entry, stop, R, targets, share count. **These are regression tests against spec drift** — the four arithmetic errors found in v1.0 would all have been caught by this |
| **Worst-case gate fixtures** | Each §3 worked example re-run at the **widest spread its own §3.1.3 caps admit**, asserting the §3.1.2 separation floor still passes. Under the former 1%-of-price filter all three examples failed this test while appearing to pass at an assumed $0.01 spread. Loosening `max_spread_r`, `max_spread_pct`, `max_spread_abs`, or `sep_cost_multiple` must break CI rather than silently readmit negative-expectancy trades |
| **Parameter registry** | A test asserting that no §2 / §2.0 threshold appears as a numeric literal anywhere else in the spec or the code, except inside its own definition row. This is the durable fix for the recurring defect class described in §19. It must also assert **cross-parameter couplings**, not only individual bounds — A25's `min_stop_distance ↔ max_spread_r` relation is the first such case, and it is invisible to a registry that checks each parameter alone |
| **Rounding-direction assertions** | Every rounded threshold is tested against its *derivation*, not its value. `assert cap == Decimal("0.01")` passes under a wrong rounding rule that happens to agree at that input; `assert cap == floor_to_tick(x) and cap <= x` does not. Each test declares whether the threshold is a minimum or a maximum (§20.13) and asserts the direction that polarity requires. A `ceil`/`floor` divergence between §3.1.3's stated formula and its own tables survived a full review round because every number in the tables was individually correct |
| Look-ahead | Property test: replaying a bar series truncated at time *t* must produce identical signals to the full series evaluated as-of *t* |
| Integration | Against IBKR **paper** account: order lifecycle, partial fills, disconnect/reconnect, bracket integrity |
| Replay harness | Deterministic bar-by-bar replay from recorded sessions with an **injectable clock** — no `datetime.now()` anywhere in strategy or risk code |
| Risk-limit tests | Each §7 rule proven to reject/flatten, including after a simulated process restart |
| CI | Full unit + fixture suite on every commit; integration nightly against paper |

### 21.2 Connection, Failure and Recovery

| Principle | Specification |
|-----------|--------------|
| **Protection lives at the broker** | Stops and targets are submitted as native IBKR **bracket/OCA** orders immediately on entry fill, so they survive client crash, network loss, and machine reboot. The local process is never the only thing standing between a position and its stop |
| **Trailing stops are mirrored, never local-only** | The T3 leg trails a locally-computed 9 EMA (§20.5), which cannot be expressed as a static broker order — so a naive implementation silently voids the guarantee above the moment a position reaches `TRAILING`. **Required behaviour:** a static stop order always rests at the broker at the *last ratcheted* trail level. On each bar close the client computes the new EMA and, if it is higher, **amends** the resting broker stop upward. If the client dies, the last amended level stands and the position remains protected — merely at a staler level than the live EMA, never at none. Amendment failures retry per §6.8 and raise `TRAIL_AMEND_FAILED`; the stale stop is left in place, never cancelled |
| On disconnect | Stop generating new signals; do **not** attempt cancels; preserve broker-side brackets; surface a `DISCONNECTED` alert |
| On reconnect | Enter `RECONCILING`; no new signals until reconciliation completes |
| Queued signals | Expire after 60s; a signal whose trigger bar is stale is discarded, never replayed |
| Client identity | Fixed `clientId` per process role; recover `nextValidId` on connect; never reuse a `clientId` across concurrently running processes |
| **IB Gateway daily restart / 2FA** | IB Gateway and TWS force a daily re-authentication and may prompt for 2FA — the most common cause of unattended IBKR systems silently dying. Required: scheduled restart outside market hours, `IBC`-style automation for credential entry, a liveness probe that alerts if no heartbeat within 60s of the expected session start, and a documented manual fallback. Never assume an unattended overnight session survives |

### 21.3 Reconciliation (broker is the source of truth)

On every startup and after every reconnect:

1. Fetch broker positions, open orders, and today's executions.
2. **Broker state wins** on any disagreement with the local DB. Local rows are corrected and the discrepancy is written to `audit_log` as `RECONCILE_DELTA`.
3. An untracked broker position (present at broker, absent locally) is adopted into `positions` with state inferred from filled quantity vs the ladder, and flagged `ADOPTED` for human review.
4. A tracked position absent at the broker is closed locally with reason `RECONCILE_CLOSED`.
5. Positions lacking a live broker-side protective stop have one submitted **before** signal generation resumes.
6. Executions deduplicated by IBKR `exec_id` (§10), which is idempotent across reconnect replays.
7. `daily_state` is rebuilt from broker executions, not trusted blindly from the local row.

### 21.4 Time, Calendar and Clock

- All timestamps stored **UTC**; all trading logic evaluated in `America/New_York` via a DST-aware library (`zoneinfo`) — never a fixed UTC offset.
- Trading calendar from an explicit provider (`pandas-market-calendars` or IBKR contract hours), covering holidays and **half-days** (13:00 ET close). The 15:55 flat-all cutoff is defined as `session_close − 5 min`, not a hard-coded time.
- **NTP clock sync required** on the host; a drift > 250ms against reference raises `CLOCK_DRIFT` and blocks new entries, since bar alignment and the 500ms latency budget are meaningless on an unsynced clock.

### 21.5 Configuration, Secrets and Security

Earlier revisions covered secrets handling only and called it security. The threat model below is deliberately small, because the system is small — but "single-user desktop application" is a scoping decision, not an absence of threats.

**Threat model.** Single operator, single machine, no multi-tenancy, no inbound network service. The assets worth protecting, in order: (1) the ability to place orders in a live brokerage account, (2) IBKR and vendor credentials, (3) the integrity of the audit trail. The realistic adversaries are local malware, another process running as the same user, and operator error — not a remote attacker, since nothing listens on a port.

| Control | Requirement |
|---------|-------------|
| Configuration | Version-controlled YAML validated by `pydantic`; every §2 threshold and §7 limit present with explicit bounds. Non-bypassable limits rejected at load if outside legal range |
| Secrets storage | IBKR credentials and vendor API keys **never** in YAML, the repo, environment files, or process arguments. OS keyring (`keyring` / Keychain / Secret Service) only. Logs redact credentials and account numbers |
| Broker API surface | IB Gateway bound to **loopback only**; trusted-IP list set to `127.0.0.1`. A Gateway listening on `0.0.0.0` grants order entry to anything on the LAN with no authentication whatsoever — this is the single highest-severity misconfiguration available in this system |
| Read-only by default | The API user runs with order-entry enabled only when `trade` is active. `scan`, `status`, and `journal` connect with a read-only client ID |
| **Kill-switch trigger integrity** | The file sentinel is moved from `/tmp/tradipy_kill` to **`$XDG_STATE_HOME/tradipy/kill`** (`~/.local/state/tradipy/kill`), in a directory created `0700` and verified `0700`-owned-by-us at startup. `/tmp` is world-writable, so any local process could flatten the account. The switch fails *safe* — an unauthorized trigger halts trading rather than moving money — so this is a denial-of-service concern, not theft; it is fixed anyway because "any process can stop your trading system" is not an acceptable property. The API and UI triggers require the same confirmation phrase as reset |
| Config integrity | Config changes recorded in `strategy_config` with a hash written to `audit_log`, so any trade traces to the exact config that produced it |
| Audit-trail integrity | `audit_log` append-only at the application layer; the DB user holds `INSERT` and `SELECT` on it, not `UPDATE` or `DELETE`. Nightly backups (§21.7) are the recovery path, not the tamper-evidence mechanism |
| Data at rest | The DB holds no PII and no credentials — positions, prices and timestamps only. Full-disk encryption (FileVault / LUKS) is the recommended control rather than application-level encryption, which would add key-management burden for negligible gain at this threat level |
| Dependencies | Lockfile pinned (`uv.lock`); `pip-audit` in CI. `ib_insync` and the vendor SDKs are the packages with the most direct access to the brokerage session |
| **Explicitly out of scope** | Authentication and authorization (no multi-user surface), network hardening (nothing listens externally), and encryption in transit beyond the TLS the IBKR and vendor SDKs already enforce. **If the system is ever given a remote UI or an HTTP control endpoint, every one of these becomes in scope** and this section must be rewritten before that ships |

### 21.6 Observability

| Concern | Requirement |
|---------|-------------|
| Metrics | All four §5.2 latency legs (data-to-signal, signal-to-order, **order-to-exchange**, end-to-end), order reject rate, reconnect count, scanner candidates/scan, active market-data lines vs cap, bar-gap count, **signals rejected by reason code** — the `SPREAD_TOO_WIDE` and `TARGETS_TOO_CLOSE` rates are the operational read on whether §3.1.3's calibration is right |
| Health | Component heartbeats (ingestion, scanner, strategy, risk, execution) with staleness thresholds |
| Alerts | Risk-limit breach, kill-switch activation, disconnect > 30s, clock drift, no heartbeat at session start, data-quality degradation, market-data line cap reached, order-to-exchange latency > 2 s, `TRAIL_AMEND_FAILED` |
| SLOs | Ingestion uptime ≥ 99.5% of session; zero unprotected open positions (any occurrence is a Sev-1) |
| Audit | `audit_log` append-only; retention ≥ 7 years for order/execution events; no PII or credentials |

### 21.7 Deployment and Data Durability

- Single supervised process group (`systemd` or equivalent) with automatic restart and start-up reconciliation; a crash must never leave a position unprotected (guaranteed by §21.2 broker-side brackets).
- Schema migrations via `alembic`; no manual DDL.
- Nightly DB backup with a tested restore path; bar data reproducible from vendor on loss.
- Non-functional targets, stated against the **two-tier data topology** of §5.5 so they are not mistaken for a scope reduction of §4:
  - **Screening tier (external provider):** full-market coverage at the §4.4 scan cadence. Symbol count is bounded by the provider, not by this system.
  - **Execution tier (IBKR):** ≤ 200 symbols under any form of IBKR subscription and ≤ 10 concurrent streaming watchlist lines, within the market-data line cap (§5.5). This is a *budget for execution-grade quotes on the narrowed watchlist*, not the screening universe.
  - RTO ≤ 5 min during market hours.

---

## 22. Appendices

### Appendix A: Source Bibliography

| # | Source | URL / Reference |
|---|--------|-----------------|
| 1 | Ross Cameron — Stock Selection Criteria | https://cdn.warriortrading.com/warriortrading.com/assets/Warrior%20Trading%20-%20Stock%20Selection.pdf |
| 2 | *How to Day Trade* (2015) | Ross Cameron, Warrior Trading |
| 3 | Bull Flag Trading | https://www.warriortrading.com/bull-flag-trading/ |
| 4 | How to Trade Bull Flag with Confidence | https://www.warriortrading.com/how-to-trade-the-bull-flag-pattern-with-confidence/ |
| 5 | Low Float Stocks | https://www.warriortrading.com/low-float-stocks/ |
| 6 | Simplest Day Trading Strategy | https://www.warriortrading.com/simplest-day-trading-strategy/ |
| 7 | IBKR Market Data Pricing | https://www.interactivebrokers.com/en/pricing/market-data-pricing.php |
| 8 | Architect Prompt (Revised) | prompts/ross_cameron_trading_system.pdf |
| 9 | Critique of the architect prompt | [docs/PROMPT-REVIEW.md](PROMPT-REVIEW.md) — where PRD structure deliberately diverges from the prompt, the reasoning is recorded there |
| 10 | Independent review of v1.2 | [docs/REVIEW-v1.2.md](REVIEW-v1.2.md) — the defect list v1.3 responds to |
| 11 | Independent review of v1.3 | [docs/REVIEW-v1.3.md](REVIEW-v1.3.md) — the defect list v1.3.1 responds to |
| 12 | Decisions log | [docs/PLAN.md](PLAN.md) — D-ids cited throughout this document; the authority on how each decision was reached |
| 13 | Revision history | [docs/CHANGELOG.md](CHANGELOG.md) — superseded rules and the reasoning behind each reversal |

**Citation granularity — known gap.** Appendix A lists sources but not locations. The §15 "Ross Teaching" column is unsourced paraphrase, and no video or webinar sources are cited despite the architect prompt's §7.1 naming them as primary media. PLAN Workstream 11's traceability pass should add page numbers for the PDF and book sources and timestamps for any video source consulted, or mark the claim as community-derived rather than sourced. Until then, treat every "Ross Teaching" cell as a paraphrase of unverified provenance — several thresholds (institutional ownership, premarket volume, the 5× RVOL multiple) are already flagged as community proxies rather than source statements.

### Appendix B: Glossary

| Term | Definition |
|------|------------|
| RVOL | Relative Volume — current volume / average volume over lookback period |
| Float | Shares available for public trading (excluding insider/locked shares) |
| VWAP | Volume Weighted Average Price — cumulative (price × volume) / cumulative volume |
| HOD | High of Day |
| ORB | Opening Range Breakout |
| LULD | Limit Up Limit Down — circuit breaker bands |
| PDT | Pattern Day Trader — FINRA rule requiring $25K minimum for unlimited day trades |
| R-Multiple | Profit or loss expressed as multiples of initial risk (stop distance) |
| Flagpole | Initial sharp move in a bull flag pattern |
| Stocks in Play | Stocks meeting Ross's criteria for unusual momentum activity |
| Float Rotation | Daily volume / float — measures how many times float traded hands |

### Appendix C: IBKR Subscription Cost Estimate (MVP)

| Item | Monthly Cost |
|------|-------------|
| US Securities Snapshot and Futures Value Bundle | ~$10.00 |
| US Equity and Options Add-On Streaming Bundle | ~$4.50 |
| **IBKR subtotal** | **~$14.50** |
| Commission waiver threshold | ≥ $30/month commissions (typical) |
| Free alternative | Cboe One / IEX non-consolidated streaming (limited) |
| Screening / news / fundamentals vendor (§5.3) | **$30–$480** — mandatory per §5.5, not optional |
| **Realistic all-in total** | **~$45–$500** |

*Verify current pricing at IBKR subscription portal before implementation. The IBKR subtotal alone is not the data budget — see §5.3.*

### Appendix D: Reserved Future-Phase Extension Points

Per the architect prompt §6.14, these are **reserved names only — deliberately not designed in this phase.** They are listed so the architecture leaves room for them, and so that the "AI Candidate" columns in §14.2 and §17 have a defined destination.

| Extension point | Consumes | Nearest current limitation (§17) |
|-----------------|----------|----------------------------------|
| AI-assisted trade review | `closed_trades`, `journal_entries`, bar context | Pattern quality scoring |
| News summarization | Headline feed, `watchlists.catalyst` | Catalyst quality assessment |
| Natural-language trade explanations | `signals.features`, `audit_log` | — |
| Pattern ranking | `signals`, realized outcomes per setup | "Obvious" stock selection; clean-chart assessment |
| Strategy optimization assistance | Backtest and walk-forward output | Parameter overfitting risk (Phase 9) |
| Journal insights | `journal_entries`, `performance_snapshots` | — |

No schema, interface, or model choice is specified for any of these, and none is in MVP scope.

---

*End of PRD v1.3.1*
