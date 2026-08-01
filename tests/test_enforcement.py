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
import importlib
import itertools
from dataclasses import fields, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.spike2a import provenance, q1_vendors, q2_float, q3_latency, q4_spreads
from scripts.spike2a.feeds import QuoteSample
from tradipy import monitor as monitor_module
from tradipy import risk as risk_module
from tradipy.bars import Bar
from tradipy.daily import (
    BRIDGE_EXCEPTIONS,
    CLOCK_COLUMNS,
    DAILY_STATE_COLUMNS,
    UNPERSISTED_FIELDS,
    ClosedTrade,
    ConfirmationRequiredError,
    DailyState,
    SessionNotOpenError,
    SessionPhase,
    bridge_fields,
    clear_lock,
    from_row,
    mark_to_market,
    open_session,
    record_close,
    record_multi_day_peak,
    record_snapshot,
    risk_state,
    to_row,
)
from tradipy.daily import lock as daily_lock
from tradipy.gates import (
    Ladder,
    apply_stop_floor_and_ceiling,
    min_separation,
    position_size,
    scan_spread_cap,
    spread_caps,
)
from tradipy.monitor import (
    _ROW_LABELS,
    ACTION_FOR,
    RULES_AT,
    EnforcementPoint,
    HaltAction,
    flatten_all,
    unrepresentable,
    unrepresentable_flatten_states,
)
from tradipy.monitor import apply as monitor_apply
from tradipy.monitor import evaluate as monitor_evaluate
from tradipy.orders import (
    LegPurpose,
    OrderLeg,
    OrderSide,
    OrderType,
    bracket,
    idempotency_key,
)
from tradipy.params import HARD_CAPS, MODE_PRESETS, PARAMS, Config, CouplingError
from tradipy.poc import setup_examples
from tradipy.positions import (
    OPEN_STATES,
    TRANSITIONS,
    IllegalTransitionError,
    LegQuantities,
    PositionState,
    leg_quantities,
    scale_in_permitted,
    transition,
)
from tradipy.rejects import ExitReason, Reject, RiskBlock, SoftFlag
from tradipy.risk import (
    EVALUATED_RULES,
    UNREACHABLE_BLOCKS,
    OpenPosition,
    OrderIntent,
    RiskState,
    RuleOutcome,
    approve,
    max_dollar_risk,
    multi_day_drawdown_breached,
    session_drawdown_breached,
    total_open_risk,
)
from tradipy.rounding import TICK_SIZE, Polarity, ceil_to_tick, floor_to_tick
from tradipy.scanner import (
    HARD_FILTERS,
    SOFT_FILTERS,
    _rank_key,
    evaluate_candidate,
    scan,
)
from tradipy.score import Catalyst
from tradipy.session import Session, SessionBar, bar_sequence
from tradipy.setups import (
    EVALUATORS,
    Criterion,
    SetupOutcome,
    SetupSignal,
    SetupType,
    _gate_criteria,
    arbitrate,
    evaluate_all,
    evaluate_bull_flag,
    nearest_resistance,
)

D = Decimal
CFG = Config.default(mode="experienced")
SRC = Path(__file__).resolve().parents[1] / "src" / "tradipy"

#: Every module that rounds anything to a tick. Each must read the direction from the
#: registry rather than name a ``Polarity`` member, and the check is that the *import* is
#: absent — see :func:`test_a_rounding_module_cannot_name_a_polarity_member`.
#:
#: This listed only ``round_for``'s callers when Phase 3 added the second one, which named the
#: guard after a property it did not check: ``quotes.py`` rounds an estimated spread with a
#: bare ``ceil_to_tick`` and was outside it. That is the v1.3.1 shape — a rule stated more
#: broadly than the thing it ranges over — reproduced in the test written to prevent it.
#: :func:`test_every_module_that_rounds_is_in_the_polarity_check` now derives the list from
#: every rounding call, not from one of them.
ROUNDING_FUNCTIONS = ("round_for", "round_threshold", "ceil_to_tick", "floor_to_tick")

#: ``params.py`` resolves the direction and ``rounding.py`` defines it; both must name
#: ``Polarity``, so neither can be held to the import check.
POLARITY_DEFINING = ("params.py", "rounding.py")

#: ``setups.py`` joined at Phase 4: it floors the §3.3 VWAP stop candidate to a tick. Note that
#: ``session.py`` deliberately did **not** — VWAP, HOD and EMA are inputs to a level rather than
#: levels, and §20.13 puts rounding once, at level computation. The guard below derives the set
#: from the source, so that distinction is checked rather than asserted here.
#: ``positions.py`` and ``orders.py`` joined at Phase 5 — the first floors the §3.1.1 breakeven
#: stop, the second rounds the §6.1 entry limit and stop-limit. ``risk.py`` deliberately did
#: **not**: a risk budget is ``equity x pct`` and open risk is ``shares x (mark - stop)``, and
#: neither is a price level compared against a tick, which is the condition ``round_for``'s own
#: docstring states for rounding at all.
ROUNDING_CONSUMERS = (
    "gates.py",
    "orders.py",
    "positions.py",
    "quotes.py",
    "scanner.py",
    "setups.py",
)

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
    flipped = (
        Polarity.MINIMUM if base.polarity(param_name) is Polarity.MAXIMUM else Polarity.MAXIMUM
    )

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
@pytest.mark.parametrize("filename", ROUNDING_CONSUMERS)
def test_a_rounding_module_cannot_name_a_polarity_member(filename: str) -> None:
    """No module that rounds a threshold may have a way to name a ``Polarity`` member.

    This is the structural half of the fix. A test asserting that the *output* is correct
    passes under either design, because the literal and the registry agree today — that is
    precisely why the divergence went unnoticed. Removing the import makes the second source
    of truth unreachable rather than merely unused.

    Parametrized over :data:`ROUNDING_CONSUMERS` rather than written for ``gates.py`` alone,
    because Phase 3 added a second consumer and a guarantee that names one file protects one
    file. ``scanner.py`` rounds §4.2's price range and LULD distance; ``quotes.py`` rounds
    §20.14's estimated spread. :func:`test_every_module_that_rounds_is_in_the_polarity_check`
    is what stops a fourth being added outside this list.
    """
    tree = ast.parse((SRC / filename).read_text(encoding="utf-8"))
    imported = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "Polarity" not in imported, (
        f"{filename} imports Polarity, so a call site can name a direction again. Rounding "
        "direction must come from Config.polarity() (PRD §20.13)."
    )


@pytest.mark.polarity
def test_every_module_that_rounds_is_in_the_polarity_check() -> None:
    """Guard on the guard: the list above must name every module that rounds to a tick.

    A hand-maintained list of files to check is exactly the mechanism that goes stale
    silently — the check keeps passing on the files it knows about while a new one rounds
    unobserved. Derived from the source instead, and from **every** rounding function rather
    than only ``round_for``: rounding with a bare ``ceil_to_tick`` is still rounding, and a
    module doing that while naming a ``Polarity`` member is the divergence the whole F4 block
    exists to make unreachable.

    Detected by AST rather than substring, so a rounding function named in a docstring or a
    comment does not enlist a module that never calls one.
    """
    rounds: set[str] = set()
    for path in SRC.glob("*.py"):
        if path.name in POLARITY_DEFINING:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called = {
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute)
        }
        if called & set(ROUNDING_FUNCTIONS):
            rounds.add(path.name)

    assert rounds == set(ROUNDING_CONSUMERS), (
        f"ROUNDING_CONSUMERS is stale: modules that round are {sorted(rounds)}, "
        f"listed are {sorted(ROUNDING_CONSUMERS)}"
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
    """PRD §20.13: a threshold built from several parameters must have one direction.

    ``round_for`` is a method on ``Config`` rather than a helper in ``gates`` as of Phase 3,
    because the scanner needed the same resolution and the alternatives were a private
    cross-module import or a second place that names a direction.
    """
    assert CFG.round_for(D("0.018"), "max_spread_abs", "max_spread_pct") == D("0.01")
    with pytest.raises(ValueError, match="conflicting polarities"):
        CFG.round_for(D("0.018"), "max_spread_abs", "min_sep_r")
    with pytest.raises(ValueError, match="no declared polarity"):
        CFG.round_for(D("0.018"), "start_of_day_equity")
    # "No governing parameter" is a *third* failure and says so. It reported "conflicting
    # polarities []" until this was written — a message naming a conflict between nothing and
    # nothing, which is worse than no message because it sends the reader looking for two
    # parameters that do not exist.
    with pytest.raises(ValueError, match="no governing parameter"):
        CFG.round_for(D("0.018"))


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


# ---------------------------------------------------------------------------
# D30 — every dataset is simulated, and nothing can reach a market to change that
# ---------------------------------------------------------------------------
#
# **Read the import lint as a denylist, not a proof.** It enumerates twenty roots across
# `src/`, `scripts/` and `tests/`; a new vendor's client, or `subprocess` calling `curl`,
# passes it clean. The provenance gate below is the backstop, because it constrains what may
# be *read* rather than what may be imported. A green lint is not the guarantee.
#
# The guarantee: *"this project reads simulated data only."* Round 7 shipped the same sentence
# in prose — PHASE-2A-SPIKE §3.2, "live trading, of any size, for any reason" — beside two
# committed scripts that connected to IBKR and pulled real ticks, because §3.2 forbade *trading*
# and they only *read*. A guarantee whose wording does not cover the code beside it is the fifth
# defect class with better prose. These are the attacks.


def _broker_or_network_imports(path: Path) -> list[str]:
    """Every import in ``path`` whose root module can reach a market or a socket.

    AST, not text search, for the reason ``test_parameter_registry`` parses rather than greps: a
    module named in a docstring is a string, an ``import`` is an import, and a lint that cannot
    tell them apart fires on the sentence explaining why it exists. This file is itself the
    proof — it names every forbidden module below and imports none of them.
    """
    found: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        # `continue` rather than a default empty list, so `node` stays narrowed to the two
        # statement types past this point — `ast.AST` has no `lineno` and the report needs one.
        roots: list[str]
        if isinstance(node, ast.Import):
            roots = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots = [node.module.split(".")[0]]
        else:
            continue
        found += [
            f"{path.name}:{node.lineno} imports {root}"
            for root in roots
            if root in FORBIDDEN_IMPORT_ROOTS
        ]
    return found


#: Broker SDKs, market-data vendors, and the network stack. The vendors are listed even though
#: none was ever a dependency: D30's cost is that reaching for one is easy and reviewing for one
#: is not, and PRD §5.1 names Polygon and Benzinga as the intended sources, so they are exactly
#: what a future contributor would reach for first.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        # Brokers
        "ib_insync",
        "ibapi",
        "ib_async",
        # Market-data vendors (PRD §5.1)
        "alpaca",
        "polygon",
        "benzinga",
        "yfinance",
        "finnhub",
        "alpha_vantage",
        "tradier",
        # The network itself — the layer under all of the above
        "socket",
        "urllib",
        "http",
        "requests",
        "httpx",
        "aiohttp",
        "websocket",
        "websockets",
        "ftplib",
        "xmlrpc",
    }
)

#: Everything Python in the repository. Unlike the registry lint, ``tests/`` **is** in scope:
#: that lint exempts fixtures because a fixture must state a literal (convention 4), and no
#: analogous reason exists to import a broker from a test.
LINTED_TREES = ("src", "scripts", "tests")


def _linted_files() -> list[Path]:
    repo = Path(__file__).resolve().parents[1]
    return sorted(p for tree in LINTED_TREES for p in (repo / tree).rglob("*.py"))


@pytest.mark.spec
def test_no_broker_or_network_import_reaches_the_repository() -> None:
    """D30's import half, as the thing that fails when it stops being true.

    Not D30's headline claim — see the section comment. This is a denylist, so it proves the
    twenty enumerated roots are absent and nothing more.
    """
    files = _linted_files()
    assert len(files) > 20, "the lint found almost nothing — check LINTED_TREES, not the result"

    offenders = [hit for path in files for hit in _broker_or_network_imports(path)]
    assert not offenders, (
        "these can reach a market or a socket, and D30 permits neither:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.spec
def test_the_broker_import_lint_catches_a_planted_import(tmp_path: Path) -> None:
    """The guard on the guard.

    A lint that scans a clean tree passes whether or not it works. Each form below is one a
    contributor would plausibly write, and the last two are the ones a text search for
    ``import ib_insync`` at column zero would miss.
    """
    planted = {
        "module_scope.py": "from ib_insync import IB, Stock\n",
        "plain_import.py": "import ib_insync\n",
        "aliased.py": "import ib_insync as ib\n",
        "submodule.py": "import urllib.request\n",
        "inside_a_function.py": "def fetch():\n    import requests\n    return requests\n",
        "lazily_in_a_constructor.py": (
            "class Feed:\n"
            "    def __init__(self):\n"
            "        try:\n"
            "            from ib_insync import IB\n"
            "        except ImportError:\n"
            "            raise RuntimeError('spike-only prerequisite')\n"
        ),
    }
    for name, body in planted.items():
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        assert _broker_or_network_imports(path), f"the lint is blind to {name}: {body!r}"

    # And it does not fire on a mention. `feeds.py` explains at length why a broker feed was
    # removed; a lint that flags the explanation makes the explanation unwritable.
    innocent = tmp_path / "docstring_only.py"
    innocent.write_text(
        '"""Removed at D30: this used to import ib_insync and call requests.get."""\n'
        'MENTIONED = "ib_insync"\n',
        encoding="utf-8",
    )
    assert not _broker_or_network_imports(innocent)


@pytest.mark.spec
def test_widening_the_permitted_origins_cannot_pass_unnoticed() -> None:
    """The tripwire on the one line that encodes the current rung of the ladder.

    ``PERMITTED_ORIGINS`` is what a contributor edits to make a refusal go away, and editing it
    is exactly the decision D30 reserves. This test fails when that line changes — which is the
    point, not a nuisance: changing it *and* this assertion *and* the PLAN decision together is
    the recorded advance, and changing the line alone is not available.
    """
    assert frozenset({provenance.DataOrigin.SIMULATED}) == provenance.PERMITTED_ORIGINS, (
        "the permitted origins changed. If the ladder is being advanced, that is a PLAN "
        "decision superseding D30 — and for LIVE, the PRD §18.8 evidence bar as well."
    )


def _declare(directory: Path, origin: provenance.DataOrigin, *covered: Path) -> None:
    (directory / provenance.PROVENANCE_FILENAME).write_text(
        provenance.render(
            origin=origin,
            generator="tests/test_enforcement.py",
            seed=None,
            covered=covered,
            detail="fixture",
        ),
        encoding="utf-8",
    )


@pytest.fixture
def declared(tmp_path: Path) -> Path:
    """A directory holding one file, correctly declared ``SIMULATED``."""
    data = tmp_path / "kept.csv"
    data.write_text("symbol,bid,ask\nAXTI,10.00,10.02\n", encoding="utf-8")
    _declare(tmp_path, provenance.DataOrigin.SIMULATED, data)
    return data


@pytest.mark.spec
def test_the_gate_accepts_correctly_declared_simulated_data(declared: Path) -> None:
    """The precondition for every refusal below. Without it they could pass vacuously."""
    prov = provenance.require(declared)
    assert prov.origin is provenance.DataOrigin.SIMULATED
    assert prov.is_simulated and not prov.answers_prereg


@pytest.mark.spec
def test_undeclared_data_is_refused_rather_than_assumed_simulated(tmp_path: Path) -> None:
    """The default matters more than the check.

    Treating a missing marker as ``SIMULATED`` would be the friendly reading and would restore
    the original hole: the file that most needs a declaration is the one somebody added without
    writing one.
    """
    orphan = tmp_path / "orphan.csv"
    orphan.write_text("symbol\nAXTI\n", encoding="utf-8")
    with pytest.raises(provenance.UndeclaredProvenanceError, match=r"no PROVENANCE\.txt"):
        provenance.require(orphan)


@pytest.mark.spec
def test_an_undeclared_file_does_not_inherit_its_neighbours_declaration(declared: Path) -> None:
    """The concrete history: ``quotes_real.csv``, written by the deleted collector into the same
    directory as a ``PROVENANCE.txt`` reading "SYNTHETIC", carrying no marker of its own."""
    intruder = declared.parent / "quotes_real.csv"
    intruder.write_text("symbol,bid,ask\nMSFT,410.00,410.02\n", encoding="utf-8")
    with pytest.raises(provenance.UndeclaredProvenanceError, match="not covered"):
        provenance.require(intruder)


@pytest.mark.spec
def test_a_file_edited_after_its_declaration_is_refused(declared: Path) -> None:
    """A declaration describes bytes, not a filename."""
    declared.write_text("symbol,bid,ask\nAXTI,10.00,10.50\n", encoding="utf-8")
    with pytest.raises(provenance.UndeclaredProvenanceError, match="does not match the digest"):
        provenance.require(declared)


@pytest.mark.spec
@pytest.mark.parametrize("origin", [provenance.DataOrigin.PAPER, provenance.DataOrigin.LIVE])
def test_real_data_is_refused_however_honestly_it_declares_itself(
    declared: Path, origin: provenance.DataOrigin
) -> None:
    """A well-formed declaration naming a forbidden origin is still a refusal.

    This is the case the removal of the collectors does not cover: a contributor who writes a
    new one, declares its output truthfully, and expects the pipeline to run.
    """
    _declare(declared.parent, origin, declared)
    with pytest.raises(provenance.ForbiddenOriginError, match="not permitted"):
        provenance.require(declared)


@pytest.mark.spec
def test_a_malformed_declaration_is_refused_like_a_missing_one(declared: Path) -> None:
    """The other half of "undeclared is not simulated": a marker with no readable origin."""
    marker = declared.parent / provenance.PROVENANCE_FILENAME
    marker.write_text("origin  ATLANTIS\ncovers\n", encoding="utf-8")
    with pytest.raises(provenance.UndeclaredProvenanceError, match="expected one of"):
        provenance.require(declared)


@pytest.mark.spec
def test_a_declaration_survives_the_round_trip_for_a_long_filename(tmp_path: Path) -> None:
    """``render`` → ``read`` must agree, including where the name overruns its column.

    The guard on the guard, per the skill's step 5. Padded to a fixed width with no separator,
    an 18-character name ran into its digest, the entry parsed as one token and was dropped —
    so a file could be declared and then refused as undeclared. ``q3_measurements.csv``, at 19
    characters, is the name the deleted Q3 collector wrote, which is how close this came to
    mattering.
    """
    long_name = tmp_path / "q3_measurements.csv"
    long_name.write_text("kind,seconds\ndata_to_signal,0.4\n", encoding="utf-8")
    short_name = tmp_path / "vix.csv"
    short_name.write_text("date,close\n2026-07-07,23.1\n", encoding="utf-8")

    _declare(tmp_path, provenance.DataOrigin.SIMULATED, long_name, short_name)
    prov = provenance.read(tmp_path)
    assert set(prov.files) == {"q3_measurements.csv", "vix.csv"}
    provenance.require(long_name, short_name)


def _rejected_rows(n: int) -> list[q4_spreads.Classification]:
    """``n`` signal bars, every one rejected — a 100% rate, which §7 calls RECALIBRATE.

    Built rather than sampled because the disposition block is what is under test and it only
    appears at that outcome. An empty ``rows`` list reaches ``CALIBRATED`` via "no gated bars",
    where the block is unreachable on *either* branch — which is how the first version of the
    test below asserted the absence of a string that was never going to be present.
    """
    quote = QuoteSample(
        symbol="AXTI",
        captured_at=datetime(2026, 7, 7, 13, 31, tzinfo=UTC),
        bid=D("10.00"),
        ask=D("10.40"),
        bid_size=100,
        ask_size=100,
    )
    bar = q4_spreads.SignalBar(
        symbol="AXTI",
        session="2026-07-07",
        setup="vwap_reclaim",
        price=D("10.00"),
        r=D("0.30"),
        quote=quote,
    )
    return [
        q4_spreads.Classification(
            bar=bar,
            spread=D("0.40"),
            signal_cap=D("0.04"),
            scan_cap=D("0.10"),
            rejected=True,
            reason="SPREAD_TOO_WIDE",
        )
        for _ in range(n)
    ]


@pytest.mark.spec
def test_a_simulated_run_cannot_print_a_prereg_verdict_or_raise_a_disposition(
    declared: Path,
) -> None:
    """§7 binds to measured data, so simulated input must produce neither a §7 verdict nor a D7
    disposition — PLAN's rule that any value capable of triggering one must be reproducible from
    a provenance-marked input, applied at the only place that prints one.

    Paired with the test below deliberately. Alone, this asserts the absence of two strings,
    which would pass just as well if the strings had been deleted from the module.
    """
    simulated = provenance.require(declared)
    text = q4_spreads.report(_rejected_rows(10), [], simulated)

    assert "pipeline outcome (NOT a §7 verdict)" in text
    assert "§7 verdict:" not in text
    assert "raise as a spec decision" not in text, "a simulated run must not raise a disposition"
    assert "SIMULATED" in text, "the origin travels with the numbers"


@pytest.mark.spec
def test_a_measured_run_prints_both__so_the_test_above_is_not_vacuous() -> None:
    """The contrast case: on the same rows, both strings are reachable.

    ``Provenance`` is built directly instead of through :func:`provenance.require`, because
    ``require`` would — correctly — refuse a ``PAPER`` origin. What is under test here is the
    *report*, not the gate, and conflating the two would make this test unwritable without
    weakening the gate to write it.
    """
    measured = provenance.Provenance(
        origin=provenance.DataOrigin.PAPER,
        generator="a paper-stage collector that does not exist yet",
    )
    assert measured.answers_prereg

    text = q4_spreads.report(_rejected_rows(10), [], measured)
    assert "§7 verdict:" in text
    assert "NOT a §7 verdict" not in text
    assert "raise as a spec decision" in text, "RECALIBRATE must still raise D7 on real data"


@pytest.mark.spec
def test_q3_withholds_its_disposition_on_simulated_input(declared: Path) -> None:
    """Unmeasured is not a pass, and neither is invented.

    A p95 over fabricated intervals reports the generator's parameters. The measurements below
    would otherwise clear both §7 thresholds and print "Both p95s within §7's thresholds", which
    is the sentence a reader would quote.
    """
    simulated = provenance.require(declared)
    measurements = [
        q3_latency.Measurement(kind="data_to_signal", seconds=D("0.4")),
        q3_latency.Measurement(kind="signal_to_order", seconds=D("0.2")),
    ]

    text = q3_latency.report(measurements, simulated)
    assert "disposition WITHHELD" in text
    assert "within §7's thresholds" not in text

    measured = provenance.Provenance(
        origin=provenance.DataOrigin.PAPER, generator="a collector that does not exist yet"
    )
    assert "within §7's thresholds" in q3_latency.report(measurements, measured)


# The gate is only worth what its call sites are worth. `Config.polarity()` was documented as
# deciding rounding direction, was tested, and had zero callers — so these assert the wiring,
# not the mechanism.
def _runnable_inputs(directory: Path) -> tuple[Path, Path]:
    bars = directory / "signal_bars.csv"
    bars.write_text(
        "symbol,session,setup,price,r,signal_at\n"
        "AXTI,2026-07-07,bull_flag,10.00,0.30,2026-07-07T09:35:00+00:00\n",
        "utf-8",
    )
    quotes = directory / "quotes.csv"
    quotes.write_text(
        "symbol,captured_at,bid,ask,bid_size,ask_size\n"
        "AXTI,2026-07-07T09:35:00+00:00,10.00,10.02,100,100\n",
        "utf-8",
    )
    return bars, quotes


@pytest.mark.spec
def test_q4_main_refuses_undeclared_input_rather_than_measuring_it(tmp_path: Path) -> None:
    bars, quotes = _runnable_inputs(tmp_path)
    assert q4_spreads.main([str(bars), str(quotes)]) == 3

    _declare(tmp_path, provenance.DataOrigin.SIMULATED, bars, quotes)
    assert q4_spreads.main([str(bars), str(quotes)]) == 0


@pytest.mark.spec
def test_q3_main_refuses_undeclared_input_rather_than_measuring_it(tmp_path: Path) -> None:
    latency = tmp_path / "latency.csv"
    latency.write_text("kind,seconds\ndata_to_signal,0.4\n", encoding="utf-8")
    assert q3_latency.main([str(latency)]) == 3

    _declare(tmp_path, provenance.DataOrigin.SIMULATED, latency)
    assert q3_latency.main([str(latency)]) == 0


#: Enough of a VIX series for the §7 window rule to have two non-overlapping runs to choose.
_VIX_CSV = "date,close\n" + "".join(f"2026-01-{d:02d},{20 + d % 7}.1\n" for d in range(1, 26))
_PREOPEN_CSV = "session,symbol,price,gap_premarket_pct\n"


@pytest.mark.spec
@pytest.mark.parametrize(
    ("module", "files"),
    [
        ("windows", [("vix.csv", _VIX_CSV)]),
        ("universe", [("preopen.csv", _PREOPEN_CSV)]),
        ("q2_float", [("floats.csv", "symbol,provider,float_shares,as_of\n")]),
        (
            "q1_vendors",
            [
                (
                    "vendors.csv",
                    "provider,monthly_cost_usd,concurrent_symbols,refresh_seconds,"
                    "sample_coverage_pct,hard_filters_expressible\n",
                )
            ],
        ),
        ("sample", [("vix.csv", _VIX_CSV), ("preopen.csv", _PREOPEN_CSV)]),
    ],
)
def test_every_spike_entry_point_gates_its_input(
    tmp_path: Path, module: str, files: list[tuple[str, str]]
) -> None:
    """Not just the ones that print a §7 outcome.

    The first version of D30 gated `q4_spreads` and `q3_latency` and left the rest reading the
    same declared bytes ungated, while six documents said every measurement module called the
    gate. A gate with an unguarded side entrance is the guarantee, not the mechanism.

    `sample` is here because it arrived later, from a branch that did not know about D30 — which
    is the case this test is really for. It is also the only entry point that reads *two* files,
    and a composing entry point is where undeclared data most easily enters, each half looking
    like somebody else's responsibility.

    The declared case is asserted too. Without it a module that refused *everything* would pass
    — the same "confirms the happy path" mistake as asserting only the accept case, run
    backwards.
    """
    entry = importlib.import_module(f"scripts.spike2a.{module}")
    paths = []
    for name, body in files:
        path = tmp_path / name
        path.write_text(body, encoding="utf-8")
        paths.append(path)
    argv = [str(p) for p in paths]

    assert entry.main(argv) == 3, f"{module} read undeclared input"

    _declare(tmp_path, provenance.DataOrigin.SIMULATED, *paths)
    assert entry.main(argv) == 0, f"{module} refuses correctly declared input"


@pytest.mark.spec
def test_q2_withholds_its_disposition_on_simulated_input(declared: Path) -> None:
    """Q2's whole output is §7 threshold comparisons and a named A10 disposition.

    The first version of D30 wired the gate to the entry points and the withholding to two,
    leaving this module printing "A10 not tripped by this sample" over fabricated floats — the
    same defect as the §7 verdict, one module along.
    """
    simulated = provenance.require(declared)
    fresh = [
        q2_float.FloatReading(
            symbol="AXTI", provider="finviz", float_shares=D("5000000"), as_of=date(2026, 7, 25)
        )
    ]
    on = date(2026, 7, 29)

    assert "A10 disposition WITHHELD" in q2_float.report(fresh, on, simulated)

    # The contrast, so the assertion above is not the absence of an unreachable string. With one
    # provider the reachable measured outcome is PARTIAL, not "not tripped" — §7's disagreement
    # condition needs two sources, and `disagreement` returns None rather than zero for exactly
    # that reason. Asserting the "not tripped" wording here would have been asserting a string
    # this fixture cannot produce under either branch.
    measured = provenance.Provenance(
        origin=provenance.DataOrigin.PAPER, generator="a second provider that does not exist yet"
    )
    text = q2_float.report(fresh, on, measured)
    assert "A10 disposition WITHHELD" not in text
    assert "PARTIAL. The staleness half is within threshold" in text


@pytest.mark.spec
def test_q1_withholds_its_disposition_on_simulated_input(declared: Path) -> None:
    """Q1 is the one Q-module D30's withholding guarantee had no test for.

    A vendor trial clearing every §7 threshold would otherwise print "§7 verdict: at least one
    provider passes Q1" over a fabricated matrix — licensing a Phase 3 go-ahead (D29) from a
    random number generator. Q2 and Q3 each have this test beside their own report(); Q4 has the
    paired non-vacuous version above. Q1 had neither, and removing its ``prov.answers_prereg``
    branch entirely left all other tests passing.
    """
    simulated = provenance.require(declared)
    passing = [
        q1_vendors.VendorTrial(
            provider="polygon_screener",
            monthly_cost_usd=400,
            concurrent_symbols=500,
            refresh_seconds=45,
            sample_coverage_pct=97,
            hard_filters_expressible=True,
        )
    ]

    text = q1_vendors.report(passing, simulated)
    assert "pipeline outcome (NOT a §7 verdict)" in text
    assert "§7 verdict:" not in text

    # The contrast, so the assertion above is not the absence of an unreachable string.
    measured = provenance.Provenance(
        origin=provenance.DataOrigin.PAPER, generator="a vendor trial that does not exist yet"
    )
    measured_text = q1_vendors.report(passing, measured)
    assert "§7 verdict: at least one provider passes Q1" in measured_text
    assert "NOT a §7 verdict" not in measured_text


@pytest.mark.spec
def test_q1_does_not_claim_a_verdict_from_zero_vendor_trials() -> None:
    """An empty or wholly-unparsable ``vendors.csv`` must not print a §7 verdict.

    Before this guard, ``q1_vendors.report([], measured)`` fell straight into the "no provider
    passes Q1" branch and printed "Implication per §6: PRD §4 is rewritten before Phase 3
    (scanner) starts" — the spike's largest possible consequence, from zero trials. Q2 prints
    "UNANSWERED"; Q3 prints "no measurements — unanswered, not passed"; Q4 returns CALIBRATED
    with "no gated bars — nothing measured, so nothing is claimed". Q1 had no equivalent
    (review round 10, K3).
    """
    measured = provenance.Provenance(
        origin=provenance.DataOrigin.PAPER, generator="a vendor trial that does not exist yet"
    )
    text = q1_vendors.report([], measured)
    assert "§7 verdict" not in text
    assert "PRD §4 is rewritten" not in text
    assert "UNANSWERED — no vendor trials recorded, have 0" in text

    # The contrast, so the assertions above are not the absence of an unreachable string: a
    # non-empty measured list still gets a real verdict, on either side of the pass/fail line.
    passing = [
        q1_vendors.VendorTrial(
            provider="polygon_screener",
            monthly_cost_usd=400,
            concurrent_symbols=500,
            refresh_seconds=45,
            sample_coverage_pct=97,
            hard_filters_expressible=True,
        )
    ]
    assert "§7 verdict: at least one provider passes Q1" in q1_vendors.report(passing, measured)


# `declare` is the only writer besides the generator, so it is the only other place a false
# declaration can originate.
@pytest.mark.spec
def test_declaring_a_file_does_not_evict_the_ones_already_declared(tmp_path: Path) -> None:
    """The merge, and the header it must not overwrite.

    ``declare`` runs against a directory the generator wrote. Replacing the header would leave
    four generator-produced files described as "hand-authored", with the seed dropped — a marker
    that is false about data it did not produce, which is the defect the marker exists to
    prevent. (This happened: the first version of ``declare`` did exactly that.)
    """
    generated = tmp_path / "quotes.csv"
    generated.write_text("symbol,bid,ask\nAXTI,10.00,10.02\n", encoding="utf-8")
    (tmp_path / provenance.PROVENANCE_FILENAME).write_text(
        provenance.render(
            origin=provenance.DataOrigin.SIMULATED,
            generator="scripts/spike2a/synthetic_data_generator.py",
            seed=42,
            covered=[generated],
            detail="spike start       2026-07-29\nNot market data. Not vendor data.",
        ),
        encoding="utf-8",
    )

    by_hand = tmp_path / "latency.csv"
    by_hand.write_text("kind,seconds\ndata_to_signal,0.4\n", encoding="utf-8")
    provenance.declare(by_hand)

    after = provenance.read(tmp_path)
    assert set(after.files) == {"quotes.csv", "latency.csv"}, "the merge dropped an entry"
    assert after.generator == "scripts/spike2a/synthetic_data_generator.py"
    assert after.seed == 42, "the seed that produced quotes.csv was dropped"
    assert "Not market data" in after.detail, "the generator's own description was overwritten"
    provenance.require(generated, by_hand)


@pytest.mark.spec
def test_declaring_cannot_relabel_a_marker_that_does_not_parse(tmp_path: Path) -> None:
    """Only a *missing* marker is the fresh-start case.

    ``read`` raises the same exception type for absent and malformed, and ``declare`` used to
    catch it — so ``origin PAPERR``, one keystroke from a real declaration, was silently
    rewritten to ``SIMULATED``. That is the default this module refuses everywhere else.
    """
    data = tmp_path / "quotes.csv"
    data.write_text("symbol,bid,ask\nMSFT,410.00,410.02\n", encoding="utf-8")
    (tmp_path / provenance.PROVENANCE_FILENAME).write_text("origin  PAPERR\n", encoding="utf-8")

    with pytest.raises(provenance.UndeclaredProvenanceError, match="expected one of"):
        provenance.declare(data)


@pytest.mark.spec
def test_declaring_cannot_relabel_honestly_declared_real_data(tmp_path: Path) -> None:
    data = tmp_path / "quotes.csv"
    data.write_text("symbol,bid,ask\nMSFT,410.00,410.02\n", encoding="utf-8")
    _declare(tmp_path, provenance.DataOrigin.LIVE, data)

    with pytest.raises(provenance.ForbiddenOriginError, match="refusing to overwrite"):
        provenance.declare(data)


@pytest.mark.spec
def test_the_declare_cli_unblocks_input_the_generator_does_not_cover(tmp_path: Path) -> None:
    """Hand-authored files still need ``provenance declare`` when added beside generated ones.

    The generator now covers ``floats.csv`` and ``latency.csv``, but ``declare`` remains the path
    for any input added later — and a gate with no supported way past it is not a gate, it is an
    outage.
    """
    latency = tmp_path / "latency.csv"
    latency.write_text("kind,seconds\ndata_to_signal,0.4\n", encoding="utf-8")
    assert q3_latency.main([str(latency)]) == 3

    assert provenance._main([str(latency)]) == 0
    assert q3_latency.main([str(latency)]) == 0


# ---------------------------------------------------------------------------
# K5 / D24 / D32 — the §4.2 scanner's guarantees (Phase 3)
#
# Round 10's K5: a gate document sized Phase 3 at all fourteen §4.2 rows, and warned what
# that produces — "the soft filters that are off-by-default or flag-only, INST_OWN_HIGH
# among them, which D24 keeps deliberately inert, would be built as rejection paths."
# `tradipy.rejects` answers it structurally by splitting the namespace, so a soft code is a
# different type from a rejection. A type annotation is not a runtime guarantee, so the
# violation is performed here anyway: every soft input pushed to its worst value, and the
# assertion that nothing was rejected.
# ---------------------------------------------------------------------------
WORST_SOFT_INPUTS: dict[str, object] = {
    "premarket_volume": D("1"),
    "market_cap": D("900000000000"),
    "atr": D("0.01"),
    "avg_atr": D("9.99"),
    "catalyst": Catalyst.NONE,
    "sessions_since_halt": 0,
    "institutional_ownership_pct": D("1.00"),
    "short_interest_pct": D("1.00"),
}

#: One override per §4.2 hard row, chosen to trip that row and only that row.
TRIPS_HARD_FILTER: dict[Reject, dict[str, object]] = {
    Reject.GAP_TOO_SMALL: {"premarket_gap_pct": D("0"), "daily_gap_pct": D("0")},
    Reject.RVOL_TOO_LOW: {"rvol": D("1")},
    Reject.FLOAT_TOO_HIGH: {"float_shares": D("400000000")},
    Reject.PRICE_OUT_OF_RANGE: {"price": D("64.00")},
    Reject.ADV_TOO_LOW: {"adv_shares": D("1000")},
    Reject.NEAR_LULD: {"luld_upper": D("4.01")},
    Reject.SPREAD_TOO_WIDE: {"spread": D("1.00")},
}

#: The keys of the table above, in a stable order, hoisted out of the ``parametrize`` call.
#: Written inline, basedpyright flows ``parametrize``'s expected ``ParameterSet`` type back
#: into ``sorted()`` and infers the lambda's parameter as ``ParameterSet``, so ``c.value``
#: fails to typecheck against a signature that is correct at runtime. Binding it here breaks
#: that inference chain.
HARD_FILTER_CODES: list[Reject] = sorted(TRIPS_HARD_FILTER, key=lambda c: c.value)


@pytest.mark.spec
def test_the_three_code_namespaces_cannot_be_confused() -> None:
    """No value string is shared between ``Reject``, ``SoftFlag`` and ``ExitReason``.

    The types differ, so mixing them is a static error. This is the runtime half: a code added
    to two enums would type-check everywhere and mean two different things. ``ExitReason`` joined
    at Phase 4 — a rejection declines a trade never taken and an exit closes one that was, so
    ``BAILED_OUT`` reaching a pre-entry gate is as wrong as ``SPREAD_TOO_WIDE`` closing a
    position.
    """
    namespaces = [
        {m.value for m in Reject},
        {m.value for m in SoftFlag},
        {m.value for m in ExitReason},
    ]
    for a, b in itertools.combinations(namespaces, 2):
        assert a & b == set()
    assert all(isinstance(f.code, Reject) for f in HARD_FILTERS)
    assert all(isinstance(f.code, SoftFlag) for f in SOFT_FILTERS)
    assert not any(isinstance(f.code, Reject) for f in SOFT_FILTERS)
    # And every criterion a setup reports carries a Reject, never an exit reason.
    outcome = setup_examples()[0].evaluate(CFG)
    assert all(isinstance(c.code, Reject) for c in outcome.criteria)
    assert not any(isinstance(c.code, ExitReason) for c in outcome.criteria)


@pytest.mark.spec
def test_no_soft_flag_can_reach_the_rejection_path() -> None:
    """K5, performed: every soft row raised at once, and the candidate is still accepted."""
    from tests.test_scanner import candidate

    result = evaluate_candidate(candidate(**WORST_SOFT_INPUTS), CFG)
    assert result.reject is None and result.rejects == () and result.passed
    assert result.score is not None, "a flagged candidate is still ranked"

    raised = set(result.flags)
    assert raised == {f.code for f in SOFT_FILTERS} - {SoftFlag.INST_OWN_HIGH}, (
        f"expected every soft row but the D24-disabled one; got {sorted(f.value for f in raised)}"
    )
    # And the codes that did surface are not assignable to the rejection path at all.
    assert not any(isinstance(code, Reject) for code in result.flags)


@pytest.mark.spec
def test_institutional_ownership_cannot_fire_at_the_shipped_default() -> None:
    """D24 / A22: the row is registered, unvalidated, and inert.

    Attempted at the threshold, above it, and at 100% — the three values that would fire it
    if the enable flag were not consulted first. §4.2's own note is why: the premise is
    doubtful, no Appendix A source states the threshold, and Phase 2a has not confirmed the
    data even exists.
    """
    from tests.test_scanner import candidate

    threshold = CFG["min_institutional_ownership_pct"]
    assert CFG["institutional_ownership_enabled"] == D("0"), "D24: off by default"
    for ownership in (threshold, threshold + D("0.05"), D("1.00")):
        result = evaluate_candidate(candidate(institutional_ownership_pct=ownership), CFG)
        assert SoftFlag.INST_OWN_HIGH not in result.flags, f"fired at {ownership}"
        assert result.passed


@pytest.mark.spec
def test_institutional_ownership_fires_when_enabled__so_the_above_is_not_vacuous() -> None:
    """The other half: enabling the row makes it work, so "inert" is a decision not a bug.

    Without this, deleting the filter body entirely would leave the D24 test green — which
    is the fifth defect class reproduced inside the test written to prevent it.
    """
    from tests.test_scanner import candidate

    cfg = CFG.with_overrides(institutional_ownership_enabled=1)
    threshold = cfg["min_institutional_ownership_pct"]

    at = evaluate_candidate(candidate(institutional_ownership_pct=threshold), cfg)
    below = evaluate_candidate(candidate(institutional_ownership_pct=threshold - D("0.01")), cfg)
    assert SoftFlag.INST_OWN_HIGH in at.flags and at.passed, "enabled, at the threshold"
    assert SoftFlag.INST_OWN_HIGH not in below.flags
    assert at.passed and below.passed, "enabling a *soft* row still rejects nothing"


@pytest.mark.polarity
def test_luld_distance_follows_the_registry_polarity() -> None:
    """Flip ``min_luld_distance_pct`` and §4.2's Circuit Breakers gate admits a closer price.

    Chosen at a price where the two directions differ: ``0.10 x $4.25 = $0.425``, which
    ceils to $0.43 and floors to $0.42. Under the declared MINIMUM a band $0.42 away is too
    close; under the flip it is admitted. If this test ever stops distinguishing the two, the
    scanner has gone back to naming a direction.
    """
    from tests.test_scanner import candidate

    price = D("4.25")
    raw = CFG["min_luld_distance_pct"] * price
    assert ceil_to_tick(raw) == D("0.43") and floor_to_tick(raw) == D("0.42")

    near = candidate(price=price, luld_upper=price + D("0.42"), luld_lower=D("0.01"))
    flipped = _with_flipped_polarity(CFG, "min_luld_distance_pct")

    assert evaluate_candidate(near, CFG).reject is Reject.NEAR_LULD
    assert evaluate_candidate(near, flipped).reject is None, (
        "the flipped declaration must admit a price the rounded-up minimum rejects"
    )


@pytest.mark.spec
@pytest.mark.parametrize("code", HARD_FILTER_CODES)
def test_every_hard_filter_can_actually_reject(code: Reject) -> None:
    """Each of §4.2's seven hard rows is wired, not merely declared.

    A filter table whose bodies all return ``True`` passes every happy-path test in the
    suite. This is the reachability half — one candidate per row, asserting that row and no
    other is the one that binds.
    """
    from tests.test_scanner import candidate

    result = evaluate_candidate(candidate(**TRIPS_HARD_FILTER[code]), CFG)
    assert result.rejects == (code,), (
        f"expected exactly {code.value}, got {[r.value for r in result.rejects]}"
    )


@pytest.mark.spec
def test_the_hard_filter_reachability_table_covers_every_row() -> None:
    """Guard on the guard: a row added to §4.2 must not be silently untested above."""
    assert set(TRIPS_HARD_FILTER) == {f.code for f in HARD_FILTERS}


@pytest.mark.boundary
def test_the_watchlist_cannot_exceed_the_registered_size() -> None:
    """§4.3's "top 5" is a ceiling, and a config change moves it rather than being ignored."""
    from tests.test_scanner import candidate

    universe = [candidate(symbol=f"S{i:02d}", rvol=D(str(6 + i))) for i in range(30)]
    for size in (1, 5, 20):
        cfg = CFG.with_overrides(watchlist_size=size)
        report = scan(universe, cfg)
        assert len(report.survivors) == len(universe), "the fixture must over-supply"
        assert len(report.watchlist) == size


@pytest.mark.spec
def test_the_scanner_reads_nothing_and_imports_nothing_that_could() -> None:
    """D30, applied to the module most likely to want a feed.

    The broker-import denylist above is a denylist, so a green result is not proof that
    nothing can reach a market. For ``scanner.py`` specifically an **allowlist** is possible,
    because §4.2 is arithmetic over inputs and needs nothing else: the module may import the
    four stdlib names below and its own package, and nothing more. A scanner that sources its
    own universe is Phase 2's job and would fail here first.
    """
    tree = ast.parse((SRC / "scanner.py").read_text(encoding="utf-8"))
    permitted = {"__future__", "collections.abc", "dataclasses", "decimal"}

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module)
        elif isinstance(node, ast.Import):
            roots.update(a.name for a in node.names)
    outside = {r for r in roots if not r.startswith("tradipy")} - permitted
    assert not outside, f"scanner.py imports outside its allowlist: {sorted(outside)}"

    reads = [
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"
    ]
    assert not reads, "scanner.py opens a file; §4.2 is arithmetic over inputs (D30)"


@pytest.mark.spec
def test_the_scan_spread_cap_has_exactly_one_implementation() -> None:
    """``gates.scan_spread_cap`` is *called* by ``spread_caps``, not paralleled by it.

    ``scan_spread_cap``'s docstring says "deriving the cap twice — once here, once there — is
    the v1.2 defect class, so ``spread_caps`` delegates." Equal outputs do not establish that:
    two independent implementations of the same formula agree until one is edited, which is
    the entire v1.2 story. So the call is asserted structurally, and the agreement is asserted
    as well — across the §4.2 price range, where the two terms of the ``min()`` swap over at
    $4.00 and the one-tick clamp binds below $2.00.
    """
    tree = ast.parse((SRC / "gates.py").read_text(encoding="utf-8"))
    body = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "spread_caps"
    )
    calls = {
        n.func.id
        for n in ast.walk(body)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "scan_spread_cap" in calls, (
        "spread_caps no longer delegates; the scan cap now has two definitions (v1.2 class)"
    )

    r = D("0.15")
    for price in (D("1.00"), D("1.99"), D("3.99"), D("4.00"), D("4.01"), D("20.00")):
        assert spread_caps(price, r, CFG).scan == scan_spread_cap(price, CFG), price


@pytest.mark.spec
def test_ranking_refuses_an_unscored_result_rather_than_ordering_it() -> None:
    """``_rank_key`` raises rather than sorting a candidate §4.1 never scored.

    Unreachable through :func:`~tradipy.scanner.scan`, which only ranks survivors — so it is
    tested by calling it directly. A guard reachable only by a future caller is still a
    guarantee, and an untested one is how three of the four v0.0.1 holes stayed open.
    """
    from tests.test_scanner import candidate

    rejected = evaluate_candidate(candidate(rvol=D("1")), CFG)
    assert rejected.score is None
    with pytest.raises(ValueError, match="rejected and has no score"):
        _rank_key(rejected)


@pytest.mark.spec
def test_two_different_candidates_can_score_identically() -> None:
    """The saturation claim ``_rank_key``'s docstring argues the tiebreak from.

    Its reasoning is that ties arise between *different* inputs, because §20.10's normalizers
    saturate — not merely between duplicated fixtures, which tie trivially and prove nothing
    about whether the tiebreak is needed. Two candidates whose RVOL differs by 60× score
    identically here, because both are above ``score_cap_rvol``.

    **One half of that argument does not survive being tested, and the docstring is corrected
    to match.** ``float_inverse`` saturating at 0 cannot produce a tie *among survivors*:
    ``score_cap_float`` and ``max_float_shares`` are the same number, so the only float that
    saturates the normalizer and still passes §4.2's Float filter is the cap exactly — one
    value, not a range. That is the coincidence ``score.py`` flags and
    ``test_score_float_cap_currently_equals_the_scan_filter`` pins, showing up as a
    consequence: the two parameters being equal is also what makes half the saturation
    argument inapplicable. If either moves, this becomes reachable.
    """
    from tests.test_scanner import candidate

    cap_rvol = CFG["score_cap_rvol"]
    a = candidate(symbol="AAA", rvol=cap_rvol + D("1"))
    b = candidate(symbol="BBB", rvol=cap_rvol * D("4"))

    sa, sb = evaluate_candidate(a, CFG).score, evaluate_candidate(b, CFG).score
    assert sa is not None and sb is not None
    assert a.rvol != b.rvol, "the fixture must actually differ for this to mean anything"
    assert sa.total == sb.total, "the saturation argument for the tiebreak does not hold"
    assert [r.candidate.symbol for r in scan([b, a], CFG).watchlist] == ["AAA", "BBB"]

    # And the float half, shown unreachable rather than asserted away.
    assert CFG["score_cap_float"] == CFG["max_float_shares"]
    over_cap = candidate(symbol="CCC", float_shares=CFG["score_cap_float"] + D("1"))
    assert evaluate_candidate(over_cap, CFG).reject is Reject.FLOAT_TOO_HIGH


# ---------------------------------------------------------------------------
# Phase 4 — the §3 setups (D33). Each block performs the violation it forbids.
# ---------------------------------------------------------------------------
@pytest.mark.spec
def test_a_signal_cannot_coexist_with_a_failed_criterion() -> None:
    """§3.x states its criteria as *"all required"*, so ``SetupOutcome`` refuses the pair.

    Constructed directly rather than reached through an evaluator, because no evaluator can
    produce it — which is exactly why the guarantee needs a test that tries. An outcome carrying
    both a signal and a failure is how a rejected setup comes to be routed as an order.
    """
    accepted = setup_examples()[0].evaluate(CFG)
    assert accepted.signal is not None and accepted.levels is not None

    failure = Criterion("invented", Reject.SETUP_NOT_PRESENT, False, "planted by the test")
    with pytest.raises(ValueError, match="cannot coexist"):
        SetupOutcome(
            accepted.symbol,
            accepted.setup_type,
            (*accepted.criteria, failure),
            accepted.levels,
            accepted.signal,
        )


@pytest.mark.spec
def test_no_setup_can_fire_on_the_session_s_opening_bar() -> None:
    """§20.2: *"no VWAP-dependent setup can fire before 09:31."* All three are VWAP-dependent.

    The violation is attempted with a session whose *only* bar is the 09:30 bar, and again at
    index 0 of a longer one, so neither a short series nor a long one admits it.
    """
    example = setup_examples()[0]
    full = example.session
    for setup in SetupType:
        for session, index in ((full.through(0), 0), (full, 0)):
            outcome = EVALUATORS[setup](example.label.upper(), session, index, TICK_SIZE, CFG)
            timing = outcome.criteria[0]
            assert not timing.passed, f"{setup.value} fired on the opening bar"
            assert outcome.reject is Reject.SETUP_NOT_PRESENT
            assert outcome.signal is None


@pytest.mark.spec
def test_a_gap_wider_than_the_registered_maximum_invalidates_the_pattern() -> None:
    """§20.1: *"a gap > 2 minutes invalidates any in-progress pattern."*

    The bars are unchanged — only the *minutes* they carry move, so nothing about the pattern's
    prices or volumes differs between the passing and failing case. A check that read only the
    list order could not tell the two apart, and that is the failure this performs.
    """
    example = setup_examples()[0]
    bars = example.bars
    widest = int(CFG["max_pattern_gap_minutes"])

    for missing, intact in ((widest, True), (widest + 1, False)):
        minutes = [*range(len(bars) - 1), len(bars) - 2 + missing + 1]
        session = Session(tuple(SessionBar(m, b) for m, b in zip(minutes, bars, strict=True)))
        assert session.gap_before(len(bars) - 1) == missing
        outcome = evaluate_bull_flag("BF", session, len(bars) - 1, TICK_SIZE, CFG)
        gap = next(c for c in outcome.criteria if "gap" in c.name)
        assert gap.passed is intact, gap.detail
        if not intact:
            assert outcome.signal is None


@pytest.mark.spec
def test_arbitration_cannot_return_two_signals_for_one_symbol() -> None:
    """§20.11 rule 1: *"at most one open position per symbol regardless of setup count."*

    Performed on a bar where two setups really do fire, then again on hand-built outcomes for two
    different symbols — which §20.11 never asked to be arbitrated together, and silently picking
    one of them would suppress a signal.
    """
    from tests.test_setups import _dual_fire_session

    session = _dual_fire_session()
    outcomes = evaluate_all("BF", session, len(session) - 1, TICK_SIZE, CFG)
    accepted = [o for o in outcomes if o.accepted]
    assert len(accepted) > 1, "the fixture must fire twice for this to prove anything"

    winner, superseded = arbitrate(outcomes)
    assert winner is not None
    assert len(superseded) == len(accepted) - 1
    assert all(o.signal is not None for o in superseded)

    other = accepted[0]
    assert other.levels is not None and other.signal is not None
    foreign = SetupOutcome(
        "OTHER",
        other.setup_type,
        other.criteria,
        other.levels,
        SetupSignal("OTHER", other.setup_type, other.levels, other.signal.shares),
    )
    with pytest.raises(ValueError, match="per-symbol"):
        arbitrate([*accepted, foreign])


@pytest.mark.spec
def test_a_rejected_setup_is_never_sized() -> None:
    """§4.1's withholding rule, applied one layer up: no share count on a rejection.

    §3.4's worked example is the case — it derives a full set of levels and is then declined by
    the room gate. A size sitting on that is an invitation to route it.
    """
    rejected = [ex.evaluate(CFG) for ex in setup_examples() if ex.expect_reject is not None]
    assert rejected, "the fixtures must contain a rejected example for this to check anything"
    for outcome in rejected:
        assert outcome.reject is not None
        assert outcome.signal is None
        assert outcome.levels is not None, "the levels are reported; only the size is withheld"


@pytest.mark.spec
def test_t1_has_exactly_one_implementation() -> None:
    """``gates.exit_ladder`` *calls* ``t1_level``; :mod:`tradipy.setups` does not restate it.

    Asserted structurally, like the ``scan_spread_cap`` delegation: two implementations of
    ``entry + t1_r_multiple × R`` agree until one is edited, which is the whole v1.2 story. §3.3's
    T2 is defined relative to T1, so a second definition here would be the one that drifts.
    """
    tree = ast.parse((SRC / "gates.py").read_text(encoding="utf-8"))
    body = next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "exit_ladder"
    )
    calls = {
        n.func.id
        for n in ast.walk(body)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "t1_level" in calls, "exit_ladder no longer delegates; T1 now has two definitions"

    # And `setups.py` does not read the multiple at all — checked by AST rather than by
    # substring, because the parameter is *named* in a docstring there explaining why T1 is
    # delegated, and a check that cannot tell prose from code is a check that gets switched off.
    setups = ast.parse((SRC / "setups.py").read_text(encoding="utf-8"))
    subscripts = {
        n.slice.value
        for n in ast.walk(setups)
        if isinstance(n, ast.Subscript)
        and isinstance(n.slice, ast.Constant)
        and isinstance(n.slice.value, str)
    }
    assert "t1_r_multiple" not in subscripts, (
        "setups.py reads t1_r_multiple from the registry, which means it derives T1 itself"
    )


@pytest.mark.spec
def test_the_target_ordering_check_fires_when_handed_a_ladder_that_violates_it() -> None:
    """§3.1.1's ``entry < T1 < T2``, both halves: the implication, and the check.

    §3.1.1 calls the ordering *"guaranteed by the pre-entry room gate"*. It is — because the
    structural target is one of the gate's own resistance candidates — so the check below is
    unreachable through the three MVP evaluators. Both facts are asserted, because the first is a
    property of the *candidate set* rather than of the gate: a setup whose T2 is not among the
    candidates would lose the guarantee with nothing to notice.
    """
    for example in setup_examples():
        levels = example.evaluate(CFG).levels
        assert levels is not None
        room_passed = (levels.resistance.level - levels.entry_price) >= levels.room.required
        if room_passed:
            assert levels.ladder.ordered_above(levels.entry_price), example.section

    levels = setup_examples()[0].evaluate(CFG).levels
    assert levels is not None
    inverted = Ladder(t1=levels.ladder.t1, t2=levels.ladder.t1 - TICK_SIZE)
    criteria = _gate_criteria(
        entry=levels.entry_price,
        stop=levels.stop_price,
        stop_reject=None,
        r=levels.r_per_share,
        spread=levels.spread_at_signal,
        ladder=inverted,
        room=levels.room,
        separation=levels.min_separation,
        resistance=levels.resistance,
        cfg=CFG,
    )
    ordering = next(c for c in criteria if c.name.startswith("Target ordering"))
    assert not ordering.passed
    assert ordering.code is Reject.TARGETS_TOO_CLOSE


@pytest.mark.spec
@pytest.mark.parametrize("module", ["session.py", "setups.py"])
def test_the_setup_layer_reads_nothing_and_imports_nothing_that_could(module: str) -> None:
    """D30, extended to Phase 4's two modules — an allowlist, not a denylist.

    §3's criteria are arithmetic over a bar series the caller supplies, so the same argument that
    made an allowlist possible for ``scanner.py`` applies here: these modules may import the
    listed stdlib names and their own package, and nothing else. A strategy engine that grew a
    feed would fail here first, and it is the module most likely to want one.
    """
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
    permitted = {"__future__", "collections.abc", "dataclasses", "decimal", "enum", "typing"}

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module)
        elif isinstance(node, ast.Import):
            roots.update(a.name for a in node.names)
    outside = {r for r in roots if not r.startswith("tradipy")} - permitted
    assert not outside, f"{module} imports outside its allowlist: {sorted(outside)}"

    reads = [
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"
    ]
    assert not reads, f"{module} opens a file; §3 is arithmetic over a supplied series (D30)"


@pytest.mark.spec
@pytest.mark.parametrize("setup", list(SetupType))
def test_every_setup_can_reject_with_setup_not_present(setup: SetupType) -> None:
    """The one code Phase 4 adds must be reachable for each setup, or it names nothing.

    A flat series has no flagpole, no consolidation above VWAP and no dip below it, so all three
    patterns are absent. Reachability per code is what
    ``test_every_hard_filter_can_actually_reject`` does for §4.2, and the argument is the same: an
    unreachable code is a rule nothing enforces.
    """
    flat = bar_sequence([Bar(D("5.00"), D("5.00"), D("5.00"), D("5.00"), 1000)] * 40)
    outcome = EVALUATORS[setup]("FLAT", flat, len(flat) - 1, TICK_SIZE, CFG)
    assert outcome.reject is Reject.SETUP_NOT_PRESENT
    assert outcome.signal is None


@pytest.mark.spec
def test_the_resistance_set_cannot_lose_its_only_unconditional_candidate() -> None:
    """§3.1.1's set must always contain a level above entry, or the room gate has no input.

    ``whole_dollar_above`` is the one candidate that cannot be below entry, which is what makes
    :func:`~tradipy.setups.nearest_resistance` total. Performed by handing it a HOD and a
    structural target that are both below entry: the whole dollar still carries it.
    """
    resistance = nearest_resistance(D("5.16"), prior_hod=D("5.00"), structural_target=D("5.10"))
    assert resistance.source == "next whole dollar"
    assert resistance.level == D("6")
    assert [name for name, _ in resistance.candidates] == ["next whole dollar"]


# ---------------------------------------------------------------------------
# Phase 5 (D34) — §6, §7 and §20.12's guarantees, each performed against
# ---------------------------------------------------------------------------
#
# Same rule as every block above: for each sentence of the form "X cannot happen", the test that
# attempts X. Two of these assert an **absence** rather than a presence, which is unusual and
# deliberate: docs/PHASE-5-DESIGN.md §1.1 states that two §6 guarantees are *not* closed, and a
# guarantee documented as unclosed and then quietly closed is as much a drift as the reverse.


def _phase5_signal() -> SetupSignal:
    """The §3.2 worked example's signal — the one Phase 5 fixture that must exist."""
    signal = next(
        outcome.signal
        for example in setup_examples()
        if (outcome := example.evaluate(CFG)).signal is not None
    )
    return signal


@pytest.mark.spec
def test_exit_leg_quantities_cannot_fail_to_cover_the_position() -> None:
    """§21.6 makes an unprotected share a Sev-1, so the §3.1.1 split may not lose one.

    The guarantee is on :class:`~tradipy.positions.LegQuantities`, not on the function that
    builds it, precisely so that a *second* construction path cannot bypass it — which is what
    made ``MODE_PRESETS`` mutable behind a frozen ``Config``. Performed by constructing the type
    directly with legs that do not sum.
    """
    with pytest.raises(ValueError, match="sum to"):
        LegQuantities(t1=500, t2=250, t3=249, shares=1000)
    # And the real split never does, at any count the fractions do not divide.
    for shares in (1, 2, 3, 7, 999, 2500):
        q = leg_quantities(shares, CFG)
        assert q.t1 + q.t2 + q.t3 == shares


@pytest.mark.spec
def test_a_bracket_cannot_be_built_for_a_position_with_no_shares() -> None:
    """``position_size`` returns 0 for "no budget" *and* "skip", so 0 must not build a draft.

    That ambiguity is a documented open finding on ``gates.position_size``. A bracket is where it
    would become four legs of nothing, and the refusal comes from ``leg_quantities`` rather than
    from a second check in ``bracket`` — one definition, per convention 1. This test therefore
    also fails if that delegation is replaced by a local guard whose message drifts.
    """
    signal = _phase5_signal()
    with pytest.raises(ValueError, match="shares must be positive"):
        bracket(
            SetupSignal("ZERO", signal.setup_type, signal.levels, 0),
            signal.levels.entry_price,
            "2026-07-31",
            "ACC",
            CFG,
        )


@pytest.mark.spec
def test_no_draft_price_can_reach_a_broker_unrounded() -> None:
    """§20.13: *"every price submitted to the broker … must be a whole tick."*

    An ``OrderDraft`` is the last representation before submission, so this is where the
    requirement binds. Performed on a sub-penny ask, which is the only input to
    :func:`~tradipy.orders.bracket` that nothing upstream has rounded.
    """
    signal = _phase5_signal()
    draft = bracket(signal, D("5.1637"), "2026-07-31", "ACC", CFG)
    for leg in draft.legs:
        for price in (leg.limit_price, leg.stop_price):
            assert price is None or price % TICK_SIZE == 0, f"{leg.purpose} price {price}"
    # And a leg constructed by hand with an unrounded price is refused, so the guarantee does not
    # depend on `bracket` being the only builder.
    with pytest.raises(ValueError, match="whole tick"):
        OrderLeg(
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=1,
            purpose=LegPurpose.STOP,
            stop_price=D("5.0449"),
        )


@pytest.mark.spec
def test_the_state_machine_refuses_every_transition_section_twenty_twelve_omits() -> None:
    """§20.12 is an enumeration, so the *complement* is what has to fail.

    The happy-path walk passes against a machine that permits everything, which is the shape of
    hole this whole file exists for. Every ordered pair outside :data:`TRANSITIONS` is attempted.
    """
    attempted = refused = 0
    for src, dst in itertools.product(PositionState, repeat=2):
        if dst in TRANSITIONS[src]:
            continue
        attempted += 1
        with pytest.raises(IllegalTransitionError):
            transition(src, dst)
        refused += 1
    assert attempted == refused
    # Including the self-transition, which §20.12 lists for no state.
    for state in PositionState:
        with pytest.raises(IllegalTransitionError):
            transition(state, state)
    # And the two edges §20.12's table omits and its diagram supplies must be present, or the
    # machine can neither start nor finish — the reading is load-bearing, not cosmetic.
    assert PositionState.ARMED in TRANSITIONS[PositionState.IDLE]
    for exit_state in (
        PositionState.STOPPED_OUT,
        PositionState.INVALIDATED,
        PositionState.BAILED_OUT,
    ):
        assert TRANSITIONS[exit_state] == frozenset({PositionState.CLOSED})


@pytest.mark.spec
def test_a_second_position_at_full_risk_cannot_be_approved() -> None:
    """§7 row 1 is NON-BYPASSABLE, so the total-risk cap must not be reachable around.

    Performed three ways, because "non-bypassable" is a claim about every path: a second §3
    signal in sequence, a hand-built open position at full risk, and an override attempting to
    raise the cap past §7's hard ceiling.
    """
    signal = _phase5_signal()
    budget = max_dollar_risk(CFG)

    full = OpenPosition(
        symbol="HELD",
        shares=signal.shares,
        mark=signal.levels.entry_price,
        current_stop=signal.levels.stop_price,
        state=PositionState.OPEN_FULL,
        correlation_group="symbol:HELD",
    )
    state = RiskState(start_of_day_equity=CFG["start_of_day_equity"], positions=(full,))
    assert total_open_risk(state) >= budget * D("0.99")
    decision = approve(signal, state, CFG)
    assert not decision.approved
    assert decision.reason is RiskBlock.MAX_RISK_EXCEEDED
    assert decision.approved_shares == 0, "§7 rejects rather than trims (§9.2 approved_shares)"

    # The cap cannot be raised out of the way: `max_risk_per_trade_pct` is in HARD_CAPS.
    with pytest.raises(ValueError):
        CFG.with_overrides(max_risk_per_trade_pct=HARD_CAPS["max_risk_per_trade_pct"] * 2)


@pytest.mark.spec
def test_a_halted_account_cannot_be_approved_by_any_path() -> None:
    """§7.2's kill switch and §7.1.2's lockout are NON-BYPASSABLE and have no bypassing config.

    ``trading_halted`` is not a registered parameter, so there is nothing to override; the attempt
    below is the closest reachable thing, and it must not help.
    """
    signal = _phase5_signal()
    halted = RiskState(
        start_of_day_equity=CFG["start_of_day_equity"],
        trading_halted=True,
        halt_reason="kill_switch",
    )
    assert approve(signal, halted, CFG).reason is RiskBlock.TRADING_HALTED
    # Even as a REDUCE order the account is halted — but §7.2's action is *flatten*, so an exit is
    # exactly what should be permitted. Asserted so the two rules are not conflated.
    assert approve(signal, halted, CFG, intent=OrderIntent.REDUCE).approved
    with pytest.raises(KeyError):
        CFG.with_overrides(trading_halted=0)


@pytest.mark.spec
def test_scale_in_cannot_happen_before_t1_by_any_state() -> None:
    """§7.1.1: *"adds are only ever legal after T1, never while … at full risk."*

    Attempted from every §20.12 state with a zero projected risk, which is the most permissive
    arithmetic there is — so anything that returns True here is the state filter failing.
    """
    permitted = {state for state in PositionState if scale_in_permitted(state, Decimal(0), CFG)}
    assert permitted == {PositionState.T1_FILLED, PositionState.T2_FILLED}


@pytest.mark.spec
def test_two_different_trigger_bars_cannot_share_an_idempotency_key() -> None:
    """§6.7: the key must be derived from signal identity, so no two signals may collide.

    §6.7's own argument is that a UUID cannot serve: *"a freshly generated one is unique by
    construction, so a duplicate check against it can never fire."* The converse guarantee is this
    one, and the delimiter is the way it fails — so an embedded ``|`` is refused rather than
    silently producing a shared key.
    """
    base = ("ABCD", SetupType.BULL_FLAG, "2026-07-31", 37, "ACC")
    keys = {
        idempotency_key(*base),
        idempotency_key("ABCD", SetupType.BULL_FLAG, "2026-07-31", 38, "ACC"),
        idempotency_key("ABCD", SetupType.HOD_BREAKOUT, "2026-07-31", 37, "ACC"),
        idempotency_key("ABCD", SetupType.BULL_FLAG, "2026-08-03", 37, "ACC"),
    }
    assert len(keys) == 4
    # The collision path a delimited join has, closed.
    with pytest.raises(ValueError, match="separator"):
        idempotency_key("AB|CD", SetupType.BULL_FLAG, "2026-07-31|37", 37, "ACC")


@pytest.mark.spec
def test_a_risk_block_cannot_land_where_a_reject_belongs_and_the_reverse() -> None:
    """The fourth namespace, held apart from the other three by type — K5's argument again.

    Performed rather than annotated, because a type hint is not a runtime guarantee. The
    membership tests below are what a caller would actually get wrong.
    """
    for block in RiskBlock:
        assert block not in set(Reject)
        assert block not in set(SoftFlag)
        assert block not in set(ExitReason)
        with pytest.raises(ValueError):
            Reject(block.value)
    for reject in Reject:
        with pytest.raises(ValueError):
            RiskBlock(reject.value)
    # And a §4.2 soft flag cannot become an account-level block either.
    for flag in SoftFlag:
        with pytest.raises(ValueError):
            RiskBlock(flag.value)


@pytest.mark.spec
@pytest.mark.parametrize("module", ["positions.py", "risk.py", "orders.py"])
def test_the_phase_5_layer_reads_nothing_and_imports_nothing_that_could(module: str) -> None:
    """D30, extended to Phase 5's three modules — an allowlist, not a denylist.

    The layer most likely to want a broker is the one that builds broker orders, so this is the
    allowlist that matters most. ``hashlib`` is permitted for ``orders.py`` alone: §6.7 specifies
    sha256 by name, and a hash is arithmetic. Note what is **absent** and would be the first thing
    a transport implementation reached for — ``socket``, ``ib_insync``, ``sqlite3``, ``json``,
    ``pathlib``, ``os`` — none of which is in the list below.
    """
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
    permitted = {
        "__future__",
        "collections.abc",
        "dataclasses",
        "decimal",
        "enum",
        "hashlib",
        "types",
        "typing",
    }

    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module)
        elif isinstance(node, ast.Import):
            roots.update(a.name for a in node.names)
    outside = {r for r in roots if not r.startswith("tradipy")} - permitted
    assert not outside, f"{module} imports outside its allowlist: {sorted(outside)}"

    reads = [
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"
    ]
    assert not reads, f"{module} opens a file; §7's state is supplied, not sensed (D30)"


@pytest.mark.spec
def test_the_two_guarantees_phase_5_cannot_make_are_still_absent() -> None:
    """docs/PHASE-5-DESIGN.md §1.1 states two §6/§7 guarantees as **unclosed**. Pin the absence.

    A guarantee documented as unclosed and then quietly closed is as much a documentation drift as
    one documented as closed and never wired — which is the sixth defect class from the other
    side. If either assertion below starts failing, the design document is what needs editing.

    1. §6.7's *"the DB — not process memory — is the arbiter"*: there is no store, so the
       duplicate check reads a set the caller supplies.
    2. §7.1.2's *"the non-bypassable limits are meaningless if they reset on restart"*: nothing
       persists, so :class:`RiskState` has no load path.
    """
    orders_src = (SRC / "orders.py").read_text(encoding="utf-8")
    risk_src = (SRC / "risk.py").read_text(encoding="utf-8")

    # No persistence of any kind in either module.
    for name, src in (("orders.py", orders_src), ("risk.py", risk_src)):
        for forbidden in ("sqlite3", "open(", "Path(", "json.dump", "pickle"):
            assert forbidden not in src, f"{name} appears to persist ({forbidden})"

    # The duplicate check's arbiter is a supplied argument, and omitting it does not silently pass
    # as a real check.
    signal = _phase5_signal()
    decision = approve(signal, RiskState(start_of_day_equity=CFG["start_of_day_equity"]), CFG)
    row = next(r for r in decision.rules_evaluated if r.rule.startswith("Duplicate order"))
    assert row.passed and "not evaluated" in row.detail

    # `RiskState` has no field that could hold a loaded row, and no classmethod that loads one.
    assert not [n for n in dir(RiskState) if "load" in n or "from_" in n]


@pytest.mark.spec
def test_approve_evaluates_every_rule_and_cannot_silently_drop_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§9.2's ``rules_evaluated`` is *"every rule checked, for audit"* — so *every* must bind.

    The first version of this guarantee was `assert len(rules_evaluated) >= 10` against an actual
    12, which passes with a rule missing. That is the fifth defect class exactly: a test adjacent
    to the hole, confirming the happy path. `approve` now compares its own output against
    :data:`~tradipy.risk.EVALUATED_RULES` and raises, and this performs the drop.

    The patch goes through ``monkeypatch`` rather than ``importlib`` plus ``try/finally``: the
    latter assigns to an attribute of an untyped ``ModuleType``, which a type checker cannot see
    and correctly refuses, and it restores by hand what the fixture restores for free.
    """
    signal = _phase5_signal()
    state = RiskState(start_of_day_equity=CFG["start_of_day_equity"])
    decision = approve(signal, state, CFG)
    assert tuple(r.rule for r in decision.rules_evaluated) == EVALUATED_RULES

    # Perform the violation: a loop one rule short must not produce a decision.
    monkeypatch.setattr(
        risk_module, "EVALUATED_RULES", (*EVALUATED_RULES, "A rule nothing appends")
    )
    with pytest.raises(AssertionError, match="did not evaluate"):
        approve(signal, state, CFG)


@pytest.mark.spec
def test_no_risk_block_is_unreachable_and_approve_still_cannot_reach_the_drawdowns() -> None:
    """Two facts that must both hold, and which Phase 6 changed in opposite directions.

    Through Phase 5 this fixture was ``test_the_two_drawdown_blocks_are_unreachable_until_phase_6``
    and its docstring said *"when Phase 6 wires the loop, this fails."* It did, and this is what
    it becomes.

    1. :data:`~tradipy.risk.UNREACHABLE_BLOCKS` is now **empty**, because
       :func:`tradipy.monitor.evaluate` supplies the block path §7 marks *Continuous* and *End of
       day*. Asserted on the set rather than by deleting the name, so a member added back is a
       claim that needs the fixture the Phase 5 version had.
    2. :func:`tradipy.risk.approve` still cannot produce either drawdown block. §7 does not mark
       rows 7 and 8 *Pre-order*, so a pre-order engine reporting one would be applying a rule at
       a point §7 does not name — and the deep state below is the one that makes the difference
       visible: both predicates fire, ``approve`` reports neither, ``monitor`` reports both.
    """
    assert not UNREACHABLE_BLOCKS, (
        "Phase 6 wired §7's Continuous and End-of-day points, so no RiskBlock member is "
        "produced by nothing; a member added back here needs the fixture Phase 5's had"
    )

    signal = _phase5_signal()
    equity = CFG["start_of_day_equity"]
    deep = RiskState(
        start_of_day_equity=equity,
        realized_pnl=-equity * CFG["multi_day_dd_pct"] - Decimal(1),
        session_equity_peak=equity * Decimal("1.5"),
        multi_day_peak_equity=equity * Decimal("1.5"),
    )
    assert session_drawdown_breached(deep, CFG)
    assert multi_day_drawdown_breached(deep, CFG)

    drawdowns = {RiskBlock.SESSION_DRAWDOWN, RiskBlock.MULTI_DAY_DRAWDOWN}
    assert approve(signal, deep, CFG).reason not in drawdowns
    assert {r.block for r in approve(signal, deep, CFG).blocks} & drawdowns == set()

    # And Phase 6 does reach them, at the points §7 does name.
    assert (
        monitor_evaluate(deep, EnforcementPoint.CONTINUOUS, CFG).reason
        is RiskBlock.DAILY_LOSS_LIMIT
    ), "row 2 is earlier in §7's table, so it is the reason; row 7 is on .breaches"
    assert RiskBlock.SESSION_DRAWDOWN in {
        r.block for r in monitor_evaluate(deep, EnforcementPoint.CONTINUOUS, CFG).breaches
    }
    assert (
        monitor_evaluate(deep, EnforcementPoint.END_OF_DAY, CFG).reason
        is RiskBlock.MULTI_DAY_DRAWDOWN
    )


@pytest.mark.spec
def test_every_risk_block_can_actually_fire() -> None:
    """No :class:`~tradipy.rejects.RiskBlock` member may be produced by nothing.

    The positive counterpart of the fixture above, and the same guarantee
    ``test_every_hard_filter_can_actually_reject`` makes about §4.2's codes: a reason code the
    system can never emit is a rule believed to be enforced and is not, which is the fifth
    defect class in its purest form. §7's table has thirteen rows and this asserts that every
    one of them that is not already a :class:`~tradipy.rejects.Reject` has a path.

    Derived over the **enum**, not over a list here, so a member added to ``RiskBlock`` without a
    producer fails immediately.
    """
    equity = CFG["start_of_day_equity"]
    signal = _phase5_signal()
    base = RiskState(start_of_day_equity=equity)

    def approve_reason(**kw) -> RiskBlock | Reject | None:
        state = kw.pop("state", base)
        return approve(signal, state, CFG, **kw).reason

    full = OpenPosition(
        signal.symbol,
        signal.shares,
        signal.levels.entry_price,
        signal.levels.stop_price,
        PositionState.OPEN_FULL,
        "g",
    )
    breakeven = OpenPosition(
        "OTHER",
        signal.shares,
        signal.levels.entry_price,
        signal.levels.entry_price,
        PositionState.T1_FILLED,
        "g",
    )
    at_limit = Decimal(-1) * equity * CFG["daily_loss_pct"]

    produced: dict[RiskBlock, RiskBlock | Reject | None] = {
        RiskBlock.MAX_RISK_EXCEEDED: approve_reason(
            state=RiskState(start_of_day_equity=equity, positions=(full,))
        ),
        RiskBlock.DAILY_LOSS_LIMIT: approve_reason(
            state=RiskState(start_of_day_equity=equity, realized_pnl=at_limit)
        ),
        # Needs a position already at breakeven, or §7 row 1 fires first — which is H1 — *and*
        # `max_open_positions` at 1, because the `experienced` preset's 3 leaves room. That the
        # row is only reachable at one of the two shipped presets is itself H1.
        RiskBlock.MAX_POSITIONS: approve(
            signal,
            RiskState(start_of_day_equity=equity, positions=(breakeven,)),
            CFG.with_overrides(max_open_positions=1),
            correlation="elsewhere",
        ).reason,
        RiskBlock.LOSS_STREAK_LOCKOUT: approve_reason(
            state=RiskState(
                start_of_day_equity=equity,
                consecutive_losses=int(CFG["max_consecutive_losses"]),
            )
        ),
        RiskBlock.BUYING_POWER: approve_reason(buying_power=Decimal(1)),
        # Needs an account started near FINRA's floor, or §7's daily-loss row locks first — H2.
        RiskBlock.PDT_VIOLATION: approve(
            signal,
            RiskState(
                start_of_day_equity=PARAMS["start_of_day_equity"].lo,
                realized_pnl=Decimal(-1),
                day_trades_in_window=3,
            ),
            CFG,
        ).reason,
        RiskBlock.OUTSIDE_SESSION_WINDOW: approve(
            replace(
                signal,
                levels=replace(
                    signal.levels,
                    trigger_minute=int(CFG["session_last_entry_minute"]) + 1,
                ),
            ),
            base,
            CFG,
        ).reason,
        RiskBlock.CORRELATED_EXPOSURE: approve_reason(
            state=RiskState(start_of_day_equity=equity, positions=(breakeven,)),
            correlation="g",
        ),
        RiskBlock.TRADING_HALTED: approve_reason(
            state=RiskState(start_of_day_equity=equity, trading_halted=True)
        ),
        RiskBlock.DUPLICATE_ORDER: approve_reason(
            state=RiskState(start_of_day_equity=equity, submitted_keys=frozenset({"k"})),
            idempotency_key="k",
        ),
        # The two Phase 6 added, at the enforcement points §7 names for them.
        RiskBlock.SESSION_DRAWDOWN: monitor_evaluate(
            RiskState(
                start_of_day_equity=equity,
                unrealized_pnl=-equity * CFG["session_dd_pct"] - TICK_SIZE,
                session_equity_peak=equity,
            ),
            EnforcementPoint.CONTINUOUS,
            CFG,
        )
        .breaches[-1]
        .block,
        RiskBlock.MULTI_DAY_DRAWDOWN: monitor_evaluate(
            RiskState(
                start_of_day_equity=equity,
                multi_day_peak_equity=equity * (Decimal(1) + CFG["multi_day_dd_pct"] * 2),
            ),
            EnforcementPoint.END_OF_DAY,
            CFG,
        ).reason,
    }

    assert set(produced) == set(RiskBlock), (
        "a RiskBlock member has no producer here: "
        f"{sorted(m.name for m in set(RiskBlock) - set(produced))}"
    )
    wrong = {m.name: got for m, got in produced.items() if got is not m}
    assert not wrong, f"these RiskBlock members were not produced by the path claimed: {wrong}"


@pytest.mark.spec
def test_correlated_exposure_and_max_positions_are_not_the_same_fixture() -> None:
    """Guard on the guard for the fixture above: two rows driven by one state must differ.

    ``MAX_POSITIONS`` and ``CORRELATED_EXPOSURE`` are driven from the *same* single-position
    state and separated only by the ``correlation`` argument, which is exactly the configuration
    in which one of them silently becomes the other's alias. Asserted here rather than trusted.
    """
    equity = CFG["start_of_day_equity"]
    signal = _phase5_signal()
    breakeven = OpenPosition(
        "OTHER",
        signal.shares,
        signal.levels.entry_price,
        signal.levels.entry_price,
        PositionState.T1_FILLED,
        "g",
    )
    state = RiskState(start_of_day_equity=equity, positions=(breakeven,))
    one = CFG.with_overrides(max_open_positions=1)
    # Same state, same config: only the correlation argument differs, and the answers must too.
    assert approve(signal, state, one, correlation="g").reason is RiskBlock.MAX_POSITIONS, (
        "§7 row 3 is earlier in the table than row 10, so it is the reason when both fire"
    )
    assert approve(signal, state, CFG, correlation="g").reason is RiskBlock.CORRELATED_EXPOSURE, (
        "at max_open_positions=3 only the correlation row can fire"
    )
    assert (
        approve(signal, state, CFG, correlation="elsewhere").reason
        is not RiskBlock.CORRELATED_EXPOSURE
    ), "and with a different group neither fires, or the pair proves nothing"


@pytest.mark.boundary
def test_every_phase_5_threshold_has_a_boundary_fixture() -> None:
    """Guard on the guard: the boundary claim in ``docs/PHASE-5-DESIGN.md`` §8 must be *derived*.

    That document says all nine Phase 5 thresholds are exercised at their own limit. Its first
    draft said six of nine and named two things that are not registry rows, which is why the
    coverage set is computed here from the source instead of counted by a reader — the same
    argument :func:`test_every_module_that_rounds_is_in_the_polarity_check` makes about a
    hand-maintained file list.

    Scope, stated because an unqualified claim about a checker is what F8 was about: this asserts
    that each name appears inside a ``@pytest.mark.boundary`` block. It cannot verify that the
    fixture exercises the *limit* rather than merely mentioning the parameter; that is a review
    judgement, and the enumeration in PHASE-5-DESIGN §8 is where it is recorded.
    """
    phase5_rows = frozenset(
        {
            "max_correlated_positions",
            "session_last_entry_minute",
            "entry_limit_offset_ticks",
            "stop_limit_offset_ticks",
            "t1_scale_out_pct",
            "t2_scale_out_pct",
            "min_partial_fill_pct",
            "partial_fill_timeout_seconds",
            "partial_fill_spread_widening_multiple",
        }
    )
    assert phase5_rows <= set(PARAMS), "a name here is not registered — the list is stale"

    suite = Path(__file__).resolve().parent / "test_phase5.py"
    blocks = [
        block
        for block in suite.read_text(encoding="utf-8").split("\n@pytest.mark.")
        if block.startswith("boundary")
    ]
    assert blocks, "no boundary-marked fixtures found — check the split, not the result"
    covered = {row for row in phase5_rows for block in blocks if row in block}
    assert covered == phase5_rows, f"no boundary fixture names: {sorted(phase5_rows - covered)}"


# ---------------------------------------------------------------------------
# Phase 6 (D35) — §7's other five enforcement points, §10's daily_state, §20.8
# ---------------------------------------------------------------------------
_PHASE_6_ROWS = frozenset({"session_flat_all_minute", "multi_day_dd_window_sessions"})


def _open_session(cfg: Config = CFG) -> DailyState:
    return record_snapshot(open_session("2026-08-03"), cfg["start_of_day_equity"])


def _a_closed_trade(cfg: Config = CFG) -> ClosedTrade:
    signal = _phase5_signal()
    return ClosedTrade(
        symbol=signal.symbol,
        setup_type=signal.setup_type,
        entry_price=signal.levels.entry_price,
        exit_price=signal.levels.stop_price,
        shares=signal.shares,
        r_per_share=signal.levels.r_per_share,
        commission=cfg["est_round_trip_cost_per_share"] * signal.shares,
        fees=D(0),
        exit_reason=ExitReason.STOPPED_OUT,
    )


@pytest.mark.spec
def test_section_seven_cannot_be_evaluated_without_the_section_twenty_eight_snapshot() -> None:
    """§20.8: *"it does not fall back to a stale or computed value."* Perform the fallback.

    The guarantee is that there is **no** value to fall back to, so the violation is trying to
    reach §7's rules from a session that has not synced. Every mutation is attempted, not only
    the bridge: a caller that can accrue a trade into a NO_TRADE session has produced a realized
    P&L denominated in nothing.
    """
    opened = open_session("2026-08-03")
    assert opened.start_of_day_equity is None

    with pytest.raises(SessionNotOpenError):
        risk_state(opened)
    with pytest.raises(SessionNotOpenError):
        mark_to_market(opened, D(0))
    with pytest.raises(SessionNotOpenError):
        record_close(opened, _a_closed_trade(), unrealized_after=D(0))
    with pytest.raises(SessionNotOpenError):
        daily_lock(opened, RiskBlock.DAILY_LOSS_LIMIT)

    # And the state itself cannot be hand-built into the contradiction the phase encodes.
    with pytest.raises(ValueError, match=r"§20\.8"):
        DailyState(session_date="2026-08-03", phase=SessionPhase.TRADING)


@pytest.mark.spec
def test_the_start_of_day_snapshot_cannot_be_taken_twice() -> None:
    """§20.8: *"immutable for the remainder of the session."* Perform the second snapshot."""
    state = _open_session()
    equity = state.start_of_day_equity
    assert equity is not None, "_open_session() has taken §20.8's snapshot"
    for attempt in (equity, equity * 2, D(25_000)):
        with pytest.raises(ValueError, match="immutable"):
            record_snapshot(state, attempt)


@pytest.mark.spec
def test_a_section_seven_lock_cannot_be_cleared_by_reloading_the_row() -> None:
    """§11.1: *"lock persists across restart and cannot be cleared by relaunching."*

    The violation is the relaunch: serialise a locked session, read it back, and check that the
    lock is still there and still needs §7.2's phrase. §7.1.2's *durability* is not built — there
    is no store — but the arithmetic that makes durability meaningful is, and this is it.
    """
    locked = daily_lock(_open_session(), RiskBlock.DAILY_LOSS_LIMIT)
    reloaded = from_row(to_row(locked))
    assert reloaded.phase is SessionPhase.LOCKED
    assert reloaded.trading_halted
    assert reloaded.halt_reason is RiskBlock.DAILY_LOSS_LIMIT

    # And §7's pre-order engine still refuses, through the same bridge.
    assert approve(_phase5_signal(), risk_state(reloaded), CFG).reason is RiskBlock.TRADING_HALTED

    with pytest.raises(ConfirmationRequiredError):
        clear_lock(reloaded, "", "")
    with pytest.raises(ConfirmationRequiredError):
        clear_lock(reloaded, "wrong", "right")
    assert clear_lock(reloaded, "right", "right").phase is SessionPhase.TRADING


@pytest.mark.spec
def test_a_closed_trade_that_cannot_have_an_r_multiple_refuses_to_exist() -> None:
    """§9.2's ``r_multiple`` divides by ``shares x R``; neither may be zero.

    Returning a number here is the failure mode that matters: §18.7 is judged on the aggregate
    of these, and one fabricated multiple is a gate result nobody can trace.
    """
    trade = _a_closed_trade()
    for bad in ({"shares": 0}, {"shares": -1}, {"r_per_share": D(0)}, {"r_per_share": D(-1)}):
        with pytest.raises(ValueError):
            replace(trade, **bad)
    for bad in ({"entry_price": D(0)}, {"exit_price": D(0)}, {"commission": D(-1)}):
        with pytest.raises(ValueError):
            replace(trade, **bad)

    # And the multiple is on NET, which is the half a stored field could get wrong once.
    assert trade.r_multiple == trade.net_pnl / (trade.r_per_share * trade.shares)
    assert trade.r_multiple != trade.gross_pnl / (trade.r_per_share * trade.shares)


@pytest.mark.spec
def test_the_daily_state_bridge_cannot_silently_drop_a_field() -> None:
    """Every :class:`~tradipy.risk.RiskState` field must be supplied by the bridge or declared.

    :class:`~tradipy.daily.DailyState` and ``RiskState`` share eight fields, which is the exact
    configuration the v1.2 defect class arises in. The guarantee is that
    :func:`tradipy.daily.risk_state` is the **only** thing that maps one to the other; the
    violation is a field on either side that the bridge does not carry.

    Derived from the two dataclasses **and from
    :data:`tradipy.daily.BRIDGE_EXCEPTIONS`**, so a field added to ``RiskState`` in a later phase
    fails here rather than defaulting quietly into every §7 rule. The exception list is read from
    the module rather than restated here: an earlier draft of this fixture carried its own copy,
    which disagreed with the constant it was shadowing — the v1.2 defect class in the test written
    to prevent it.
    """
    daily_names, risk_names = bridge_fields()
    carried = risk_names - BRIDGE_EXCEPTIONS

    state = record_close(_open_session(), _a_closed_trade(), unrealized_after=D("-12.34"))
    equity = state.start_of_day_equity
    assert equity is not None, "the session is open, so §20.8's snapshot is set"
    state = record_multi_day_peak(state, [equity * 2], CFG)
    built = risk_state(state)
    for name in sorted(carried):
        # `trading_halted` is a *property* of DailyState rather than a field, which is why the
        # membership check below is against `hasattr` and not against `daily_names`.
        assert hasattr(state, name), f"the bridge cannot supply RiskState.{name}"
        assert getattr(built, name) == getattr(state, name), name

    # And the exception list is exactly the fields that are *not* same-named copies: two are
    # arguments, and `halt_reason` changes type because §10's column is a VARCHAR.
    assert BRIDGE_EXCEPTIONS - risk_names == frozenset(), "an exception names no RiskState field"
    assert "halt_reason" in daily_names
    locked = daily_lock(state, RiskBlock.SESSION_DRAWDOWN)
    assert risk_state(locked).halt_reason == RiskBlock.SESSION_DRAWDOWN.value
    assert locked.halt_reason is RiskBlock.SESSION_DRAWDOWN


@pytest.mark.spec
def test_the_unpersisted_fields_set_is_derived_and_not_a_list_somebody_typed() -> None:
    """Finding 1, pinned in both directions: §10 has no column for exactly four §7 inputs.

    A field quietly *gaining* a column is as much a drift as one quietly losing it — the first
    would mean §10's schema changed and this document did not, and the second is the finding.
    """
    declared = {f.name for f in fields(DailyState)}
    written = set(DAILY_STATE_COLUMNS.values())
    assert declared - written == UNPERSISTED_FIELDS
    assert written <= declared, "a column maps to a field DailyState does not have"
    assert "updated_at" in CLOCK_COLUMNS and "updated_at" not in DAILY_STATE_COLUMNS


@pytest.mark.spec
def test_the_flatten_directive_cannot_invent_a_state_section_twenty_twelve_omits() -> None:
    """§7's *"Flatten all"* against §20.12 — review round 14's H3, as an enforcement fixture.

    Three violations performed:

    1. A directive whose ``to_state`` is anything but ``CLOSED`` or ``None``.
    2. Committing an unrepresentable directive — it must raise §20.12's own refusal, not a
       different error and certainly not succeed.
    3. A flatten that skips a position, which §21.6 makes a Sev-1 arriving as an omission.
    """
    signal = _phase5_signal()
    positions = tuple(
        OpenPosition(
            f"X-{state.value}",
            signal.shares,
            signal.levels.entry_price,
            signal.levels.stop_price,
            state,
            "g",
        )
        for state in sorted(OPEN_STATES, key=list(PositionState).index)
    )
    directives = flatten_all(positions, ExitReason.KILL_SWITCH)

    assert len(directives) == len(positions), "a flatten may not silently skip a position"
    for directive in directives:
        assert directive.to_state in (None, PositionState.CLOSED)
        if directive.representable:
            assert directive.commit() is PositionState.CLOSED
        else:
            with pytest.raises(IllegalTransitionError):
                directive.commit()

    blocked = unrepresentable(directives)
    assert blocked, "if §20.12 gained the missing edges, PHASE-6-DESIGN §6 finding 2 is stale"
    assert {d.from_state for d in blocked} == unrepresentable_flatten_states(ExitReason.KILL_SWITCH)
    # And the set is derived from `reachable_exit_reasons`, not re-walked here: flipping the
    # question for a reason §20.12 *can* express from more states must change the answer.
    assert unrepresentable_flatten_states(ExitReason.STOPPED_OUT) < unrepresentable_flatten_states(
        ExitReason.KILL_SWITCH
    )


@pytest.mark.spec
def test_monitor_evaluates_every_rule_for_its_point_and_cannot_silently_drop_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§9.2's *"every rule checked, for audit"*, at §7's non-pre-order points.

    Performs the violation, the same way the ``approve`` fixture does. The version of this
    guarantee that asserts a *length* passes with a rule swapped for another, which is a shape
    the length check cannot see at all — so the mutation below **mislabels** one row rather than
    removing it: §7 asks that every row be checked, and a trace with row 11's name against row
    2's arithmetic is two rules missing, not one.
    """
    state = risk_state(_open_session())
    for point, rows in RULES_AT.items():
        expected = (
            rows if point is EnforcementPoint.ANY else (*rows, *RULES_AT[EnforcementPoint.ANY])
        )
        decision = monitor_evaluate(state, point, CFG)
        assert tuple(r.rule for r in decision.rules_evaluated) == tuple(
            _ROW_LABELS[row] for row in expected
        ), point

    original = monitor_module._evaluate_row

    def mislabelling(
        row: RiskBlock, state_: RiskState, cfg: Config, *, kill_switch: bool
    ) -> RuleOutcome:
        swapped = RiskBlock.DAILY_LOSS_LIMIT if row is RiskBlock.TRADING_HALTED else row
        return original(swapped, state_, cfg, kill_switch=kill_switch)

    monkeypatch.setattr(monitor_module, "_evaluate_row", mislabelling)
    with pytest.raises(AssertionError, match="did not apply"):
        monitor_evaluate(state, EnforcementPoint.CONTINUOUS, CFG)
    monkeypatch.undo()

    # And §7's Pre-order rows stay `approve`'s: asking for them here must refuse, not restate.
    with pytest.raises(ValueError, match="Pre-order"):
        monitor_evaluate(state, EnforcementPoint.PRE_ORDER, CFG)


@pytest.mark.spec
def test_a_weaker_action_cannot_win_when_a_stronger_rule_breaches_at_the_same_point() -> None:
    """§7's Violation Action must be the strictest breach, never the first one.

    The violation is the under-enforcement: a decision that reports *"lock new entries"* while a
    row demanding *"flatten all"* is also breaching leaves the position open. Both the reason and
    the action are asserted, and the fixture checks they actually differ so it cannot pass by
    coincidence.
    """
    equity = CFG["start_of_day_equity"]
    state = RiskState(
        start_of_day_equity=equity,
        consecutive_losses=int(CFG["max_consecutive_losses"]),
    )
    decision = monitor_evaluate(state, EnforcementPoint.POST_TRADE_CLOSE, CFG, kill_switch=True)
    assert decision.reason is RiskBlock.LOSS_STREAK_LOCKOUT
    assert decision.action is HaltAction.FLATTEN_AND_HALT
    assert ACTION_FOR[decision.reason] is HaltAction.LOCK_NEW_ENTRIES, (
        "this fixture is vacuous unless the first-breach action and the strictest one differ"
    )
    assert decision.flatten and decision.locks


@pytest.mark.spec
def test_row_eight_locks_tomorrow_and_must_not_lock_today() -> None:
    """§7 row 8's action is *"Lock account **next** day"*, and locking today would be wrong.

    The violation is the over-enforcement, which is the direction the other four actions make
    tempting: every other locking action binds the session it fires in.
    """
    equity = CFG["start_of_day_equity"]
    over = D(1) + D(2) * CFG["multi_day_dd_pct"]
    state = record_multi_day_peak(_open_session(), [equity * over], CFG)
    decision = monitor_evaluate(risk_state(state), EnforcementPoint.END_OF_DAY, CFG)
    assert decision.action is HaltAction.LOCK_ACCOUNT_NEXT_DAY

    carried = monitor_apply(state, decision)
    assert carried.phase is SessionPhase.TRADING, "§7 row 8 must not lock the session it fires in"
    assert carried.locks_next_session
    assert approve(_phase5_signal(), risk_state(carried), CFG).reason is not (
        RiskBlock.TRADING_HALTED
    )

    tomorrow = record_snapshot(open_session("2026-08-04", carried_lock=decision.reason), equity)
    assert tomorrow.phase is SessionPhase.LOCKED


@pytest.mark.spec
@pytest.mark.parametrize("module", ["daily.py", "monitor.py"])
def test_the_phase_6_layer_reads_nothing_and_imports_nothing_that_could(module: str) -> None:
    """D30, extended to Phase 6's two modules — an allowlist, not a denylist.

    The layer that persists §10's row is the one most likely to want a database, so ``sqlite3``
    being absent from the list below is the load-bearing part. Note what else is absent and
    would be the first reach for a *"Continuous (1 sec)"* loop: ``time``, ``datetime``,
    ``asyncio``, ``threading``, ``sched``.
    """
    tree = ast.parse((SRC / module).read_text(encoding="utf-8"))
    permitted = {
        "__future__",
        "collections.abc",
        "dataclasses",
        "decimal",
        "enum",
        "types",
        "typing",
    }
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module)
        elif isinstance(node, ast.Import):
            roots.update(a.name for a in node.names)
    outside = {r for r in roots if not r.startswith("tradipy")} - permitted
    assert not outside, f"{module} imports outside its allowlist: {sorted(outside)}"

    reads = [
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"
    ]
    assert not reads, f"{module} opens a file; §7's state is supplied, not sensed (D30)"


@pytest.mark.spec
def test_the_guarantee_phase_6_cannot_make_is_still_absent() -> None:
    """docs/PHASE-6-DESIGN.md §1.1 states §7.1.2's **durability** as unclosed. Pin the absence.

    The arithmetic half is built — :func:`tradipy.daily.to_row` and
    :func:`tradipy.daily.from_row` — and the store half is refused. A guarantee documented as
    unclosed and then quietly closed is as much a drift as the reverse, which is the sixth defect
    class from the other side. If this starts failing, the design document is what needs editing.

    **Detected by AST, not by substring.** The Phase 5 version of this fixture searched the
    source text for ``"open("`` and ``"Path("``, which reports a docstring *describing* a
    guarantee as a violation of it — and this module's docstrings describe exactly that. A
    ``datetime`` named in prose is not a clock; a ``datetime`` imported is. The import half is
    :func:`test_the_phase_6_layer_reads_nothing_and_imports_nothing_that_could` above; this is
    the call half.
    """
    forbidden_calls = {"open", "connect", "dump", "dumps", "load", "loads", "write_text"}
    for name in ("daily.py", "monitor.py"):
        tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
        called = {
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute)
        }
        offending = called & forbidden_calls
        assert not offending, f"{name} calls {sorted(offending)}; §7.1.2 has no store here (D30)"

    # `to_row` produces a value; nothing writes it, and there is no loader that finds a row.
    assert isinstance(to_row(_open_session()), dict)
    assert not [n for n in dir(DailyState) if "load" in n or "save" in n]


@pytest.mark.boundary
def test_every_phase_6_threshold_has_a_boundary_fixture() -> None:
    """Guard on the guard: PHASE-6-DESIGN §8's boundary claim must be *derived*.

    Same argument as the Phase 5 version — the coverage set is computed from the source rather
    than counted by a reader, because PHASE-4-DESIGN's *"six of nine"* was counted by a reader.

    Scope, stated because an unqualified claim about a checker is what F8 was about: this asserts
    each name appears inside a ``@pytest.mark.boundary`` block. It cannot verify the fixture
    exercises the *limit* rather than mentioning the parameter; that is a review judgement, and
    PHASE-6-DESIGN §8 is where the enumeration is recorded.
    """
    assert set(PARAMS) >= _PHASE_6_ROWS, "a name here is not registered — the list is stale"
    suite = Path(__file__).resolve().parent / "test_phase6.py"
    blocks = [
        block
        for block in suite.read_text(encoding="utf-8").split("\n@pytest.mark.")
        if block.startswith("boundary")
    ]
    assert blocks, "no boundary-marked fixtures found — check the split, not the result"
    covered = {row for row in _PHASE_6_ROWS for block in blocks if row in block}
    assert covered == _PHASE_6_ROWS, f"no boundary fixture names: {sorted(_PHASE_6_ROWS - covered)}"


@pytest.mark.spec
def test_the_phase_6_rows_are_the_ones_the_registry_gained() -> None:
    """Guard on the guard for the list above: it must be the actual Phase 6 additions.

    Derived from the registry's own ``source`` citations rather than trusted, so a row added to
    Phase 6's block in ``params.py`` without a boundary fixture fails rather than being invisible
    to the check written to catch exactly that.
    """
    cited = {
        name
        for name, p in PARAMS.items()
        if "§21.4" in p.source or "multi-day drawdown row" in p.source
    }
    assert cited == _PHASE_6_ROWS, (
        f"registry rows citing Phase 6's sections: {sorted(cited)}, list says "
        f"{sorted(_PHASE_6_ROWS)}"
    )
