"""Enforcement fixtures — the fifth defect class.

PLAN Workstream 11 predicted one: *"The honest extrapolation is that a fifth class exists. It
will not be found by tightening any of the four checks above."* The v0.0.1 code review found
it, four times over in one sitting, and it is this:

    **Unenforced guarantee** — a rule that is stated normatively, has a mechanism built for
    it, is believed to be enforced, and is not.

It is invisible to all four earlier checks by construction. The rule appears once, so the
registry passes. The values are arithmetically correct, so the fixtures pass. The boundary
behaves as documented, so the boundary fixtures pass. The direction is right, so the polarity
assertions pass. Nothing looks at whether the mechanism is *wired to anything*, and the
documentation asserting that it is, is what stops anyone checking.

The four instances, all reproduced by execution before being fixed:

===========================================================  ===============================
Guarantee                                                     What was actually enforced
===========================================================  ===============================
``Config`` is frozen; §7 caps are non-bypassable              ``MODE_PRESETS`` was a mutable
                                                              dict read live, so one
                                                              assignment took a validated
                                                              config to 50% risk-per-trade
"No numeric literal for a registered threshold anywhere"      the lint was blind to 7 of 29
                                                              parameters via ``normalize()``
"Every construction path validates; there is no other"        couplings only, never ranges
"Polarity, not the call site, decides rounding"               the call site decided;
                                                              ``Config.polarity`` had zero
                                                              callers and flipping a registry
                                                              polarity broke no test
===========================================================  ===============================

The generalizable check: **for every documented guarantee, write the test that breaks it.**
Not the test that confirms the happy path — the one that performs the violation the
guarantee forbids and asserts it fails. Three of the four above had a passing test
immediately adjacent to the hole.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from tradipy.gates import (
    _rounded,
    apply_stop_floor_and_ceiling,
    min_separation,
    position_size,
    spread_caps,
)
from tradipy.params import HARD_CAPS, MODE_PRESETS, PARAMS, Config, CouplingError
from tradipy.rounding import TICK_SIZE, Polarity, ceil_to_tick, floor_to_tick

D = Decimal
CFG = Config.default(mode="experienced")
GATES_SRC = Path(__file__).resolve().parents[1] / "src" / "tradipy" / "gates.py"

#: PRD §2.0's mode-preset table, transcribed here so the test compares against the document
#: rather than against `MODE_PRESETS`, which is the thing under test.
BEGINNER_PRESET = {
    "max_risk_per_trade_pct": "0.005",
    "daily_loss_pct": "0.02",
    "max_open_positions": "1",
    "max_consecutive_losses": "2",
}
EXPERIENCED_PRESET = {
    "max_risk_per_trade_pct": "0.01",
    "daily_loss_pct": "0.03",
    "max_open_positions": "3",
    "max_consecutive_losses": "3",
}


def _with_flipped_polarity(base: Config, param_name: str) -> Config:
    """A config identical to ``base`` except that ``param_name`` declares the opposite polarity.

    Used to prove the gates *read* the declaration rather than agreeing with it by
    coincidence. ``PARAMS`` is read-only, so the flip goes through the accessor — which is
    also the only thing the gates consult.
    """
    flipped = Polarity.MINIMUM if base.polarity(param_name) is Polarity.MAXIMUM else Polarity.MAXIMUM

    class Flipped(Config):
        def polarity(self, name: str) -> Polarity:
            return flipped if name == param_name else super().polarity(name)

    return Flipped(base.values, mode=base.mode)


# ---------------------------------------------------------------------------
# F1 — the registry mappings are read-only, and a live Config cannot be reached
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_registry_mappings_are_read_only() -> None:
    """``PARAMS``, ``MODE_PRESETS``, ``HARD_CAPS`` and every inner preset dict."""
    targets = [
        ("PARAMS", PARAMS),
        ("MODE_PRESETS", MODE_PRESETS),
        ("HARD_CAPS", HARD_CAPS),
        *((f"MODE_PRESETS[{m!r}]", p) for m, p in MODE_PRESETS.items()),
    ]
    for label, mapping in targets:
        with pytest.raises(TypeError):
            mapping["injected"] = D("1")  # type: ignore[index]
        assert "injected" not in mapping, f"{label} accepted a write"


@pytest.mark.spec
def test_mode_preset_mutation_cannot_reach_a_live_config() -> None:
    """The F1 reproduction, kept as a test so it stays impossible.

    ``Config.__getitem__`` used to fall through to ``MODE_PRESETS[self.mode]`` on every
    lookup rather than resolving the preset at construction. That made the preset a live
    dependency of an object advertising itself as frozen and validated::

        cfg = Config.default()                    # 1% risk, 2,500 shares
        MODE_PRESETS["experienced"]["max_risk_per_trade_pct"] = Decimal("0.50")
        cfg["max_risk_per_trade_pct"]             # 0.50 — same object, no validator ran

    Fifty percent of equity on one trade, past a cap PRD §7 calls non-bypassable. Two
    existing tests guarded ``Config.values`` against exactly this and neither covered the
    presets, which is what made it invisible.
    """
    cfg = Config.default(mode="experienced")
    before = cfg["max_risk_per_trade_pct"]

    with pytest.raises(TypeError):
        MODE_PRESETS["experienced"]["max_risk_per_trade_pct"] = D("0.50")  # type: ignore[index]

    assert cfg["max_risk_per_trade_pct"] == before
    assert cfg["max_risk_per_trade_pct"] <= HARD_CAPS["max_risk_per_trade_pct"]
    # And the value is resolved into `values`, not read through the preset on each lookup.
    assert "max_risk_per_trade_pct" in cfg.values


# ---------------------------------------------------------------------------
# F4 — the registry decides rounding direction, not the call site
# ---------------------------------------------------------------------------
@pytest.mark.polarity
def test_gates_do_not_import_polarity() -> None:
    """``gates.py`` must have no way to name a ``Polarity`` member.

    This is the structural half of the fix. A test asserting that the *output* is correct
    passes under either design, because the literal and the registry agree today — that is
    precisely why the divergence went unnoticed. Removing the import makes the second source
    of truth unreachable rather than merely unused.
    """
    tree = ast.parse(GATES_SRC.read_text(encoding="utf-8"))
    imported = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "Polarity" not in imported, (
        "gates.py imports Polarity, so a call site can name a direction again. Rounding "
        "direction must come from Config.polarity() (PRD §20.13)."
    )


@pytest.mark.polarity
def test_signal_spread_cap_follows_the_registry_polarity() -> None:
    """Flip ``max_spread_r``'s declaration and the §3.1.3 signal cap rounds the other way.

    This is the v1.3.1 defect made reachable on demand: under MAXIMUM the cap on the §3.2
    Bull Flag's R floors to $0.01; under MINIMUM it ceils to $0.02, admitting a spread the
    unrounded threshold rejects. If this test ever stops distinguishing the two, the gates
    have gone back to naming a direction at the call site.
    """
    r = D("0.12")  # §3.2 Bull Flag
    price = D("5.16")
    raw = CFG["max_spread_r"] * r  # 0.018

    correct = spread_caps(price, r, CFG).signal
    flipped = spread_caps(price, r, _with_flipped_polarity(CFG, "max_spread_r")).signal

    assert correct == max(TICK_SIZE, floor_to_tick(raw)) and correct == TICK_SIZE
    assert flipped == ceil_to_tick(raw) == 2 * TICK_SIZE
    assert flipped > correct, "the flipped declaration must admit a wider spread"


@pytest.mark.polarity
def test_separation_floor_follows_the_registry_polarity() -> None:
    """Same proof on a MINIMUM: flipping ``min_sep_r`` makes the floor round down."""
    r, spread = D("0.15"), D("0.01")
    raw = max(CFG["min_sep_r"] * r, CFG["sep_cost_multiple"] * (spread + D("0.015")))

    correct = min_separation(r, spread, CFG)
    assert correct == ceil_to_tick(raw)

    # Flipping one of the three governing parameters leaves the threshold unclassifiable,
    # which must raise rather than silently pick one.
    with pytest.raises(ValueError, match="conflicting polarities"):
        min_separation(r, spread, _with_flipped_polarity(CFG, "min_sep_r"))


@pytest.mark.polarity
def test_rounded_requires_exactly_one_classification() -> None:
    """PRD §20.13: a threshold built from several parameters must have one direction."""
    assert _rounded(CFG, D("0.018"), "max_spread_abs", "max_spread_pct") == D("0.01")
    with pytest.raises(ValueError, match="conflicting polarities"):
        _rounded(CFG, D("0.018"), "max_spread_abs", "min_sep_r")
    with pytest.raises(ValueError, match="no declared polarity"):
        _rounded(CFG, D("0.018"), "start_of_day_equity")


# ---------------------------------------------------------------------------
# F5 / D28 — mode
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_default_mode_is_the_one_the_prd_declares() -> None:
    """PRD §2.0 row: ``mode`` defaults to ``beginner``.

    The code defaulted to ``experienced`` through v0.0.1, which doubled risk-per-trade,
    raised the daily loss limit from 2% to 3% and the position cap from 1 to 3, against a
    document that says otherwise. Nothing detected it because every test passed the mode
    explicitly.
    """
    assert Config.default().mode == "beginner"
    assert Config({n: p.default for n, p in PARAMS.items()}).mode == "beginner"


@pytest.mark.spec
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("beginner", BEGINNER_PRESET),
        ("experienced", EXPERIENCED_PRESET),
    ],
)
def test_mode_presets_match_prd_2_0(mode: str, expected: dict[str, str]) -> None:
    cfg = Config.default(mode=mode)  # type: ignore[arg-type]
    for name, value in expected.items():
        assert cfg[name] == D(value), f"{mode}.{name}"


@pytest.mark.spec
def test_beginner_mode_halves_the_position_size() -> None:
    """The consequence of the default, stated in shares rather than in percent.

    §3.2's Bull Flag is 2,500 shares in the PRD's tables, which are computed at 1% x $30,000.
    At the declared ``beginner`` default it is 1,250. That difference is why the mode default
    was a spec question rather than a typo.
    """
    entry, stop = D("5.16"), D("5.04")
    beginner = position_size(entry, stop, Config.default(mode="beginner"))
    experienced = position_size(entry, stop, Config.default(mode="experienced"))
    assert experienced == 2500
    assert beginner * 2 == experienced


@pytest.mark.spec
def test_an_unknown_mode_is_rejected_before_it_reaches_the_validator() -> None:
    """``Literal`` is a static hint with no runtime effect.

    Without this check the failure was a bare ``KeyError: 'typo'`` raised from inside
    ``validate_couplings`` — the exact shape the completeness guard was added to prevent.
    """
    with pytest.raises(ValueError, match="mode must be one of"):
        Config.default(mode="Beginner")  # type: ignore[arg-type]
    vals = {n: p.default for n, p in PARAMS.items()}
    with pytest.raises(ValueError, match="mode must be one of"):
        Config(vals, mode="typo")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# D27 — the risk settings are configurable, and the caps still hold
# ---------------------------------------------------------------------------
@pytest.mark.spec
@pytest.mark.parametrize(
    ("name", "lo", "hi"),
    [
        ("max_risk_per_trade_pct", "0.0025", "0.02"),
        ("daily_loss_pct", "0.01", "0.05"),
        ("max_open_positions", "1", "3"),
        ("max_consecutive_losses", "2", "5"),
    ],
)
def test_risk_settings_are_configurable_across_their_prd_range(name: str, lo: str, hi: str) -> None:
    """PRD §2's "User-Configurable" column, made true.

    Through v0.0.1 these lived only in ``MODE_PRESETS`` with no registry entry, so §2's
    stated ranges (0.25%-2%, 1%-5%, 2-5) existed nowhere in code and none of the three was
    reachable through any configuration path at all.
    """
    assert PARAMS[name].lo == D(lo) and PARAMS[name].hi == D(hi)
    for value in (lo, hi):
        assert CFG.with_overrides(**{name: value})[name] == D(value)


@pytest.mark.spec
@pytest.mark.parametrize("name", sorted(HARD_CAPS))
def test_risk_settings_cannot_be_pushed_past_the_non_bypassable_caps(name: str) -> None:
    """PRD §7: above the cap must fail, at the cap must pass."""
    cap = HARD_CAPS[name]
    assert CFG.with_overrides(**{name: str(cap)})[name] == cap
    with pytest.raises(ValueError):  # ValueError covers CouplingError
        CFG.with_overrides(**{name: str(cap + D("0.01"))})


@pytest.mark.spec
def test_hard_cap_check_binds_when_a_registry_ceiling_is_raised() -> None:
    """The §7 check is redundant only while the two ceilings agree — and it knows it.

    ``validate_couplings`` compares the *effective* value against ``HARD_CAPS``, while
    per-parameter validation compares it against ``Param.hi``. They are the same number
    today, so the coupling check cannot currently fire. Bypassing the range check the way a
    widened ceiling would proves the second guard is real rather than decorative.
    """
    over_cap = dict(CFG.values)
    over_cap["max_risk_per_trade_pct"] = HARD_CAPS["max_risk_per_trade_pct"] + D("0.01")

    class NoRangeCheck(Config):
        """Stands in for a future registry whose ceiling was raised above the §7 cap."""

        def __post_init__(self) -> None:
            from tradipy.params import validate_couplings

            object.__setattr__(self, "values", dict(self.values))
            validate_couplings(self)

    with pytest.raises(CouplingError, match="non-bypassable cap"):
        NoRangeCheck(over_cap, mode="experienced")


@pytest.mark.spec
def test_composite_score_weights_must_sum_to_one() -> None:
    """PRD §20.10 promises ``score in [0, 1]``, which is false unless the weights are convex.

    A cross-parameter property, so it lives in ``validate_couplings`` rather than in
    ``score.py`` — the score module cannot check a constraint on parameters it only reads.
    """
    weights = [n for n in PARAMS if n.startswith("score_weight_")]
    assert sum((CFG[n] for n in weights), start=D(0)) == D(1)
    with pytest.raises(CouplingError, match="weights sum to"):
        CFG.with_overrides(score_weight_rvol="0.5")


# ---------------------------------------------------------------------------
# §20.13 — the max-stop ceiling is now an invariant, not a convention
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_position_size_refuses_a_stop_the_ceiling_rejects() -> None:
    """``position_size`` never consulted ``max_stop_pct``, so honouring it was a convention.

    ``gates.py`` recorded this as a Phase 2 gap: any path that derived a stop without going
    through ``apply_stop_floor_and_ceiling`` could size a trade §20.13 requires be skipped.
    Returning the verdict from ``vwap_reclaim_stop`` fixed the information loss but not the
    invariant. It raises now, so the ceiling cannot be routed around.
    """
    entry = D("1.50")  # inside the documented $1.00-$1.99 dead band
    stop, verdict = apply_stop_floor_and_ceiling(entry, entry - D("0.05"), CFG)
    assert verdict is not None, "precondition: this entry is unreachable per the stop bounds"

    with pytest.raises(ValueError, match="exceeds max_stop_pct"):
        position_size(entry, stop, CFG)

    # A stop exactly at the ceiling is still sized, so the refusal is at the right boundary.
    ok_entry = D("10.00")
    at_limit = ok_entry - CFG["max_stop_pct"] * ok_entry
    assert position_size(ok_entry, at_limit, CFG) > 0


# ---------------------------------------------------------------------------
# Lookup errors name the registry rather than leaking a bare KeyError
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_unknown_parameter_lookups_say_where_to_look() -> None:
    """Both read and write paths. A bare ``KeyError: 'typo'`` tells the caller nothing."""
    with pytest.raises(KeyError, match="not a registered parameter"):
        CFG["max_spread_R"]
    with pytest.raises(KeyError, match="not a registered parameter"):
        CFG.with_overrides(max_spread_R="0.15")


@pytest.mark.spec
def test_partial_config_names_every_missing_parameter() -> None:
    """The message must be actionable: 46 missing names beats "invalid config"."""
    with pytest.raises(ValueError, match="missing") as exc:
        Config({"min_stop_distance": D("0.10")})
    assert "room_gate_multiple" in str(exc.value)
