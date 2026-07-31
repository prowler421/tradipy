# Review round 14 — a cold read of the Phase 5 build

> **Scope.** Phase 5 (PLAN **D34**): `src/tradipy/positions.py`, `src/tradipy/risk.py`,
> `src/tradipy/orders.py`, `tests/test_phase5.py`, the §6/§7/§20.12 block appended to
> `tests/test_enforcement.py`, the `risk` CLI command, and
> [PHASE-5-DESIGN.md](../PHASE-5-DESIGN.md). Working tree as reported by `git status`, before this
> round's own edits.
>
> **Findings prefix `H`.** `M` was round 13.
>
> **What kind of round this is, stated up front because round 12 got this wrong and round 13
> corrected it:** a cold read of the Phase 5 *artifacts* by a party that did not write them,
> carrying full repository context from `CLAUDE.md`. It is **not** the §21.1 / Workstream 11 cold
> read of the whole codebase by a reader with no prior context — that item is still outstanding, as
> it has been across all six defect classes. It also ran **no second adversarial pass over its own
> draft**, which round 13 recorded as a limitation of its process and which applies here too.
>
> **`make check` was not run in this round either.** The sandbox denied `uv` cache access and the
> system Python has no `pytest`. Every test claim in the documents under review is therefore
> **documented, not reproduced** by this round. That is the same gap round 12 had and round 13
> closed by having a working toolchain; it is open again, and the verdict below is qualified by it.

---

## Verdict

Phase 5 is **well scoped and well built for what D34 claims**: the pure half of §6/§7/§20.12 —
signal → `RiskDecision` → `OrderDraft`, with transport, persistence and the §18.7 viability gate
explicitly refused or deferred. The design document is unusually honest about that boundary; the
implementation matches it; and the test suite applies the project's defect-class lessons —
especially convention 6 — to the new surface.

The main weaknesses are not implementation bugs but **spec tensions the code correctly surfaces**
rather than silently fixing: total open risk versus concurrent positions, daily loss versus PDT
reachability, and §20.12's gaps for post-T1 invalidation and kill-switch / EOD flattening.

| Area | Assessment |
|---|---|
| Gate posture (D34) | Clear and consistently enforced |
| Module boundaries | Clean one-way graph; `poc` untouched; CLI composes |
| PRD transcription | Strong within stated scope; readings raised in [CHANGELOG.md](../CHANGELOG.md) |
| Registry discipline | 9 new rows, coupling for the ladder sum, FINRA figures as constants |
| Test depth | Worked examples, per-row §7 fixtures, enforcement violations, joint-incoherence pins |
| **`make check`** | **Not verified in this review** (sandbox blocked `uv`) |

---

## Where this stands against the design

[PHASE-5-DESIGN.md](../PHASE-5-DESIGN.md) is the authoritative record. Its central argument holds:
**§18.7 governs whether to trade; Phase 5 governs whether the arithmetic that would refuse a trade
is correct.** The three modules do what its §3–§5 describe, and the dependency table matches the
imports.

What the design says is **not** built — submit, DB-backed idempotency, a kill-switch file reader,
the continuous drawdown loop, T3's broker trail — is also absent from the code, with tests that pin
the absence rather than imply it closed.

---

## Implementation highlights

**`positions.py` — state machine and ladder mechanics.** Twelve-state `TRANSITIONS` with the
documented *table-where-it-has-a-row, diagram-where-it-has-none* reading. `leg_quantities` enforces
the §21.6 invariant (`t1 + t2 + t3 == shares`) with a breaking `__post_init__`. `scale_in_permitted`
checks **both** state and arithmetic, matching §7.1.1's after-T1-only conclusion.
`reachable_exit_reasons` makes the §7.2 / EOD flatten gap *visible* instead of papering over it.

**`risk.py` — pre-order engine.** `approve()` evaluates every rule, reports all failures, and
self-checks against `EVALUATED_RULES` — the right response to the fifth defect class.
`UNREACHABLE_BLOCKS` for rows 7–8 is deliberate and tested; the predicates exist for Phase 6.
`total_open_risk` uses live stops and includes `PENDING_ENTRY`, correct per §7.1.1.
`OrderIntent.REDUCE` bypasses entry checks, a correct reading of *"allow exits"*. `approve_all`
accrues state sequentially, which §7 row 1 requires.

**`orders.py` — bracket construction.** Four legs, T3's trail excluded per D18. Tick validation on
`OrderLeg` construction — the last binding point before submission. `idempotency_key` uses `sha256`
with a separator-collision guard. Entry limit `ceil`, stop-limit `floor`, per the documented §20.13
reading.

**CLI integration.** `python -m tradipy risk` runs the §3 examples through `approve_all` and prints
the headline finding — the second signal blocked by total risk while `max_open_positions` still has
room. That is good pedagogical honesty.

---

## Findings

### H1 — `max_open_positions` is inert at full risk *(spec question, MEDIUM-HIGH)*

Reproduced in tests, raised not resolved. §2.2 sizes each trade to approximately the whole risk
budget; §7 row 1 caps **total** open risk at the same figure. A second full-risk position always
hits `MAX_RISK_EXCEEDED` before `MAX_POSITIONS`.

**Disposition:** correct to raise in [CHANGELOG.md](../CHANGELOG.md) and pin both directions. Do
not "fix" in code without a spec decision on whether the cap is per-position or total, or whether
concurrency binds only after T1.

### H2 — PDT row unreachable at the default $30k equity *(spec question, MEDIUM)*

The daily-loss lockout (5% ceiling, $1,500) always fires before equity can fall $5,000 to FINRA's
floor. The rule is not dead — it is reachable near `start_of_day_equity`'s `lo` of $25,000 — but it
is **jointly incoherent** with the defaults.

**Disposition:** as H1 — pinned, not enforced as a coupling (convention 5 / A25 precedent).

### H3 — §20.12 cannot express post-T1 invalidation or a kill-switch flatten *(spec question, MEDIUM-HIGH)*

Under the chosen transition reading, `T1_FILLED → {T2_FILLED, STOPPED_OUT}` only, so `INVALIDATED`
and `BAILED_OUT` after T1 have no target state. Likewise `KILL_SWITCH` and `EOD_FLAT` are reachable
only from `TRAILING`.

The code *reports* this via `reachable_exit_reasons` and tests, and does not widen the machine
unilaterally. That is the right call, but it means **Phase 5 and Phase 4's post-entry rules do not
compose cleanly for mid-ladder scenarios** until the PRD resolves §20.12.

### H4 — G2 narrowed, not closed *(MEDIUM)*

`daily_loss_pct` now has a pre-order enforcement point in `approve()`. Continuous (1 s) and
post-fill enforcement remain Phase 6 / transport. Claiming G2 closed would be the F8 shape; the
design and the `RiskBlock.DAILY_LOSS_LIMIT` docstring correctly say *narrows*.

### H5 — trading-hours lower bound delegated to `Levels` *(LOW-MEDIUM)*

`approve()` checks only `trigger_minute <= session_last_entry_minute`; negative ordinals are blocked
at `Levels.__post_init__`. Adequate for the MVP path, since setups always supply valid minutes.
**G9** — premarket unrepresentable — remains open, because ordinal minute 0 *is* 09:30 by
construction.

### H6 — the CLI demo skips two optional §7 inputs *(LOW)*

`_run_risk` / `approve_all` do not pass `idempotency_key` or `spread_now`, so the duplicate-order
rule prints *"not evaluated"*. That is correct reporting per the skip-when-absent design, but the
demo does not exercise the full audit trail a production caller would supply.

### H7 — `RiskDecision` omits `signal_id` and `evaluated_at` *(LOW, by design)*

Documented on `RiskDecision`; the caller and transport attach these. Fine for D34's scope.

---

## What is genuinely good

1. **Refusal versus deferral** is stated everywhere it matters — design §1.1, `orders.py`'s header,
   the CLI banner, the root changelog.
2. **The fourth namespace, `RiskBlock`,** prevents account-level blocks from polluting candidate
   rejection. K5 extended correctly.
3. **The no-clock pattern** is consistent with Phase 4 — `trigger_minute`,
   `seconds_since_submit`, a supplied `session_date`.
4. **The convention 6 suite** covers leg-sum violations, sub-tick drafts, illegal transitions,
   dropped rules, namespace mixing, the D30 import allowlist, and the absence of persistence.
5. **The derived boundary guard** (`test_every_phase_5_threshold_has_a_boundary_fixture`) prevents
   the PHASE-4-DESIGN "six of nine" prose drift.
6. **The design document's own adversarial fact-check** — 24 discrepancies found, five code and
   test gaps fixed — is the right methodology for this repository.

---

## Risk the findings list underplays

The largest operational risk is **misreading "Phase 5 built" from PLAN or §12.1 without reading
PHASE-5-DESIGN §2.** Order routing, crash-safe idempotency, restart-surviving risk limits and
calibrated thresholds are all still out of scope. Wiring a broker adapter on top of this layer
before resolving H1–H3 would bake in audit semantics — reject versus trim, concurrency semantics,
mid-ladder exits — that the PRD has not settled.

Second: **`session_dd_pct` and `multi_day_dd_pct` now have readers but only as predicates.** The
registered-but-unenforced count improved; the continuous and end-of-day **enforcement** gap remains
until Phase 6.

---

## Recommended next steps

**Now, for merge confidence:** run `make check` locally and `uv run python -m tradipy risk` — the
design document itself says its author could not.

**Raise as spec questions, do not code-resolve:** H1, H2, H3, `approved_shares` trim versus reject
(already raised), and the §20.12 diagram/table reconciliation.

**After the spike, Phase 4b and D31:** the transport half, slippage (`impact_coefficient`), the
viability gate, and persistence for §6.7 and §7.1.2.

---

## Appendix: verification limits

- **Scope:** uncommitted working-tree changes per `git status`. Read
  [PHASE-5-DESIGN.md](../PHASE-5-DESIGN.md), `positions.py`, `risk.py`, `orders.py`,
  `tests/test_phase5.py`, the Phase 5 block in `tests/test_enforcement.py`, the `risk` CLI command,
  [CHANGELOG.md](../CHANGELOG.md) and PLAN **D34**.
- **`make check` / `uv run pytest`:** not run — the sandbox denied `uv` cache access and the system
  Python has no `pytest`. The test claims in the documents (291 functions, a green gate) are
  documented, **not reproduced here**.
- **Review type:** cold read of the Phase 5 artifacts with full repository context from
  `CLAUDE.md`; not a formal adversarial second pass over this document's own draft.

---
---

# Disposition (added after the round, by the party that built Phase 5)

**This section is not part of the review.** Reviews are kept unedited as the record of what was
found; the disposition of each finding goes here, below the rule, so that what the round said and
what was done about it cannot be conflated later.

| Finding | Disposition |
|---|---|
| **H1** | **Already raised, no change.** [CHANGELOG.md](../CHANGELOG.md)'s Unreleased section carries it as the first of two findings-that-change-a-verdict, with three candidate resolutions and none taken; `tests/test_phase5.py` pins it in both directions at both mode presets. The review's instruction — do not code-resolve without a spec decision — is the disposition already in force |
| **H2** | **Already raised, no change.** Same treatment, as the second finding. Not enforced as a coupling per convention 5 and A25's precedent: the incoherent combination is the shipped default, so raising would make `Config.default` throw |
| **H3** | **Already raised; the review's framing is stronger than the document's and the document was corrected.** `positions.py`'s `_transitions` docstring and `reachable_exit_reasons` both record the gap, and the CHANGELOG carries two rows for it. What the round adds is the *composition* consequence — that Phase 4's post-entry predicates and Phase 5's state machine do not meet for a mid-ladder invalidation — which the design document had recorded only as a cost of the reading rather than as an inter-phase boundary. PHASE-5-DESIGN §5's §20.12 row and §6's second CHANGELOG row now say so. **No code change:** widening a normative table on this layer's authority is the thing the reading exists to avoid |
| **H4** | **Agreed, already stated that way.** No change |
| **H5** | **Agreed, already stated that way.** The `Levels.__post_init__` floor was itself added by the design document's own fact-check, one step before this round; G9 stays open. No change |
| **H6** | **Fixed in this change**, per convention 8 — one call site, no spec implication, no behaviour change to any rule. `python -m tradipy risk` now computes §6.7's key **before** `approve`, which is also the ordering that section requires (*"persisted before order submission"*), and passes it through a new `approve_all(..., keys=...)` parameter shaped like the existing `groups`. `approve_all` folds an approved key into `submitted_keys`, without which §6.3's eighth check is inert across a batch — a caller with no store could not reach the duplicate case at all. `risk.py` still does not import `orders`: the key is supplied, because §6.2 puts `PreTradeRiskCheck` before `OrderDraft` and a risk engine that built orders would invert that. One fixture added, `test_approve_all_folds_an_approved_key_into_the_submitted_set`, asserting on `RiskDecision.blocks` rather than on `reason` — the second signal fails §7 row 1 as well (that is H1), and row 1 is earlier in §7's table, so demanding `reason is DUPLICATE_ORDER` would assert a rule ordering nobody specified. `spread_now` is deliberately still unsupplied: the demo has no order-time quote distinct from the signal-time one, and passing the same value twice would be a check dressed as a comparison. That rule already reports *"at signal time (unchanged)"* and is evaluated, not skipped |
| **H7** | **Agreed, by design.** No change |

**No new defect class.** H1 and H2 are further populations of the **third** (joint incoherence), and
the count stays at six. H3 is a §20.12 transcription gap rather than a class. What is new and worth
recording is the *shape* H1 and H2 share and which the existing boundary fixtures cannot catch: both
need **two parameters read together**, and in each case one of them is not a gate threshold at all
(`start_of_day_equity`, `max_open_positions`). Round 12's §5.2 heuristic — that the boundary
fixtures vary the parameters an example admits while holding its inputs fixed — explains the miss,
and the thing that found both was running §7's rules against §2's own worked examples rather than
reading either.

**On the round's own limitation.** Two consecutive rounds have now been unable to run `make check`,
for different environmental reasons. That is worth naming as a trend rather than as two incidents:
round 13 is the only round in the series that ran the real gate, and it found it **red** on the
changeset it reviewed. Nothing in this round or in the Phase 5 changeset should be read as evidence
that the gate is green.
