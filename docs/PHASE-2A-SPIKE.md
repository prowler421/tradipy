# Phase 2a — Data Feasibility Spike

**Status: not started. Scope and pre-registration both committed 2026-07-29 — §7 is filled and
binding. The blocking action is a vendor trial account, which is not something this repository can
open.**

Q4 is the only question runnable without one, and it needs historical intraday NBBO data for the
sample the §7 rule selects. Until that data exists locally, nothing here can execute. **Writing
more about this spike is not progress on it** — the next action is external.

Normative source: [PRD.md](PRD.md) §5.5, which recommends this spike and calls it **V7**. §4.2
defines the filter set it must reproduce, §12.1 places it at Phase 2a depending on Phase 2, and
§18.7 is the viability gate its outputs feed. Where this document and the PRD disagree, the PRD
governs; where this document adds detail the PRD does not state, it is scope-setting for one
spike and not a spec change.

**One sequencing change, now decided.** §5.5 treats unresolved answers here as a gate on **Phase
5**, and §12.1 originally listed Phase 3 (scanner) as depending on Phase 2, not on 2a — Phase 3's
only nod to this being a Risk cell reading "Float data availability." **Phase 3 is now gated on 2a**
as well, on the grounds that a scanner built to §4.2's filter set before knowing whether that set is
obtainable is the specific waste §5.5 warns about. Recorded as **D29** in [PLAN.md](PLAN.md); §12.1's
dependency cell is amended to match.

---

## 1. Why this exists, and why now

The scanner design in PRD §4 assumes real-time, full-universe screening on gap %, RVOL and
float. §5.5 calls that **the weakest feasibility assumption in the PRD** and gives three reasons:
IBKR is an order-management API rather than a screener and caps concurrent market-data lines at
roughly 100; float and short-interest data are unreliable for exactly the small-cap names the
strategy targets; and premarket volume is inconsistent across feeds.

Every threshold in `tradipy.params` is calibrated against three hand-authored worked examples.
The test suite proves they are applied consistently. **It cannot say whether `max_spread_r = 0.15`
admits 90% of qualifying setups or 5%** — and A21's worst case is that it disables VWAP Reclaim,
one of the three MVP setups. Two of the documented open findings in `tests/README.md` are
unresolvable without a real spread distribution.

[PLAN.md](PLAN.md) has ranked this the highest-value technical action since before any code
existed. It has been deferred twice, both times for work that could be finished in one sitting,
and the PLAN records that the argument does not survive a third use. The invariant layer is now
finished, the enforcement holes are closed, and [REVIEW-2026-07-29](reviews/REVIEW-2026-07-29.md) found
nothing that outranks this. **There is no competing candidate for the next piece of work.**

**This is investigative code, not implementation.** Its output is a report and a dataset. §8 says
what it must not become.

---

## 2. The four questions

§5.5 poses three; the PLAN's A21 risk row adds a fourth that is arguably the most consequential,
because it is the only one that can invalidate a shipped default.

| # | Question | Why it gates something |
|---|---|---|
| **Q1** | Can a real-time candidate list matching §4.2's hard filters be obtained, from which provider, at what cost and what refresh interval? | A negative answer **rewrites PRD §4**, and per D29 Phase 3 does not start until it does |
| **Q2** | How fresh and accurate is float and short-interest data on a sample of recent gappers? | Float ≤ 20M is the single most important filter (D4). If it runs on stale data, the universe is not the universe §4 describes. Disposition for **A10** |
| **Q3** | What is the *measured* data-to-signal and signal-to-order latency? | §5.5's "every 30–60 seconds" full-universe refresh, §4.4's 30–120 s scan schedule and §20.1's bar-close grace are all assumptions. Feeds Phase 5 design |
| **Q4** | What is the realized NBBO spread distribution on qualifying names, and what rejection rate does `max_spread_r = 0.15` imply per MVP setup? | Directly tests **A21**. May recalibrate `max_spread_r`, `est_round_trip_cost_per_share` and `sep_cost_multiple`, and resolves two `tests/README.md` open findings |

Q4 is the one to run first if the timebox slips, because it needs only historical quote data on a
known symbol list — no real-time subscription, no scanner, no vendor commitment.

---

## 3. Scope

### 3.1 In scope

- Vendor evaluation against Q1: trial or documentation review, then a measured test on at least
  one paid trial.
- A **symbol sample** of historical gappers, selected by the pre-registered rule in §7.
- Historical intraday quote and bar data for that sample, sufficient to compute Q4.
- Float and short-interest values for that sample from **at least two independent providers**,
  so disagreement can be measured rather than assumed.
- Latency measurement on a paper connection for Q3.
- A written report with the numbers, the method, and the disposition each question implies.
- A throwaway script per question, committed under `scripts/spike2a/` and clearly marked.

### 3.2 Out of scope

- Any scanner, strategy engine, execution path, or persistence layer.
- Any change to `src/tradipy/` other than registering a parameter the spike shows is needed —
  and that only with a §2.0 row to cite, per convention 1.
- Live trading, of any size, for any reason.
- Choosing the production vendor. The spike produces evidence; the choice is a decision to be
  recorded in the PLAN's decision log with its rejected alternatives.

### 3.3 Providers to evaluate

§5.5 names Polygon and "a market-data vendor or a paid scanner" as examples, and Appendix C
budgets **$30–$480/month** for the screening/news/fundamentals tier against a ~$14.50 IBKR
subtotal. Evaluate at minimum: IBKR's own `reqScannerSubscription` (to establish the negative
concretely rather than by assumption), one full-market real-time vendor, and one
fundamentals/float source distinct from whichever vendor supplies quotes. Finviz is A10's
assumed source and should be measured, not inherited.

Record for each: what it costs at the tier actually required, whether the §4.2 filter set is
expressible in its query language or must be filtered client-side, how many symbols it will
stream concurrently, and its stated versus measured refresh interval.

---

## 4. Method

### 4.1 Sample design

The sample is where a spike like this fails, so it is pre-registered in §7 rather than chosen
while looking at results. Two properties matter:

- **No survivorship.** The sample must be drawn from names that *met §4.2's filters at the time*,
  not from names that subsequently moved. Drawing from "recent big movers" measures the spread
  distribution of winners and will make `max_spread_r` look far more permissive than it is. This
  is the single most likely way to get a wrong answer to Q4.
- **Regime coverage.** At least one quiet stretch and one active stretch, per §18.7's requirement
  that results hold "across at least one quiet-market period." A sample drawn only from an active
  window overstates available liquidity.

### 4.2 What to record per candidate

Per symbol-session, and per signal-bar for Q4: timestamp (UTC, per §20.1), price, gap %, RVOL and
the ADV it was computed against, float and short interest with provider and as-of time, premarket
volume, NBBO bid/ask and sizes at the sampled instant, and which §4.2 filters passed. Record
**rejections too** — §20.14 requires `spread_at_signal` persisted for every signal including
rejected ones, and a rejection-rate question cannot be answered from accepted candidates.

### 4.3 Q4 in particular

For each sampled signal bar, compute the §3.1.3 caps from `tradipy.gates.spread_caps` using the
observed price and an R derived from the setup's stop rule, then classify the observed spread
against them. **Use the library, not a reimplementation** — the point is to test the shipped
thresholds, and a second implementation of the cap arithmetic would be a second definition of a
registered threshold, which convention 1 forbids and which would silently absorb any disagreement.

Report the rejection rate three ways: overall, per MVP setup, and per price decile — because A21's
concern is specifically cheap stocks, and an aggregate number will hide it.

---

## 5. Deliverables

| # | Artifact | Where |
|---|---|---|
| D1 | Q1 report: provider matrix, per-provider cost at the required tier, filter expressibility, concurrent-symbol limits, measured refresh | `docs/SPIKE-2A-RESULTS.md` |
| D2 | Q2 report: cross-provider float and short-interest disagreement rate on the sample, with as-of staleness distribution | same |
| D3 | Q3 report: measured data-to-signal and signal-to-order latency, distribution not mean | same |
| D4 | Q4 report: realized spread distribution and implied rejection rate — overall, per setup, per price decile | same |
| D5 | The raw sample dataset, so every number in D1–D4 is recomputable | `data/spike2a/` (gitignored if large; checksum and provenance in the report) |
| D6 | Throwaway scripts, one per question, marked as spike code | `scripts/spike2a/` |
| D7 | Proposed dispositions: A10, A21, D2's RVOL lookback divergence, Appendix C's cost table, and any recalibration of `max_spread_r` / `est_round_trip_cost_per_share` / `sep_cost_multiple` | a section of D1–D4's report, raised not applied |

D7 is raised, not applied. Recalibrating a registered threshold is a spec decision: it needs a
§2.0 row, a PLAN decision entry with its rejected alternative, a `docs/CHANGELOG.md` entry, and —
because `max_spread_r` changes which trades the system takes — the "changes trading behaviour"
marker D20, D21, D27 and D28 all carry.

---

## 6. Exit criteria and what each outcome implies

The spike is **done** when D1–D4 each state a number and a method, and the report says which of
the four questions remain unanswered and why. It is explicitly permitted to finish with an
unanswered question, provided the reason is recorded — §5.5's instruction is to *"treat
unresolved answers here as a gate on Phase 5, not a detail to discover mid-build."*

| Outcome | Implication |
|---|---|
| Q1 negative — no provider delivers the §4.2 filter set in real time within budget | **PRD §4 is rewritten.** Either the filter set narrows to what is obtainable, or the refresh interval lengthens, or the universe shrinks to a pre-built watchlist. Per D29, Phase 3 does not start until §4 matches reality. §5.5's closing sentence separately gates Phase 5 |
| Q1 positive but the budget exceeds Appendix C's $500 ceiling | §18.7's arithmetic changes. Against a $30,000 account, $500/month is 20%/year of fixed drag and belongs in the viability gate, not in an appendix |
| Q2 shows material cross-provider float disagreement | A10 is confirmed as a live risk. Options: widen the float ceiling to absorb error, require two-provider agreement, or downgrade float from hard filter to soft. All three are spec decisions |
| Q4 rejection rate is high on cheap stocks | **A21 realized.** Either `max_spread_r` is recalibrated against the distribution, or VWAP Reclaim is dropped from the MVP set, or the price floor rises. The third interacts with the documented $1.00–$1.99 open findings and may resolve them |
| Q4 rejection rate is negligible | `max_spread_r` is not binding and the gate is decoration. Worth knowing — an inert gate is the state `room_gate_multiple` is already in at its default, and this project's convention is to document inertness rather than let it read as protection |
| Q3 latency exceeds §5.5's 30–60 s refresh assumption or §4.4's scan schedule | §4.4 and §20.1's `bar_close_grace_ms` are both revisited before Phase 5 |

---

## 7. Pre-registration — **to be completed and committed before any data is pulled**

This section exists because a spike whose thresholds are chosen after seeing the data is not
evidence, and this project has already found five defect classes — plus a second population of
the fifth — that between them mostly reduce to a claim being checked against something chosen to
agree with it. Fill in every row, commit, then start.

**Committed 2026-07-29, before any data was pulled.** Every row below is binding. A value here is
changed only by amending this section in a commit that predates the next data pull, and any change
after data exists must be recorded as such — the point of the table is that it cannot be quietly
retrofitted to a result.

| Item | Committed value |
|---|---|
| **Sample windows** | Two 10-session windows, selected by the mechanical rule in the next row. **Not calendar dates** — see below |
| **Window selection rule** | Compute daily closing VIX over the 12 months ending the day before the spike starts. Take the **highest-VIX 10 consecutive sessions** as the active window and the **lowest-VIX 10 consecutive sessions** as the quiet window, non-overlapping; if they overlap, take the lowest-VIX non-overlapping run. VIX is chosen because it is independent of any quantity this spike measures |
| **Sample size** | Every symbol-session in the two windows that passes the selection rule below, capped at **400** symbol-sessions. If the cap binds, take the first 400 by (date, symbol) ascending — **not** by gap size, RVOL, or any measured quantity |
| **Selection rule** | A symbol-session enters the sample if, using data available **at or before 09:30 ET that day**, it passes §4.2's hard filters *other than* spread and LULD: gap ≥ 4% premarket or ≥ 10% daily, RVOL ≥ 5× 30-day ADV, float ≤ 20M, price $1.00–$20.00, ADV ≥ 500K. Spread is excluded because it is what Q4 measures; LULD because proximity is intraday. Soft filters are recorded, never used to include or exclude |
| **Exclusions** | Three, all decided now: (1) sessions where the symbol was halted before 09:30, because the pre-open state is not comparable; (2) symbols with no NBBO data from the chosen vendor for ≥ 5% of the session, recorded as a **coverage failure feeding Q1**, not silently dropped; (3) nothing else. In particular, **no exclusion of names that did not subsequently move** — that is the survivorship failure §4.1 names |
| **Q1 pass threshold** | A provider passes if it delivers ≥ **95%** of the sample's symbol-sessions as candidates, expresses or client-side-filters the full §4.2 hard set, streams ≥ **200** concurrent symbols, and its measured refresh is ≤ **60 s** full-universe — at ≤ **$500/month** all-in including IBKR, per Appendix C's ceiling. Any single failure is a Q1 negative for that provider |
| **Q2 pass threshold** | Float is **unreliable** if the two providers disagree by > **10%** on more than **15%** of sampled symbols, or if > **10%** of symbols have a float as-of date older than **30 days**. Either condition trips A10 |
| **Q3 pass threshold** | §5.5's assumption **fails** if measured p95 data-to-signal latency exceeds **30 s**, or p95 signal-to-order exceeds **2 s**. Report the full distribution regardless; the mean is not the threshold |
| **Q4 pass thresholds — both bounds** | `max_spread_r` is **recalibrated** if > **30%** of sampled signal bars are rejected by the signal-time cap, in aggregate or in any single price decile below $5.00. It is declared **inert** if < **2%** are rejected in every decile. Between 2% and 30% it is **left alone and reported as calibrated** |
| **Timebox** | **4 weeks** from the first vendor contact. On expiry, whatever is answered is reported and the rest is recorded as unanswered with the reason, per §6 — the spike does not extend to reach a conclusion |
| **Budget** | **$600** total on trials and subscriptions for the spike itself. Q4 runs first because it needs no subscription, so a budget overrun cannot cost the one answer that can invalidate a shipped default |

Four notes on why these values and not others.

**The windows are a rule, not dates, and that is deliberate.** Pre-registration requires committing
before looking, but you cannot know which stretch was quiet without looking at *something*. Routing
the choice through VIX — a series this spike does not measure and cannot influence — gives a
window that is fixed in advance and still verifiably quiet, without the choice being informed by
spreads, gaps, or rejection rates. If the rule is run twice it returns the same windows.

**The 400 cap is tie-broken by date and symbol on purpose.** Any cap broken by a measured quantity
— largest gaps, highest RVOL — reintroduces exactly the survivorship bias §4.1 warns about,
through the back door of a sample-size limit.

**Q4's dead band is the load-bearing part.** 2%–30% means "the gate is calibrated" is a *third*
outcome with its own range, not the default when neither extreme fires. A one-sided threshold makes
"the gate is fine" unfalsifiable, which is the v1.3.1 defect class — a rule stated more broadly
than the case it was checked against. The per-decile clause below $5.00 exists because A21's concern
is specifically cheap stocks and an aggregate rate will hide a cheap-stock outage.

**These numbers are judgements, and none is from the PRD.** 95%, 200 symbols, 10%, 15%, 30 days,
30 s, 2 s, 30%, 2% — every one is this document's call, in the same sense that `Param.source` marks
a bound `(bounds: code)`. They are defensible, not derived. What makes them useful is that they are
committed, so a result that misses one cannot be reinterpreted as a pass.

---

## 8. What this spike must not become

§5.5 warns against building a scanner on a data source that turns out not to exist. The
symmetric failure is subtler and more likely: the spike code works, and it becomes the scanner by
accretion. `scripts/spike2a/` is throwaway, is not imported by `src/tradipy/`, and gets no test
coverage obligation. If the answer to Q1 is positive, Phase 3 is written fresh against the PRD.

Two further guardrails:

- **No threshold literal in spike code for a registered parameter.** Read from
  `tradipy.params`. Convention 1 applies to `scripts/` by policy, but note that **the AST lint
  does not currently scan it** — `test_no_registered_literal_hardcoded_in_source` iterates
  `SRC.glob("*.py")` with `SRC = src/tradipy`, non-recursively. Since this guardrail is the one
  keeping a second definition of `max_spread_r` out of the code that measures `max_spread_r`,
  extending the lint's roots to `scripts/` is a prerequisite for the guardrail being mechanical
  rather than aspirational. This is the same gap G8 flags in the docs that state the rule
  unqualified.
- **No `datetime` import into `src/tradipy/`.** §20.1 is the natural first implementation task
  *after* this spike, precisely because a `Bar` that knows when it closed should be shaped by the
  feed that was chosen. Adding a timestamp during the spike commits the bar model to whichever
  vendor happened to be under trial that afternoon.

---

## 9. Where the results land

| Artifact | Update |
|---|---|
| [PRD.md](PRD.md) §4, §4.2 | Filter set and refresh interval, if Q1 forces it |
| [PRD.md](PRD.md) §5.5 | Replace the recommendation with the finding |
| [PRD.md](PRD.md) Appendix C | Real quotes in place of estimates |
| [PRD.md](PRD.md) §18.7 | Data cost into the viability arithmetic |
| [PRD.md](PRD.md) §13 | A10, A21 dispositioned; A8's RVOL lookback if Q1 settles 30- vs 50-day |
| [PLAN.md](PLAN.md) | Phase 2a row → Done; new decisions D29+ for the provider choice and any recalibration; the "data is the binding constraint" paragraph rewritten to say what was measured |
| [docs/CHANGELOG.md](CHANGELOG.md) | Any PRD rule that changes, with what it was, what it is, and why |
| `src/tradipy/params.py` | Only thresholds with a §2.0 row, and only via a recorded decision |
| `tests/README.md` | The $1.00–$1.99 open findings, if Q4 resolves them |
