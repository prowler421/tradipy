# CLAUDE.md

Guidance for Claude Code (and other AI assistants) contributing to **tradipy**.

## What this project is

tradipy is the **invariant layer** of a Ross Cameron momentum day-trading system. It is
deliberately *not* the strategy engine. It exists because six review rounds each surfaced a
distinct defect class that the check designed for the previous round could not catch — four
in `docs/PRD.md`, a fifth in the code implementing it, and a sixth in the code that *measures*
it, which every check built for the first five was pointed away from. This code turns the PRD's
rules into executable, tested invariants.

`docs/PRD.md` is **normative**. Section §20 (Computation Semantics) governs on any conflict
between prose, comments, and code. Read it before changing behavior.

## Architecture

Sixteen small, pure modules under `src/tradipy/`, plus a CLI:

- `rounding.py` — tick arithmetic and polarity-aware threshold rounding. The governing
  principle is *"rounding must never weaken a constraint."* `Polarity.MINIMUM` rounds up;
  `Polarity.MAXIMUM` rounds down and clamps to one tick.
- `rejects.py` — the `Reject` reason codes, the `SoftFlag` codes for §4.2's seven Soft rows, the
  `ExitReason` codes for §3's post-entry rules and §9.2's closed trades, and the `RiskBlock` codes
  for §7's rule table. Four enums, not one: a soft row flags and never rejects, an exit closes a
  position that a rejection declined to open, and a `RiskBlock` is a fact about the *account*
  rather than the candidate — so splitting the namespaces makes mixing them a type error rather
  than a review finding (round 10, K5; the third arrived with Phase 4, transcribed from §20.12,
  and the fourth with Phase 5).
  Separate from `gates` so `quotes` need not depend on `gates`; `Reject` is re-exported from
  `tradipy.gates` for compatibility.
- `params.py` — the parameter registry: the single source of truth for every tunable
  threshold, each with its legal range, source citation, and polarity. Also holds the §2.0
  mode presets (an overlay on the registry defaults), the §7 hard caps, the cross-parameter
  coupling validator, and `Config.round_for()`, which resolves a rounding direction from the
  registry for every consumer that rounds.
- `bars.py` — PRD §20.4 flagpole geometry and the measured move.
- `quotes.py` — PRD §20.14 NBBO spread and quote validity.
- `score.py` — PRD §20.10 composite score and §14.2's conviction gate.
- `gates.py` — pre-entry gates and position sizing (spread caps, separation floor, room
  requirement, exit ladder, stop construction, sizing). No numeric threshold literal appears
  here, and no rounding direction either; both are read from the registry by name.
- `scanner.py` — PRD §4: the seven §4.2 hard filters, the seven §4.2 soft flags, and §4.3's
  ranked watchlist. Same two rules as `gates` — no threshold literal, no rounding direction.
  Pure: it applies §4.2 to a universe it is *given*, and sources nothing (D30).
- `session.py` — PRD §20.1/§20.2/§20.3/§20.5/§20.6 over an ordered series: session VWAP, HOD
  (wicks, plus §20.3's not-the-opening-print rule), the 9 EMA, §20.1's missing-bar gap rule, and
  `tighter()`/`wider()` as named definitions. A `SessionBar` carries **minutes from the open as an
  `int`**, not a timestamp — §21.1 forbids `datetime.now()` in strategy code. `through(i)` is the
  truncation primitive §21.1's look-ahead property test needs. Does **not** round.
- `setups.py` — PRD §3.2/§3.3/§3.4, §20.11 arbitration, and §3's post-entry rules as predicates.
  Same two rules as `gates` and `scanner`: no threshold literal, no rounding direction. Where §3
  defines nothing — *flag*, *consolidation candle*, *dip*, *leg* — the reading taken is on the
  function and raised in `docs/CHANGELOG.md`; `docs/PHASE-4-DESIGN.md` §5 is the list. Out of
  scope and stated: §20.12's state machine, T3's EMA trail (D18), §7's pre-order rules.
- `positions.py` — PRD §20.12's position state machine as a transition **table** plus a pure
  transition function, §3.1.1's stop-to-breakeven and its 50/25/25 ladder split over an integer
  share count, and §7.1.1's scale-in legality. §20.12's diagram and its table disagree on the
  permitted transitions and neither is complete; the reading taken is *the table where it has a
  row, the diagram where it has none*, recorded on `TRANSITIONS` and raised in `docs/CHANGELOG.md`.
- `risk.py` — PRD §6.3's eight pre-trade checks and nine of §7's eleven non-signal-time rows at
  the **Pre-order** enforcement point, returning §9.2's `RiskDecision` with **every** rule
  evaluated, asserted against `EVALUATED_RULES` so a rule dropped from the loop raises rather than
  shortening a list. Rows 7 and 8 — the drawdowns — have predicates and no block path *here*,
  because §7 marks them *Continuous* and *End of day*; `monitor.py` is their caller, and
  `UNREACHABLE_BLOCKS` is now **empty** with a test asserting the emptiness. State is handed in as
  a frozen `RiskState` (§10's `daily_state` row plus the open positions §7.1.1 needs) — no broker,
  clock, file or database. §7's two signal-time rows stay in `gates` and are re-applied here,
  because §7 marks their enforcement point pre-order as well. Does **not** round. Approval never
  trims: §7 says *"Reject order"* and §9.2's `approved_shares` says *"may be <"*; §7 governs and
  the conflict is raised.
- `orders.py` — PRD §6.1's bracket as an `OrderDraft`, §6.7's `sha256` idempotency key, §6.4's
  partial-fill decision. **One of the two boundaries of the whole package:** §6.2's lifecycle is
  `Signal → PreTradeRiskCheck → OrderDraft → Submit`, and the fourth arrow is *refused*, not
  deferred (D30). Every price on a draft is validated to be a whole tick, because a draft is the
  last representation before submission (§20.13).
- `daily.py` — PRD §10's `daily_state` as a value plus pure transitions, §20.8's snapshot gate,
  §9.2's `ClosedTrade`, and §7 row 4's *Post-trade close* accrual. The first thing in the package
  to **compute** `realized_pnl`, `consecutive_losses`, `day_trades_in_window` and the session
  peak rather than accept them. `SessionPhase.NO_TRADE` carries `start_of_day_equity = None` and
  `risk_state()` refuses it, because §20.8's *"does not fall back to a stale or computed value"* is
  only enforceable if the fallback does not exist. `to_row()` / `from_row()` map §10's columns as a
  plain `dict` — no store, so §7.1.2's *arithmetic* is testable and its *durability* is not.
  `UNPERSISTED_FIELDS` names the four §7 inputs §10 has no column for. Does **not** round.
- `monitor.py` — PRD §7's **other five** enforcement points (*Continuous*, *post-fill*,
  *Post-trade close*, *End of day* and *Any*) and its **Violation Action** column, which nothing
  had read. `RULES_AT` and `ACTION_FOR` are transcriptions of those two columns; the reason is
  §7's table order and the action is the *strictest* breach, which are two different questions.
  `flatten_all` computes §7's *"Flatten all"* per position and marks the four §20.12 cannot express
  — round 14's H3 as a blocker. Reuses `risk`'s three predicates and `RuleOutcome` rather than
  restating either. **The second boundary:** it decides, and sends nothing. Does **not** round.
- `poc.py` / `__main__.py` — the proof of concept. `poc` composes the gates into one
  evaluation and holds the simulated scanner universe; `__main__` is
  `python -m tradipy demo` / `evaluate` / `scan` / `setups` / `risk` / `monitor`, argparse and
  nothing else. Explicitly not the strategy engine: it gates a candidate and filters a universe it
  was handed, it does not find one.

Data flows one way. `rounding`, `rejects` and `bars` import only the standard library;
`params` imports `rounding`; `quotes` and `gates` import `params`, `rejects` and `rounding`;
`score` imports `params`; `session` imports `bars` and `params`; `scanner` imports `params`,
`rejects`, `score` and `gates`; `setups` imports `bars`, `session`, `params`, `rejects`,
`rounding` and `gates`; `positions` imports `params`, `rejects` and `rounding`; `risk` imports
`gates`, `params`, `positions`, `rejects`, `rounding` and `setups`; `orders` imports `params`,
`positions`, `rounding` and `setups`; `daily` imports `params`, `rejects`, `risk` and `setups`;
`monitor` imports `daily`, `params`, `positions`, `rejects`, `rounding` and `risk`. `poc` imports
everything up to and including `setups` and **none of the five modules Phases 5 and 6 added** —
both phases compose at the CLI, so `__main__` imports `poc` plus `setups`, `positions`, `risk`,
`orders`, `daily` and `monitor`. Everything is `Decimal`.

## Repository layout

```
src/tradipy/        # the library (rounding, rejects, params, bars, quotes, score, gates,
                    # scanner, session, setups, positions, risk, orders, daily, monitor)
                    # plus poc.py and __main__.py — the runnable proof of concept
tests/              # pytest suite — worked examples, registry, boundary/polarity marks,
                    # enforcement fixtures, and doc-count consistency
docs/               # start at docs/README.md (index)
  PRD.md            #   normative; §20 governs on any conflict
  PLAN.md           #   workstreams, sequencing, decision log D1–D35 (no D31), risks
  CHANGELOG.md      #   PRD corrections — NOT the root CHANGELOG.md, which tracks the package
  PHASE-2A-SPIKE.md #   data spike scope with binding pre-registration
  PHASE-4-DESIGN.md #   design record for the §3 strategy engine (D33)
  PHASE-5-DESIGN.md #   design record for §7 pre-order risk / §6 orders (D34) — and for
                    #   what it refused to build, which is the half §12.1 names first
  PHASE-6-DESIGN.md #   design record for §7's other five enforcement points, §10's
                    #   daily_state and §20.8 (D35) — the first phase whose §12.1
                    #   dependency was actually met
  api.md architecture.md development.md
  reviews/          #   every independent review round, kept unedited as the record
scripts/            # maintenance helpers — registry baseline, link checker
  spike2a/          #   the Phase 2a spike. Throwaway (PHASE-2A-SPIKE §8) but **inside** the
                    #   registry lint's scope, and the source of the sixth defect class.
                    #   provenance.py is the D30 gate and is not throwaway
data/spike2a/       # spike inputs — gitignored, empty on a clean clone. Every file is
                    # synthetic (D30); the generator declares it in PROVENANCE.txt and the
                    # measurement modules refuse to read anything that file does not cover
.claude/skills/     # guarantee-test, review-round (mirrored as .cursor/rules/*.mdc)
.github/workflows/  # CI and release; dependabot.yml covers Actions only
```

## Non-negotiable conventions

1. **One definition per threshold.** A registered threshold lives once in `params.PARAMS`
   and is read by name. No literal for a registered threshold anywhere else — the registry
   test enforces this against the PRD prose as well as the code, **within its stated scope**:
   the lint walks `src/tradipy/*.py` non-recursively plus `scripts/` recursively, skips
   `params.py` and `__init__.py` **inside `src/tradipy/` only**, and exempts an `_UNDISTINCTIVE`
   value set. `tests/` is not scanned, deliberately — fixtures must state literals (convention
   4). State the rule with that scope wherever it appears; an unqualified version of it is what
   F8 was about.
2. **Polarity, not the call site, decides rounding.** Every module that rounds routes through
   `Config.round_for(value, *governed_by)`, which reads the direction from the registry. Do
   not import `Polarity` into any of them and do not name a member at a call site: that gives
   direction two definitions. `gates.py`, `orders.py`, `positions.py`, `quotes.py`,
   `scanner.py` and `setups.py` are the consumers, and a test proves the import is absent from
   each **and** derives that list from the source, so a seventh cannot be added outside it.
   *(This sentence said "are the four" and named four for the whole of Phase 5, which added two
   — fixed inline per convention 8. The count is derived by
   `test_every_module_that_rounds_is_in_the_polarity_check`, which is why the drift was
   harmless; restating it here is what was not.)* It lived in `gates.py` as `_rounded` until
   Phase 3 added a second consumer; direction is registry data, so it moved onto the registry
   object. `risk.py`, `daily.py` and `monitor.py` do **not** round and are deliberately outside
   the list: a P&L is not a price level compared against a tick.
3. **`Decimal` everywhere money is compared to a tick or summed into P&L** (PRD §9.2). No
   `float`.
4. **Assertions test the derivation, not the value.** `assert cap == floor_to_tick(x) and
   cap <= x`, never `assert cap == Decimal("0.01")` — the latter passes under a wrong rule
   that happens to agree at that input.
5. **Documented open findings stay documented.** Some incoherent couplings (e.g. the
   min-tradeable-price band, documented on `min_tradeable_price_from_stop_bounds` and
   `signal_cap_ticks_at_min_r`, not on `validate_couplings`) are deliberately surfaced, not
   enforced, because the incoherent combination is the shipped default. Do not silently
   enforce them; that is a spec decision.
6. **Every guarantee needs the test that breaks it.** For any sentence of the form "X cannot
   happen", write the test that attempts X and asserts it fails. A test confirming the happy
   path passes whether or not the guarantee is enforced — which is how four guarantees came
   to be unenforced at once in v0.0.1, three of them with a passing test right beside the
   hole. This is the fifth defect class; see `tests/test_enforcement.py`.
7. **A bound the PRD does not state must say so.** `Param.source` marks code-originated
   ranges `(bounds: code)`. §2, §3.1.1, §3.4, §20.10 and §20.14 have no Bounds column, so
   their `lo`/`hi` are this module's judgement, not spec.
8. **Fix trivial findings; do not disposition them.** A review finding that is fixable in one
   line, has no spec implication and changes no behaviour gets **fixed in the same change**,
   listed in one line in the review, and gets no `docs/CHANGELOG.md` entry, no decision, and no
   disposition block. Seven rounds of review machinery exist for defects that recur or that
   require a spec call; a heading that says "four" above a list of six needs neither, and
   putting it through the full apparatus costs more than the defect. **The judgement is the
   convention's weak point** — when unsure whether a finding is trivial, disposition it. A
   finding that turns out to recur, or to have a behaviour consequence, was never trivial.
9. **All data is simulated, and nothing may reach a market.** PLAN D30 puts every dataset on a
   three-rung ladder — `SIMULATED` → `PAPER` → `LIVE` — and the current rung is `SIMULATED`. In
   practice: no broker SDK, market-data vendor client or network module may be imported anywhere
   in `src/`, `scripts/` or `tests/`; every dataset carries a `PROVENANCE.txt` declaring its
   origin and naming each file it covers with that file's digest; and data whose origin is
   undeclared is **refused, not assumed simulated** — the file that most needs a declaration is
   the one somebody added without writing one. `scripts/spike2a/provenance.py` is the gate and
   `tests/test_enforcement.py` enforces it. The import half is a **denylist** of twenty roots, so
   a green lint is not proof that nothing can reach a market; the provenance gate is the backstop,
   because it constrains what may be read rather than what may be imported. Advancing a rung means editing `PERMITTED_ORIGINS`,
   which a test pins deliberately so the edit cannot pass unnoticed: it is a recorded decision,
   and for `LIVE` the PRD §18.8 evidence bar as well. The consequence is stated rather than
   worked around — PHASE-2A-SPIKE §7 binds to *measured* data, so Q1–Q4 are unanswerable,
   Phase 3 stays gated through D29, and a spike run prints a *pipeline outcome*, never a §7
   verdict.

## Coding standards

- Python 3.13. Modern typing (`X | None`, builtins generics, `collections.abc`), `pathlib`,
  `dataclasses`, `enum`. No legacy `typing` aliases.
- Small functions, explicit types on public APIs, Google-style docstrings on public modules,
  classes, and functions.
- Formatting and imports are Ruff's job. Never hand-format. Two deliberate configurations to
  leave alone: the `PARAMS` registry is fenced with `# fmt: off` / `# fmt: on` so the PRD table
  reads row by row, and the PRD's `×`, `–`, `−` glyphs are allow-listed in Ruff's
  `allowed-confusables` (ASCII-ifying them breaks the PRD scanner in
  `test_parameter_registry.py`).
- The runtime is stdlib-only. Do not add a dependency, framework, Docker, CLI, or logging
  without a concrete, stated need.

## Testing expectations

- Every behavior change needs a test in `tests/`. Use the `spec`, `boundary`, and `polarity`
  markers where they apply.
- Regenerate the registry baseline only deliberately:
  `uv run python scripts/regen_registry_baseline.py`, then read the diff.
- `make check` (lint + format check + typecheck + test) must be green before work is done.

## Dependency management

Use `uv` exclusively: `uv sync`, `uv run ...`, `uv add ...`. Dev tools live in the `dev`
dependency group. Commit changes to `uv.lock`.

## Release process

Semantic Versioning. Bump `version` in `pyproject.toml`, add a dated section to
`CHANGELOG.md` (Keep a Changelog format), commit, tag `vX.Y.Z`, and push tags. The release
workflow builds the sdist and wheel.

## Documentation requirements

When behavior changes: update `CHANGELOG.md`, the relevant `docs/` file, and any affected
docstring. If a rule in the code diverges from `docs/PRD.md`, that is a spec question — raise
it, do not resolve it silently in code.

## Review checklist

- [ ] No new literal for a registered threshold; any bound the PRD does not state is marked
      `(bounds: code)` in its `Param.source`.
- [ ] Rounding goes through `Config.round_for`, with the polarity read from the registry.
- [ ] `Decimal` used for all price/P&L comparisons.
- [ ] Tests added/updated and assert the derivation, with the right marker.
- [ ] Every new guarantee has a test that performs the violation it forbids.
- [ ] No broker, vendor or network import in `src/`, `scripts/` or `tests/`; any new dataset is
      declared in a `PROVENANCE.txt` and read through `provenance.require` (D30).
- [ ] `make check` passes, and `uv run python -m tradipy demo` still exits 0.
- [ ] Root `CHANGELOG.md` updated for code/tooling; `docs/CHANGELOG.md` for spec decisions.
- [ ] No unnecessary dependency, abstraction, or framework introduced.
