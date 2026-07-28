# Ross Cameron Momentum Trading System — Product Requirements Document

**Version:** 1.1  
**Status:** Phase 1 draft — **pending independent verification** (PLAN Workstream 11)  
**Date:** 2026-07-28  
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

---

## 2. Quantitative Thresholds

Every threshold below includes: proposed default, confidence rating, Ross source, sensitivity note, and user-configurable flag.

| Parameter | Proposed Default | Confidence | Ross Source | Sensitivity | User-Configurable |
|-----------|------------------|------------|-------------|-------------|-------------------|
| **Minimum Gap %** | ≥ 4% premarket gap from prior close; OR ≥ 10% daily change | High (10% daily); Medium (4% premarket) | Stock Selection PDF: "up at least 10% on the day"; book mentions 4–5% premarket gaps | High — lowering gap threshold increases candidate count but dilutes quality | Yes |
| **Relative Volume (RVOL)** | ≥ 5× 30-day average daily volume | Medium | Warrior "Stock Selection" PDF cites "at least a Relative Volume Ratio of 5," but the governing architect prompt, its §7.4 states Ross rarely gives an exact multiple and treats 5× as a community proxy — hence Medium, not High. Source example uses a **50-day** ADV lookback; see A8 / D2 for the 30-day divergence | High — 3× captures more names; 10× misses early movers | Yes |
| **Float** | ≤ 20M shares (prefer ≤ 10M) | High | Stock Selection PDF + "20-20 rule" ($20 price, 20M float) | Medium — lower float = more volatility but less liquidity | Yes |
| **Price Range** | $1.00 – $20.00 (ideal $2 – $10) | High | Stock Selection PDF: "$1.00 and $20.00" | Medium — exceptions allowed for "obvious" leading gainer | Yes |
| **Average Daily Volume** | ≥ 500,000 shares/day (30-day) | Medium | Community/education material; not explicitly stated by Ross | Medium — ensures exit liquidity on low-float names | Yes |
| **Premarket Volume** | ≥ 100,000 shares premarket AND/OR ≥ 2× prior day premarket volume | Medium | Implied by premarket scanning workflow; no exact number in source | Medium — filters illiquid premarket gappers | Yes |
| **Max Extension from VWAP** | No entry if price > 3% above VWAP (regular session) OR > 5% above VWAP (first 30 min) | Low | Ross avoids chasing; no exact % in source — community proxy | High — tighter = fewer entries; looser = more chase risk | Yes |
| **Max Extension from HOD** | No entry if within 0.5% of HOD without consolidation (≥ 3 candles, ≥ 50% retrace) | Medium | Implied by bull flag / pullback entry logic | Medium | Yes |
| **Stop Distance** | Pattern-derived level (setup-specific), then **widened** to a $0.10 minimum distance if narrower. If the resulting distance exceeds 5% of entry, **skip the trade** (do not tighten — tightening puts the stop inside the pattern) | High | Bull flag: "max loss at low of pullback"; book uses $0.10–$0.50 typical | High — directly affects position size | Yes |
| **Profit Target / R-Multiple** | Target 1: 2R (minimum); Target 2: measured move (flagpole height); Target 3: HOD retest + extension | High | Stock Selection PDF: "2:1 Profit to Loss ratio" | High — 1.5R reduces expectancy; 3R reduces win rate | Yes |
| **Max Risk Per Trade** | 1% of account equity (default); hard cap 2% | High | Book: 1–2% depending on experience level | Critical — linear impact on drawdown | Yes (within 0.25%–2% bounds) |
| **Daily Loss Limit** | 3% of account equity (hard stop); beginner mode: 2% | High | Book: $200–$1,000 or 2–5% by experience | Critical — prevents catastrophic days | Yes (within 1%–5% bounds; cannot disable) |
| **Max Open Positions** | 1 concurrent position (default); 3 in experienced mode | Medium | Ross typically focuses on 1–2 leading gainers | Medium — more positions = correlation risk | Yes, **hard ceiling 3** (an earlier draft said "max 3" and "max 4" in the same row) |
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

**Commissions are not included in R.** IBKR per-share pricing plus regulatory fees typically runs ~$0.005–$0.01/share round-trip. On the example above that is ~$15–30 against a $300 risk unit — a 5–10% drag on every R. Backtest and journal metrics must be reported **net** (§8.3, §18.2).

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

Earlier drafts specified different partial-exit schedules per setup (50/25/25 in one place, 50/50 in others). **One ladder now governs every setup**, and target *ordering* is enforced rather than assumed:

| Leg | Size | Level |
|-----|------|-------|
| **T1** | 50% | Exactly **2R** from entry (R = entry − stop) |
| **T2** | 25% | Nearest **structural** target above T1 (setup-specific: measured move, HOD, or next whole dollar) |
| **T3** | 25% | Trail 9 EMA (1-min); exit on close below the EMA |

**Ordering constraint (hard):** `entry < T1 < T2`. This is guaranteed by the pre-entry room gate below rather than checked afterwards.

**Pre-entry room gate (replaces the old tautological "R:R ≥ 2:1 to first target" criterion):** let `resistance` be the *nearest* overhead level above entry among {HOD, next whole dollar, prior leg high, measured-move projection}. Require:

```
(resistance − entry) ≥ room_gate_multiple × stop_distance
room_gate_multiple: default 2.5, configurable 2.0–3.0, cannot be set below 2.0
```

If the nearest resistance is closer than that, the trade has insufficient room and is **rejected pre-entry**. This is a real gate — unlike "R:R ≥ 2:1 to T1," which could never fail because T1 is *defined* as 2R.

The default of **2.5** rather than 2.0 exists so T1 (at 2R) and T2 (at the structural level) are separated by a meaningful margin. At exactly 2.0 the two legs can land within a cent or two of each other, which after slippage and commissions is a single exit wearing two labels (A15).

**Stop management:** on T1 fill, move the stop on the remaining 50% to breakeven (entry). This is what makes scaling in compatible with the non-bypassable per-trade risk cap (§7).

---

### 3.2 MVP Setup 1: Bull Flag

**Description:** Continuation pattern after strong upward move (flagpole), brief low-volume consolidation (flag), then breakout to new high.

#### Entry Criteria (all required)
1. Stock passes scanner hard filters (Section 4)
2. Flagpole: ≥ 3 consecutive green 1-min candles with combined move ≥ 2% and total volume ≥ 2× average 1-min volume of prior 30 bars
3. Flag: 2–5 red/consolidation candles; pullback retraces ≤ 50% of flagpole height (see §20.4 for the definition of flagpole height)
4. Flag low remains above session VWAP (§20.2). Premarket entries are **disabled by default** in the MVP (D11); when premarket trading is explicitly enabled, premarket VWAP applies instead
5. Flag volume: average volume of flag candles **≤ 70%** of flagpole average volume — the flag must show volume *contraction*. (Corrected: an earlier draft required ≥ 70%, which contradicted this setup's own "low-volume consolidation" description. See A13)
6. **Trigger:** first 1-min candle that **closes above the highest high of the flag** (not merely above the prior red candle's high — that earlier wording allowed a trigger inside the flag range, which collided with the "closes back inside flag range" invalidation)
7. Breakout candle volume ≥ 2× average flag candle volume
8. **Room gate:** nearest overhead resistance ≥ 2 × stop_distance above entry (§3.1.1). Ordering `entry < T1 < T2` must hold

#### Optional Confirmations
- Daily chart shows stock near/at all-time low (turnaround story — lower risk)
- Stock is top 1–3 leading percentage gainer
- Level 2 shows ask-side absorption (future; not MVP)

#### Stop Placement
- Hard stop at **low of flag consolidation** (lowest low of flag candles), minus 1 tick
- Minimum stop distance: $0.10. Maximum stop distance: 5% of entry price — if the flag low is further than 5% away, **skip the trade** (do not tighten the stop; tightening would place it inside the pattern and guarantee a noise stop-out)
- *(Removed: the earlier "if VWAP is above flag low, use VWAP − 1 tick" clause was unreachable — entry criterion 4 requires the flag low to be above VWAP, so VWAP can never be above the flag low.)*

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
- **Breakout** candle on weak volume (< 2× flag average) — note this is about the *breakout*, not the flag. Volume contraction *within* the flag is desirable (criterion 5); it is the failure to expand on the breakout that signals a false move. An earlier draft listed "volume drying up" as a false signal, which contradicted criterion 5
- Session RVOL declining through the flag *and* the breakout (interest leaving the name entirely)
- Flag below a declining 9 EMA with no volume on breakout
- "Obvious" stock already up > 100% with no fresh catalyst

#### Worked Example (recomputed; every line derives from the rules above)

*The earlier version of this example quoted three different entry prices ($5.20 stated, $5.21 as the trigger close, $5.12 as the actual trigger level) and is superseded.*

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
| Nearest resistance | measured move $5.51 (below next whole dollar $6.00) | gap = $0.35 |
| Room gate | $0.35 ≥ 2.5 × $0.12 = $0.30 | **PASS** ✓ |
| T1 (50%) | entry + 2R | **$5.40** |
| T2 (25%) | entry + flagpole height | **$5.51** |
| Ordering | $5.16 < $5.40 < $5.51 | ✓ |
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
7. **Room gate:** nearest overhead resistance ≥ 2 × stop_distance above entry (§3.1.1)

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

#### Worked Example (recomputed)

*The earlier version placed the stop at $6.22 while its own rule required the consolidation low of $6.20, and set T2 ($7.00) below T1 ($7.06). Both corrected.*

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
| Nearest resistance | next whole dollar $7.00 | gap = $0.52 |
| Room gate | $0.52 ≥ 2.5 × $0.15 = $0.375 | **PASS** ✓ |
| T1 (50%) | entry + 2R | **$6.78** |
| T2 (25%) | whole dollar $7.00 (> T1 ✓) | **$7.00** |
| Ordering | $6.48 < $6.78 < $7.00 | ✓ |
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
7. **Room gate:** HOD (or nearest resistance) ≥ 2 × stop_distance above entry (§3.1.1)

#### Stop Placement
- `raw_stop = max(dip_low, VWAP × 0.99) − 1 tick` — for a long, "tighter" means the **higher** of the two candidate levels, i.e. the smaller stop distance (§20.6 defines tighter/wider explicitly; §2's "whichever is wider" refers to a different comparison and is clarified there)
- Then apply the **$0.10 minimum stop distance**, which widens the stop if `entry − raw_stop < $0.10`
- Maximum 5% of entry; if exceeded, skip

#### Exit Criteria
Per the canonical ladder (§3.1.1). *Earlier drafts labelled T1 = HOD and T2 = 2R, which inverted the ladder whenever HOD sat above 2R. Corrected:*
- **T1 (50%):** 2R → move stop to breakeven on remainder
- **T2 (25%):** HOD retest (guaranteed above T1 by the room gate)
- **T3 (25%):** trail 9 EMA (1-min)
- Exit remainder immediately on a close back below VWAP

#### Invalidation
- Dip lasts > 5 candles or exceeds 2% below VWAP
- Reclaim on volume < 1.5× dip average

#### Worked Example (recomputed)

*Note: the earlier example's stop of $3.73 was in fact correct, but appeared to contradict the stop rule because the derivation was omitted — it comes from the $0.10 minimum, not from the dip low. Shown in full below. The genuine error was the inverted target ladder.*

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
| HOD | nearest overhead resistance | $4.09 |
| Room gate | (4.09 − 3.83) = $0.26 ≥ 2.5 × $0.10 = $0.25 | **PASS** ✓ |
| T1 (50%) | entry + 2R | **$4.03** |
| T2 (25%) | HOD retest (> T1 ✓) | **$4.09** |
| Ordering | $3.83 < $4.03 < $4.09 | ✓ (T1→T2 separation $0.06) |
| Shares | floor($300 / $0.10) | **3,000** |
| Position value | 3,000 × $3.83 | $11,490 (within BP cap ✓) |
| Max loss if stopped | 3,000 × $0.10 | **$300** = 1.0% of equity ✓ |

> With the earlier HOD of $4.05 this setup cleared a 2.0R gate by just $0.02, leaving T1 and T2 two cents apart — a single exit wearing two labels once costs are applied. That observation is what motivated the 2.5R default gate (A15); at HOD $4.05 this trade is now correctly **rejected**.

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
- Same as HOD breakout but on 5-min timeframe; wider stops, smaller size

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
- **Constraint:** total open risk measured from *current live stops* must remain ≤ `start_of_day_equity × max_risk_pct` (§7.1.1). Never add to losers. *(Supersedes the earlier "total risk ≤ 1.5× original max risk," which contradicted the non-bypassable cap in §7.)*

#### Scaling Out
- **Rule:** the canonical ladder in §3.1.1 — 50% at T1 (2R), 25% at T2 (structural), 25% trailed on the 9 EMA. This applies to *all* setups; per-setup variants have been removed

---

## 4. Scanner Specification

### 4.1 Scanner Pipeline

```
Universe (US equities, common stock)
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
| Liquidity / Spread | Spread ≤ 1% of price AND bid size ≥ 100 shares | Hard | `SPREAD_TOO_WIDE` | Execution quality |
| Institutional Ownership | ≥ 80% | Soft | `INST_OWN_HIGH` | Less float effectively available |
| Short Interest | ≥ 5% (flag only, not reject) | Soft | `HIGH_SHORT_INTEREST` | Potential squeeze fuel |

### 4.3 Composite Scoring (Soft Filter Ranking)

```
score = (pct_change × 0.30) + (rvol × 0.30) + (float_inverse × 0.20) + (premarket_vol × 0.10) + (catalyst_confirmed × 0.10)

Where:
  float_inverse = max(0, (20M - float) / 20M)
  catalyst_confirmed = 1.0 if manual/NLP confirmed, 0.5 if headline only, 0.0 if none
```

Return top 5 by score for watchlist. User reviews top 2–3 "most obvious."

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
| News feed | Yes | Manual + headline API | Catalyst verification |
| 1-min bars | Yes | Yes | Pattern detection |
| 5-min bars | Yes | Yes | ORB, higher TF context |
| Daily bars | Yes | Yes | RVOL, ATR, daily chart |
| Premarket / After-hours | Yes | Yes | Gap scanning |
| Corporate actions | Yes | Yes | Split adjustment |
| Trading calendar | Yes | Yes | Session boundaries |

### 5.2 Data Quality Requirements

- **Latency:** Signal generation ≤ 500ms from bar close (MVP target); order submission ≤ 100ms after signal. *These are aspirational targets, not guarantees* — IBKR routes through TWS/IB Gateway and is not a low-latency broker; the `ib_insync`/Python path adds overhead. Treat them as budgets to measure against in Phase 2, and design signals around 1-min bar closes (not sub-second reaction) so the strategy tolerates realistic latency (see §5.5)
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

**Estimated MVP cost:** $14.50/month (often waived with active trading commissions).  
**Verify at subscription time** — IBKR pricing changes periodically.

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

**Recommended action — Phase 2 data spike (V7).** Before building the execution engine, run a short, focused spike that answers concretely: (1) can we obtain a real-time candidate list matching Section 4 filters within budget, and from which provider; (2) how fresh and accurate is float/short-interest data on a sample of recent gappers; (3) what is the *measured* data-to-signal and signal-to-order latency on paper. Treat unresolved answers here as a gate on Phase 5, not a detail to discover mid-build.

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

| Scenario | Model |
|----------|-------|
| Normal L1 entry | 1 tick + 50% of spread |
| Low float (< 5M) | 2 ticks + 100% of spread |
| Halt resumption | Gap open to limit price; max slippage 3% (reject if exceeded) |
| Market order exit | 2 ticks + 100% of spread |

### 6.6 Connection Failure Recovery

**See §21.2 for the full policy.** Summary of the corrected behaviour:

- Protective stops and targets live at the broker as native **bracket/OCA** orders from the moment of entry fill, so protection survives client crash, disconnect, or reboot.
- On disconnect: stop generating signals, alert, and **do not attempt to cancel anything** — a disconnected client cannot send cancels, and cancelling brackets would strip protection from an open position. *(This replaces the earlier "cancel all open orders if reconnect not established within 10 sec," which was both impossible and unsafe.)*
- On reconnect: enter `RECONCILING` and complete §21.3 reconciliation before accepting new signals.
- Signals queued during a disconnect expire after 60 sec and are discarded, never replayed against a stale bar.

### 6.7 Duplicate Order Protection

The earlier rule ("each signal generates a unique UUID `signal_id`; reject duplicate `signal_id` within 5 min") was a no-op: a freshly generated UUID is unique **by construction**, so the duplicate check could never fire. Replaced with a deterministic key:

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
| Max sector exposure | > 1 position same sector | Pre-order | Reject order | Yes |
| Emergency kill switch | User/API trigger | Any | Flatten all; halt all trading | No |
| Min R:R ratio | Nearest overhead resistance < `min_rr` × stop_distance at signal time (the §3.1.1 room gate) | Pre-order | Reject signal | **No — cannot be disabled.** `min_rr` configurable in 2.0–3.0; cannot be set below 2.0 (matches the §1 constraint) |
| Spread check | Spread > 1% of price | Pre-order | Reject order | Yes |

### 7.1 Dynamic Position Sizing

See Section 2.2 for the formula.

**Equity definitions (these were previously conflated, making the daily-loss rule circular):**

| Term | Definition | Used for |
|------|-----------|----------|
| `start_of_day_equity` | Account net liquidation value at 09:30 ET, snapshotted once per session and **never updated intraday** | Denominator for the daily loss limit, max risk per trade, and drawdown rules |
| `live_equity` | `start_of_day_equity` + realized P&L + unrealized P&L | Reporting, buying-power checks, and the P&L numerator |

The earlier specification tested `realized + unrealized P&L ≤ −equity × pct` while defining equity to *include* unrealized P&L — so the threshold moved as the loss accrued and the limit could never be reached deterministically. Using the frozen start-of-day snapshot as the denominator fixes this.

**Position sizing uses `start_of_day_equity`**, so intraday P&L swings cannot inflate size after a winning trade (a common blow-up path).

### 7.1.1 Scaling In vs the Non-Bypassable Risk Cap

§3.5 permits adding to winners, which appeared to contradict the non-bypassable per-trade cap. The rules are reconciled as follows:

- The cap applies to **total open risk**, computed from the *current live stop* of every open position — not from the original entry risk.
- An add is permitted **only if**, after the add, total open risk still satisfies `≤ start_of_day_equity × max_risk_pct`.
- Because the stop moves to breakeven when T1 fills (§3.1.1), the original tranche contributes ~zero risk at that point, which is precisely what creates headroom for the add.
- **Consequence:** adds are only ever legal *after* T1, never while the initial position is still at full risk. This is stricter than the old "total risk ≤ 1.5× original max risk" wording, which openly violated the cap. Recorded as **A16**.

### 7.1.2 Risk State Persistence

The non-bypassable limits are meaningless if they reset on restart. `daily_state` (§10) persists `start_of_day_equity`, realized P&L, consecutive-loss count, day-trade count, and lockout flags, keyed by session date. On startup the risk engine **loads this state before accepting any signal**, and reconciles it against broker-reported positions and executions (§21.3).

### 7.2 Emergency Kill Switch

- Trigger: UI button, API endpoint, or file sentinel (`/tmp/tradipy_kill`)
- Action: Cancel all open orders → market-close all positions → set `trading_halted = true`
- Requires manual reset with confirmation phrase

---

## 8. Backtesting Framework

### 8.1 Design Principles

- **No look-ahead:** RVOL, VWAP, indicators computed on data available at signal bar close only
- **Realistic fills:** Simulate partial fills on bars where volume < order size × 10
- **Conservative bias:** When uncertain, assume worse fill (higher buy, lower sell)

### 8.2 Realism Requirements

| Requirement | Implementation Design |
|-------------|----------------------|
| Partial fills | Fill qty = min(order_qty, bar_volume × participation_rate); default participation_rate = 5% |
| Slippage | Per Section 6.5 model applied to every simulated fill |
| Halt/LULD simulation | Use historical halt timestamps; no entries 5 min before known halts; resumption at next trade price + slippage |
| Look-ahead bias | Enforce `as_of_time` on all feature queries; unit test with shifted data |
| Premarket/auction | Model opening auction as first regular-session bar; premarket signals fill at 9:30 open + slippage |
| Corporate actions | Adjust historical prices/volumes for splits before any calculation |
| Walk-forward | Train params on 60-day window, test on next 20-day; roll forward |
| Monte Carlo | Bootstrap trade sequence 10,000 times; report 95th percentile max drawdown |

### 8.3 Required Metrics

| Metric | Definition |
|--------|------------|
| Expectancy | (win_rate × avg_win) − (loss_rate × avg_loss). **Reported net** of commissions, regulatory fees and modeled slippage; the gross figure may also be shown but the viability gate (§18.7) is judged on net |
| Sharpe Ratio | Annualized; rf = 0 |
| Profit Factor | Gross profit / gross loss |
| Max Drawdown | Peak-to-trough equity decline |
| Win Rate | Winning trades / total trades |
| Avg Winner / Loser | Mean P&L of wins and losses |
| Holding Time Distribution | Histogram of trade duration |
| Risk-Adjusted Return | Return / max drawdown |
| Trade Count Sufficiency | Flag if < 100 trades in sample |
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
| **Backtester** | Historical simulation | Historical data, config | Performance report |
| **Configuration** | Strategy params, risk limits | YAML/DB | Config objects |
| **LoggingAudit** | Structured logs, audit trail | All events | Log streams, DB |
| **Monitoring** | Health checks, alerts | Component heartbeats | Alerts |
| **NotificationSystem** | Email/push/desktop alerts | Risk events, signals | Notifications |

### 9.2 Data Contracts

#### TradeSignal
```python
@dataclass
class TradeSignal:
    signal_id: str          # UUID
    symbol: str
    setup_type: str         # e.g. "BULL_FLAG"
    direction: str          # "LONG" (MVP: long only)
    entry_price: float      # limit price
    stop_price: float
    target_prices: list[float]
    shares: int
    r_multiple: float
    confidence: str         # HIGH / MEDIUM / LOW
    timestamp: datetime
    metadata: dict          # pattern-specific data
```

#### OrderEvent
```python
@dataclass
class OrderEvent:
    order_id: str
    signal_id: str
    symbol: str
    side: str
    order_type: str
    quantity: int
    limit_price: float | None
    stop_price: float | None
    status: str             # PENDING, SUBMITTED, FILLED, CANCELLED, REJECTED
    filled_qty: int
    avg_fill_price: float | None
    timestamp: datetime
```

### 9.3 Event Flow

```
IBKR → MarketDataIngestion → FeatureStore → Scanner → StrategyEngine
                                                        ↓
                                              RiskEngine (pre-trade)
                                                        ↓
                                              ExecutionEngine → IBKR
                                                        ↓
                                              PortfolioManager → TradeJournal
```

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
| float_shares | BIGINT | Updated daily |
| avg_daily_volume_30d | BIGINT | |
| sector | VARCHAR(64) | |
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

### 11.1 Framework Recommendation

**PySide6 (Qt for Python)** — native desktop, excellent table/widget support, embeds pyqtgraph for charts. Alternative: Tauri + Python backend (more complex setup).

### 11.2 Screen Layouts

#### Trading Dashboard (Primary)
```
+-------------------------------------------------------------+
| [Account: $25,000] [Daily P&L: +$120] [Risk: 1%/3%] [KILL]  |
+-------------------------------------------------------------+
|  WATCHLIST (Top 5)    |  CHART (1-min + VWAP + 9 EMA)        |
|  Symbol | Chg | RVOL   |                                     |
|  XYZ    | +42%| 12x    |                                     |
|  ABC    | +18%|  8x    |                                     |
+-------------------------------------------------------------+
|  ACTIVE SIGNALS       |  ORDERS & POSITIONS                  |
|  Bull Flag XYZ $5.20  |  Pos | Symbol | P&L | Stop | Target  |
+-------------------------------------------------------------+
|  RISK PANEL: Daily loss used 40% | Streak: 0 | Positions: 1  |
+-------------------------------------------------------------+
```

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

### 11.3 MVP UI

CLI-only for MVP:
- `tradipy scan` — run scanner, print watchlist
- `tradipy trade --paper` — enable strategy engine in paper mode
- `tradipy status` — positions, P&L, risk utilization
- `tradipy journal` — view/add journal entries

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
| 3 | Scanner (hard filters) | Medium | 2 | Float data availability |
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

*A previous revision stated "~11–12 weeks," which did not equal the sum of its own rows and omitted the §5.5 data spike entirely. The range above is the honest sum; note it excludes any vendor-integration work that the spike may prove necessary, and excludes iteration time if the Viability Gate fails.*

---

## 13. Assumptions Register

| ID | Assumption | Consequence if Wrong |
|----|------------|---------------------|
| A1 | Ross's 5× RVOL / 10% daily / $1–$20 / ≤20M float remain valid criteria | Scanner may miss or include wrong stocks; thresholds are user-configurable |
| A2 | 2:1 R:R minimum produces positive expectancy at ~50% win rate | Lower R:R requires higher win rate; system enforces 2:1 by default |
| A3 | Manual catalyst verification acceptable for MVP | Without it, false positives from pump-and-dump increase |
| A4 | Long-only for MVP (Ross primarily trades long) | Short setups not supported initially |
| A5 | **$30,000** account assumed for sizing examples — deliberately above the $25,000 PDT minimum | At exactly $25K, the first loss triggers PDT restriction before the daily loss limit binds. Smaller accounts need a sub-PDT mode (≤ 3 day trades per rolling 5 days) or cash-account settlement handling |
| A6 | ib_insync remains maintained and compatible with IBKR API | May need migration to native ibapi |
| A7 | 3% above VWAP extension limit approximates Ross's "don't chase" rule | May enter too early or too late vs discretionary trader |
| A8 | 30-day RVOL lookback chosen for faster regime adaptation (the architect prompt's own §7.4 example cites 50-day ADV; 5× multiple downgraded to Medium confidence) | Different lookback changes the candidate set; 50-day is smoother but slower to react to fresh momentum |
| A9 | Non-professional IBKR data pricing (~$14.50/mo) | Professional classification increases costs 10× |
| A10 | Float data from IBKR fundamental data or Finviz scrape | Stale/missing float → scanner inaccuracy |
| A11 | Top 2–3 "most obvious" gappers outperform lower-ranked | "Obviousness" proxy via pct_change ranking |
| A12 | Breakout-or-bailout (3 candles) approximates Ross's patience threshold | May exit winners early or hold losers too long |
| A13 | Bull-flag volume should **contract** in the flag (≤ 70% of flagpole average) | Reverses an earlier draft that required ≥ 70%. If contraction is the wrong read, the filter rejects valid high-volume consolidations; threshold is configurable |
| A14 | For VWAP-invalidated setups, the **effective** stop is `max(pattern_stop, VWAP − 1 tick)` | If wrong, position sizing overstates risk-per-share and undersizes trades; realized R differs from nominal R |
| A15 | Room gate requires resistance ≥ **2.5R** (2R plus a 25% margin) so T1 and T2 are meaningfully separated | Tighter margin produces ladders where T1 and T2 collapse into one exit after costs; looser margin rejects more setups |
| A16 | Adds are legal only after T1 fills and the stop moves to breakeven | Stricter than Ross, who may add before the first target. Reduces both risk and upside participation |
| A17 | Premarket trading disabled by default in MVP (D11) | Forgoes premarket gap continuation entries; removes the contradiction between premarket setups and the 09:30 trading-hours lockout |

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
| Extended move | "Too far" judgment | > 3% above VWAP = skip | > 2× ATR from VWAP = skip | Alt A | No |
| Skip valid setup | Contextual pass | Auto-skip if daily loss > 50% utilized | Auto-skip if 2 consecutive losses | Alt A | No |

---

## 15. Validation Matrix

| Strategy Concept | Ross Teaching | Deterministic Rule | Conf. | Assumptions | Alternatives |
|------------------|---------------|-------------------|-------|-------------|--------------|
| Relative Volume | ≥ 5× average volume | RVOL ≥ 5× 30-day ADV at signal time on 1-min bars | Medium | 5× is a community proxy (Ross rarely states an exact multiple, per the architect prompt, its §7.4); source example uses **50-day** ADV, PRD assumes 30-day (A8) | 3× or 10×; z-score; 50-day lookback |
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
| 5-Min Breakout | Higher TF breakout | 5-min close > 20-bar high on 2× vol | Medium | — | 15-min TF |
| Scaling In | Add to winners | Add 25–50% at new HOD after T1; total risk ≤ 1.5× | High | Never add to losers | Fixed add size |
| Scaling Out | Partial profits | 50% at 2R, 25% at measured move, 25% trail | High | — | All-out at 2R |
| Stop Loss | Low of pattern | Pattern low or VWAP (tighter); min $0.10 | High | — | ATR-based stop |
| Profit Target | 2:1 minimum | T1 = 2R; T2 = measured move; T3 = trail 9 EMA | High | — | Fixed $ targets |
| Position Sizing | Risk-based | shares = floor(equity × risk% / stop_distance) | High | — | Fixed share count |
| Daily Loss Limit | Stop when max loss hit | Flatten all at −3% equity; lock account | High | Beginner 2% | Fixed $ amount |
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
| Liquidity | Adequate volume | ADV ≥ 500K; spread ≤ 1% | Medium | — | — |
| Short Interest | Squeeze potential | Flag if ≥ 5%; no reject | Low | — | — |
| Institutional Ownership | Effective float | Soft flag if > 80% | Low | — | — |

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
| V7 | Data/scan feasibility (see §5.5) | Signals miss or arrive late | Phase 2 data spike before committing to execution build |

### 18.7 Viability gate (go / no-go before real capital)

No real money should be committed until, at minimum: backtest and paper trading each show **positive expectancy net of modeled slippage and fees** over **≥ 100 trades per MVP setup**; results hold **out-of-sample** (walk-forward) and across at least one quiet-market period; and Monte Carlo 95th-percentile max drawdown stays within the account's risk tolerance. Failing any of these, the correct decision is to iterate on the signal or stop — not to trade a specified-but-unvalidated system.

---

## 19. Acceptance Criteria Checklist

**Self-assessment only.** These boxes were ticked by the document's author. A cold review in v1.1 found four arithmetic errors inside the §3 worked examples and roughly a dozen internal contradictions — all of which had been sitting behind a fully-checked list. The lesson is recorded rather than hidden: **a self-certified checklist is not evidence.** Final sign-off requires PLAN Workstream 11 by someone other than the author.

| Verification status | |
|---|---|
| Author self-assessment | ✓ complete (below) |
| Independent review | ☐ **outstanding** |
| Worked examples recomputed | ✓ v1.1 (four errors fixed) |
| Machine-checkable example fixtures | ☐ outstanding (§21.1 — the durable fix) |

- [x] Every setup in Section 4 has fully specified entry, exit, stop, target, and invalidation rules with numeric parameters where applicable
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

The earlier formula summed raw, unnormalized quantities — `premarket_vol` in raw shares (~10⁵) dominated `rvol` (~10¹) and `float_inverse` (0–1) by four orders of magnitude, so the score was effectively "premarket volume, ranked." It also could not satisfy the "score ≥ 0.7" conviction gate in §14.2, which presumes a 0–1 range. Corrected:

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
| `TRAILING` | Final 25% on ratcheting 9 EMA stop | → `CLOSED` |

Every transition is persisted (`positions.state`) and emitted to the audit log, so a restart can resume mid-position (§21.3) rather than discovering an untracked broker position.

---

## 21. Non-Functional Requirements & Operations

### 21.1 Testing Strategy

| Layer | Requirement |
|-------|-------------|
| Unit | Every §20 computation (VWAP, EMA seeding, RVOL as-of, flagpole height, sizing, room gate) with hand-computed fixtures |
| **Worked-example fixtures** | Each §3 worked example encoded as a test: input bar series → asserted entry, stop, R, targets, share count. **These are regression tests against spec drift** — the four arithmetic errors found in v1.0 would all have been caught by this |
| Look-ahead | Property test: replaying a bar series truncated at time *t* must produce identical signals to the full series evaluated as-of *t* |
| Integration | Against IBKR **paper** account: order lifecycle, partial fills, disconnect/reconnect, bracket integrity |
| Replay harness | Deterministic bar-by-bar replay from recorded sessions with an **injectable clock** — no `datetime.now()` anywhere in strategy or risk code |
| Risk-limit tests | Each §7 rule proven to reject/flatten, including after a simulated process restart |
| CI | Full unit + fixture suite on every commit; integration nightly against paper |

### 21.2 Connection, Failure and Recovery

The earlier §6.6 policy ("cancel all open orders if reconnect not established within 10 sec") is replaced — it was both unachievable and unsafe: a disconnected client *cannot* send cancels, and cancelling protective stops would leave an unprotected position.

| Principle | Specification |
|-----------|--------------|
| **Protection lives at the broker** | Stops and targets are submitted as native IBKR **bracket/OCA** orders immediately on entry fill, so they survive client crash, network loss, and machine reboot. The local process is never the only thing standing between a position and its stop |
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

### 21.5 Configuration and Secrets

- Config in version-controlled YAML validated by `pydantic`; every §2 threshold and §7 limit present with explicit bounds. Non-bypassable limits rejected at load if outside legal range.
- Secrets (IBKR credentials, data-vendor keys) **never** in YAML or the repo — environment variables or OS keyring only. Logs redact credentials and account numbers.
- Config changes recorded in `strategy_config` with a hash written to `audit_log`, so any trade can be traced to the exact config that produced it.

### 21.6 Observability

| Concern | Requirement |
|---------|-------------|
| Metrics | Data-to-signal latency, signal-to-order latency, order reject rate, reconnect count, scanner candidates/scan, active market-data lines vs cap, bar-gap count |
| Health | Component heartbeats (ingestion, scanner, strategy, risk, execution) with staleness thresholds |
| Alerts | Risk-limit breach, kill-switch activation, disconnect > 30s, clock drift, no heartbeat at session start, data-quality degradation, market-data line cap reached |
| SLOs | Ingestion uptime ≥ 99.5% of session; zero unprotected open positions (any occurrence is a Sev-1) |
| Audit | `audit_log` append-only; retention ≥ 7 years for order/execution events; no PII or credentials |

### 21.7 Deployment and Data Durability

- Single supervised process group (`systemd` or equivalent) with automatic restart and start-up reconciliation; a crash must never leave a position unprotected (guaranteed by §21.2 broker-side brackets).
- Schema migrations via `alembic`; no manual DDL.
- Nightly DB backup with a tested restore path; bar data reproducible from vendor on loss.
- Non-functional targets: support a 200-symbol scan universe and 10 concurrent watchlist subscriptions within the IBKR market-data line cap (§5.5); RTO ≤ 5 min during market hours.

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
| **Total** | **~$14.50** |
| Commission waiver threshold | ≥ $30/month commissions (typical) |
| Free alternative | Cboe One / IEX non-consolidated streaming (limited) |

*Verify current pricing at IBKR subscription portal before implementation.*

---

*End of PRD v1.0*
