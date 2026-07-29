"""The three PRD §20 computations that need no feed: §20.4, §20.10, §20.14.

Each was fully specified and entirely absent from the code through v0.0.1. §20.14 was the
starkest: ``Reject.QUOTE_STALE`` and ``Reject.QUOTE_CROSSED`` were declared and returned by
nothing, while ``quote_stale_seconds`` and ``min_quote_size`` were registered and read by
nothing — a rule with a parameter, a reason code and no behaviour.

Assertions are written against the **derivation**, as everywhere else in this suite. §20.4's
expected values are the ones PRD §3.2's worked example states, and they are recomputed here
from a bar series rather than transcribed, which is what §21.1 asks worked-example fixtures
to do (*"input bar series -> asserted entry, stop, R, targets, share count"*).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tradipy.bars import (
    Bar,
    flagpole_ending_at,
    flagpole_height,
    green_runs,
    measured_move,
    retrace_pct,
    select_flagpole,
)
from tradipy.params import PARAMS, Config
from tradipy.poc import BULL_FLAG_BARS, BULL_FLAG_FLAG_START, bull_flag_geometry
from tradipy.quotes import Quote, check_quote, estimated_spread, spread_at_signal
from tradipy.rejects import Reject
from tradipy.rounding import TICK_SIZE, ceil_to_tick
from tradipy.score import Catalyst, ScoreInputs, composite_score, meets_conviction_gate

D = Decimal
CFG = Config.default(mode="experienced")


def _quote(**kw) -> Quote:
    base = {
        "bid": D("5.15"),
        "ask": D("5.16"),
        "bid_size": 500,
        "ask_size": 500,
        "age_seconds": D("0.5"),
    }
    return Quote(**{**base, **kw})


# ===========================================================================
# §20.14 Spread and quote validity
# ===========================================================================
@pytest.mark.spec
def test_spread_is_ask_minus_bid() -> None:
    """PRD §20.14: ``spread = NBBO_ask - NBBO_bid``. Never last-trade-derived."""
    q = _quote(bid=D("3.82"), ask=D("3.83"))
    assert q.spread == q.ask - q.bid == TICK_SIZE
    spread, verdict = spread_at_signal(q, CFG)
    assert verdict is None and spread == q.spread


@pytest.mark.spec
def test_a_clean_quote_passes() -> None:
    assert check_quote(_quote(), CFG) is None


@pytest.mark.spec
def test_a_one_sided_quote_is_not_a_spread() -> None:
    """PRD §20.14: *"Both sides must be **present**"*.

    A missing side reaches this layer as a zero rather than as an absent field, and without
    this check a $0.00 bid against a $5.16 ask passed validity and produced a $5.16 "spread"
    — which every downstream gate would then have treated as a real, catastrophically wide
    market rather than as no market at all.
    """
    for missing in (_quote(bid=D("0")), _quote(ask=D("0")), _quote(bid=D("0"), ask=D("0"))):
        assert check_quote(missing, CFG) is Reject.DATA_QUALITY_DEGRADED
        assert spread_at_signal(missing, CFG)[0] is None


@pytest.mark.boundary
def test_odd_lot_quote_is_data_quality_degraded_at_its_own_limit() -> None:
    """PRD §20.14: *"a one-sided or odd-lot-only quote is not a spread"*.

    Asserted at ``min_quote_size`` exactly and one share below it, on both sides, so the
    test fails if the comparison is ever loosened to ``>`` or applied to one side only.
    """
    size = int(CFG["min_quote_size"])
    assert check_quote(_quote(bid_size=size, ask_size=size), CFG) is None
    for side in ("bid_size", "ask_size"):
        assert check_quote(_quote(**{side: size - 1}), CFG) is Reject.DATA_QUALITY_DEGRADED


@pytest.mark.boundary
def test_stale_quote_is_rejected_at_its_own_limit() -> None:
    """PRD §20.14: *"a quote older than 2 seconds at bar close is stale"* — strictly older."""
    limit = CFG["quote_stale_seconds"]
    assert check_quote(_quote(age_seconds=limit), CFG) is None
    assert check_quote(_quote(age_seconds=limit + D("0.001")), CFG) is Reject.QUOTE_STALE


@pytest.mark.spec
def test_crossed_and_locked_quotes_are_rejected_and_never_clamped() -> None:
    """PRD §20.14: ``ask <= bid`` is rejected outright, *"never clamped to zero"*.

    The clamping matters more than the rejection. A zero spread makes the §3.1.2 separation
    floor collapse to ``sep_cost_multiple x est_round_trip_cost_per_share``, i.e. trivially
    satisfiable — during exactly the dislocations that produce crossed quotes.
    """
    locked = _quote(bid=D("5.16"), ask=D("5.16"))
    crossed = _quote(bid=D("5.17"), ask=D("5.16"))
    for q in (locked, crossed):
        assert check_quote(q, CFG) is Reject.QUOTE_CROSSED
        spread, verdict = spread_at_signal(q, CFG)
        assert spread is None, "an invalid quote must not hand back a gateable number"
        assert verdict is Reject.QUOTE_CROSSED
    assert crossed.spread < 0, "the raw difference stays negative rather than being clamped"


@pytest.mark.spec
def test_validity_is_checked_before_crossedness_before_staleness() -> None:
    """The documented order is part of the contract, so it is pinned rather than assumed."""
    all_three = _quote(bid=D("5.17"), ask=D("5.16"), bid_size=1, age_seconds=D("99"))
    assert check_quote(all_three, CFG) is Reject.DATA_QUALITY_DEGRADED

    crossed_and_stale = _quote(bid=D("5.17"), ask=D("5.16"), age_seconds=D("99"))
    assert check_quote(crossed_and_stale, CFG) is Reject.QUOTE_CROSSED


@pytest.mark.spec
def test_estimated_spread_never_understates_the_cost() -> None:
    """PRD §20.14 backtest substitute: ``max(1 tick, spread_pct_median x price)``.

    Rounded **up**: the spread is an input to two constraints and understating it weakens
    both — it lowers the §3.1.2 floor and loosens the §3.1.3 gate. Same principle as §20.13,
    applied to an input rather than a threshold.
    """
    price, median = D("3.83"), D("0.004")
    est = estimated_spread(price, median, CFG)
    assert est == ceil_to_tick(median * price) and est >= median * price
    # The one-tick floor holds where the product rounds away entirely.
    assert estimated_spread(D("1.00"), D("0.0001"), CFG) == TICK_SIZE


# ===========================================================================
# §20.4 Flagpole height and measured move
# ===========================================================================
@pytest.mark.spec
def test_green_is_close_above_open_and_a_doji_is_not_green() -> None:
    assert Bar(D("1"), D("2"), D("1"), D("1.5"), 10).is_green
    assert not Bar(D("1"), D("2"), D("1"), D("1"), 10).is_green
    assert not Bar(D("1.5"), D("2"), D("1"), D("1"), 10).is_green


@pytest.mark.spec
def test_flagpole_height_uses_first_low_and_last_high_not_the_extremes() -> None:
    """PRD §20.4 names the first candle's LOW and the last candle's HIGH, specifically.

    Not ``max(high) - min(low)`` over the run. The two agree on a monotonic sequence and
    diverge as soon as a green bar dips below its predecessor's low, which green bars do.
    """
    pole = [
        Bar(D("5.00"), D("5.20"), D("4.90"), D("5.10"), 100),  # highest high of the run
        Bar(D("5.10"), D("5.15"), D("4.80"), D("5.12"), 100),  # lowest low of the run
        Bar(D("5.12"), D("5.18"), D("5.11"), D("5.17"), 100),
    ]
    assert flagpole_height(pole) == D("5.18") - D("4.90") == D("0.28")
    assert flagpole_height(pole) != max(b.high for b in pole) - min(b.low for b in pole)


@pytest.mark.spec
def test_flagpole_height_must_be_positive() -> None:
    flat = [Bar(D("5.00"), D("5.05"), D("5.10"), D("5.02"), 100)]
    with pytest.raises(ValueError, match="height must be positive"):
        flagpole_height(flat)
    with pytest.raises(ValueError, match="at least one bar"):
        flagpole_height([])


@pytest.mark.spec
def test_green_runs_are_maximal_and_flagpole_ending_at_is_unambiguous() -> None:
    """§20.4 pins one end of the run (*"ending immediately before the flag"*), so no tie."""
    assert green_runs(BULL_FLAG_BARS) == [(0, 3), (7, 7)]
    assert flagpole_ending_at(BULL_FLAG_BARS, BULL_FLAG_FLAG_START - 1) == (0, 3)
    assert flagpole_ending_at(BULL_FLAG_BARS, BULL_FLAG_FLAG_START) is None, "flag bar is red"
    assert flagpole_ending_at(BULL_FLAG_BARS, 99) is None


@pytest.mark.spec
def test_select_flagpole_prefers_length_then_volume() -> None:
    """PRD §20.4's tie rule: *"the longest qualifying run; ties broken by greater volume"*."""
    bars = [
        Bar(D("1"), D("2"), D("1"), D("1.5"), 100),  # run A: 2 bars, volume 300
        Bar(D("1.5"), D("2"), D("1"), D("1.8"), 200),
        Bar(D("1.8"), D("2"), D("1"), D("1.0"), 50),  # red
        Bar(D("1"), D("2"), D("1"), D("1.5"), 900),  # run B: 2 bars, volume 1900
        Bar(D("1.5"), D("2"), D("1"), D("1.8"), 1000),
        Bar(D("1.8"), D("2"), D("1"), D("1.0"), 50),  # red
        Bar(D("1"), D("2"), D("1"), D("1.5"), 10),  # run C: 3 bars, volume 30
        Bar(D("1"), D("2"), D("1"), D("1.5"), 10),
        Bar(D("1"), D("2"), D("1"), D("1.5"), 10),
    ]
    runs = green_runs(bars)
    assert runs == [(0, 1), (3, 4), (6, 8)]
    # Length wins outright, even against six times the volume.
    assert select_flagpole(bars, runs) == (6, 8)
    # With the long run disqualified, the volume tie-break decides between the two 2-bar runs.
    assert select_flagpole(bars, runs, qualifies=lambda p: len(p) == 2) == (3, 4)
    assert select_flagpole(bars, runs, qualifies=lambda p: False) is None


@pytest.mark.spec
def test_section_3_2_geometry_is_derived_from_bars_not_transcribed() -> None:
    """Every number in PRD §3.2's flagpole/flag block, recomputed from :data:`BULL_FLAG_BARS`.

    §3.2 states: flagpole $4.80 -> $5.15 over 4 green candles, height $0.35; flag high $5.12,
    low $5.05, retrace 28.6%; flag/flagpole average volume 0.55; measured move $5.51.
    """
    geo = bull_flag_geometry()
    assert (geo.pole_start, geo.pole_end) == (0, 3)
    assert geo.pole_low == D("4.80")
    assert geo.pole_high == D("5.15")
    assert geo.height == geo.pole_high - geo.pole_low == D("0.35")
    assert geo.flag_high == D("5.12")
    assert geo.flag_low == D("5.05")
    assert geo.retrace == (geo.pole_high - geo.flag_low) / geo.height
    assert geo.retrace.quantize(D("0.001")) == D("0.286")
    assert geo.flag_volume_ratio == D("0.55")

    entry = BULL_FLAG_BARS[-1].close
    assert entry == D("5.16"), "§3.2 trigger: first candle closing above the flag high"
    assert entry > geo.flag_high, "§3.2 criterion 6"
    assert measured_move(entry, geo.height) == D("5.51")


@pytest.mark.spec
def test_retrace_pct_is_a_fraction_and_rejects_a_zero_height() -> None:
    assert retrace_pct(D("5.15"), D("4.98"), D("0.35")) > D("0.48")
    with pytest.raises(ValueError, match="height must be positive"):
        retrace_pct(D("5.15"), D("5.05"), D("0"))


# ===========================================================================
# §20.10 Composite score
# ===========================================================================
def _inputs(**kw) -> ScoreInputs:
    base = {
        "pct_change": D("0"),
        "rvol": D("0"),
        "float_shares": PARAMS["score_cap_float"].default,
        "premarket_volume": D("0"),
        "catalyst": Catalyst.NONE,
    }
    return ScoreInputs(**{**base, **kw})


@pytest.mark.boundary
def test_composite_score_spans_exactly_zero_to_one() -> None:
    """PRD §20.10: *"score in [0, 1], directly comparable to the >= 0.7 conviction gate"*.

    Asserted at both ends rather than at an illustrative value, because the claim is about
    the range and a mid-range check cannot see a broken cap.
    """
    floor = composite_score(_inputs(), CFG)
    assert floor.total == D(0)

    ceiling = composite_score(
        _inputs(
            pct_change=CFG["score_cap_pct_change"],
            rvol=CFG["score_cap_rvol"],
            float_shares=D(0),
            premarket_volume=CFG["score_cap_premarket_vol"],
            catalyst=Catalyst.CONFIRMED,
        ),
        CFG,
    )
    assert ceiling.total == D(1)


@pytest.mark.boundary
def test_inputs_beyond_their_caps_do_not_push_the_score_above_one() -> None:
    """Each normalizer is ``min(x / cap, 1)``; ten times the cap must not score ten times."""
    huge = composite_score(
        _inputs(
            pct_change=CFG["score_cap_pct_change"] * 10,
            rvol=CFG["score_cap_rvol"] * 10,
            float_shares=D(0),
            premarket_volume=CFG["score_cap_premarket_vol"] * 10,
            catalyst=Catalyst.CONFIRMED,
        ),
        CFG,
    )
    assert huge.total == D(1)
    for component in (huge.pct_change, huge.rvol, huge.premarket_vol):
        assert component == D(1)


@pytest.mark.boundary
def test_negative_and_oversized_inputs_cannot_take_the_score_below_zero() -> None:
    """§20.10 writes ``max(0, ...)`` only on ``float_inverse``; the floor is applied to all.

    A red name that reached the scanner would otherwise contribute negative score, and a
    float above the cap would subtract — both breaking the range §14.2's gate compares to.
    """
    negative = composite_score(
        _inputs(pct_change=D("-30"), rvol=D("-5"), float_shares=D("999999999")), CFG
    )
    assert negative.total == D(0)
    assert negative.float_inverse == D(0)


@pytest.mark.spec
def test_catalyst_encodes_full_half_and_none() -> None:
    """1.0 / 0.5 / 0.0 — the endpoints structural, the midpoint registered."""
    assert Catalyst.CONFIRMED.weight(CFG) == D(1)
    assert Catalyst.NONE.weight(CFG) == D(0)
    assert Catalyst.HEADLINE_ONLY.weight(CFG) == CFG["score_catalyst_headline"]
    tuned = CFG.with_overrides(score_catalyst_headline="0.25")
    assert Catalyst.HEADLINE_ONLY.weight(tuned) == D("0.25")


@pytest.mark.spec
def test_score_is_the_weighted_sum_of_its_own_components() -> None:
    """Derivation, not value: the total must equal the components the caller can inspect.

    §14.4 objects that *"a high score can be earned entirely on premarket volume"*. That is
    only checkable if the total and the parts cannot drift apart.
    """
    s = composite_score(
        _inputs(
            pct_change=D("12.5"),
            rvol=D("8"),
            float_shares=D("6000000"),
            premarket_volume=D("400000"),
            catalyst=Catalyst.HEADLINE_ONLY,
        ),
        CFG,
    )
    assert s.total == (
        CFG["score_weight_pct_change"] * s.pct_change
        + CFG["score_weight_rvol"] * s.rvol
        + CFG["score_weight_float"] * s.float_inverse
        + CFG["score_weight_premarket_vol"] * s.premarket_vol
        + CFG["score_weight_catalyst"] * s.catalyst
    )


@pytest.mark.boundary
def test_conviction_gate_fires_at_its_own_threshold() -> None:
    """PRD §14.2: ``score >= min_conviction_score``, inclusive."""
    gate = CFG["min_conviction_score"]
    # Reach the threshold exactly through the catalyst and float terms alone.
    at_gate = CFG.with_overrides(min_conviction_score=str(D("0.30")))
    s = composite_score(_inputs(float_shares=D(0), catalyst=Catalyst.CONFIRMED), CFG)
    assert s.total == CFG["score_weight_float"] + CFG["score_weight_catalyst"] == D("0.30")
    assert meets_conviction_gate(s, at_gate), "at the threshold must pass"
    assert not meets_conviction_gate(s, CFG), f"below the {gate} default must fail"


@pytest.mark.spec
def test_score_float_cap_currently_equals_the_scan_filter() -> None:
    """**Open finding.** ``score_cap_float`` and ``max_float_shares`` are both 20,000,000.

    §20.10 states its normalizer independently of §2's scanner ceiling, so they are two
    parameters rather than one restated — but they mean nearly the same thing, and a change
    to §2's float ceiling that leaves the score normalizer behind would silently give
    at-ceiling names a non-zero float component. Pinned so the divergence is a decision.
    """
    assert PARAMS["score_cap_float"].default == PARAMS["max_float_shares"].default, (
        "if these have deliberately diverged, update this test and record why in "
        "docs/CHANGELOG.md — do not just delete it"
    )
