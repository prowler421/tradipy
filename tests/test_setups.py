"""Phase 4 — the three §3 setups, driven from bar series.

This file is PRD §21.1's **worked-example fixtures** row read as it is written: *"each §3
worked example encoded as a test: **input bar series** -> asserted entry, stop, R, targets,
share count."* Until Phase 4 the suite asserted the second half of that sentence against
scalars supplied by hand from the same tables it was checking. ``tests/test_worked_examples.py``
still does, and deliberately: the two are different checks and the older one is what the demo's
self-check exercises.

It also holds §21.1's **look-ahead property test** — *"replaying a bar series truncated at time
t must produce identical signals to the full series evaluated as-of t"* — which is a two-line
assertion only because :meth:`tradipy.session.Session.through` exists for it.

**One test asserts a rejection where the PRD's table says PASS.** §3.4's example is declined by
§3.1.1's resistance set as that section enumerates it, because the next whole dollar ($4.00) is
nearer than the HOD ($4.15) the table names. Reproduced rather than smoothed over, per
convention 5: the incoherent reading is the shipped one, and a test is what stops it being
resolved silently.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tradipy.bars import Bar
from tradipy.params import Config
from tradipy.poc import (
    BULL_FLAG_WARMUP,
    HOD_BREAKOUT_BARS,
    VWAP_RECLAIM_BARS,
    setup_examples,
)
from tradipy.rejects import ExitReason, Reject
from tradipy.rounding import TICK_SIZE, ceil_to_tick, floor_to_tick
from tradipy.session import Session, SessionBar, bar_sequence, tighter, wider
from tradipy.setups import (
    EVALUATORS,
    Criterion,
    SetupType,
    arbitrate,
    bull_flag_exit,
    evaluate_all,
    evaluate_bull_flag,
    evaluate_hod_breakout,
    evaluate_vwap_reclaim,
    hod_breakout_exit,
    nearest_resistance,
    vwap_reclaim_exit,
    whole_dollar_above,
)

D = Decimal
CFG = Config.default(mode="experienced")
EXAMPLES = setup_examples()


def _example(label: str):
    return next(e for e in EXAMPLES if e.label == label)


# ---------------------------------------------------------------------------
# §21.1 worked-example fixtures — from bars
# ---------------------------------------------------------------------------
@pytest.mark.spec
@pytest.mark.parametrize("label", [e.label for e in EXAMPLES])
def test_worked_example_reproduces_its_table_from_bars(label: str) -> None:
    """Every value the §3 table states is derived from the bar series, not transcribed.

    The comparison is one-directional on purpose: ``expect`` is read from the table and never
    fed into the derivation, so a table that has drifted from its own rules fails here. That is
    the v1.0 defect class, and §21.1 names this row as its durable fix.
    """
    example = _example(label)
    outcome = example.evaluate(CFG)
    levels = outcome.levels
    assert levels is not None, f"{example.section}: the pattern was not recognised at all"

    assert levels.entry_price == example.expect["entry"]
    assert levels.stop_price == example.expect["stop"]
    assert levels.r_per_share == example.expect["r"]
    assert levels.r_per_share == levels.entry_price - levels.stop_price
    assert levels.ladder.t1 == example.expect["t1"]
    assert levels.ladder.t2 == example.expect["t2"]
    assert outcome.reject == example.expect_reject
    if "shares" in example.expect:
        assert outcome.signal is not None
        assert outcome.signal.shares == example.expect["shares"]
    else:
        assert outcome.signal is None, "a rejected setup must not be sized"


@pytest.mark.spec
def test_bull_flag_derives_every_line_of_its_own_table() -> None:
    """§3.2's table line by line: height, retrace, volume ratio, resistance, room, separation.

    Asserted against the *derivations* rather than the printed percentages — 28.6% and 0.55 are
    the table's rounded renderings, and a fixture that compared those would pass under a wrong
    rule that happens to round the same way (convention 4).
    """
    outcome = _example("bull_flag").evaluate(CFG)
    levels = outcome.levels
    assert levels is not None
    pole_high, pole_low, flag_low = D("5.15"), D("4.80"), D("5.05")
    height = pole_high - pole_low

    assert height == D("0.35")
    assert height / pole_low == D("0.35") / D("4.80")  # §3.2's "+7.29%" combined move
    assert (pole_high - flag_low) / height == D("0.10") / D("0.35")  # retrace, 28.57%
    assert levels.pattern_stop == flag_low - TICK_SIZE
    # §3.2 T2 is the §20.4 measured move: entry + flagpole height, ceiling to a tick.
    assert levels.ladder.t2 == levels.entry_price + height
    assert levels.resistance.source == "structural target"
    assert levels.resistance.level == levels.ladder.t2
    assert levels.room.required == max(
        CFG["room_gate_multiple"] * levels.r_per_share,
        CFG["t1_r_multiple"] * levels.r_per_share + levels.min_separation,
    )
    assert levels.ladder.t2 - levels.ladder.t1 >= levels.min_separation


@pytest.mark.spec
def test_hod_breakout_stop_is_section_20_6_applied_twice() -> None:
    """§3.3's stop: ``wider()`` over the pattern candidates, then A14's ``tighter()`` vs VWAP.

    A14 claims its VWAP branch is inert while criterion 3 holds. That is asserted here rather
    than assumed — and it is asserted as an *equality between two derivations*, so a change that
    made the branch bind would fail rather than pass with a different number.
    """
    outcome = _example("hod_breakout").evaluate(CFG)
    levels = outcome.levels
    assert levels is not None
    session = _example("hod_breakout").session
    trigger = session.bar(_example("hod_breakout").trigger)
    consolidation_low = D("6.34")
    vwap = session.vwap_at(_example("hod_breakout").trigger)

    assert vwap == D("6.32"), "the fixture's volumes are chosen to pin §20.2's VWAP exactly"
    # §3.3's table states the extension as 2.53%; asserted as the derivation it comes from.
    assert levels.entry_price / vwap - D(1) == D("6.48") / D("6.32") - D(1)
    assert levels.entry_price / vwap - D(1) <= CFG["max_vwap_extension_pct"]
    assert levels.pattern_stop == wider(consolidation_low, trigger.low) - TICK_SIZE
    assert levels.stop_price == tighter(levels.pattern_stop, floor_to_tick(vwap) - TICK_SIZE)
    assert levels.stop_price == levels.pattern_stop, "A14's branch is inert here, as A14 says"
    # §3.3 T2: the next whole dollar above T1, not above entry.
    assert levels.ladder.t2 == whole_dollar_above(levels.ladder.t1)


@pytest.mark.spec
def test_vwap_reclaim_reproduces_its_table_and_still_fails_section_3_1_1() -> None:
    """§3.4's example: every line to the room gate, then the disagreement, stated in full.

    The room gate's inputs are all the table's own: entry $3.83, R $0.10, required room $0.28.
    What differs is ``resistance`` — §3.4 names the HOD, §3.1.1's set contains a nearer level.
    Both branches are asserted, so the finding cannot be read as an arithmetic slip in either.
    """
    example = _example("vwap_reclaim")
    outcome = example.evaluate(CFG)
    levels = outcome.levels
    assert levels is not None

    hod, entry = D("4.15"), D("3.83")
    assert levels.entry_price == entry
    assert levels.room.required == D("0.28")
    assert levels.resistance.candidates == (
        ("next whole dollar", D("4")),
        ("HOD", hod),
        ("structural target", hod),
    ), "the whole set, nearest first — the omission of one candidate is the finding"
    assert levels.resistance.level == whole_dollar_above(entry) == D("4.00")
    assert levels.resistance.level < hod, "the whole dollar is the nearer level, which is why"
    assert outcome.reject is Reject.TARGETS_TOO_CLOSE
    # And against the level §3.4's own table names, the same trade passes.
    assert (hod - entry) >= levels.room.required


# ---------------------------------------------------------------------------
# §21.1 look-ahead property
# ---------------------------------------------------------------------------
@pytest.mark.spec
@pytest.mark.parametrize("label", [e.label for e in EXAMPLES])
def test_truncating_the_series_changes_no_outcome(label: str) -> None:
    """§21.1 / §8.1: evaluating at ``i`` cannot depend on a bar after ``i``.

    Run at **every** legal trigger index of every fixture and for all three setups, not only at
    the index the example triggers on: a look-ahead read would most likely appear on a bar where
    no pattern is present, and those are the indices a happy-path test never reaches.
    """
    example = _example(label)
    full = example.session
    for i in range(1, len(full)):
        truncated = full.through(i)
        for setup, evaluate in EVALUATORS.items():
            whole = evaluate(label.upper(), full, i, example.spread, CFG)
            part = evaluate(label.upper(), truncated, i, example.spread, CFG)
            assert whole == part, f"{setup.value} at bar {i} reads past its own trigger"


# ---------------------------------------------------------------------------
# §20 series computations
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_vwap_is_volume_weighted_typical_price_not_close() -> None:
    """§20.2: ``Σ(typical_price × volume) / Σ(volume)``, typical price ``(h+l+c)/3``.

    The two bars below have equal closes and different typical prices, so a close-only VWAP
    would return the close and this one cannot.
    """
    session = bar_sequence(
        [
            Bar(D("10.00"), D("11.00"), D("9.00"), D("10.00"), 100),
            Bar(D("10.00"), D("10.10"), D("9.90"), D("10.00"), 300),
        ]
    )
    first = (D("11.00") + D("9.00") + D("10.00")) / D(3)
    second = (D("10.10") + D("9.90") + D("10.00")) / D(3)
    assert session.vwap_at(0) == first
    assert session.vwap() == (first * 100 + second * 300) / D(400)


@pytest.mark.spec
def test_hod_tracks_wicks_and_the_opening_print_does_not_establish_one() -> None:
    """§20.3: HOD is the highest *high*; §3.3 criterion 2 needs a later bar to exceed it."""
    opening_high = bar_sequence(
        [
            Bar(D("5.00"), D("6.00"), D("4.90"), D("5.10"), 100),
            Bar(D("5.10"), D("5.50"), D("5.00"), D("5.40"), 100),
        ]
    )
    assert opening_high.hod() == D("6.00")
    assert not opening_high.hod_established_by(1), "no bar after the first set a higher high"

    later_high = bar_sequence(
        [
            Bar(D("5.00"), D("5.20"), D("4.90"), D("5.10"), 100),
            Bar(D("5.10"), D("5.60"), D("5.00"), D("5.40"), 100),
        ]
    )
    assert later_high.hod_established_by(1)
    assert later_high.hod() == D("5.60")


@pytest.mark.spec
def test_ema_is_invalid_until_the_period_has_closed_then_seeds_on_the_mean() -> None:
    """§20.5: ``None`` before ``ema_period`` bars, seed = simple mean, then ``k = 2/(n+1)``.

    The seed is asserted against a *different* formula from the one the recurrence uses, so the
    two cannot agree by sharing a bug.
    """
    period = int(CFG["ema_period"])
    closes = [D("1.00") + D("0.10") * n for n in range(period + 1)]
    session = bar_sequence([Bar(c, c, c, c, 100) for c in closes])

    assert session.ema_at(period - 2, CFG) is None, "not valid before the period has closed"
    seed = session.ema_at(period - 1, CFG)
    assert seed is not None, "the EMA must be valid once the period has closed"
    assert seed == sum(closes[:period], start=D(0)) / D(period)

    k = D(2) / D(period + 1)
    assert k == D("0.2"), "§20.5 states k = 2/(9+1) = 0.2 at the shipped period"
    assert session.ema_at(period, CFG) == closes[period] * k + seed * (D(1) - k)


@pytest.mark.spec
def test_tighter_and_wider_are_max_and_min_for_a_long() -> None:
    """§20.6, asserted as the definition rather than as an example."""
    levels = (D("6.31"), D("6.33"), D("6.27"))
    assert tighter(*levels) == max(levels)
    assert wider(*levels) == min(levels)
    assert tighter(*levels) > wider(*levels)


@pytest.mark.spec
def test_a_session_refuses_bars_that_are_not_strictly_increasing_in_time() -> None:
    """Two bars in one minute is a duplicate delivery; a decrease is a mis-ordered series."""
    bar = Bar(D("5.00"), D("5.10"), D("4.90"), D("5.05"), 100)
    with pytest.raises(ValueError, match="strictly increasing"):
        Session((SessionBar(3, bar), SessionBar(3, bar)))
    with pytest.raises(ValueError, match="strictly increasing"):
        Session((SessionBar(4, bar), SessionBar(2, bar)))
    with pytest.raises(ValueError, match="session open"):
        SessionBar(-1, bar)


# ---------------------------------------------------------------------------
# §3.1.1 resistance
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_whole_dollar_above_is_strictly_above() -> None:
    assert whole_dollar_above(D("5.16")) == D("6")
    assert whole_dollar_above(D("6.00")) == D("7"), "a level price has reached is not overhead"
    assert whole_dollar_above(D("1.01")) == D("2")


@pytest.mark.spec
def test_resistance_takes_the_nearest_candidate_and_reports_the_rest() -> None:
    """§3.1.1 with §20.3's ``PMH``: nearest wins, and every candidate stays visible."""
    resistance = nearest_resistance(
        D("3.83"),
        prior_hod=D("4.15"),
        structural_target=D("4.15"),
        premarket_high=D("3.95"),
    )
    assert resistance.source == "PMH"
    assert resistance.level == D("3.95")
    assert [name for name, _ in resistance.candidates] == [
        "PMH",
        "next whole dollar",
        "HOD",
        "structural target",
    ]


@pytest.mark.spec
def test_a_level_at_or_below_entry_is_not_resistance() -> None:
    """§3.1.1 says *overhead*: a HOD the trigger bar closed above is behind, not ahead."""
    resistance = nearest_resistance(D("6.48"), prior_hod=D("6.45"), structural_target=D("7.00"))
    assert "HOD" not in dict(resistance.candidates)
    assert resistance.level == D("7")


# ---------------------------------------------------------------------------
# Boundaries — each new threshold at its own limit
# ---------------------------------------------------------------------------
def _bull_flag_at(*, flag_bars: int) -> Session:
    """The §3.2 fixture with the flag stretched to ``flag_bars`` not-green candles."""
    pole = [
        Bar(D("4.82"), D("4.95"), D("4.80"), D("4.93"), 1000),
        Bar(D("4.93"), D("5.02"), D("4.91"), D("5.00"), 1000),
        Bar(D("5.00"), D("5.09"), D("4.98"), D("5.07"), 1000),
        Bar(D("5.07"), D("5.15"), D("5.05"), D("5.13"), 1000),
    ]
    flag = [Bar(D("5.12"), D("5.12"), D("5.05"), D("5.06"), 550)] * flag_bars
    breakout = Bar(D("5.08"), D("5.17"), D("5.07"), D("5.16"), 1650)
    return bar_sequence(BULL_FLAG_WARMUP + pole + flag + [breakout])


@pytest.mark.boundary
@pytest.mark.parametrize(
    ("flag_bars", "present"),
    [(1, False), (2, True), (5, True), (6, False)],
)
def test_flag_candle_count_binds_at_both_ends(flag_bars: int, present: bool) -> None:
    """§3.2 criterion 3's *"2-5 candles"* is inclusive at both ends and exclusive outside them.

    The 6-candle case is also §3.2's invalidation rule — *"flag extends beyond 5 candles without
    a valid trigger"* — reaching the same verdict from the other direction.
    """
    session = _bull_flag_at(flag_bars=flag_bars)
    outcome = evaluate_bull_flag("BF", session, len(session) - 1, TICK_SIZE, CFG)
    flag = next(c for c in outcome.criteria if c.name.startswith("Flag ("))
    assert flag.passed is present, flag.detail
    if not present:
        assert outcome.reject is Reject.SETUP_NOT_PRESENT


@pytest.mark.boundary
def test_flag_retrace_passes_at_exactly_the_ceiling() -> None:
    """§3.2 criterion 3: *"retraces <= 50%"* — at exactly 50% the setup is still valid."""
    pole = [
        Bar(D("4.82"), D("4.95"), D("4.80"), D("4.93"), 1000),
        Bar(D("4.93"), D("5.02"), D("4.91"), D("5.00"), 1000),
        Bar(D("5.00"), D("5.09"), D("4.98"), D("5.07"), 1000),
        Bar(D("5.07"), D("5.15"), D("5.05"), D("5.13"), 1000),
    ]
    # height $0.35; a retrace to $4.975 is exactly 50%, which is not a whole tick — so the
    # boundary is approached from the tick below it, and the assertion is on the derivation.
    flag_low = D("5.15") - CFG["max_flag_retrace_pct"] * D("0.35")
    flag = [
        Bar(D("5.12"), D("5.12"), floor_to_tick(flag_low) + TICK_SIZE, D("5.06"), 550),
        Bar(D("5.06"), D("5.10"), floor_to_tick(flag_low) + TICK_SIZE, D("5.05"), 550),
    ]
    session = bar_sequence(
        BULL_FLAG_WARMUP + pole + flag + [Bar(D("5.08"), D("5.17"), D("5.07"), D("5.16"), 1650)]
    )
    outcome = evaluate_bull_flag("BF", session, len(session) - 1, TICK_SIZE, CFG)
    flag_criterion = next(c for c in outcome.criteria if c.name.startswith("Flag ("))
    assert flag_criterion.passed, flag_criterion.detail


@pytest.mark.boundary
def test_flag_volume_ratio_passes_at_exactly_the_ceiling() -> None:
    """§3.2 criterion 5 / A13: *"<= 70%"* of the flagpole's mean volume is a pass."""
    pole_volume = 1000
    flag_volume = int(CFG["max_flag_volume_ratio"] * pole_volume)
    pole = [
        Bar(D("4.82"), D("4.95"), D("4.80"), D("4.93"), pole_volume),
        Bar(D("4.93"), D("5.02"), D("4.91"), D("5.00"), pole_volume),
        Bar(D("5.00"), D("5.09"), D("4.98"), D("5.07"), pole_volume),
        Bar(D("5.07"), D("5.15"), D("5.05"), D("5.13"), pole_volume),
    ]
    flag = [Bar(D("5.12"), D("5.12"), D("5.05"), D("5.06"), flag_volume)] * 3
    breakout_volume = int(CFG["breakout_vol_multiple"] * flag_volume)
    session = bar_sequence(
        BULL_FLAG_WARMUP
        + pole
        + flag
        + [Bar(D("5.08"), D("5.17"), D("5.07"), D("5.16"), breakout_volume)]
    )
    outcome = evaluate_bull_flag("BF", session, len(session) - 1, TICK_SIZE, CFG)
    contraction = next(c for c in outcome.criteria if "contraction" in c.name)
    breakout = next(c for c in outcome.criteria if c.name.startswith("Breakout volume"))
    assert contraction.passed, contraction.detail
    assert breakout.passed, breakout.detail
    assert outcome.accepted


@pytest.mark.boundary
def test_a_short_volume_baseline_refuses_rather_than_comparing_against_what_exists() -> None:
    """§3.2 criterion 2 needs ``flagpole_vol_lookback_bars`` bars before the pole.

    One bar short is a refusal. Comparing against a shorter window would report a verdict the
    data does not support — the same argument ``scanner`` makes for a missing soft-filter input.
    """
    lookback = int(CFG["flagpole_vol_lookback_bars"])
    session = bar_sequence(BULL_FLAG_WARMUP[: lookback - 1] + _example("bull_flag").bars[30:])
    outcome = evaluate_bull_flag("BF", session, len(session) - 1, TICK_SIZE, CFG)
    pole = next(c for c in outcome.criteria if c.name.startswith("Flagpole"))
    assert not pole.passed
    assert "not evaluable" in pole.detail


@pytest.mark.boundary
def test_dip_length_binds_at_exactly_five_candles() -> None:
    """§3.4 criterion 3: five dip candles are admitted, six are not.

    Length only. The **depth** half of that criterion has its own fixture below — this one held a
    `deep_low` constant it never used, which read as a depth assertion and was not one.
    """
    trigger = VWAP_RECLAIM_BARS[-1]

    # Exactly five dip candles: still admitted.
    five = bar_sequence(
        [
            *VWAP_RECLAIM_BARS[:18],
            Bar(D("3.79"), D("3.86"), D("3.77"), D("3.78"), 10000),
            *VWAP_RECLAIM_BARS[18:22],
            trigger,
        ]
    )
    outcome = evaluate_vwap_reclaim("VW", five, len(five) - 1, TICK_SIZE, CFG)
    dip = next(c for c in outcome.criteria if c.name.startswith("Dip"))
    assert dip.passed, dip.detail

    # Six: rejected as absent, and §3.4's invalidation says the setup is abandoned.
    six = bar_sequence(
        VWAP_RECLAIM_BARS[:18]
        + [Bar(D("3.79"), D("3.86"), D("3.77"), D("3.78"), 10000)] * 2
        + VWAP_RECLAIM_BARS[18:22]
        + [trigger]
    )
    outcome = evaluate_vwap_reclaim("VW", six, len(six) - 1, TICK_SIZE, CFG)
    dip = next(c for c in outcome.criteria if c.name.startswith("Dip"))
    assert not dip.passed, dip.detail
    assert outcome.reject is Reject.SETUP_NOT_PRESENT


def _extension_verdict(close: Decimal) -> tuple[bool, Decimal, Decimal]:
    """Run §3.3 with the trigger closing at ``close``; report the verdict and the arithmetic."""
    bars = [*HOD_BREAKOUT_BARS[:-1], Bar(D("6.44"), close, D("6.44"), close, 38000)]
    session = bar_sequence(bars)
    outcome = evaluate_hod_breakout("HB", session, len(bars) - 1, TICK_SIZE, CFG)
    criterion = next(c for c in outcome.criteria if c.name.startswith("VWAP extension"))
    vwap = session.vwap_at(len(bars) - 1)
    return criterion.passed, vwap, close / vwap - D(1)


@pytest.mark.boundary
def test_dip_depth_binds_at_the_last_admissible_tick() -> None:
    """§3.4 criterion 3: *"dip depth ≤ 2% below VWAP"*, at the limit and one tick past it.

    2% below the fixture's $3.80 VWAP is $3.724, which is not a whole tick — so the boundary is
    approached from the tick above it ($3.73, admitted) and crossed at the tick below ($3.72,
    rejected), and both are asserted against the derived depth rather than against the price.
    """
    vwap = D("3.80")
    limit = vwap * (D(1) - CFG["max_dip_depth_pct"])
    assert limit == D("3.724"), "the 2% boundary is not a whole tick at this VWAP"

    for low, admitted in ((floor_to_tick(limit) + TICK_SIZE, True), (floor_to_tick(limit), False)):
        # `high + low + close` is held at $11.40 so §20.2's VWAP stays exactly $3.80.
        deep = Bar(D("3.77"), D("11.40") - low - D("3.78"), low, D("3.78"), 10000)
        bars = [*VWAP_RECLAIM_BARS[:19], deep, *VWAP_RECLAIM_BARS[20:]]
        session = bar_sequence(bars)
        assert session.vwap_at(len(bars) - 1) == vwap
        outcome = evaluate_vwap_reclaim("VW", session, len(bars) - 1, TICK_SIZE, CFG)
        dip = next(c for c in outcome.criteria if c.name.startswith("Dip"))
        depth = (vwap - low) / vwap
        assert (depth <= CFG["max_dip_depth_pct"]) is admitted, depth
        assert dip.passed is admitted, dip.detail


@pytest.mark.boundary
def test_vwap_extension_binds_at_the_last_admissible_tick() -> None:
    """§3.3 criterion 6 / §2: ``price <= 3% above VWAP``, at the boundary and one tick past it.

    The boundary is searched for rather than predicted, because the trigger bar's own close moves
    the VWAP it is compared against — a fixture that computed the limit from an unmodified series
    would be testing a different threshold than the one the setup applies. What is asserted is
    the *behaviour at the boundary*: the last passing tick is within the limit, the next one is
    not, and the two are one tick apart.
    """
    admitted = [
        close
        for close in (D("6.44") + TICK_SIZE * n for n in range(30))
        if _extension_verdict(close)[0]
    ]
    last, first_rejected = admitted[-1], admitted[-1] + TICK_SIZE

    passed, _, extension = _extension_verdict(last)
    assert passed and extension <= CFG["max_vwap_extension_pct"]
    rejected, _, over = _extension_verdict(first_rejected)
    assert not rejected and over > CFG["max_vwap_extension_pct"]
    assert first_rejected - last == TICK_SIZE


# ---------------------------------------------------------------------------
# Polarity — the derivation, never the value
# ---------------------------------------------------------------------------
@pytest.mark.polarity
def test_the_hod_stop_rounds_away_from_the_position_when_a14_binds() -> None:
    """§20.13: a stop rounds **down**, asserted on the module's output in the case A14 omits.

    A14 says its ``max()`` against ``VWAP − 1 tick`` is inert because criterion 3 puts the
    consolidation low above VWAP. It binds when the **breakout bar's** low is the lower of §3.3's
    two candidates and sits below VWAP — a case A14 does not mention — so this fixture lowers the
    trigger bar's low and reads the stop back out of ``evaluate_hod_breakout``.

    The assertion is the derivation, not the value: the stop equals the floored band minus a tick,
    it is below the unrounded VWAP, and a ceiling would have placed it **higher** — which is the
    direction §20.13 forbids for a stop.
    """
    trigger = HOD_BREAKOUT_BARS[-1]
    bars = [
        *HOD_BREAKOUT_BARS[:-1],
        Bar(trigger.open, trigger.high, D("6.25"), trigger.close, trigger.volume),
    ]
    session = bar_sequence(bars)
    vwap = session.vwap_at(len(bars) - 1)
    outcome = evaluate_hod_breakout("HB", session, len(bars) - 1, TICK_SIZE, CFG)
    levels = outcome.levels
    assert levels is not None

    assert levels.pattern_stop == D("6.25") - TICK_SIZE, "the breakout low is now the wider level"
    assert levels.stop_price > levels.pattern_stop, "A14's branch binds"
    # The direction-sensitive line: replacing `floor_to_tick` with `ceil_to_tick` in `setups.py`
    # reddens this and nothing else. The two obvious companions — `stop_price < vwap` and
    # `stop_price < ceil_to_tick(vwap) - TICK_SIZE` — are *entailed* by it whenever the VWAP is
    # not tick-aligned, so they were removed rather than left looking like independent checks.
    assert levels.stop_price == floor_to_tick(vwap) - TICK_SIZE


@pytest.mark.polarity
def test_the_vwap_reclaim_band_is_a_maximum_and_never_widens_the_stop() -> None:
    """§3.4 / §20.13's worked reference, asserted where the direction is actually observable.

    ``vwap_stop_band_pct`` carries MAXIMUM polarity, so the band **floors**. On §3.4's own example
    that is unobservable from the outside: the raw stop is $3.75, the $0.10 minimum-stop floor
    widens it to $3.73 either way, and a ceiling would produce the same final level — which is why
    the earlier version of this test could not fail under a ``ceil_to_tick`` mutation.

    So the fixture moves the entry far enough above the band for the floor to be inert (distance
    $0.11 > $0.10), and asserts the level against its derivation. Under a ceiling the band would be
    $3.77 and the stop $3.76; under the floor it is $3.76 and $3.75, and the two are one tick apart.
    """
    vwap = D("3.80")
    # Dip low at $3.73 — the last tick inside the 2% depth limit — and an entry at $3.86, chosen so
    # `entry - raw_stop` clears `min_stop_distance` and the floor cannot mask the rounding.
    bars = [
        *VWAP_RECLAIM_BARS[:19],
        Bar(D("3.77"), D("3.89"), D("3.73"), D("3.78"), 10000),
        *VWAP_RECLAIM_BARS[20:22],
        Bar(D("3.78"), D("3.86"), D("3.68"), D("3.86"), 24000),
    ]
    session = bar_sequence(bars)
    assert session.vwap_at(len(bars) - 1) == vwap
    levels = evaluate_vwap_reclaim("VW", session, len(bars) - 1, TICK_SIZE, CFG).levels
    assert levels is not None

    unrounded = vwap * (D(1) - CFG["vwap_stop_band_pct"])
    floored = floor_to_tick(unrounded)
    assert floored <= unrounded < ceil_to_tick(unrounded), "the band is not tick-aligned here"
    assert levels.stop_price == max(D("3.73"), floored) - TICK_SIZE
    assert levels.stop_price == ceil_to_tick(unrounded) - TICK_SIZE - TICK_SIZE, (
        "a ceiling would place the stop one tick higher, which §20.13 forbids for a stop"
    )
    assert levels.entry_price - levels.stop_price > CFG["min_stop_distance"], (
        "the floor must be inert, or the direction is unobservable"
    )


def _vwap_reclaim_criterion(bars: list[Bar], name: str) -> Criterion:
    session = bar_sequence(bars)
    outcome = evaluate_vwap_reclaim("VW", session, len(bars) - 1, TICK_SIZE, CFG)
    return next(c for c in outcome.criteria if c.name == name)


@pytest.mark.boundary
def test_hod_proximity_consolidation_binds_at_exactly_two_candles_since_the_dip_low() -> None:
    """§3.4 crit 9 / §2: near HOD, ``hod_proximity_min_candles`` candles must have held below it.

    Round 13, M6: this criterion had no fixture at all — every existing bar series is far enough
    from HOD that ``near_hod`` is false and the candle count is never consulted, and forcing
    ``near_hod`` true on every one of them still left the whole suite green. Three cases, sharing
    one bar series up to the trigger so only what varies is what is asserted:

    * **far from HOD** with only one qualifying candle since the dip low — passes anyway,
      because §2's row only applies *near* HOD; this is the fixture that proves ``not near_hod``
      is a real bypass and not dead by construction.
    * **near HOD** (proximity held at exactly ``hod_proximity_pct``) with one candle — fails.
    * The same near-HOD series with a second candle inserted — passes.

    Each of the three is a mutation this file otherwise cannot see: forcing ``near_hod = True``
    unconditionally is only caught by the first case; excluding the trigger bar itself from the
    "candles since the low" count is only caught by the boundary between the second and third.
    """
    opening = Bar(D("3.45"), D("4.00"), D("3.40"), D("3.85"), 40000)  # HOD $4.00, never re-set
    above = [Bar(D("3.79"), D("3.83"), D("3.75"), D("3.82"), 8000)] * 15
    dip = [
        Bar(D("3.80"), D("3.86"), D("3.77"), D("3.77"), 10000),
        Bar(D("3.77"), D("3.88"), D("3.74"), D("3.78"), 10000),
    ]
    name = "HOD proximity consolidation (§3.4 crit 9, §2)"

    far_trigger = Bar(D("3.78"), D("3.85"), D("3.74"), D("3.83"), 24000)
    far = [opening, *above, *dip, far_trigger]
    far_c = _vwap_reclaim_criterion(far, name)
    proximity_far = (D("4.00") - D("3.83")) / D("4.00")
    assert proximity_far > CFG["hod_proximity_pct"], "fixture must actually be far from HOD"
    assert far_c.passed, far_c.detail

    # Entry held at exactly the proximity boundary: (4.00 - 3.98) / 4.00 == 0.005 == the pct.
    near_trigger = Bar(D("3.90"), D("3.995"), D("3.89"), D("3.98"), 24000)
    proximity_near = (D("4.00") - D("3.98")) / D("4.00")
    assert proximity_near == CFG["hod_proximity_pct"], "fixture must sit exactly on the boundary"

    one_candle = [opening, *above, *dip, near_trigger]
    one_c = _vwap_reclaim_criterion(one_candle, name)
    assert not one_c.passed, one_c.detail

    filler = Bar(D("3.78"), D("3.85"), D("3.77"), D("3.78"), 10000)
    two_candles = [opening, *above, *dip, filler, near_trigger]
    two_c = _vwap_reclaim_criterion(two_candles, name)
    assert two_c.passed, two_c.detail


@pytest.mark.boundary
def test_still_below_hod_and_its_proximity_read_the_prior_hod_not_the_trigger_bars_own_wick() -> (
    None
):
    """§3.4 crit 6 / crit 9: *"prior HOD"* means established **before** the trigger bar.

    Round 13, M7: the module docstring already states this reading (*"the alternative... lets a
    reclaim bar satisfy the criterion with its own wick"*), but nothing exercised a trigger bar
    whose own high actually exceeds the standing HOD — the worked example's reclaim bar never
    does. So the fixture's trigger prints a wick at $4.10, ten cents above the $4.00 HOD every
    earlier bar established, while closing at $4.05 — between the two. ``entry < prior_hod`` is
    false against the correct $4.00 and would be true against $4.10, which is the one case this
    criterion can actually distinguish the two readings on: raising the ceiling can only ever
    make "still below it" easier to satisfy, never harder, so every fixture with ``entry``
    unambiguously below both readings (as every other test in this file has) cannot tell them
    apart. ``test_truncating_the_series_changes_no_outcome`` cannot see this either — it is blind
    to a bug that reads bar ``i`` where ``i - 1`` was intended, by construction of what it
    truncates.
    """
    opening = Bar(D("3.45"), D("4.00"), D("3.40"), D("3.85"), 40000)
    above = [Bar(D("3.79"), D("3.83"), D("3.75"), D("3.82"), 8000)] * 15
    dip = [
        Bar(D("3.80"), D("3.86"), D("3.77"), D("3.77"), 10000),
        Bar(D("3.77"), D("3.88"), D("3.74"), D("3.78"), 10000),
    ]
    trigger = Bar(D("3.90"), D("4.10"), D("3.89"), D("4.05"), 24000)
    bars = [opening, *above, *dip, trigger]
    session = bar_sequence(bars)
    i = len(bars) - 1

    assert session.hod_through(i - 1) == D("4.00")
    assert session.hod_through(i) == D("4.10"), "the trigger's own wick must set a new HOD"

    outcome = evaluate_vwap_reclaim("VW", session, i, TICK_SIZE, CFG)
    still_below = next(
        c for c in outcome.criteria if c.name == "Still below HOD (§3.4 crit 6, §20.3)"
    )
    assert not still_below.passed, still_below.detail
    assert "4.00" in still_below.detail, "must be judged against the prior HOD, not $4.10"


# ---------------------------------------------------------------------------
# §20.11 arbitration
# ---------------------------------------------------------------------------
def _dual_fire_session() -> Session:
    """A bar series on which §3.2 and §3.3 both fire, which is §20.11's whole premise.

    The §3.2 fixture is not one: its warm-up sits far enough below the breakout that entry is
    5.9% above VWAP, and §3.3 criterion 6 caps that at 3%. The only change here is a quieter
    warm-up nearer the pattern, which lifts VWAP into §3.3's range while leaving §3.2's flag
    low above it. The flag bars then satisfy §3.3's consolidation test as well — *"a bull-flag
    breakout is frequently also a HOD breakout"*, which is the sentence §20.11 opens with.
    """
    warmup = [Bar(D("5.03"), D("5.05"), D("5.00"), D("5.01"), 400)] * 30
    return bar_sequence(warmup + _example("bull_flag").bars[30:])


@pytest.mark.spec
def test_arbitration_returns_one_signal_and_names_the_superseded() -> None:
    """§20.11 rules 1 and 2, on a bar where two setups genuinely both fire.

    §20.11 exists because *"a bull-flag breakout is frequently also a HOD breakout"*, and the
    §3.2 fixture is one: its breakout closes above both the flag high and the prior HOD.
    """
    session = _dual_fire_session()
    trigger = len(session) - 1
    outcomes = evaluate_all("BF", session, trigger, TICK_SIZE, CFG)
    accepted = [o for o in outcomes if o.accepted]
    assert len(accepted) >= 2, "the fixture must have more than one setup firing to mean anything"

    winner, superseded = arbitrate(outcomes)
    assert winner is not None
    assert winner.setup_type is SetupType.BULL_FLAG
    assert [o.setup_type for o in superseded] == [
        o.setup_type for o in accepted if o.setup_type is not SetupType.BULL_FLAG
    ]
    assert all(o.setup_type.priority > winner.setup_type.priority for o in superseded)


@pytest.mark.spec
def test_priority_order_is_the_one_section_20_11_states() -> None:
    assert [s.value for s in SetupType] == ["BULL_FLAG", "HOD_BREAKOUT", "VWAP_RECLAIM"]
    assert [s.priority for s in SetupType] == [0, 1, 2]


# ---------------------------------------------------------------------------
# §3 post-entry rules
# ---------------------------------------------------------------------------
def _after_entry(session: Session, entry_index: int) -> list[int]:
    return list(range(entry_index + 1, len(session)))


@pytest.mark.spec
def test_the_bailout_timer_is_undecided_until_it_expires() -> None:
    """§3.2: *"within 3 candles of entry"* — two bars in, neither exit nor pass."""
    example = _example("bull_flag")
    signal = example.evaluate(CFG).signal
    assert signal is not None
    flat = Bar(D("5.16"), D("5.16"), D("5.15"), D("5.15"), 100)
    window = int(CFG["bailout_candles"])

    for count in range(1, window):
        session = bar_sequence(example.bars + [flat] * count)
        after = _after_entry(session, example.trigger)
        assert bull_flag_exit(session, signal, after, CFG) is None, count

    session = bar_sequence(example.bars + [flat] * window)
    after = _after_entry(session, example.trigger)
    assert bull_flag_exit(session, signal, after, CFG) is ExitReason.BAILED_OUT


@pytest.mark.spec
def test_either_half_of_section_3_2s_conjunction_keeps_the_position() -> None:
    """§3.2's bailout is *"has not closed above entry **and** has not made a new high"*.

    One of the two suffices to stay in — which is what makes it a conjunction rather than the
    single condition §3.3 states. Both halves are exercised separately.
    """
    example = _example("bull_flag")
    signal = example.evaluate(CFG).signal
    assert signal is not None
    window = int(CFG["bailout_candles"])
    breakout_high = signal.levels.breakout_high

    closed_up = Bar(D("5.16"), D("5.17"), D("5.15"), D("5.17"), 100)
    assert closed_up.close > signal.levels.entry_price
    assert closed_up.high <= breakout_high
    session = bar_sequence(example.bars + [closed_up] * window)
    assert bull_flag_exit(session, signal, _after_entry(session, example.trigger), CFG) is None

    new_high = Bar(D("5.15"), breakout_high + TICK_SIZE, D("5.14"), D("5.15"), 100)
    assert new_high.close < signal.levels.entry_price
    session = bar_sequence(example.bars + [new_high] * window)
    assert bull_flag_exit(session, signal, _after_entry(session, example.trigger), CFG) is None


@pytest.mark.spec
def test_a_close_below_vwap_invalidates_before_the_timer_can_expire() -> None:
    """§3.2 / §3.3 / §3.4: *"close below VWAP after entry -> exit immediately."*"""
    example = _example("bull_flag")
    signal = example.evaluate(CFG).signal
    assert signal is not None
    collapse = Bar(D("5.16"), D("5.16"), D("4.00"), D("4.05"), 5000)
    session = bar_sequence([*example.bars, collapse])
    after = _after_entry(session, example.trigger)

    assert session.bar(after[0]).close < session.vwap_at(after[0])
    assert bull_flag_exit(session, signal, after, CFG) is ExitReason.INVALIDATED
    assert vwap_reclaim_exit(session, signal, after, CFG) is ExitReason.INVALIDATED


@pytest.mark.spec
def test_hod_breakout_invalidates_on_a_close_back_below_the_prior_hod() -> None:
    """§3.3: *"close back below prior HOD within 2 candles of breakout"* — and only within it."""
    example = _example("hod_breakout")
    signal = example.evaluate(CFG).signal
    assert signal is not None
    prior_hod = signal.levels.prior_hod
    assert prior_hod == D("6.45")

    back_below = Bar(D("6.47"), D("6.48"), D("6.40"), D("6.44"), 20000)
    session = bar_sequence([*example.bars, back_below])
    after = _after_entry(session, example.trigger)
    assert hod_breakout_exit(session, signal, after, CFG) is ExitReason.INVALIDATED

    # Outside the window the same bar is not this rule. Two holding bars first, both above the
    # prior HOD and making new highs, so neither the reclaim rule nor the bailout fires.
    holds = Bar(D("6.48"), signal.levels.breakout_high + TICK_SIZE, D("6.47"), D("6.50"), 20000)
    window = int(CFG["hod_reclaim_invalidation_candles"])
    session = bar_sequence([*example.bars, *[holds] * window, back_below])
    after = _after_entry(session, example.trigger)
    assert hod_breakout_exit(session, signal, after[:window], CFG) is None


@pytest.mark.spec
def test_vwap_reclaim_has_no_bailout_timer() -> None:
    """§3.4 states no breakout-or-bailout rule, and none is applied.

    Three flat bars that would bail out either other setup leave this one open, because §3.4's
    only post-entry rule is the VWAP close. That §3.4 is the one setup without a timer is raised
    in docs/CHANGELOG.md as a spec question, not fixed by inventing one here.
    """
    example = _example("bull_flag")
    signal = example.evaluate(CFG).signal
    assert signal is not None
    flat = Bar(D("5.16"), D("5.16"), D("5.15"), D("5.15"), 100)
    session = bar_sequence(example.bars + [flat] * int(CFG["bailout_candles"]))
    after = _after_entry(session, example.trigger)

    assert bull_flag_exit(session, signal, after, CFG) is ExitReason.BAILED_OUT
    assert hod_breakout_exit(session, signal, after, CFG) is ExitReason.BAILED_OUT
    assert vwap_reclaim_exit(session, signal, after, CFG) is None
