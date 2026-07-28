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

from decimal import Decimal
from types import MappingProxyType

import pytest

from tradipy.gates import (
    Reject,
    apply_stop_floor_and_ceiling,
    check_room,
    exit_ladder,
    min_separation,
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
from tradipy.rounding import TICK_SIZE, Polarity, ceil_to_tick, floor_to_tick, round_threshold
from tests.test_worked_examples import EXAMPLES, IDS

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
def test_room_gate_multiple_must_exceed_t1_multiple() -> None:
    """PRD §3.1.1: T1 sits at 2R, so a room gate at 2.0 leaves T2 no room above T1."""
    with pytest.raises(CouplingError, match="must exceed"):
        CFG.with_overrides(room_gate_multiple="2.0")


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


@pytest.mark.polarity
def test_every_gate_parameter_declares_a_polarity() -> None:
    """PRD §20.13: classify as MINIMUM or MAXIMUM **before** choosing a rounding function.

    Any parameter used as a gate threshold must declare its polarity. An unclassified
    threshold is how the v1.3.1 defect happened, so this is enforced rather than trusted.
    """
    gate_params = [
        "room_gate_multiple", "min_stop_distance", "max_stop_pct",
        "max_spread_abs", "max_spread_pct", "max_spread_r",
        "min_rvol", "max_float_shares", "min_adv_shares", "max_vwap_extension_pct",
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
def test_partial_config_is_rejected_with_a_useful_error() -> None:
    """Accepted consequence of validating in ``__post_init__``: ``values`` must be complete.

    A ``Config`` missing ``room_gate_multiple`` is not a config. Raising here beats letting
    a ``KeyError`` escape from inside the coupling validator.
    """
    with pytest.raises(ValueError, match="missing"):
        Config({"min_stop_distance": D("0.10")})
