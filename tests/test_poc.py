"""The proof-of-concept pipeline and CLI.

``python -m tradipy demo`` is a runnable smoke test of the whole invariant layer, so it needs
its own tests: a demo that silently stops checking is worse than no demo, because its green
output is what people will trust instead of reading the code.

The self-check inside the demo compares every derived value against the PRD §3 tables and
exits non-zero on disagreement. :func:`test_demo_exits_zero_and_reproduces_the_prd` asserts
that from the outside; :func:`test_demo_self_check_would_catch_spec_drift` asserts the check
itself is not vacuous — the failure mode a self-checking demo is most likely to have.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from tradipy.__main__ import main
from tradipy.params import Config
from tradipy.poc import Candidate, check_against_prd, evaluate, worked_examples
from tradipy.quotes import Quote
from tradipy.rejects import Reject

D = Decimal
CFG = Config.default(mode="experienced")

#: Reused CLI argument groups, so the parametrized cases stay one line each.
EXPERIENCED = ["--mode", "experienced"]
BULL_FLAG_ARGS = ["--entry", "5.16", "--stop", "5.04", "--resistance", "5.51"]
TIGHT_ROOM_ARGS = ["--entry", "4.00", "--stop", "3.90", "--resistance", "4.26"]
LOW_BAND_ARGS = ["--entry", "1.50", "--stop", "1.45", "--resistance", "2.50"]
EXAMPLES = worked_examples()
IDS = [c.label for c in EXAMPLES]


def _quote(price: Decimal, spread: Decimal | None = None, **kw) -> Quote:
    if spread is None:
        spread = D("0.01")
    base = {
        "bid": price - spread,
        "ask": price,
        "bid_size": 500,
        "ask_size": 500,
        "age_seconds": D("0.5"),
    }
    return Quote(**{**base, **kw})


# ---------------------------------------------------------------------------
# The pipeline
# ---------------------------------------------------------------------------
@pytest.mark.spec
@pytest.mark.parametrize("candidate", EXAMPLES, ids=IDS)
def test_every_prd_example_is_accepted_and_matches_its_table(candidate: Candidate) -> None:
    ev = evaluate(candidate, CFG)
    assert ev.accepted, f"{candidate.section}: rejected with {ev.reject}"
    assert check_against_prd(ev) == [], f"{candidate.section}: derived values disagree"


@pytest.mark.spec
@pytest.mark.parametrize("candidate", EXAMPLES, ids=IDS)
def test_every_gate_is_reported_not_just_the_failing_one(candidate: Candidate) -> None:
    """A PoC that stops at the first reject tells you less than one that shows the rest."""
    gates = [g.gate for g in evaluate(candidate, CFG).results]
    assert gates == [
        "quote validity",
        "stop construction",
        "spread gate",
        "room gate",
        "exit ladder",
        "separation floor",
        "position size",
    ]


@pytest.mark.spec
def test_demo_self_check_would_catch_spec_drift() -> None:
    """The self-check must fail when the table and the rules disagree.

    This is the check on the check. PRD v1.0 shipped four arithmetic errors inside these
    examples and a fully-ticked acceptance checklist; a self-check that cannot fail would
    reproduce exactly that.
    """
    drifted = replace(EXAMPLES[0], expect={**EXAMPLES[0].expect, "shares": 9999})
    mismatches = check_against_prd(evaluate(drifted, CFG))
    assert len(mismatches) == 1
    assert "shares" in mismatches[0] and "9999" in mismatches[0]


@pytest.mark.spec
def test_an_invalid_quote_stops_the_chain_rather_than_fabricating_a_spread() -> None:
    """Every gate after §20.14 consumes the spread; there is no honest value to pass on."""
    bad = replace(EXAMPLES[0], quote=_quote(D("5.16"), bid_size=1))
    ev = evaluate(bad, CFG)
    assert ev.reject is Reject.DATA_QUALITY_DEGRADED
    assert ev.spread is None and ev.shares is None
    assert [g.gate for g in ev.results] == ["quote validity"]


@pytest.mark.spec
def test_a_rejected_stop_is_reported_but_never_sized() -> None:
    """§20.13 requires skipping, and ``position_size`` now raises rather than obliging."""
    unreachable = Candidate(
        entry=D("1.50"),  # inside the documented $1.00-$1.99 dead band
        raw_stop=D("1.45"),
        structural_target=D("2.50"),
        resistance=D("2.50"),
        quote=_quote(D("1.50")),
    )
    ev = evaluate(unreachable, CFG)
    assert ev.reject is Reject.STOP_TOO_WIDE
    assert ev.shares is None, "a trade the ceiling rejects must not be sized"
    assert "position size" not in [g.gate for g in ev.results]
    # The later gates are still evaluated, because their inputs exist.
    assert len(ev.results) == 6


@pytest.mark.boundary
def test_the_room_gate_rejection_from_the_prd_sensitivity_table() -> None:
    """PRD §3.4's sensitivity table: $0.26 of room clears 2.5R and fails the unified test."""
    tight = Candidate(
        entry=D("4.00"),
        raw_stop=D("3.90"),
        structural_target=D("4.26"),
        resistance=D("4.26"),
        quote=_quote(D("4.00")),
    )
    ev = evaluate(tight, CFG)
    assert ev.reject is Reject.TARGETS_TOO_CLOSE
    room = next(g for g in ev.results if g.gate == "room gate")
    assert not room.passed and "0.28" in room.detail and "0.250" in room.detail


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_demo_exits_zero_and_reproduces_the_prd(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "Self-check OK" in out
    assert "3/3 examples accepted" in out
    assert "FAIL" not in out
    for section in ("§3.2", "§3.3", "§3.4", "§20.4"):
        assert section in out


@pytest.mark.spec
def test_bare_invocation_runs_the_demo(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "Self-check OK" in capsys.readouterr().out


@pytest.mark.spec
def test_demo_in_beginner_mode_skips_the_self_check_rather_than_failing_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The PRD tables are computed at the experienced preset, and the demo says so.

    Reporting a failure here would be wrong — the share counts differ because the mode does,
    not because anything drifted — and silently passing would be worse.
    """
    assert main(["demo", "--mode", "beginner"]) == 0
    out = capsys.readouterr().out
    assert "Self-check skipped" in out
    assert "1,250 sh" in out


@pytest.mark.spec
def test_evaluate_accepts_a_good_candidate(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["evaluate", *EXPERIENCED, *BULL_FLAG_ARGS])
    out = capsys.readouterr().out
    assert code == 0
    assert "ACCEPT" in out and "2,500 sh" in out


@pytest.mark.spec
@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (TIGHT_ROOM_ARGS, "TARGETS_TOO_CLOSE"),
        ([*BULL_FLAG_ARGS, "--spread", "-0.01"], "QUOTE_CROSSED"),
        ([*BULL_FLAG_ARGS, "--bid-size", "50"], "DATA_QUALITY_DEGRADED"),
        ([*BULL_FLAG_ARGS, "--quote-age", "3"], "QUOTE_STALE"),
        (LOW_BAND_ARGS, "STOP_TOO_WIDE"),
    ],
    ids=["room", "crossed", "odd_lot", "stale", "stop_too_wide"],
)
def test_evaluate_exits_three_and_names_the_reason(
    args: list[str], expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 3, not 2: argparse owns 2 for usage errors, and a REJECT is a correct answer."""
    assert main(["evaluate", *EXPERIENCED, *args]) == 3
    out = capsys.readouterr().out
    assert f"REJECT  {expected}" in out


@pytest.mark.spec
def test_evaluate_reports_the_composite_score_when_asked(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "evaluate",
            *EXPERIENCED,
            *BULL_FLAG_ARGS,
            "--rvol", "20",
            "--pct-change", "50",
            "--float-shares", "0",
            "--premarket-volume", "1000000",
            "--catalyst", "confirmed",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "§20.10 composite score  1.0000" in out
    assert "gate >= 0.7: PASS" in out


@pytest.mark.spec
def test_evaluate_omits_the_score_when_no_rvol_is_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["evaluate", *BULL_FLAG_ARGS])
    assert "composite score" not in capsys.readouterr().out


@pytest.mark.spec
def test_the_cli_defaults_to_the_prd_declared_mode_outside_the_demo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``demo`` uses experienced to reproduce the tables; everything else follows §2.0."""
    main(["evaluate", *BULL_FLAG_ARGS])
    assert "mode=beginner" in capsys.readouterr().out
    main(["demo"])
    assert "mode=experienced" in capsys.readouterr().out


@pytest.mark.spec
def test_the_demo_reports_a_failure_rather_than_passing_quietly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exercise the branch that matters most: the one that runs when the PRD is wrong.

    A self-check whose failure path has never executed is a self-check nobody has tested.
    The drift is injected into the example set rather than into the rules, which is the
    direction spec drift actually travels.
    """
    import tradipy.__main__ as cli

    original = cli.prd_examples

    def drifted() -> list[Candidate]:
        examples = original()
        examples[0] = replace(examples[0], expect={**examples[0].expect, "t1": D("9.99")})
        return examples

    cli.prd_examples = drifted  # type: ignore[assignment]
    try:
        assert main(["demo"]) == 1
    finally:
        cli.prd_examples = original  # type: ignore[assignment]

    out = capsys.readouterr().out
    assert "SELF-CHECK FAILED" in out
    assert "9.99" in out and "§3.2" in out


@pytest.mark.spec
def test_bull_flag_geometry_rejects_a_flag_start_with_no_green_run_before_it() -> None:
    """§20.4 requires a green run *ending immediately before the flag*; there may not be one."""
    from tradipy.poc import BULL_FLAG_BARS, BULL_FLAG_FLAG_START, bull_flag_geometry

    with pytest.raises(ValueError, match="no green run ends at index"):
        bull_flag_geometry(BULL_FLAG_BARS, flag_start=BULL_FLAG_FLAG_START + 1)


@pytest.mark.spec
def test_a_candidate_without_a_prd_table_is_not_self_checked() -> None:
    """``check_against_prd`` is a no-op for anything the user supplied."""
    plain = Candidate(
        entry=D("5.16"),
        raw_stop=D("5.04"),
        structural_target=D("5.51"),
        resistance=D("5.51"),
        quote=_quote(D("5.16")),
    )
    assert check_against_prd(evaluate(plain, CFG)) == []


@pytest.mark.spec
def test_a_non_numeric_argument_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["evaluate", "--entry", "cheap", "--stop", "5.04", "--resistance", "5.51"])
    assert exc.value.code == 2
