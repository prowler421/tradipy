"""Boundary fixtures — PRD §3.1.3 robustness invariant, §21.1 worst-case gate fixtures.

This file exists because of the v1.3 defect class: **joint incoherence**. Two parameters
were each inside their own bounds and each defensible alone — the §4.2 spread filter
admitted 1% of price, and §3.1.2's separation floor consumed spread as an input — but they
could not both hold. At the filter's own limit, crossing the spread twice cost up to 83% of
R, and all three worked examples failed their own separation floor while appearing to pass
at an assumed $0.01 spread.

The generalizable lesson, from PLAN Workstream 11: **test every gate at the boundary its
own filters admit, not at an illustrative value.** A parameter registry would have passed
that defect clean, because every value appeared exactly once.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from types import MappingProxyType

import pytest

from tests.test_worked_examples import EXAMPLES, IDS
from tradipy.bars import Bar, green_runs, measured_move, select_flagpole
from tradipy.gates import (
    Reject,
    apply_stop_floor_and_ceiling,
    check_room,
    exit_ladder,
    min_separation,
    position_size,
    required_room,
    spread_caps,
    vwap_reclaim_stop,
)
from tradipy.params import (
    DISCRIMINATING_CAP_TICKS,
    PARAMS,
    Config,
    CouplingError,
    min_tradeable_price_from_stop_bounds,
    signal_cap_ticks_at_min_r,
)
from tradipy.rounding import (
    TICK_SIZE,
    Polarity,
    ceil_to_tick,
    floor_to_tick,
    is_whole_tick,
    round_threshold,
)

D = Decimal
CFG = Config.default(mode="experienced")


# ---------------------------------------------------------------------------
# §3.1.3 robustness invariant
# ---------------------------------------------------------------------------
@pytest.mark.boundary
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_separation_floor_holds_at_widest_admitted_spread(ex) -> None:
    """Every §3 example must clear its separation floor at the **widest spread its own
    filters admit** — not at the $0.01 the tables assume.

    PRD §3.1.3 states this as a testable invariant precisely so that loosening
    ``max_spread_r``, ``max_spread_pct``, ``max_spread_abs`` or ``sep_cost_multiple`` breaks
    CI rather than silently readmitting negative-expectancy trades.
    """
    r = ex.entry - ex.stop
    widest = spread_caps(ex.entry, r, CFG).binding
    floor = min_separation(r, widest, CFG)
    ladder = exit_ladder(ex.entry, r, ex.structural_target, CFG)
    actual = ladder.t2 - ladder.t1

    assert actual >= floor, (
        f"{ex.section}: at the widest admitted spread {widest}, the separation floor is "
        f"{floor} but T2-T1 is only {actual}. This is the v1.3 defect: the gate and the "
        "filter feeding it were not jointly calibrated."
    )


@pytest.mark.boundary
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_old_one_percent_filter_would_fail_the_invariant(ex) -> None:
    """Regression pin: the *superseded* 1%-of-price spread filter must still fail.

    If a future change reintroduces a percentage-of-price cap at 1%, this test fails —
    which is the point. It encodes *why* §3.1.3 exists, not merely what it says.
    """
    r = ex.entry - ex.stop
    old_spread = floor_to_tick(ex.entry * D("0.01"))
    round_trip = old_spread * 2

    assert round_trip > CFG["min_sep_r"] * r, (
        f"{ex.section}: round-trip spread cost {round_trip} at the old 1% filter should "
        f"exceed the 0.5R erosion threshold ({CFG['min_sep_r'] * r}) — §18.2"
    )

    floor = min_separation(r, old_spread, CFG)
    ladder = exit_ladder(ex.entry, r, ex.structural_target, CFG)
    assert ladder.t2 - ladder.t1 < floor, (
        f"{ex.section}: the old 1% filter must fail this invariant; if it now passes, the "
        "separation floor has been weakened"
    )


# ---------------------------------------------------------------------------
# §3.1.2 — which term of the unified room requirement binds
# ---------------------------------------------------------------------------
@pytest.mark.boundary
@pytest.mark.parametrize("ex", EXAMPLES, ids=IDS)
def test_which_room_term_binds_is_pinned(ex) -> None:
    """PRD §3.1.2: the unified requirement is ``max(proportional, 2R + min_separation)``.

    The point of unifying them is that *"on wide-spread names the separation floor is the
    stricter of the two"* — so which term binds is a fact about the calibration and worth
    pinning. On all three MVP examples at a $0.01 spread the **separation** term binds, which
    means the §3.1.1 proportional multiple is not what is actually gating these trades.
    """
    r = ex.entry - ex.stop
    req = required_room(r, ex.spread, CFG)
    assert req.separation_term > req.proportional_term, (
        f"{ex.section}: expected the separation term to bind; if the proportional term now "
        "binds, the calibration changed and §3.1.2's rationale should be re-read"
    )
    assert req.binding is Reject.TARGETS_TOO_CLOSE


@pytest.mark.boundary
def test_binding_reason_is_chosen_from_unrounded_terms() -> None:
    """§3.3 is the sub-tick case: the two terms differ by half a tick and round to one value.

    Review flagged that ``required_room`` compares the unrounded terms but returns the
    rounded requirement, and proposed comparing the rounded ones instead. Making that change
    is what showed it to be wrong: at R = $0.15 the proportional term is $0.375 and the
    separation term $0.380, both ceiling to $0.38, so a rounded comparison reports
    ``INSUFFICIENT_ROOM`` — that the setup failed the §3.1.1 proportional gate. It did not.
    The separation term is stricter; rounding erased the gap.

    The requirement is $0.38 either way, so only the reason code is at stake, and it should
    name the constraint that is actually stricter. This pins that.
    """
    r, spread = D("0.15"), D("0.01")
    req = required_room(r, spread, CFG)

    assert req.proportional_term == D("0.375")
    assert req.separation_term == D("0.380")
    assert req.required == D("0.38"), "both terms round to the same requirement"
    assert round_threshold(req.proportional_term, Polarity.MINIMUM) == req.required, (
        "if this stops holding, §3.3 is no longer the sub-tick case and this test needs a "
        "new fixture rather than deletion"
    )
    assert req.binding is Reject.TARGETS_TOO_CLOSE, (
        "the separation term is stricter by $0.005; a rounded comparison would misreport "
        "this as INSUFFICIENT_ROOM"
    )


@pytest.mark.boundary
def test_separation_term_actually_rejects_when_proportional_would_pass() -> None:
    """Proves the separation term is enforced, not decorative.

    Constructed so the two terms disagree: at R = $0.10 and a $0.01 spread the proportional
    term needs $0.25 of room while the unified requirement needs $0.28. A setup with $0.26 of
    room must therefore be **rejected** — a system checking only §3.1.1's multiple would take
    it.

    Added after a mutation check: replacing ``required_room`` with the proportional term alone
    passed the entire suite, because all three worked examples clear the separation term with
    margin. Every gate needs at least one case where it is the binding constraint.
    """
    entry, r, spread = D("4.00"), D("0.10"), D("0.01")
    req = required_room(r, spread, CFG)
    assert req.proportional_term == D("0.25")
    assert req.required == D("0.28")

    resistance = entry + D("0.26")  # clears 0.25, fails 0.28
    assert check_room(entry, resistance, r, spread, CFG) is Reject.TARGETS_TOO_CLOSE

    resistance_ok = entry + D("0.28")
    assert check_room(entry, resistance_ok, r, spread, CFG) is None


@pytest.mark.boundary
def test_room_gate_multiple_can_never_strictly_bind_at_defaults() -> None:
    """**Open spec finding: ``room_gate_multiple`` is inert at its default.**

    The two terms of the unified requirement (§3.1.2) are::

        proportional = room_gate_multiple * R          = 2.5R
        separation   = t1_r_multiple * R + min_separation
                     = 2R + max(min_sep_r * R, cost)   >= 2R + 0.5R = 2.5R

    Since ``min_separation`` is floored at ``min_sep_r * R`` = 0.5R **by construction**, and
    ``room_gate_multiple`` (2.5) equals ``t1_r_multiple + min_sep_r`` (2.0 + 0.5) **exactly**,
    the proportional term can never *exceed* the separation term at defaults — only tie it.

    Two consequences:

    1. ``room_gate_multiple`` does no work at 2.5. §3.1.2 says ``min_sep_r`` is *"redundant
       with a 2.5 room gate"*; the dominance runs the other way.
    2. ``INSUFFICIENT_ROOM`` is only ever emitted on a **tie** (large R, where the 0.5R term
       beats the cost term), never because the proportional constraint was stricter.

    This is not a code bug — it follows from three defaults that were each set for good
    reasons in different revisions. Resolving it is a spec decision: raise
    ``room_gate_multiple`` above 2.5 so it can bind, or delete it and let §3.1.2 stand alone.
    Until then this test pins the property so it cannot be assumed away.
    """
    assert CFG["room_gate_multiple"] == CFG["t1_r_multiple"] + CFG["min_sep_r"], (
        "the dominance argument depends on this exact equality"
    )

    for r in ["0.05", "0.10", "0.15", "0.20", "0.60", "2.00"]:
        req = required_room(D(r), D("0.01"), CFG)
        assert req.proportional_term <= req.separation_term, (
            f"R={r}: proportional term unexpectedly exceeded the separation term — if this "
            "now happens, room_gate_multiple has been raised and this finding is resolved"
        )


@pytest.mark.boundary
def test_proportional_term_can_bind_only_above_the_default_multiple() -> None:
    """It becomes live at ``room_gate_multiple`` > ``t1_r_multiple + min_sep_r``.

    Shown at the 3.0 upper bound, where the proportional term genuinely dominates on a wide
    stop. This is the evidence for the "raise it" option in the finding above.
    """
    cfg3 = CFG.with_overrides(room_gate_multiple="3.0")
    req = required_room(D("0.60"), D("0.01"), cfg3)
    assert req.proportional_term > req.separation_term
    assert req.binding is Reject.INSUFFICIENT_ROOM


@pytest.mark.boundary
def test_signal_spread_cap_would_floor_to_zero_without_the_clamp() -> None:
    """A25: ``floor_to_tick(max_spread_r * R)`` reaches $0.00 below R = tick/max_spread_r.

    Unclamped, that rejects **every trade** — silently, with a plausible-looking
    ``SPREAD_TOO_WIDE`` on each. The clamp converts a total outage into a merely permissive
    gate. This test documents the boundary and proves the clamp is what prevents the outage.
    """
    boundary_r = TICK_SIZE / CFG["max_spread_r"]
    assert boundary_r.quantize(D("0.0001")) == D("0.0667")

    tight_r = D("0.05")  # below the boundary, reachable if min_stop_distance is lowered
    assert tight_r < boundary_r

    unclamped = floor_to_tick(CFG["max_spread_r"] * tight_r)
    assert unclamped == D("0.00"), "the unclamped cap should collapse to zero"

    clamped = round_threshold(CFG["max_spread_r"] * tight_r, Polarity.MAXIMUM)
    assert clamped == TICK_SIZE, "the clamp must hold the cap at one tick"


@pytest.mark.boundary
def test_default_config_keeps_r_above_the_zero_cap_boundary() -> None:
    """At defaults the coupling is safe: min_stop_distance $0.10 > boundary $0.067."""
    assert CFG["min_stop_distance"] > TICK_SIZE / CFG["max_spread_r"]


@pytest.mark.boundary
def test_coupling_validator_rejects_the_legal_but_unsound_combination() -> None:
    """A25's recommended fix: fail at config load, not at trade time.

    ``min_stop_distance`` may legally go to $0.01 per §2.0 and ``max_spread_r`` to 0.50, and
    each is individually in bounds — so per-parameter validation passes. The coupling
    validator is what catches it.
    """
    with pytest.raises(CouplingError, match="coupling, not two independent bounds"):
        CFG.with_overrides(min_stop_distance="0.01")

    # And the bound itself is legal in isolation, proving per-parameter checks are not enough.
    PARAMS["min_stop_distance"].validate(D("0.01"))


@pytest.mark.boundary
def test_a25_recommended_validator_would_reject_the_shipped_defaults() -> None:
    """**Open spec discrepancy, found by implementing A25.**

    A25's prose locates the outage boundary at ``tick / max_spread_r`` = $0.0667 (factor 1),
    but its recommended config-load validator is written as ``2 * tick / max_spread_r`` =
    $0.1333 (factor 2). The shipped ``min_stop_distance`` default is $0.10, which satisfies
    the first and fails the second — so A25's recommended validator rejects the PRD's own
    defaults.

    This test pins both facts so the discrepancy cannot be quietly resolved in either
    direction. Closing it requires a spec decision: raise ``min_stop_distance`` to $0.14,
    raise ``max_spread_r`` to 0.20, or amend A25 to factor 1. All three change trading
    behaviour, so none belongs in code.
    """
    factor_1 = TICK_SIZE / CFG["max_spread_r"]
    factor_2 = 2 * TICK_SIZE / CFG["max_spread_r"]
    default_min_stop = PARAMS["min_stop_distance"].default

    assert factor_1.quantize(D("0.0001")) == D("0.0667")
    assert factor_2.quantize(D("0.0001")) == D("0.1333")
    assert default_min_stop >= factor_1, "the enforced no-outage invariant holds"
    assert default_min_stop < factor_2, (
        "A25's recommended factor-2 validator rejects the shipped defaults — if this now "
        "passes, the spec resolved the discrepancy and this test should be deleted"
    )


@pytest.mark.boundary
def test_signal_spread_cap_is_only_one_tick_wide_at_minimum_r() -> None:
    """Consequence of the above: at the tightest legal R the gate admits a single value.

    ``max_spread_r * min_stop_distance`` = 0.15 × $0.10 = $0.015, which floors to $0.01 — the
    clamp floor. A one-tick-wide maximum is pass/fail on one spread rather than a threshold,
    so minimum-R trades are admitted only at the tightest possible market. Worth measuring in
    Phase 2a (A21) alongside the low-price-band effect below.
    """
    assert signal_cap_ticks_at_min_r(CFG) == 1
    assert signal_cap_ticks_at_min_r(CFG) < DISCRIMINATING_CAP_TICKS


@pytest.mark.boundary
def test_t1_cannot_be_configured_below_the_non_bypassable_2r_floor() -> None:
    """PRD §1: *"Minimum 2:1 reward-to-risk on every trade … **non-bypassable**"*.

    §2 states T1 as *"2R (minimum)"* and §3.1.1 as *"Exactly 2R"*, but ``t1_r_multiple``
    carried a code-originated range of ``[1.0, 5.0]`` — so ``with_overrides`` happily put T1
    at 1R and nothing objected. D26 removed the ``room_gate_multiple > t1_r_multiple``
    coupling, which had been the only thing incidentally constraining it, so this had to
    become an explicit bound rather than a side effect.
    """
    assert PARAMS["t1_r_multiple"].lo == D("2.0"), "§2 states 2R as a minimum, not a default"
    with pytest.raises(ValueError, match="outside legal bounds"):
        CFG.with_overrides(t1_r_multiple="1.0")

    # Upward is allowed — §2 marks the R-multiple user-configurable — and T1 moves with it.
    wider = CFG.with_overrides(t1_r_multiple="3.0")
    assert exit_ladder(D("5.16"), D("0.12"), D("5.99"), wider).t1 == D("5.52")


@pytest.mark.boundary
def test_room_gate_multiple_at_its_prd_lower_bound_is_legal_and_inert() -> None:
    """**D26.** PRD §1, §2.0, §3.1.1 and §7 all state 2.0 is legal. It is, and it does nothing.

    Until v0.1.0 ``validate_couplings`` raised on ``room_gate_multiple <= t1_r_multiple``,
    making the PRD's own lower bound throw. The justification cited §3.1.1, which says the
    multiple *"cannot go below 2.0"* — that is ``>= 2.0``, not ``> 2.0`` — so the cited
    section did not support the check, and grep found the deviation declared nowhere.

    Removing it is safe because the ordering guarantee never came from the proportional term.
    ``min_separation`` is a MINIMUM-polarity threshold over a strictly positive quantity, so
    it is at least one tick at every legal configuration; the §3.1.2 separation term
    ``t1_r_multiple * R + min_separation`` therefore strictly exceeds ``t1_r_multiple * R``,
    and it is what actually guarantees ``entry < T1 < T2``. At 2.0 the proportional term is
    dominated, exactly as it already is at the 2.5 default — see the finding above. Inert,
    not unsafe.

    **The obvious derivation is wrong, and a first draft of D26 used it in six places.**
    ``min_separation >= min_sep_r * R > 0`` fails at ``min_sep_r = 0.0``, which §2.0 permits.
    The conclusion survives — the cost term carries it — but the stated reasoning did not,
    which is the v1.3.1 class (a rule generalized past its justification) restated the v1.2
    way (in more than one copy), inside the fix for a finding about unenforced guarantees.
    The worst case is exercised below rather than argued.
    """
    worst_case = CFG.with_overrides(min_sep_r="0.0", room_gate_multiple="2.0")
    assert worst_case["min_sep_r"] * D("0.15") == 0, "the false derivation's premise fails here"
    assert min_separation(D("0.15"), D("0.01"), worst_case) >= TICK_SIZE, (
        "the correct derivation holds: the cost term is strictly positive at every legal "
        "configuration, and a MINIMUM rounds up"
    )
    assert required_room(D("0.15"), D("0.01"), worst_case).separation_term > (
        worst_case["t1_r_multiple"] * D("0.15")
    ), "entry < T1 < T2 survives min_sep_r = 0 with room_gate_multiple at its floor"

    at_lower_bound = CFG.with_overrides(room_gate_multiple="2.0")
    assert at_lower_bound["room_gate_multiple"] == PARAMS["room_gate_multiple"].lo

    for r in ["0.05", "0.10", "0.15", "0.60", "2.00"]:
        req_default = required_room(D(r), D("0.01"), CFG)
        req_floor = required_room(D(r), D("0.01"), at_lower_bound)
        assert req_floor.separation_term > req_floor.proportional_term, (
            f"R={r}: at the 2.0 lower bound the proportional term must be dominated"
        )
        assert req_floor.required == req_default.required, (
            f"R={r}: lowering room_gate_multiple to its PRD floor must not change the "
            "requirement, because the separation term already governs"
        )
        assert req_floor.required > CFG["t1_r_multiple"] * D(r), (
            "entry < T1 < T2 is guaranteed by §3.1.2's separation term, not by the multiple"
        )

    # Below the PRD's floor, per-parameter validation is what rejects it — one bound, in the
    # registry, exactly where §2.0 states it.
    with pytest.raises(ValueError, match="outside legal bounds"):
        CFG.with_overrides(room_gate_multiple="1.9")


# ---------------------------------------------------------------------------
# Low-price band: the clamp changes what max_spread_pct means below ~$2
# ---------------------------------------------------------------------------
@pytest.mark.boundary
def test_scan_cap_clamp_binds_below_two_dollars() -> None:
    """Documents a live consequence of the one-tick clamp on the **scan** gate.

    ``floor_to_tick(max_spread_pct * price)`` is $0.00 for any price under $2.00 at the 0.5%
    default, so the clamp raises it to one tick. Two consequences worth pinning:

    1. ``max_spread_pct`` stops behaving like a percentage below $2.00 — at $1.00 the
       effective cap is 1.00% of price, double what the parameter promises.
    2. In absolute terms the cap is *maximally strict* there: only 1-tick spreads are
       admitted across the whole $1.00–$1.99 band, which §2 includes in the tradeable
       universe ($1.00–$20.00).

    Economically this is contained — the signal-time ``0.15 × R`` gate plus the $0.10 stop
    floor are what actually protect expectancy — but the band is *de facto* excluded by a
    clamp introduced for an unrelated reason. Phase 2a's spread-distribution measurement
    (A21) should quantify the rejection rate before this is treated as intentional.
    """
    r = D("0.15")  # comfortably above the zero-cap boundary
    for price, expected_pct_of_price in [(D("1.00"), D("0.0100")), (D("1.50"), D("0.0067"))]:
        caps = spread_caps(price, r, CFG)
        assert caps.scan == TICK_SIZE, f"clamp should bind at ${price}"
        effective = (caps.scan / price).quantize(D("0.0001"))
        assert effective == expected_pct_of_price
        assert effective > CFG["max_spread_pct"], (
            f"at ${price} the effective cap {effective} exceeds the declared "
            f"max_spread_pct {CFG['max_spread_pct']}"
        )

    # At and above $2.00 the parameter behaves as declared.
    for price in [D("2.00"), D("4.00"), D("20.00")]:
        caps = spread_caps(price, r, CFG)
        assert caps.scan / price <= CFG["max_spread_pct"], f"should hold at ${price}"


# ---------------------------------------------------------------------------
# Rounding direction — assert the derivation, not the value
# ---------------------------------------------------------------------------
@pytest.mark.polarity
def test_minimum_thresholds_round_up_and_never_weaken() -> None:
    """PRD §20.13: a MINIMUM rounds up, so the rounded value is never easier to clear."""
    for raw in ["0.0750", "0.1050", "0.1000", "0.0001", "0.3333"]:
        v = D(raw)
        rounded = round_threshold(v, Polarity.MINIMUM)
        assert rounded == ceil_to_tick(v), "MINIMUM must use ceil_to_tick"
        assert rounded >= v, f"rounding a minimum must not lower it ({rounded} < {v})"


@pytest.mark.polarity
def test_maximum_thresholds_round_down_and_never_weaken() -> None:
    """PRD §20.13: a MAXIMUM rounds down (then clamps), so it is never easier to clear.

    This is the assertion that would have caught the v1.3.1 defect. ``assert cap == 0.01``
    passes under a wrong rule that happens to agree at that input; asserting the
    *derivation* does not.
    """
    for raw in ["0.0180", "0.0225", "0.0150", "0.0999", "0.0200"]:
        v = D(raw)
        rounded = round_threshold(v, Polarity.MAXIMUM)
        assert rounded == max(TICK_SIZE, floor_to_tick(v)), "MAXIMUM must use clamped floor"
        assert rounded <= v or rounded == TICK_SIZE, (
            f"rounding a maximum must not raise it ({rounded} > {v})"
        )


@pytest.mark.polarity
def test_ceil_on_a_maximum_would_be_more_permissive() -> None:
    """Pins *why* the polarity split exists — the v1.3.1 defect made concrete.

    An earlier draft applied ``ceil_to_tick`` to §3.1.3's spread cap by analogy with the
    minimum-gate rule. On the Bull Flag example that widened the admitted spread from $0.01
    to $0.02, which in turn raised the required separation floor from $0.08 to $0.11 —
    leaving the example passing by exactly $0.00 instead of $0.03.
    """
    r = D("0.12")  # §3.2 Bull Flag
    raw = CFG["max_spread_r"] * r  # 0.018

    correct = round_threshold(raw, Polarity.MAXIMUM)
    wrong = ceil_to_tick(raw)
    assert correct == D("0.01") and wrong == D("0.02")
    assert wrong > correct, "the wrong direction admits a wider spread"

    floor_correct = min_separation(r, correct, CFG)
    floor_wrong = min_separation(r, wrong, CFG)
    assert floor_correct == D("0.08") and floor_wrong == D("0.11")

    actual_separation = D("5.51") - D("5.40")
    assert actual_separation - floor_correct == D("0.03"), "margin under the correct rule"
    assert actual_separation - floor_wrong == D("0.00"), "zero margin under the wrong rule"


# ---------------------------------------------------------------------------
# Rounding direction at a NON-DEGENERATE input
#
# Everything above this block asserts direction against `round_threshold`, which the five
# §3.1.2/§3.1.3 gate thresholds route through. Nothing asserted it for the *other* rounding
# in the package — the exit ladder, the stop chain, the sizing truncation — and at the three
# §3 worked examples it could not: every level is already a whole tick and all three risk
# divisions are exact ($300/$0.12, $300/$0.15, $300/$0.10), so ceil, floor and round all
# agree. Twelve direction-and-truncation mutations survived the entire suite while PRD §19's
# "rounding-direction assertions" row was ticked. That is the fifth defect class again, in
# the module its own fix had just touched.
#
# The fixture below is deliberately degenerate in no respect: a 2.5R T1 on a $0.13 R lands
# between ticks, the risk budget does not divide evenly, and the VWAP band is a tenth of a
# tick off. Direction and truncation are visible in every one.
# ---------------------------------------------------------------------------
NON_TICK_R = D("0.13")  # 2.5 x 0.13 = 0.325 — half a tick past a boundary
NON_TICK_CFG = CFG.with_overrides(t1_r_multiple="2.5")


@pytest.mark.polarity
def test_targets_round_up_away_from_entry_at_a_non_tick_level() -> None:
    """PRD §20.13: *"Targets (long): round up."* Away from entry, so R is never flattered.

    Rounding a target down would report a fill at a level the market never had to reach,
    which inflates every backtested R by up to a tick — the specific dishonesty §20.13's
    direction rule exists to prevent.
    """
    entry = D("5.16")
    raw_t1 = entry + NON_TICK_CFG["t1_r_multiple"] * NON_TICK_R  # 5.485
    raw_t2 = D("5.5149")

    ladder = exit_ladder(entry, NON_TICK_R, raw_t2, NON_TICK_CFG)

    assert not is_whole_tick(raw_t1) and not is_whole_tick(raw_t2), "fixture must not be degenerate"
    assert ladder.t1 == ceil_to_tick(raw_t1) == D("5.49")
    assert ladder.t2 == ceil_to_tick(raw_t2) == D("5.52")
    assert ladder.t1 > raw_t1 and ladder.t2 > raw_t2, "a rounded target must never move closer"
    assert ladder.t1 != floor_to_tick(raw_t1), "floor here would flatter backtested R"


@pytest.mark.polarity
def test_stops_round_down_away_from_the_position_at_a_non_tick_level() -> None:
    """PRD §20.13: *"Stops (long): round down."* Away from the position, so it is never tighter.

    Rounding a stop up moves it into the pattern and manufactures a noise stop-out, which is
    the same failure §2 forbids when it says a too-wide stop means skip rather than tighten.
    """
    entry, raw_stop = D("5.16"), D("5.0449")
    stop, verdict = apply_stop_floor_and_ceiling(entry, raw_stop, CFG)

    assert not is_whole_tick(raw_stop), "fixture must not be degenerate"
    assert verdict is None
    assert stop == floor_to_tick(raw_stop) == D("5.04")
    assert stop < raw_stop, "a rounded stop must never move closer to entry"
    assert stop != ceil_to_tick(raw_stop), "ceil here would tighten the stop into the pattern"


@pytest.mark.polarity
def test_the_min_stop_floor_widens_and_never_narrows() -> None:
    """The $0.10 floor is a MINIMUM *distance*, so the level it produces rounds **down**.

    Shown with a floor that does not land on a tick from this entry: at ``min_stop_distance``
    $0.105 the floored stop is $0.11 away, and the ceiled one would be $0.10 — narrower than
    the floor demands, i.e. the constraint weakened by the arithmetic meant to enforce it.
    """
    cfg = CFG.with_overrides(min_stop_distance="0.105")
    entry = D("5.16")
    stop, verdict = apply_stop_floor_and_ceiling(entry, entry - TICK_SIZE, cfg)

    assert verdict is None
    assert stop == floor_to_tick(entry - cfg["min_stop_distance"]) == D("5.05")
    assert entry - stop >= cfg["min_stop_distance"], "the floor must never be undershot"
    assert entry - ceil_to_tick(entry - cfg["min_stop_distance"]) < cfg["min_stop_distance"]


@pytest.mark.polarity
def test_the_vwap_band_rounds_down_before_the_tick_is_subtracted() -> None:
    """§20.13's worked reference, with the **intermediate** pinned rather than only the result.

    ``VWAP x 0.99 = $3.762 -> floor -> $3.76 -> -1 tick -> $3.75``. The existing §3.4 fixture
    asserts the final $3.73, which arrives via the min-stop floor and is therefore identical
    under either rounding direction — so the step the reference exists to demonstrate was
    unpinned. Here the dip low sits below the band and the entry is far enough above that the
    floor does not fire, so the band's own direction is what decides the stop.
    """
    entry, dip_low, vwap = D("3.90"), D("3.70"), D("3.80")
    raw_band = vwap * (Decimal(1) - CFG["vwap_stop_band_pct"])  # 3.7620

    stop, verdict = vwap_reclaim_stop(entry, dip_low, vwap, CFG)

    assert not is_whole_tick(raw_band), "fixture must not be degenerate"
    assert verdict is None
    assert stop == floor_to_tick(raw_band) - TICK_SIZE == D("3.75")
    assert stop != ceil_to_tick(raw_band) - TICK_SIZE, "ceil would place the stop a tick tighter"


@pytest.mark.polarity
def test_share_count_truncates_and_never_rounds_up() -> None:
    """PRD §2.2: shares = **floor**(max_dollar_risk / stop_distance).

    Rounding to nearest breaches the §7 per-trade cap by up to one share's worth of R, which
    is a hard rule rather than a rounding preference. The three §3 examples all divide
    exactly, so floor, round and ceil agree on every one of them.
    """
    entry, entry_stop = D("5.16"), D("5.03")  # R = $0.13
    budget = CFG["start_of_day_equity"] * CFG["max_risk_per_trade_pct"]
    exact = budget / (entry - entry_stop)

    shares = position_size(entry, entry_stop, CFG)

    assert exact != exact.to_integral_value(), "fixture must not divide evenly"
    assert shares == int(exact) == 2307
    assert shares * (entry - entry_stop) <= budget, "§7: the risk cap is not a target to round to"
    assert shares < exact, "truncation must lose the fraction, not recover it"
    assert shares != round(exact), "round-to-nearest here breaches the per-trade cap"
    assert shares != int(exact.to_integral_value(rounding=ROUND_CEILING))


@pytest.mark.polarity
def test_the_optional_sizing_caps_truncate_too() -> None:
    """Both §2.2 constraints are ``<=``, so both floor. Neither divided evenly is tested."""
    entry, stop = D("5.16"), D("5.03")
    bp, adv = D("7777"), D("123456")

    by_bp = position_size(entry, stop, CFG, buying_power=bp)
    by_adv = position_size(entry, stop, CFG, adv_shares=adv)

    assert by_bp == int((bp * CFG["max_bp_usage_pct"]) / entry) == 753
    assert by_bp * entry <= bp * CFG["max_bp_usage_pct"]
    assert by_adv == int(CFG["max_pct_of_adv"] * adv) == 1234
    assert by_adv <= CFG["max_pct_of_adv"] * adv


@pytest.mark.polarity
def test_measured_move_is_returned_unrounded() -> None:
    """§20.13 rounds **once**, at level computation — which for a target is ``exit_ladder``.

    Its own docstring says so; nothing asserted it, so rounding here would have been a silent
    second rounding of the same quantity.
    """
    entry, height = D("5.16"), D("0.3549")
    assert measured_move(entry, height) == entry + height
    assert not is_whole_tick(measured_move(entry, height))


@pytest.mark.polarity
def test_a_full_tie_between_flagpole_candidates_resolves_deterministically() -> None:
    """§20.4 breaks ties by length then volume and is silent past that; earliest wins.

    A documented choice with no test is the shape of defect this file exists for, and an
    arbitrary winner would make flagpole selection depend on iteration order.
    """
    twin = [
        Bar(D("1.00"), D("2.00"), D("1.00"), D("1.50"), 100),
        Bar(D("1.50"), D("2.00"), D("1.00"), D("1.80"), 100),
        Bar(D("1.80"), D("2.00"), D("1.00"), D("1.00"), 50),  # red separator
        Bar(D("1.00"), D("2.00"), D("1.00"), D("1.50"), 100),
        Bar(D("1.50"), D("2.00"), D("1.00"), D("1.80"), 100),
    ]
    runs = green_runs(twin)
    assert runs == [(0, 1), (3, 4)], "the two candidates must tie on both length and volume"
    assert select_flagpole(twin, runs) == (0, 1)


@pytest.mark.polarity
def test_every_gate_parameter_declares_a_polarity() -> None:
    """PRD §20.13: classify as MINIMUM or MAXIMUM **before** choosing a rounding function.

    Any parameter used as a gate threshold must declare its polarity. An unclassified
    threshold is how the v1.3.1 defect happened, so this is enforced rather than trusted.
    """
    gate_params = [
        "room_gate_multiple",
        "min_stop_distance",
        "max_stop_pct",
        "max_spread_abs",
        "max_spread_pct",
        "max_spread_r",
        "min_rvol",
        "max_float_shares",
        "min_adv_shares",
        "max_vwap_extension_pct",
    ]
    unclassified = [n for n in gate_params if PARAMS[n].polarity is None]
    assert not unclassified, f"gate parameters missing a polarity: {unclassified}"


# ---------------------------------------------------------------------------
# §20.13 max-stop ceiling — the gate that had no test
# ---------------------------------------------------------------------------
@pytest.mark.boundary
def test_max_stop_ceiling_rejects_at_its_own_limit() -> None:
    """The ceiling fires the tick past ``max_stop_pct × entry`` and not before.

    ``apply_stop_floor_and_ceiling`` had zero test references before this. Mutation testing
    *could not have* found the gap while it existed: the only caller discarded the verdict,
    so deleting the ceiling changed nothing observable. Coverage counted the line; nothing
    asserted it. Now that the verdict propagates, deleting the ceiling kills this test and
    two others — see the mutation table in ``tests/README.md``.
    """
    entry = D("10.00")
    limit = CFG["max_stop_pct"] * entry  # $0.50

    at_limit, verdict = apply_stop_floor_and_ceiling(entry, entry - limit, CFG)
    assert verdict is None, "a stop exactly at the ceiling is admitted"
    assert entry - at_limit == limit

    _, verdict = apply_stop_floor_and_ceiling(entry, entry - limit - TICK_SIZE, CFG)
    assert verdict is Reject.STOP_TOO_WIDE, "one tick wider must skip the trade"


@pytest.mark.boundary
def test_ceiling_verdict_survives_the_vwap_reclaim_chain() -> None:
    """Regression: ``vwap_reclaim_stop`` must propagate ``STOP_TOO_WIDE``, not drop it.

    At a $1.50 entry the min-stop floor widens the stop to $1.40, a distance of $0.10 —
    6.7% of entry, past the 5% ceiling. The prior signature returned a bare ``Decimal``, so
    this trade received a live stop where §20.13 requires a skip.
    """
    stop, verdict = vwap_reclaim_stop(D("1.50"), D("1.45"), D("1.48"), CFG)
    assert verdict is Reject.STOP_TOO_WIDE
    assert stop == D("1.40"), "the level is still returned; the caller must honour the verdict"


# ---------------------------------------------------------------------------
# Open finding: min_stop_distance <-> max_stop_pct empties the $1.00-$1.99 band
# ---------------------------------------------------------------------------
@pytest.mark.boundary
def test_stop_bounds_empty_the_bottom_of_the_price_band() -> None:
    """``min_stop_distance / max_stop_pct`` = $2.00, but ``min_price`` admits $1.00.

    Below the crossover the floor forces a stop the ceiling rejects, so every entry in
    $1.00-$1.99 is unconditionally ``STOP_TOO_WIDE`` — independent of setup quality, spread,
    or R. Structurally this is finding 2 (the scan-cap clamp) reached by a different
    mechanism, and strictly stronger: the clamp makes that band maximally strict, this makes
    it empty.

    Not enforced in ``validate_couplings`` — the incoherent combination is the shipped
    default set, so raising would break ``Config.default()``. See
    :func:`min_tradeable_price_from_stop_bounds`. This test fails once the spec resolves it,
    which is the point.
    """
    crossover = min_tradeable_price_from_stop_bounds(CFG)
    assert crossover == D("2.00")
    assert PARAMS["min_price"].default < crossover, "§2 admits prices the stop math cannot serve"

    for price in ("1.00", "1.50", "1.99"):
        entry = D(price)
        _, verdict = apply_stop_floor_and_ceiling(entry, entry - TICK_SIZE, CFG)
        assert verdict is Reject.STOP_TOO_WIDE, f"${price} should be unreachable, not tradeable"

    for price in ("2.00", "2.01"):
        entry = D(price)
        _, verdict = apply_stop_floor_and_ceiling(entry, entry - TICK_SIZE, CFG)
        assert verdict is None, f"${price} is at or above the crossover and must pass"


@pytest.mark.boundary
def test_config_values_cannot_be_mutated_in_place() -> None:
    """``frozen=True`` freezes the binding; the dict behind it needs its own proxy.

    Direct assignment into ``cfg.values`` previously bypassed both ``Param.validate`` and
    ``validate_couplings``, which is every guarantee the class offers.

    Deliberately built on a **local** config, not the module-level ``CFG``. An earlier draft
    used ``CFG`` and passed, but mutation-checking the fix exposed the reason not to: with
    the proxy removed the assignment succeeds, and because ``CFG`` is shared it silently
    corrupted ``min_stop_distance`` for three later tests. A test asserting that mutation is
    impossible must not be the thing that performs it on shared state.
    """
    cfg = Config.default(mode="experienced")
    with pytest.raises(TypeError):
        cfg.values["min_stop_distance"] = D("99")  # type: ignore[index]
    assert cfg["min_stop_distance"] == PARAMS["min_stop_distance"].default
    assert CFG["min_stop_distance"] == PARAMS["min_stop_distance"].default


@pytest.mark.boundary
def test_proxy_does_not_retain_a_live_handle_to_the_callers_dict() -> None:
    """``MappingProxyType`` is a view, not a copy — so the copy must be unconditional.

    An earlier ``__post_init__`` skipped wrapping when the input was already a proxy, on the
    theory that re-wrapping was redundant. It was not: ``Config(MappingProxyType(d))`` then
    held a live view of ``d``, and mutating ``d`` afterwards changed the config through a
    class that advertises immutability.
    """
    live = {n: p.default for n, p in PARAMS.items()}
    cfg = Config(MappingProxyType(live))
    live["min_stop_distance"] = D("99")
    assert cfg["min_stop_distance"] == PARAMS["min_stop_distance"].default


@pytest.mark.boundary
def test_direct_construction_cannot_skip_coupling_validation() -> None:
    """Validation lives in ``__post_init__``, so no construction path can route around it.

    Previously only ``default()`` and ``with_overrides()`` validated, so
    ``Config(values)`` accepted the exact A25 pair the validator exists to reject.
    """
    vals = {n: p.default for n, p in PARAMS.items()}
    vals["min_stop_distance"] = D("0.01")  # below tick / max_spread_r = $0.0667
    with pytest.raises(CouplingError):
        Config(vals)


@pytest.mark.boundary
def test_direct_construction_cannot_skip_range_validation() -> None:
    """The other half of the same hole, open until v0.1.0.

    ``__post_init__`` checked *couplings* but never per-parameter **ranges**, which lived
    only in ``with_overrides``. So the test above passed, the docstring said "no construction
    path can route around it", and this was accepted::

        Config({**defaults, "max_spread_r": Decimal("99")})

    ``max_spread_r`` is bounded [0.05, 0.50]. At 99 the §3.1.3 signal-time cap on a $0.15 R
    becomes **$14.85** — the spread gate is off, silently, on a config that reports itself
    validated. The lesson is the one the project keeps relearning: a test that proves half a
    guarantee is what stops anyone checking the other half.
    """
    vals = {n: p.default for n, p in PARAMS.items()}
    vals["max_spread_r"] = D("99")
    with pytest.raises(ValueError, match="outside legal bounds"):
        Config(vals)

    # And the gate really would have been disabled, which is why this is not a style point.
    assert PARAMS["max_spread_r"].hi < D("99")
    assert D("99") * D("0.15") > CFG["max_spread_abs"] * 100


@pytest.mark.boundary
def test_config_rejects_unregistered_names() -> None:
    """``values`` may not carry a key that is not a registered parameter.

    Completeness was checked from v0.0.1; the reverse direction was not, so a typo produced
    a config that silently ignored the value the caller thought they had set.
    """
    vals = {n: p.default for n, p in PARAMS.items()}
    vals["max_spread_R"] = D("0.15")  # capital R
    with pytest.raises(ValueError, match="unregistered name"):
        Config(vals)


@pytest.mark.boundary
def test_partial_config_is_rejected_with_a_useful_error() -> None:
    """Accepted consequence of validating in ``__post_init__``: ``values`` must be complete.

    A ``Config`` missing ``room_gate_multiple`` is not a config. Raising here beats letting
    a ``KeyError`` escape from inside the coupling validator.
    """
    with pytest.raises(ValueError, match="missing"):
        Config({"min_stop_distance": D("0.10")})
