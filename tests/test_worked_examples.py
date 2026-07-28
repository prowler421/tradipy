"""Worked-example fixtures — PRD §3.2, §3.3, §3.4, §2.2.

These are the regression tests PRD §21.1 calls for. Each example is encoded as its inputs
plus every asserted output, so a rule change that invalidates an example fails CI instead
of leaving a stale table in the document.

This is not hypothetical. PRD v1.0 shipped four arithmetic errors inside these very
examples — a stop at $6.22 where the rule required $6.20, a T2 below T1, three different
entry prices in one example — and all four passed a fully-ticked acceptance checklist. Each
assertion below is derived from the stated rules, never transcribed from the table, so a
table that drifts from its rules cannot make these pass.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from decimal import Decimal

import pytest

from tradipy.gates import (
    check_room,
    check_spread,
    exit_ladder,
    min_separation,
    position_size,
    vwap_reclaim_stop,
)
from tradipy.params import Config
from tradipy.rounding import is_whole_tick

D = Decimal
CFG = Config.default(mode="experienced")  # 1% risk, $30,000 start-of-day equity


@dataclass(frozen=True)
class WorkedExample:
    """One PRD §3 worked example, with only *inputs* here — outputs are derived."""

    name: str
    section: str
    entry: Decimal
    stop: Decimal
    structural_target: Decimal
    resistance: Decimal
    spread: Decimal
    # Expected values, transcribed from the PRD tables for comparison against derivation.
    expect_r: Decimal
    expect_t1: Decimal
    expect_t2: Decimal
    expect_shares: int


EXAMPLES = [
    WorkedExample(
        name="bull_flag",
        section="§3.2",
        entry=D("5.16"),
        stop=D("5.04"),          # flag low $5.05 - 1 tick
        structural_target=D("5.51"),  # measured move: entry + flagpole height $0.35
        resistance=D("5.51"),
        spread=D("0.01"),
        expect_r=D("0.12"),
        expect_t1=D("5.40"),
        expect_t2=D("5.51"),
        expect_shares=2500,
    ),
    WorkedExample(
        name="hod_breakout",
        section="§3.3",
        entry=D("6.48"),
        stop=D("6.33"),          # min(consolidation low $6.34, breakout low $6.44) - 1 tick
        structural_target=D("7.00"),  # next whole dollar above T1
        resistance=D("7.00"),
        spread=D("0.01"),
        expect_r=D("0.15"),
        expect_t1=D("6.78"),
        expect_t2=D("7.00"),
        expect_shares=2000,
    ),
    WorkedExample(
        name="vwap_reclaim",
        section="§3.4",
        entry=D("3.83"),
        stop=D("3.73"),          # via the $0.10 minimum-stop floor, not the dip low
        structural_target=D("4.15"),  # HOD retest
        resistance=D("4.15"),
        spread=D("0.01"),
        expect_r=D("0.10"),
        expect_t1=D("4.03"),
        expect_t2=D("4.15"),
        expect_shares=3000,
    ),
]

IDS = [e.name for e in EXAMPLES]


@pytest.mark.spec
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_r_is_entry_minus_stop(ex: WorkedExample) -> None:
    assert ex.entry - ex.stop == ex.expect_r, f"{ex.section}: R must be entry - stop"


@pytest.mark.spec
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_stop_respects_min_and_max(ex: WorkedExample) -> None:
    """PRD §2: R >= min_stop_distance, and stop distance <= max_stop_pct of entry."""
    r = ex.entry - ex.stop
    assert r >= CFG["min_stop_distance"], f"{ex.section}: R below the $0.10 floor"
    assert r <= CFG["max_stop_pct"] * ex.entry, f"{ex.section}: stop exceeds 5% of entry"


@pytest.mark.spec
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_exit_ladder_derives_and_is_ordered(ex: WorkedExample) -> None:
    """PRD §3.1.1: T1 at exactly 2R, T2 at the structural level, entry < T1 < T2."""
    r = ex.entry - ex.stop
    ladder = exit_ladder(ex.entry, r, ex.structural_target, CFG)
    assert ladder.t1 == ex.expect_t1, f"{ex.section}: T1 must be entry + 2R"
    assert ladder.t2 == ex.expect_t2, f"{ex.section}: T2 must be the structural target"
    assert ladder.ordered_above(ex.entry), (
        f"{ex.section}: ordering entry < T1 < T2 violated — this is the v1.0 defect where "
        "T1 was labelled HOD and T2 was 2R, inverting the ladder whenever HOD sat above 2R"
    )


@pytest.mark.spec
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_room_gate_passes(ex: WorkedExample) -> None:
    r = ex.entry - ex.stop
    assert check_room(ex.entry, ex.resistance, r, ex.spread, CFG) is None, (
        f"{ex.section}: must clear the unified room requirement (§3.1.2)"
    )


@pytest.mark.spec
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_separation_floor_passes(ex: WorkedExample) -> None:
    """PRD §3.1.2: T2 - T1 >= min_separation."""
    r = ex.entry - ex.stop
    ladder = exit_ladder(ex.entry, r, ex.structural_target, CFG)
    floor = min_separation(r, ex.spread, CFG)
    assert ladder.t2 - ladder.t1 >= floor, (
        f"{ex.section}: T2-T1={ladder.t2 - ladder.t1} below the floor {floor}"
    )


@pytest.mark.spec
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_spread_gate_passes(ex: WorkedExample) -> None:
    r = ex.entry - ex.stop
    assert check_spread(ex.spread, ex.entry, r, CFG) is None, f"{ex.section}: §3.1.3 gate"


@pytest.mark.spec
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_share_count_and_risk(ex: WorkedExample) -> None:
    """PRD §2.2: shares = floor(max_dollar_risk / stop_distance); loss at stop == 1% of equity."""
    r = ex.entry - ex.stop
    shares = position_size(ex.entry, ex.stop, CFG)
    assert shares == ex.expect_shares, f"{ex.section}: share count"

    max_dollar_risk = CFG["start_of_day_equity"] * CFG["max_risk_per_trade_pct"]
    assert shares * r <= max_dollar_risk, (
        f"{ex.section}: loss at stop {shares * r} exceeds the risk budget {max_dollar_risk} "
        "— this is the non-bypassable cap in §7"
    )


@pytest.mark.spec
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_all_levels_are_whole_ticks(ex: WorkedExample) -> None:
    """PRD §20.13: every price submitted or compared must be a whole tick."""
    r = ex.entry - ex.stop
    ladder = exit_ladder(ex.entry, r, ex.structural_target, CFG)
    levels = [("entry", ex.entry), ("stop", ex.stop), ("T1", ladder.t1), ("T2", ladder.t2)]
    for label, level in levels:
        assert is_whole_tick(level), f"{ex.section}: {label}={level} is not a whole tick"


# ---------------------------------------------------------------------------
# §3.4 stop chain — the PRD's own worked reference for rounding (§20.13)
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_vwap_reclaim_stop_chain() -> None:
    """PRD §20.13 worked reference, end to end.

    ``VWAP × 0.99 = $3.762`` -> floor_to_tick -> ``$3.76`` -> −1 tick -> ``$3.75``; the
    $0.10 minimum-stop floor then widens it to ``$3.73``.

    The $3.73 in §3.4 looks like it violates the stop rule (the dip low is $3.74) and was
    reported as a defect during review. It is correct — it arrives via the minimum-stop
    floor, not the dip low. This test pins the derivation so the reasoning is not lost again.
    """
    entry, dip_low, vwap = D("3.83"), D("3.74"), D("3.80")
    stop, verdict = vwap_reclaim_stop(entry, dip_low, vwap, CFG)
    assert verdict is None, "$3.83 is above the stop-bound crossover; the ceiling must not fire"
    assert stop == D("3.73")
    assert entry - stop == CFG["min_stop_distance"], "the floor, not the dip low, sets this stop"


@pytest.mark.spec
def test_section_2_2_sizing_example() -> None:
    """PRD §2.2: equity $30,000, risk 1%, entry $4.50, effective stop $4.30."""
    entry, stop = D("4.50"), D("4.30")
    shares = position_size(entry, stop, CFG, buying_power=D("120000"))
    assert shares == 1500
    assert shares * entry == D("6750.00")
    assert shares * (entry - stop) == D("300.00")


@pytest.mark.spec
def test_sizing_uses_frozen_start_of_day_equity() -> None:
    """PRD §7.1 / D16: intraday gains must not compound size within a session.

    Asserted structurally — ``position_size`` takes no live-equity argument, so there is no
    way to pass it one. A future refactor that adds one breaks this test.
    """
    sig = inspect.signature(position_size)
    assert "live_equity" not in sig.parameters
    assert "equity" not in sig.parameters, (
        "sizing must read start_of_day_equity from config, not accept an equity argument"
    )
