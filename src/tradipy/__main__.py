"""``python -m tradipy`` — the runnable proof of concept.

Six subcommands:

``demo``
    Replay the three PRD §3 worked examples through every gate and self-check the derived
    values against the tables. Exits non-zero on any disagreement, so it doubles as a
    smoke test of the whole invariant layer.

``evaluate``
    Run one candidate of your own through the same chain and print accept/reject with the
    binding reason code.

``scan``
    Run a **simulated** universe through PRD §4.2's seven hard filters and seven soft flags
    and print the §4.3 ranked watchlist. Simulated because PLAN D30 puts the project on the
    ``SIMULATED`` rung of the data ladder; the universe is constructed in
    :func:`tradipy.poc.simulated_universe`, not read from anywhere.

``setups``
    Replay the same three §3 worked examples **from their bar series** through the Phase 4
    setup evaluators — PRD §21.1's worked-example row, which asks for exactly that. This is
    not a second spelling of ``demo``: ``demo`` is handed the entry, stop, target and
    resistance from the §3 tables and applies the gates, while this recognises the pattern
    and derives all four. Where the two disagree, the disagreement is the point — see §3.4.

``risk``
    Take the §3 signals through PRD §7's pre-order rule table (Phase 5) and, for each one the
    account may take, build the §6.1 bracket. **Nothing is submitted** — PLAN D30 refuses
    transport, so this prints a draft and stops, which is exactly where
    :mod:`tradipy.orders` stops. Signals are approved *sequentially* because §7's first row
    caps **total** open risk, and that is what makes the second signal's rejection the
    interesting output rather than a bug.

``monitor``
    Run one session through PRD §7's **other five** enforcement points (Phase 6): §20.8's
    snapshot, a §9.2 ``ClosedTrade`` accrued at *Post-trade close*, the daily-loss row at
    *post-fill* and *Continuous*, the kill switch at *Any*, and the flatten those actions
    require. **Nothing is flattened** — this prints the directive and the positions §20.12
    cannot express one for, which is the phase's headline finding.

Stdlib only — ``argparse`` and ``decimal``. The package has no runtime dependencies and this
does not add one.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal, InvalidOperation

from tradipy.daily import (
    UNPERSISTED_FIELDS,
    ClosedTrade,
    from_row,
    mark_to_market,
    open_session,
    record_close,
    record_multi_day_peak,
    record_snapshot,
    risk_state,
    to_row,
)
from tradipy.monitor import (
    EnforcementPoint,
    MonitorDecision,
    apply,
    eod_flat_due,
    flatten_all,
    unrepresentable,
)
from tradipy.monitor import evaluate as monitor_evaluate
from tradipy.orders import OrderDraft, bracket, idempotency_key
from tradipy.params import MODES, PARAMS, Config, Mode
from tradipy.poc import (
    BULL_FLAG_BARS,
    Candidate,
    Evaluation,
    bull_flag_geometry,
    check_against_prd,
    evaluate,
    setup_examples,
    simulated_universe,
)
from tradipy.poc import worked_examples as prd_examples
from tradipy.positions import OPEN_STATES, PositionState, leg_quantities
from tradipy.quotes import Quote
from tradipy.rejects import ExitReason
from tradipy.risk import OpenPosition, RiskDecision, RiskState, approve_all
from tradipy.rounding import TICK_SIZE
from tradipy.scanner import ScanReport, scan
from tradipy.score import Catalyst, ScoreInputs, composite_score, meets_conviction_gate
from tradipy.setups import SetupOutcome, SetupSignal

PASS, FAIL = "PASS", "FAIL"
RULE = "─" * 78


def _dp(places: int) -> Decimal:
    """A quantizer with ``places`` decimal places, e.g. ``_dp(2)`` -> ``Decimal('0.01')``.

    Built with ``scaleb`` rather than written as a literal on purpose: display precision is
    not a threshold, but ``Decimal("0.01")`` and ``Decimal("0.1")`` collide numerically with
    registered defaults, and ``test_no_registered_literal_hardcoded_in_source`` cannot tell
    the difference. It flagged four such literals in the first draft of this file, which is
    the lint doing its job — the right response is to stop writing them, not to widen the
    exemption list.
    """
    return Decimal(1).scaleb(-places)


def _decimal(text: str) -> Decimal:
    try:
        return Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"{text!r} is not a decimal number") from None


def _print_evaluation(ev: Evaluation, *, show_header: bool = True) -> None:
    c = ev.candidate
    if show_header:
        title = f"{c.section} {c.label}".strip()
        print(f"\n{title}  —  entry {c.entry}, resistance {c.resistance}")
    for g in ev.results:
        mark = PASS if g.passed else FAIL
        code = f"  [{g.reject.value}]" if g.reject else ""
        print(f"  {mark}  {g.gate:<18} {g.section:<8} {g.detail}{code}")
    verdict = "ACCEPT" if ev.accepted else f"REJECT  {ev.reject.value if ev.reject else ''}"
    print(f"  ->  {verdict}")


def _run_demo(cfg: Config, mode: Mode) -> int:
    print(RULE)
    print("tradipy Phase 1 — PRD §3 worked examples")
    print(RULE)
    print(
        f"mode={mode}  start_of_day_equity={cfg['start_of_day_equity']}  "
        f"max_risk_per_trade_pct={cfg['max_risk_per_trade_pct']}"
    )
    if mode != "experienced":
        print(
            "\nNote: the PRD's worked examples compute risk as 1% x $30,000, which is the\n"
            "'experienced' preset. Share counts below will differ from the tables, and the\n"
            "self-check is skipped. Re-run with --mode experienced to reproduce them."
        )

    geo = bull_flag_geometry()
    print(f"\n§20.4 flagpole geometry, derived from {len(BULL_FLAG_BARS)} bars:")
    print(
        f"  flagpole      bars [{geo.pole_start}..{geo.pole_end}], "
        f"low {geo.pole_low} -> high {geo.pole_high}"
    )
    print(f"  height        {geo.height}")
    print(f"  flag          high {geo.flag_high}, low {geo.flag_low}")
    print(f"  retrace       {(geo.retrace * 100).quantize(_dp(1))}%  (§3.2 crit. 3: <= 50%)")
    print(
        f"  flag/pole vol {geo.flag_volume_ratio.quantize(_dp(2))}   "
        f"(§3.2 crit. 5: <= 0.70, contraction)"
    )

    failures: list[str] = []
    accepted = 0
    for candidate in prd_examples():
        ev = evaluate(candidate, cfg)
        _print_evaluation(ev)
        accepted += ev.accepted
        if mode == "experienced":
            for mismatch in check_against_prd(ev):
                failures.append(f"{candidate.section}: {mismatch}")

    print(f"\n{RULE}")
    print(f"{accepted}/{len(prd_examples())} examples accepted by the gate chain.")
    if mode != "experienced":
        print("Self-check skipped (see note above).")
        return 0
    if failures:
        print(f"SELF-CHECK FAILED — {len(failures)} value(s) disagree with the PRD tables:")
        for f in failures:
            print(f"  {f}")
        return 1
    print("Self-check OK — every derived value matches the PRD §3 tables.")
    return 0


def _print_scan_report(report: ScanReport, cfg: Config, *, verbose: bool) -> None:
    q4 = _dp(4)
    print(f"\n§4.2 evaluation — {len(report.results)} candidate(s), 7 hard filters, 7 soft flags:")
    for result in report.results:
        sym = result.candidate.symbol
        if result.passed and result.score is not None:
            head = f"  PASS    {sym:<8} score {result.score.total.quantize(q4)}"
        else:
            reject = result.reject
            head = f"  REJECT  {sym:<8} {reject.value if reject else ''}"
        flags = ", ".join(f.value for f in result.flags)
        print(head + (f"   flags: {flags}" if flags else ""))
        if not verbose:
            # One line of evidence for a rejection, so the verdict is never unexplained.
            for hard in result.hard:
                if not hard.passed:
                    print(f"            {hard.filter:<22} {hard.detail}")
            continue
        for hard in result.hard:
            mark = PASS if hard.passed else FAIL
            print(f"      {mark}  {hard.filter:<22} {hard.detail}")
        for soft in result.soft:
            mark = "FLAG" if soft.raised else "  · "
            print(f"      {mark}  {soft.filter:<22} {soft.detail}")

    print(f"\n§4.3 watchlist — top {cfg['watchlist_size']} of {len(report.survivors)} survivor(s):")
    if not report.watchlist:
        print("  (empty)")
    for rank, result in enumerate(report.watchlist, start=1):
        score = result.score
        if score is None:
            # Unreachable: the watchlist holds survivors and §4.1 scores every survivor. Kept
            # as a raise rather than an `assert`, which `python -O` strips — a display layer
            # that silently prints nothing is how a missing value stops being noticed.
            raise RuntimeError(
                f"{result.candidate.symbol} reached the watchlist without a §20.10 score"
            )
        print(
            f"  {rank}.  {result.candidate.symbol:<8} {score.total.quantize(q4)}   "
            f"pct_change {score.pct_change.quantize(q4)}  rvol {score.rvol.quantize(q4)}  "
            f"float {score.float_inverse.quantize(q4)}  "
            f"pm_vol {score.premarket_vol.quantize(q4)}  "
            f"catalyst {score.catalyst.quantize(q4)}"
        )


def _run_scan(cfg: Config, mode: Mode, *, verbose: bool) -> int:
    print(RULE)
    print("tradipy Phase 3 — PRD §4.2 scanner over a simulated universe")
    print(RULE)
    print(f"mode={mode}  watchlist_size={cfg['watchlist_size']}")
    print(
        "\nData origin: SIMULATED (PLAN D30). This universe is constructed, not read — no\n"
        "file, feed or network is touched. D32 opened Phase 3 on simulated data, so the\n"
        "filters below are applied correctly but none of their thresholds is calibrated:\n"
        "Phase 2a Q1 (is §4.2's input contract obtainable from real data?) is unanswered.\n"
        "See docs/PHASE-3-READINESS.md."
    )
    _print_scan_report(scan(simulated_universe(cfg), cfg), cfg, verbose=verbose)
    return 0


def _run_evaluate(args: argparse.Namespace, cfg: Config) -> int:
    spread = args.spread
    quote = Quote(
        bid=args.entry - spread,
        ask=args.entry,
        bid_size=args.bid_size,
        ask_size=args.ask_size,
        age_seconds=args.quote_age,
        estimated=args.spread_estimated,
    )
    candidate = Candidate(
        label="candidate",
        entry=args.entry,
        raw_stop=args.stop,
        structural_target=args.target if args.target is not None else args.resistance,
        resistance=args.resistance,
        quote=quote,
    )
    ev = evaluate(candidate, cfg)
    print(
        f"mode={cfg.mode}  equity={cfg['start_of_day_equity']}  "
        f"risk={cfg['max_risk_per_trade_pct']}"
    )
    _print_evaluation(ev)

    if args.rvol is not None:
        score = composite_score(
            ScoreInputs(
                pct_change=args.pct_change,
                rvol=args.rvol,
                float_shares=args.float_shares,
                premarket_volume=args.premarket_volume,
                catalyst=Catalyst(args.catalyst),
            ),
            cfg,
        )
        q4 = _dp(4)
        verdict = "PASS" if meets_conviction_gate(score, cfg) else "FAIL"
        print(
            f"\n  §20.10 composite score  {score.total.quantize(q4)}  "
            f"(gate >= {cfg['min_conviction_score']}: {verdict})"
        )
        for label, value in [
            ("pct_change", score.pct_change),
            ("rvol", score.rvol),
            ("float_inverse", score.float_inverse),
            ("premarket_vol", score.premarket_vol),
            ("catalyst", score.catalyst),
        ]:
            print(f"      {label:<15} {value.quantize(q4)}")

    # 3, not 2: argparse already owns 2 for usage errors, and a rejected candidate is a
    # correct answer rather than a failure to run.
    return 0 if ev.accepted else 3


def _print_setup_outcome(out: SetupOutcome, section: str) -> None:
    verdict = "ACCEPT" if out.accepted else f"REJECT  {out.reject.value if out.reject else ''}"
    print(f"\n{section} {out.setup_type.value}  ->  {verdict}")
    for c in out.criteria:
        print(f"  {PASS if c.passed else FAIL}  {c.name:<44} {c.detail}")
    lv = out.levels
    if lv is None:
        return
    print(
        f"      entry {lv.entry_price}  stop {lv.stop_price}  R {lv.r_per_share}  "
        f"T1 {lv.ladder.t1}  T2 {lv.ladder.t2}"
    )
    print(
        "      resistance "
        + ", ".join(f"{name} {level}" for name, level in lv.resistance.candidates)
        + f"  ->  {lv.resistance.source}"
    )
    if out.signal is not None:
        print(f"      shares {out.signal.shares:,}  direction {out.signal.direction}")


def _run_setups(cfg: Config, mode: Mode) -> int:
    """Replay the §3 examples from bars, and check every derived value against its table."""
    print(RULE)
    print("tradipy Phase 4 — the three PRD §3 setups, from bar series")
    print(RULE)
    print(f"mode={mode}  equity={cfg['start_of_day_equity']}")
    print(
        "\nData origin: SIMULATED (PLAN D30). These bar series are constructed to the §3\n"
        "worked-example tables, not read — no file, feed or network is touched. D33 opened\n"
        "Phase 4 on simulated data, so the criteria below are applied as §3 states them and\n"
        "not one of their thresholds is calibrated. See docs/PHASE-4-DESIGN.md."
    )

    disagreements: list[str] = []
    for ex in setup_examples():
        out = ex.evaluate(cfg)
        _print_setup_outcome(out, ex.section)
        if (out.reject or None) != ex.expect_reject:
            disagreements.append(
                f"{ex.section}: verdict {out.reject} where the fixture expects {ex.expect_reject}"
            )
        lv = out.levels
        if lv is None:
            disagreements.append(f"{ex.section}: no levels derived")
            continue
        derived: dict[str, object] = {
            "entry": lv.entry_price,
            "stop": lv.stop_price,
            "r": lv.r_per_share,
            "t1": lv.ladder.t1,
            "t2": lv.ladder.t2,
        }
        if out.signal is not None:
            derived["shares"] = out.signal.shares
        disagreements += [
            f"{ex.section} {key}: derived {derived.get(key)}, PRD table states {want}"
            for key, want in ex.expect.items()
            if derived.get(key) != want
        ]

    print(f"\n{RULE}")
    print(
        "§3.4 is rejected on purpose. Its table names the HOD ($4.15) as the nearest overhead\n"
        "resistance; §3.1.1's set also contains the next whole dollar ($4.00), which is nearer\n"
        "and inside the required room. Every other line of that table reproduces exactly. The\n"
        "disagreement is raised in docs/CHANGELOG.md, not resolved here."
    )
    if disagreements:
        print("\nSelf-check FAILED — derived values disagree with the §3 tables:")
        for line in disagreements:
            print(f"  - {line}")
        return 1
    print("Self-check OK — every derived value matches its §3 table, including the rejection.")
    return 0


#: §6.7's key needs a session identifier and an account. Both are fixtures here, and both are
#: fixed rather than generated: §6.7's whole argument is that a value unique by construction
#: cannot serve as a dedupe key, so a demo that generated either would print a different key on
#: every run and quietly demonstrate the opposite of the rule.
_DEMO_SESSION_DATE = "2026-07-31"
_DEMO_ACCOUNT_ID = "SIMULATED-PAPER-NONE"


def _print_risk_decision(signal: SetupSignal, decision: RiskDecision) -> None:
    verdict = "APPROVE" if decision.approved else f"BLOCK  {decision.reason}"
    print(f"\n{signal.setup_type.value}  {signal.shares:,} shares  ->  {verdict}")
    for rule in decision.rules_evaluated:
        print(f"  {PASS if rule.passed else FAIL}  {rule.rule:<52} {rule.detail}")


def _print_draft(draft: OrderDraft) -> None:
    print(f"      §6.1 bracket  OCA {draft.oca_group}")
    print(f"      §6.7 key      {draft.idempotency_key}")
    for leg in draft.legs:
        limit = f"limit {leg.limit_price}" if leg.limit_price is not None else ""
        stop = f"stop {leg.stop_price}" if leg.stop_price is not None else ""
        print(
            f"        {leg.purpose.value:<9} {leg.side.value:<4} {leg.order_type.value:<11} "
            f"{leg.quantity:>6,}  {limit} {stop}".rstrip()
        )
    q = draft.quantities
    print(
        f"        §3.1.1 ladder  T1 {q.t1:,} + T2 {q.t2:,} + T3 {q.t3:,} = {q.shares:,} "
        "(T3 trails the 9 EMA — no leg, per D18)"
    )


def _run_risk(cfg: Config, mode: Mode) -> int:
    """Take the §3 signals through §7's pre-order rules and build the drafts that survive."""
    print(RULE)
    print("tradipy Phase 5 — §7 pre-order risk, then the §6.1 bracket")
    print(RULE)
    print(f"mode={mode}  start_of_day_equity={cfg['start_of_day_equity']}")
    print(
        "\nData origin: SIMULATED (PLAN D30). Nothing below is submitted anywhere: the §6.2\n"
        "lifecycle is Signal -> PreTradeRiskCheck -> OrderDraft -> Submit, and D30 refuses the\n"
        "fourth arrow. There is no broker, no paper account and no §18.7 viability gate result.\n"
        "D34 opened Phase 5's pure half only. See docs/PHASE-5-DESIGN.md."
    )

    # Built with an explicit loop rather than a walrus comprehension: the comprehension's element
    # type is `SetupSignal | None` however the filter is written, and `approve_all` takes
    # `Sequence[SetupSignal]`.
    signals: list[SetupSignal] = []
    for example in setup_examples():
        outcome = example.evaluate(cfg)
        if outcome.signal is not None:
            signals.append(outcome.signal)
    print(
        f"\n{len(signals)} of 3 §3 examples produced a signal; §3.4 was rejected by §3.1.1's "
        "room gate (Phase 4, unresolved)."
    )

    # §6.7's key is computed **before** the pre-trade check, not after it: that section requires it
    # persisted before submission, and §6.3's eighth check is a check *on* it. Supplying it here is
    # also what stops the duplicate-order row printing "not evaluated" — a demo whose audit trail
    # is two rows shorter than a real caller's teaches the wrong thing about the trail.
    keys = [
        (
            signal.symbol,
            idempotency_key(
                signal.symbol,
                signal.setup_type,
                _DEMO_SESSION_DATE,
                signal.levels.trigger_minute,
                _DEMO_ACCOUNT_ID,
            ),
        )
        for signal in signals
    ]

    # Sequentially, sharing one RiskState: §7 row 1 caps *total* open risk across positions.
    state = RiskState(start_of_day_equity=cfg["start_of_day_equity"])
    decisions = approve_all(signals, state, cfg, keys=keys)
    approved = 0
    for signal, decision in zip(signals, decisions, strict=True):
        _print_risk_decision(signal, decision)
        if not decision.approved:
            continue
        approved += 1
        _print_draft(
            bracket(signal, signal.levels.entry_price, _DEMO_SESSION_DATE, _DEMO_ACCOUNT_ID, cfg)
        )

    print(f"\n{RULE}")
    print(
        "The second signal is blocked on purpose, and it is Phase 5's headline finding. §7 row 1\n"
        "caps TOTAL open risk — across all positions, from their current live stops — at\n"
        "start_of_day_equity x max_risk_per_trade_pct, which is the same budget §2.2 sizes a\n"
        "SINGLE position to. So a second position is rejected whenever the first is still at full\n"
        "risk, at every legal configuration, while §2 advertises up to 3 concurrent positions and\n"
        f"max_open_positions is {cfg['max_open_positions']} here. §7.1.1 derives exactly this for\n"
        "scale-ins and does not extend it to new positions. Raised in docs/CHANGELOG.md, not\n"
        "resolved: see docs/PHASE-5-DESIGN.md §6 for the three candidate resolutions."
    )

    # The §20.12 path the approved drafts would follow, printed so the state machine is visible
    # rather than only tested. `transition` refuses anything off this path.
    path = " -> ".join(
        s.value
        for s in (
            PositionState.IDLE,
            PositionState.ARMED,
            PositionState.PENDING_ENTRY,
            PositionState.OPEN_FULL,
            PositionState.T1_FILLED,
            PositionState.T2_FILLED,
            PositionState.TRAILING,
            PositionState.CLOSED,
        )
    )
    print(f"\n§20.12 happy path: {path}")
    print(
        "Only the transitions §20.12's table enumerates are permitted, plus IDLE -> ARMED and\n"
        "the three exit states -> CLOSED, which its table omits and its diagram supplies. One\n"
        "consequence: a §3 invalidation firing after T1 has no state to move to. That is a\n"
        "contradiction inside §20.12, raised rather than patched."
    )

    if approved == 0:
        print("\nSelf-check FAILED — no §3 signal reached a draft.")
        return 1
    # A blocked signal is a correct answer, so it is not a failure; but the ladder invariant is.
    for signal, decision in zip(signals, decisions, strict=True):
        if decision.approved:
            q = leg_quantities(signal.shares, cfg)
            if q.t1 + q.t2 + q.t3 != signal.shares:  # pragma: no cover - LegQuantities raises
                print("\nSelf-check FAILED — ladder legs do not sum to the share count.")
                return 1
    print(f"\nSelf-check OK — {approved} draft(s) built, every leg a whole tick, ladder exact.")
    return 0


def _print_monitor(decision: MonitorDecision) -> None:
    verdict = "CLEAR" if decision.action is None else f"{decision.reason} -> {decision.action}"
    print(f"\n§7 at {decision.point.value:<17} {verdict}")
    for rule in decision.rules_evaluated:
        print(f"  {PASS if rule.passed else FAIL}  {rule.rule:<46} {rule.detail}")


def _run_monitor(cfg: Config, mode: Mode) -> int:
    """Run one session through §7's five non-pre-order enforcement points (Phase 6)."""
    print(RULE)
    print("tradipy Phase 6 — §7's other five enforcement points, over §10's daily_state")
    print(RULE)
    print(f"mode={mode}  start_of_day_equity={cfg['start_of_day_equity']}")
    print(
        "\nData origin: SIMULATED (PLAN D30). Nothing below is flattened, cancelled or sent:\n"
        "this layer computes §7's Violation Action and stops, exactly where §6.2's\n"
        "OrderDraft -> Submit arrow is refused. There is no 1-second loop either — §21.1\n"
        "forbids a clock here, so the cadence is the caller's. See docs/PHASE-6-DESIGN.md."
    )

    equity = cfg["start_of_day_equity"]

    # Every figure below is *derived* from the §3.2 worked example rather than restated. A demo
    # that hard-codes an entry and a stop is asserting against numbers the rules did not
    # produce, which is the v1.0 defect class and is what §21.1's worked-example row is for.
    signal: SetupSignal | None = None
    for example in setup_examples():
        outcome = example.evaluate(cfg)
        if outcome.signal is not None:
            signal = outcome.signal
            break
    if signal is None:  # pragma: no cover - `setups` self-checks this first
        print("\nSelf-check FAILED — no §3 example produced a signal to close.")
        return 1
    levels = signal.levels

    # §20.8 — the session opens with no equity and refuses to be evaluated.
    state = open_session(_DEMO_SESSION_DATE)
    print(f"\n§20.8  open_session -> {state.phase.value}, equity {state.start_of_day_equity}")
    try:
        risk_state(state)
        print("Self-check FAILED — §20.8 allowed a NO_TRADE session to reach §7's rules.")
        return 1
    except ValueError as exc:
        print(f"       §7 refused, correctly: {type(exc).__name__}")

    state = record_snapshot(state, equity)
    # Two prior session closes, the first above today's equity by twice §2.0's multi-day
    # allowance — so §7 row 8 is breached and its Violation Action, the one that does *not*
    # lock today, is visible below. Expressed against the registered threshold rather than as
    # a literal, so the demo follows the parameter if it moves.
    over = Decimal(1) + Decimal(2) * cfg["multi_day_dd_pct"]
    state = record_multi_day_peak(state, [equity * over, equity], cfg)
    print(
        f"§20.8  record_snapshot -> {state.phase.value}, equity {state.start_of_day_equity}, "
        f"session peak {state.session_equity_peak}, multi-day peak {state.multi_day_peak_equity}"
    )

    # §7 row 4's Post-trade close point — the first thing in the package to *produce* a
    # consecutive-loss count rather than accept one. A full-R stop-out: the exit is the signal's
    # own effective stop, so the R-multiple below should be about -1 before costs and worse
    # after, which is the whole reason §9.2 computes it on net.
    loss = ClosedTrade(
        symbol=signal.symbol,
        setup_type=signal.setup_type,
        entry_price=levels.entry_price,
        exit_price=levels.stop_price,
        shares=signal.shares,
        r_per_share=levels.r_per_share,
        # §3.1.2's own round-trip estimate, which is the only cost figure the package has.
        commission=cfg["est_round_trip_cost_per_share"] * signal.shares,
        fees=Decimal(0),
        exit_reason=ExitReason.STOPPED_OUT,
    )
    print(
        f"\n§9.2   ClosedTrade  gross {loss.gross_pnl}  net {loss.net_pnl}  "
        f"R {loss.r_multiple:.3f} (on NET, per §9.2)  loss={loss.is_loss}"
    )
    state = record_close(state, loss, unrealized_after=Decimal(0))
    print(
        f"§7 r4  record_close -> realized {state.realized_pnl}, streak "
        f"{state.consecutive_losses}, day trades {state.day_trades_in_window}"
    )

    _print_monitor(monitor_evaluate(risk_state(state), EnforcementPoint.POST_FILL, cfg))
    _print_monitor(monitor_evaluate(risk_state(state), EnforcementPoint.POST_TRADE_CLOSE, cfg))
    end_of_day = monitor_evaluate(risk_state(state), EnforcementPoint.END_OF_DAY, cfg)
    _print_monitor(end_of_day)
    carried = apply(state, end_of_day)
    print(
        f"       apply -> {carried.phase.value} today, locks_next_session="
        f"{carried.locks_next_session}  (§7 row 8 locks *next* day)"
    )

    # Drive the account into §7 row 2's limit and watch the Violation Action appear.
    state = mark_to_market(carried, -(equity * cfg["daily_loss_pct"]) - state.realized_pnl)
    continuous = monitor_evaluate(risk_state(state), EnforcementPoint.CONTINUOUS, cfg)
    _print_monitor(continuous)
    locked = apply(state, continuous)
    print(f"       apply -> {locked.phase.value}, halt_reason {locked.halt_reason}")

    if not continuous.flatten:
        print("\nSelf-check FAILED — §7 row 2 breached without requiring a flatten.")
        return 1

    # §7's "Flatten all", against §20.12 — Phase 6's headline finding. One position per §20.12
    # open state, ordered by the enum's own declaration order rather than by a list written
    # here, so the demo cannot show four states while OPEN_STATES holds five.
    lifecycle = list(PositionState)
    positions = tuple(
        OpenPosition(
            symbol=f"{signal.symbol}-{state_.value}",
            shares=signal.shares,
            mark=levels.entry_price,
            current_stop=levels.stop_price,
            state=state_,
            correlation_group=f"symbol:{signal.symbol}",
        )
        for state_ in sorted(OPEN_STATES, key=lifecycle.index)
    )
    directives = flatten_all(positions, ExitReason.KILL_SWITCH)
    blocked = unrepresentable(directives)
    print(f"\n§7.2   flatten_all -> {len(directives)} directive(s), {len(blocked)} unrecordable")
    for d in directives:
        target = d.to_state.value if d.to_state is not None else "— §20.12 has no edge —"
        print(f"       {d.shares:>6,}  {d.from_state.value:<13} -> {target}")

    print(f"\n{RULE}")
    print(
        "Those unrecordable rows are Phase 6's headline finding, and they are review round 14's\n"
        "H3 arriving as a blocker rather than a footnote. §7 has two rows whose Violation Action\n"
        "begins 'Flatten all' and a kill switch whose enforcement point is 'Any' — and of the\n"
        "four §20.12 edges into CLOSED, only one starts at an open state. So an account flattened\n"
        "by the kill switch leaves positions still recorded in the open state they were in —\n"
        "the 'untracked broker position' §20.12's persistence sentence exists to prevent.\n"
        "Raised in docs/CHANGELOG.md, not patched: widening a normative table on this layer's\n"
        "authority is the thing the §20.12 reading exists to avoid."
    )
    row = to_row(locked)
    reloaded = from_row(row)
    print(
        "\nAnd the second finding: §10's daily_state has no column for unrealized P&L, either\n"
        "drawdown peak, or §7 row 8's next-day lock. §7.1.2 says the non-bypassable limits are\n"
        "meaningless if they reset on restart — so here is the row a store would write, and\n"
        "what comes back:"
    )
    for column, value in row.items():
        print(f"       {column:<22} {value!r}")
    print(
        f"       reloaded -> {reloaded.phase.value}, halt_reason {reloaded.halt_reason} "
        "(§7 row 2's lockout survives)"
    )
    for field in sorted(UNPERSISTED_FIELDS):
        print(
            f"       LOST     {field:<22} {getattr(locked, field)!r} -> "
            f"{getattr(reloaded, field)!r}"
        )
    print(
        "       Rows 7 and 8 lose their inputs, and row 8's 'Lock account next day' is lost\n"
        "       outright — the one action whose whole purpose is to survive to the next session."
    )
    flat_minute = int(cfg["session_flat_all_minute"])
    print(
        f"\n§21.4  eod_flat_due({flat_minute}) = {eod_flat_due(flat_minute, cfg)}  "
        "(the flat-all cutoff, 15:55 ET — inclusive)"
    )
    print(f"       eod_flat_due({flat_minute - 1}) = {eod_flat_due(flat_minute - 1, cfg)}")

    if not blocked:
        print("\nSelf-check FAILED — §20.12 recorded every flatten; the finding above is stale.")
        return 1
    print(
        f"\nSelf-check OK — §20.8 refused an unopened session, §7 produced "
        f"{continuous.action}, and {len(blocked)} of {len(directives)} flattens are "
        "unrecordable under §20.12."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tradipy",
        description="Phase 1 invariant layer — pre-entry gates, sizing and §20 computations.",
        epilog=(
            "Exit codes: 0 success (demo self-check passed, or candidate ACCEPTed), "
            "1 demo self-check failed, 2 usage error, 3 candidate REJECTed. "
            "docs/PRD.md §20 is normative — this tool applies it, it does not interpret it."
        ),
    )
    # `--mode` lives on the subparsers rather than the top level. Declaring it in both places
    # does not work: a subparser's default overwrites the value argparse already parsed for
    # the same dest, so `-m tradipy --mode beginner demo` would silently run as experienced.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--mode",
        choices=MODES,
        default=None,
        help="risk preset (PRD §2.0). Default: beginner, except `demo` which uses "
        "experienced so it reproduces the PRD tables.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser(
        "demo",
        parents=[common],
        help="replay the three PRD §3 worked examples and self-check",
    )

    sc = sub.add_parser(
        "scan",
        parents=[common],
        help="run a simulated universe through the PRD §4.2 filters (Phase 3)",
    )
    sc.add_argument(
        "--verbose",
        action="store_true",
        help="show all 14 §4.2 rows per candidate, not only the failing ones",
    )

    sub.add_parser(
        "setups",
        parents=[common],
        help="replay the three PRD §3 worked examples from bar series (Phase 4)",
    )

    sub.add_parser(
        "risk",
        parents=[common],
        help="run the §3 signals through §7 pre-order risk and build the §6.1 bracket "
        "(Phase 5; submits nothing)",
    )

    sub.add_parser(
        "monitor",
        parents=[common],
        help="run one session through §7's continuous, post-fill, post-trade-close, "
        "end-of-day and any-point enforcement points (Phase 6; flattens nothing)",
    )

    ev = sub.add_parser(
        "evaluate", parents=[common], help="run one candidate through the gate chain"
    )
    ev.add_argument("--entry", type=_decimal, required=True, help="entry price (the ask)")
    ev.add_argument(
        "--stop",
        type=_decimal,
        required=True,
        help="pattern-derived stop, before the §20.13 floor and ceiling",
    )
    ev.add_argument(
        "--resistance",
        type=_decimal,
        required=True,
        help="nearest overhead resistance (§3.1.2 room gate)",
    )
    ev.add_argument(
        "--target",
        type=_decimal,
        default=None,
        help="T2 structural target; defaults to --resistance",
    )
    ev.add_argument(
        "--spread",
        type=_decimal,
        default=TICK_SIZE,
        help="NBBO spread at signal-bar close (default: one tick)",
    )
    ev.add_argument("--bid-size", type=int, default=500, help="§20.14 quote validity")
    ev.add_argument("--ask-size", type=int, default=500, help="§20.14 quote validity")
    ev.add_argument(
        "--quote-age",
        type=_decimal,
        default=Decimal(0),
        help="quote age in seconds at bar close (§20.14; default: 0, the quote at bar close)",
    )
    ev.add_argument(
        "--spread-estimated",
        action="store_true",
        help="mark the quote SPREAD_ESTIMATED (§20.14 backtest substitute)",
    )

    score = ev.add_argument_group("§20.10 composite score (optional; --rvol enables it)")
    score.add_argument("--rvol", type=_decimal, default=None, help="relative volume, x ADV")
    score.add_argument(
        "--pct-change",
        type=_decimal,
        default=Decimal(0),
        help="daily change in PERCENT units, e.g. 7.29",
    )
    score.add_argument(
        "--float-shares",
        type=_decimal,
        default=PARAMS["max_float_shares"].default,
        help="shares outstanding",
    )
    score.add_argument("--premarket-volume", type=_decimal, default=Decimal(0))
    score.add_argument(
        "--catalyst", choices=[c.value for c in Catalyst], default=Catalyst.NONE.value
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "demo"
    # These four reproduce PRD tables computed at 1% x $30,000. `risk` and `monitor` are in the
    # set because their §7 arithmetic is denominated in that equity figure and their §3 inputs
    # are those tables' share counts — at `beginner` both halve and the findings they print
    # still hold, which is asserted in tests/test_enforcement.py rather than left to the reader.
    reproduces_tables = command in {"demo", "setups", "risk", "monitor"}
    mode: Mode = getattr(args, "mode", None) or ("experienced" if reproduces_tables else "beginner")
    cfg = Config.default(mode=mode)

    if command == "demo":
        return _run_demo(cfg, mode)
    if command == "scan":
        return _run_scan(cfg, mode, verbose=args.verbose)
    if command == "setups":
        return _run_setups(cfg, mode)
    if command == "risk":
        return _run_risk(cfg, mode)
    if command == "monitor":
        return _run_monitor(cfg, mode)
    return _run_evaluate(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
