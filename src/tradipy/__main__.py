"""``python -m tradipy`` — the runnable proof of concept.

Three subcommands:

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

Stdlib only — ``argparse`` and ``decimal``. The package has no runtime dependencies and this
does not add one.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal, InvalidOperation

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
from tradipy.quotes import Quote
from tradipy.rounding import TICK_SIZE
from tradipy.scanner import ScanReport, scan
from tradipy.score import Catalyst, ScoreInputs, composite_score, meets_conviction_gate
from tradipy.setups import SetupOutcome

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
    # `demo` and `setups` both reproduce PRD tables computed at 1% x $30,000.
    reproduces_tables = command in {"demo", "setups"}
    mode: Mode = getattr(args, "mode", None) or ("experienced" if reproduces_tables else "beginner")
    cfg = Config.default(mode=mode)

    if command == "demo":
        return _run_demo(cfg, mode)
    if command == "scan":
        return _run_scan(cfg, mode, verbose=args.verbose)
    if command == "setups":
        return _run_setups(cfg, mode)
    return _run_evaluate(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
