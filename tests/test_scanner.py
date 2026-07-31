"""PRD §4 scanner fixtures — the §4.2 filter table, its boundaries, and §4.3's ranking.

Three things are asserted here, and they catch different failures:

1. **The table is the spec's, not the code's.** :func:`prd_filter_rows` parses §4.2 out of
   docs/PRD.md and compares it to :data:`~tradipy.scanner.HARD_FILTERS` and
   :data:`~tradipy.scanner.SOFT_FILTERS` in *both* directions — name, rejection code,
   hard/soft classification and order. Review finding G3 was that nothing compared the
   ``Reject`` enum to the spec's rejection-code namespace either way, so a code invented by
   the implementation and a row added to the spec were both invisible. Round 10's **K5** was
   the same gap read from the other end: a gate document that doubled Phase 3's filter scope
   from seven rows to fourteen, and nothing mechanical to contradict it.

2. **Behaviour at each filter's own limit** (``boundary`` marks). A filter tested with an
   obviously-passing and an obviously-failing candidate passes under ``>`` and under ``>=``
   alike, and §4.2 states every one of these as a weak inequality.

3. **§4.3's ranking is a ranking**, including the tiebreak §4.3 does not state.

Assertions are written against the derivation wherever the derivation is what is at stake —
``ceil_to_tick(cfg[...] * price)`` rather than ``Decimal("0.43")`` — but fixtures state
literals, because ``tests/`` is deliberately outside the registry lint's scope and a fixture
that reads its expected value out of the registry proves nothing (convention 4).

The guarantee tests live in ``test_enforcement.py``: that no soft flag can reject, that D24
keeps ``INST_OWN_HIGH`` inert, that this module never names a rounding direction, and that
all seven hard filters are reachable.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path

import pytest

from tradipy.gates import scan_spread_cap
from tradipy.params import Config
from tradipy.poc import simulated_universe
from tradipy.rejects import Reject, SoftFlag
from tradipy.rounding import TICK_SIZE, ceil_to_tick, floor_to_tick
from tradipy.scanner import (
    HARD_FILTERS,
    PERCENT_PER_UNIT,
    SOFT_FILTERS,
    ScanCandidate,
    evaluate_candidate,
    scan,
)
from tradipy.score import Catalyst, ScoreInputs, composite_score

D = Decimal
CFG = Config.default()
PRD = Path(__file__).resolve().parents[1] / "docs" / "PRD.md"


#: Where the fixture's LULD bands sit relative to its price, as a fraction. Far outside
#: ``min_luld_distance_pct``, so Circuit Breakers only binds when a test says so.
BAND = D("0.5")


def candidate(**overrides: object) -> ScanCandidate:
    """A candidate that passes all seven §4.2 hard filters and raises no soft flag.

    Every threshold-adjacent value is a literal, deliberately. A fixture built from
    ``cfg[...]`` moves with the registry and so cannot detect a threshold changing, which is
    the whole point of having one — see convention 4 and
    :func:`tradipy.poc.simulated_universe`, which does the opposite for the opposite reason.

    The LULD bands are the exception: they **follow the price** unless a test states them,
    because they describe where the price sits rather than what any filter's limit is. Fixing
    them at $2.00/$6.00 made a ``price=$1.00`` fixture fail Circuit Breakers as well as Price
    Range, and the reported reject then came from whichever row §4.2 lists first — a
    boundary test passing or failing for a reason it was not written about.
    """
    price = overrides.get("price", D("4.00"))
    assert isinstance(price, Decimal)
    base: dict[str, object] = {
        "symbol": "TEST",
        "price": price,
        "premarket_gap_pct": D("0.20"),
        "daily_gap_pct": D("0.25"),
        "rvol": D("12"),
        "float_shares": D("5000000"),
        "adv_shares": D("2000000"),
        "luld_upper": price * (D(1) + BAND),
        "luld_lower": price * (D(1) - BAND),
        "spread": D("0.01"),
        "bid_size": 500,
        "premarket_volume": D("400000"),
        "catalyst": Catalyst.CONFIRMED,
        "market_cap": D("150000000"),
        "atr": D("0.40"),
        "avg_atr": D("0.20"),
        "sessions_since_halt": None,
        "short_interest_pct": D("0.01"),
    }
    base.update(overrides)
    return ScanCandidate(**base)  # pyright: ignore[reportArgumentType]


def verdict(c: ScanCandidate, cfg: Config = CFG) -> Reject | None:
    return evaluate_candidate(c, cfg).reject


def flags(c: ScanCandidate, cfg: Config = CFG) -> tuple[SoftFlag, ...]:
    return evaluate_candidate(c, cfg).flags


# ---------------------------------------------------------------------------
# §4.2's table, parsed from the document
# ---------------------------------------------------------------------------
def prd_filter_rows() -> list[tuple[str, str, str]]:
    """``(filter name, hard/soft cell, rejection code)`` for every §4.2 row, in table order.

    Parsed rather than transcribed. A transcription is a second copy of the table, and a
    second copy of a table is the v1.2 defect class — which is a poor way to build the check
    that the first copy is implemented.
    """
    lines = PRD.read_text(encoding="utf-8").split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("### 4.2"))
    rows: list[tuple[str, str, str]] = []
    seen_table = False
    for line in lines[start:]:
        if not line.startswith("|"):
            if seen_table:
                break  # the table has ended; §4.2's trailing note is prose
            continue
        seen_table = True
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in {"Filter", ""} or set(cells[0]) <= {"-", ":"}:
            continue  # header or separator row
        rows.append((cells[0], cells[2], cells[3].strip("`")))
    return rows


@pytest.mark.spec
def test_the_prd_table_parser_found_the_table() -> None:
    """Guard on the guard: the parser must actually return §4.2's rows.

    Every conformance check below compares against this list, and a parser that silently
    returns ``[]`` makes all of them pass. That is the shape of the ``normalize()`` blind
    spot in the registry lint — a green result produced by looking at nothing.
    """
    rows = prd_filter_rows()
    assert len(rows) == 14, f"§4.2 should have 14 rows, parsed {len(rows)}: {rows}"
    assert rows[0][0] == "Gap %", rows[0]
    assert rows[-1][2] == "HIGH_SHORT_INTEREST", rows[-1]


@pytest.mark.spec
def test_hard_filters_match_the_prd_table_in_both_directions() -> None:
    """Every §4.2 Hard row is implemented, and every implemented hard filter is a §4.2 Hard row.

    Order is asserted too: :data:`HARD_FILTERS` order is the evaluation order and the order
    :attr:`~tradipy.scanner.ScanResult.reject` reports, so it is observable behaviour.
    """
    expected = [(n, code) for n, hs, code in prd_filter_rows() if hs.startswith("Hard")]
    actual = [(f.name, f.code.value) for f in HARD_FILTERS]
    assert actual == expected


@pytest.mark.spec
def test_soft_filters_match_the_prd_table_in_both_directions() -> None:
    """Same for the Soft half — including the row D24 keeps disabled, which is still a row."""
    expected = [(n, code) for n, hs, code in prd_filter_rows() if hs.startswith("Soft")]
    actual = [(f.name, f.code.value) for f in SOFT_FILTERS]
    assert actual == expected


@pytest.mark.spec
def test_the_two_tuples_partition_the_table_exactly() -> None:
    """Fourteen rows, seven and seven, with nothing counted twice or dropped.

    K5's finding was a document claiming Phase 3 owed all fourteen as rejection paths. This
    is the mechanical form of the correction: seven reject, seven flag, and the classification
    comes from the document rather than from either list.
    """
    rows = prd_filter_rows()
    assert len(HARD_FILTERS) == 7 and len(SOFT_FILTERS) == 7
    assert len(HARD_FILTERS) + len(SOFT_FILTERS) == len(rows)

    hard_codes = {f.code.value for f in HARD_FILTERS}
    soft_codes = {f.code.value for f in SOFT_FILTERS}
    assert not hard_codes & soft_codes, "a code cannot both reject and flag"
    assert hard_codes <= {m.value for m in Reject}
    assert soft_codes == {m.value for m in SoftFlag}


# ---------------------------------------------------------------------------
# §4.2 hard filters
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_a_clean_candidate_passes_every_hard_filter_and_raises_no_flag() -> None:
    result = evaluate_candidate(candidate(), CFG)
    assert result.passed and result.rejects == () and result.flags == ()
    assert result.score is not None, "§4.1 scores survivors"


@pytest.mark.spec
def test_gap_is_an_or_not_an_and() -> None:
    """§4.2: ``>= 4% premarket OR >= 10% daily``. Either alone qualifies."""
    premarket_only = candidate(premarket_gap_pct=D("0.09"), daily_gap_pct=D("0.02"))
    daily_only = candidate(premarket_gap_pct=D("0.01"), daily_gap_pct=D("0.31"))
    neither = candidate(premarket_gap_pct=D("0.01"), daily_gap_pct=D("0.02"))

    assert verdict(premarket_only) is None
    assert verdict(daily_only) is None
    assert verdict(neither) is Reject.GAP_TOO_SMALL


@pytest.mark.boundary
def test_gap_thresholds_are_weak_inequalities() -> None:
    """A candidate exactly at either floor passes; one tick of a percent below does not."""
    at_premarket = candidate(premarket_gap_pct=D("0.04"), daily_gap_pct=D("0.00"))
    below_premarket = candidate(premarket_gap_pct=D("0.0399"), daily_gap_pct=D("0.00"))
    at_daily = candidate(premarket_gap_pct=D("0.00"), daily_gap_pct=D("0.10"))
    below_daily = candidate(premarket_gap_pct=D("0.00"), daily_gap_pct=D("0.0999"))

    assert verdict(at_premarket) is None
    assert verdict(below_premarket) is Reject.GAP_TOO_SMALL
    assert verdict(at_daily) is None
    assert verdict(below_daily) is Reject.GAP_TOO_SMALL


@pytest.mark.boundary
def test_relative_volume_floor_is_inclusive() -> None:
    assert verdict(candidate(rvol=D("5.0"))) is None
    assert verdict(candidate(rvol=D("4.99"))) is Reject.RVOL_TOO_LOW


@pytest.mark.boundary
def test_float_ceiling_is_inclusive() -> None:
    """D4's "20-20 rule": at 20,000,000 exactly the name still qualifies."""
    assert verdict(candidate(float_shares=D("20000000"))) is None
    assert verdict(candidate(float_shares=D("20000001"))) is Reject.FLOAT_TOO_HIGH


@pytest.mark.boundary
def test_price_range_is_closed_at_both_ends() -> None:
    assert verdict(candidate(price=D("1.00"))) is None
    assert verdict(candidate(price=D("20.00"))) is None
    assert verdict(candidate(price=D("0.99"))) is Reject.PRICE_OUT_OF_RANGE
    assert verdict(candidate(price=D("20.01"))) is Reject.PRICE_OUT_OF_RANGE


@pytest.mark.polarity
def test_the_price_range_ends_round_in_opposite_directions() -> None:
    """§20.13: the floor rounds up and the ceiling down, so neither bound widens.

    Asserted against the derivation, at a configuration where the two directions differ.
    At the shipped $1.00/$20.00 both are already whole ticks and rounding is a no-op, so a
    test written at the defaults would pass under *any* direction — the exact shape of the
    v1.3.1 defect.
    """
    cfg = CFG.with_overrides(min_price="1.005", max_price="19.995")
    assert ceil_to_tick(D("1.005")) == D("1.01") != floor_to_tick(D("1.005"))
    assert floor_to_tick(D("19.995")) == D("19.99") != ceil_to_tick(D("19.995"))

    assert verdict(candidate(price=D("1.00")), cfg) is Reject.PRICE_OUT_OF_RANGE, (
        "the floor must round UP to $1.01, excluding a $1.00 candidate"
    )
    assert verdict(candidate(price=D("1.01")), cfg) is None
    assert verdict(candidate(price=D("20.00")), cfg) is Reject.PRICE_OUT_OF_RANGE, (
        "the ceiling must round DOWN to $19.99, excluding a $20.00 candidate"
    )
    assert verdict(candidate(price=D("19.99")), cfg) is None


@pytest.mark.boundary
def test_average_daily_volume_floor_is_inclusive() -> None:
    assert verdict(candidate(adv_shares=D("500000"))) is None
    assert verdict(candidate(adv_shares=D("499999"))) is Reject.ADV_TOO_LOW


@pytest.mark.boundary
def test_luld_distance_is_measured_against_both_bands() -> None:
    """§4.2 Circuit Breakers, at the boundary the derivation produces.

    The required distance is ``ceil_to_tick(min_luld_distance_pct x price)`` — a minimum over
    a price, so it rounds up. At $4.00 that is $0.40 exactly; the assertion is written as the
    derivation rather than as ``$0.40`` so it still means something if the rule changes.
    """
    price = D("4.00")
    required = ceil_to_tick(CFG["min_luld_distance_pct"] * price)
    far, near = D("99.00"), D("0.01")

    at_upper = candidate(price=price, luld_upper=price + required, luld_lower=near)
    inside_upper = candidate(price=price, luld_upper=price + required - TICK_SIZE, luld_lower=near)
    assert verdict(at_upper) is None
    assert verdict(inside_upper) is Reject.NEAR_LULD

    # The lower band binds on its own — a candidate can be far from limit-up and still be
    # one tick from limit-down.
    at_lower = candidate(price=price, luld_upper=far, luld_lower=price - required)
    inside_lower = candidate(price=price, luld_upper=far, luld_lower=price - required + TICK_SIZE)
    assert verdict(at_lower) is None
    assert verdict(inside_lower) is Reject.NEAR_LULD


@pytest.mark.boundary
def test_spread_filter_rejects_both_a_wide_quote_and_a_thin_bid() -> None:
    """§4.2's Liquidity / Spread row states two conditions under one code.

    The cap is asserted to be :func:`tradipy.gates.scan_spread_cap` rather than recomputed
    here: §4.2 restates §3.1.3's formula in prose, and the point of the scanner calling that
    function is that there is only one implementation of it.
    """
    price = D("4.00")
    cap = scan_spread_cap(price, CFG)
    assert cap == floor_to_tick(min(CFG["max_spread_abs"], CFG["max_spread_pct"] * price))

    assert verdict(candidate(price=price, spread=cap)) is None
    assert verdict(candidate(price=price, spread=cap + TICK_SIZE)) is Reject.SPREAD_TOO_WIDE
    assert verdict(candidate(price=price, bid_size=int(CFG["min_quote_size"]))) is None
    assert (
        verdict(candidate(price=price, bid_size=int(CFG["min_quote_size"]) - 1))
        is Reject.SPREAD_TOO_WIDE
    )


@pytest.mark.spec
def test_every_hard_filter_is_reported_not_only_the_first_failure() -> None:
    """A candidate failing several rows reports all of them, in §4.2 table order."""
    broken = candidate(
        premarket_gap_pct=D("0.00"),
        daily_gap_pct=D("0.00"),
        rvol=D("1"),
        float_shares=D("90000000"),
    )
    result = evaluate_candidate(broken, CFG)
    assert len(result.hard) == 7, "all seven are evaluated regardless"
    assert result.rejects == (
        Reject.GAP_TOO_SMALL,
        Reject.RVOL_TOO_LOW,
        Reject.FLOAT_TOO_HIGH,
    )
    assert result.reject is Reject.GAP_TOO_SMALL
    assert result.score is None, "§4.1 scores survivors only"


# ---------------------------------------------------------------------------
# §4.2 soft flags
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_each_soft_row_raises_its_own_flag_and_rejects_nothing() -> None:
    """One candidate per soft row, each still accepted.

    ``Institutional Ownership`` is absent by design — D24 disables it, and the attempt to
    raise it anyway lives in ``test_enforcement.py`` where the guarantee tests are.
    """
    cases: list[tuple[dict[str, object], SoftFlag]] = [
        ({"premarket_volume": D("50000")}, SoftFlag.PREMARKET_THIN),
        ({"market_cap": D("9000000000")}, SoftFlag.MARKET_CAP_HIGH),
        ({"atr": D("0.20"), "avg_atr": D("0.40")}, SoftFlag.ATR_LOW),
        ({"catalyst": Catalyst.NONE}, SoftFlag.NO_CATALYST),
        ({"sessions_since_halt": 2}, SoftFlag.RECENT_HALT),
        ({"short_interest_pct": D("0.30")}, SoftFlag.HIGH_SHORT_INTEREST),
    ]
    for overrides, expected in cases:
        result = evaluate_candidate(candidate(**overrides), CFG)
        assert result.flags == (expected,), f"{overrides} -> {result.flags}"
        assert result.passed, f"a soft row rejected a candidate: {expected}"
        assert result.score is not None


@pytest.mark.boundary
def test_soft_thresholds_sit_where_4_2_states_them() -> None:
    """The flag half of the same weak-inequality check the hard filters get."""
    assert flags(candidate(premarket_volume=D("100000"))) == ()
    assert flags(candidate(premarket_volume=D("99999"))) == (SoftFlag.PREMARKET_THIN,)
    assert flags(candidate(market_cap=D("2000000000"))) == ()
    assert flags(candidate(market_cap=D("2000000001"))) == (SoftFlag.MARKET_CAP_HIGH,)
    assert flags(candidate(atr=D("0.30"), avg_atr=D("0.20"))) == ()
    assert flags(candidate(atr=D("0.29"), avg_atr=D("0.20"))) == (SoftFlag.ATR_LOW,)
    assert flags(candidate(short_interest_pct=D("0.05"))) == (SoftFlag.HIGH_SHORT_INTEREST,)
    assert flags(candidate(short_interest_pct=D("0.049"))) == ()
    assert flags(candidate(sessions_since_halt=5)) == (SoftFlag.RECENT_HALT,)
    assert flags(candidate(sessions_since_halt=6)) == ()


@pytest.mark.spec
def test_a_missing_soft_input_raises_no_flag() -> None:
    """``None`` means "not available", which is not the same as "bad".

    Flagging ``MARKET_CAP_HIGH`` on a name whose market cap nobody supplied would be the
    scanner reporting a measurement it did not make. Phase 2a Q1 exists precisely because
    which of these fields a provider actually returns is unknown.
    """
    blank = candidate(
        market_cap=None,
        atr=None,
        avg_atr=None,
        sessions_since_halt=None,
        institutional_ownership_pct=None,
        short_interest_pct=None,
    )
    assert flags(blank) == ()
    assert verdict(blank) is None
    # Half an ATR pair is still not an ATR.
    assert flags(candidate(atr=D("0.01"), avg_atr=None)) == ()
    assert flags(candidate(atr=None, avg_atr=D("9.99"))) == ()


# ---------------------------------------------------------------------------
# §4.3 ranking
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_daily_gap_is_what_feeds_the_score() -> None:
    """Pin the one identification this module makes that §4.2 and §20.10 do not state.

    §4.2's daily Gap % is a fraction; §20.10's ``pct_change`` is in percent units. The
    scanner takes them to be the same quantity and converts, rather than accepting two
    numbers for one move. If that is ever decided the other way, this fails — which is the
    point. Same shape as ``test_score_float_cap_currently_equals_the_scan_filter``.
    """
    c = candidate(daily_gap_pct=D("0.2500"))
    result = evaluate_candidate(c, CFG)
    expected = composite_score(
        ScoreInputs(
            pct_change=D("25.00"),
            rvol=c.rvol,
            float_shares=c.float_shares,
            premarket_volume=c.premarket_volume,
            catalyst=c.catalyst,
        ),
        CFG,
    )
    # Asserted as what the conversion does, not as the constant it is: a §4.2 fraction of
    # 0.2500 must reach §20.10 as 25.00 percent units.
    assert c.daily_gap_pct * PERCENT_PER_UNIT == D("25.00")
    assert result.score is not None and result.score == expected


@pytest.mark.spec
def test_the_watchlist_is_ranked_by_score_and_truncated() -> None:
    """§4.1 / §4.3: survivors, best first, cut to ``watchlist_size``."""
    universe = [
        candidate(symbol="LOW", rvol=D("5.0"), premarket_volume=D("120000")),
        candidate(symbol="HIGH", rvol=D("40"), premarket_volume=D("3000000")),
        candidate(symbol="MID", rvol=D("11"), premarket_volume=D("700000")),
        candidate(symbol="OUT", rvol=D("1")),  # RVOL_TOO_LOW
    ]
    report = scan(universe, CFG.with_overrides(watchlist_size=2))

    assert len(report.results) == 4, "nothing is dropped from the audit trail"
    assert [r.candidate.symbol for r in report.survivors] == ["LOW", "HIGH", "MID"]
    assert [r.candidate.symbol for r in report.watchlist] == ["HIGH", "MID"]

    scores = [r.score.total for r in report.watchlist if r.score is not None]
    assert scores == sorted(scores, reverse=True)
    assert all(r.passed for r in report.watchlist)


@pytest.mark.spec
def test_a_rejected_candidate_is_never_ranked() -> None:
    """§4.1 orders hard filters before scoring, so a reject has no score to rank on."""
    report = scan([candidate(symbol="OUT", float_shares=D("400000000"))], CFG)
    assert report.watchlist == () and report.survivors == ()
    only = report.results[0]
    assert only.reject is Reject.FLOAT_TOO_HIGH and only.score is None


@pytest.mark.spec
def test_ties_are_broken_by_symbol_so_the_watchlist_does_not_depend_on_input_order() -> None:
    """The tiebreak is the implementation's; §4.3 states none, and ties are reachable.

    Two identical candidates score identically. Without a deterministic tiebreak the
    watchlist would be a function of the order the universe arrived in, so the same market
    would produce different answers on different days.
    """
    twins = [candidate(symbol=s) for s in ("ZZZ", "AAA", "MMM")]
    forward = scan(twins, CFG)
    backward = scan(list(reversed(twins)), CFG)

    totals = {r.score.total for r in forward.watchlist if r.score is not None}
    assert len(totals) == 1, "the fixture must actually tie for this to test anything"
    assert [r.candidate.symbol for r in forward.watchlist] == ["AAA", "MMM", "ZZZ"]
    assert [r.candidate.symbol for r in backward.watchlist] == ["AAA", "MMM", "ZZZ"]


@pytest.mark.spec
def test_an_empty_universe_produces_an_empty_report() -> None:
    report = scan([], CFG)
    assert report.results == () and report.watchlist == () and report.survivors == ()


@pytest.mark.spec
def test_the_simulated_universe_exercises_every_hard_filter() -> None:
    """``python -m tradipy scan`` must demonstrate all seven rows, not a convenient subset.

    A demo that only ever shows candidates passing is the shape of a happy-path test: it
    looks like evidence and is not. Asserted against
    :func:`tradipy.poc.simulated_universe` so the CLI's fixture cannot quietly stop covering
    a filter when a threshold moves.
    """
    report = scan(simulated_universe(CFG), CFG)
    fired = {code for r in report.results for code in r.rejects}
    assert fired == {f.code for f in HARD_FILTERS}, (
        f"hard filters no simulated candidate reaches: "
        f"{sorted(f.code.value for f in HARD_FILTERS if f.code not in fired)}"
    )
    assert len(report.survivors) > len(report.watchlist), "truncation must be visible"
    assert len(report.watchlist) == int(CFG["watchlist_size"])


@pytest.mark.spec
def test_scan_candidate_is_immutable() -> None:
    """A candidate is evidence about a moment, and rewriting it in place loses the moment."""
    c = candidate()
    with pytest.raises(FrozenInstanceError):
        c.price = D("9.99")  # pyright: ignore[reportAttributeAccessIssue]
    assert replace(c, price=D("9.99")).price == D("9.99")
    assert c.price == D("4.00")
