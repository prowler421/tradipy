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
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.spike2a import provenance, q2_float, q3_latency, q4_spreads
from scripts.spike2a.feeds import QuoteSample
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
        roots: list[str] = []
        if isinstance(node, ast.Import):
            roots = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots = [node.module.split(".")[0]]
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
    assert provenance.PERMITTED_ORIGINS == frozenset({provenance.DataOrigin.SIMULATED}), (
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
    with pytest.raises(provenance.UndeclaredProvenanceError, match="no PROVENANCE.txt"):
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
    bars.write_text("symbol,session,setup,price,r\nAXTI,2026-07-07,bull_flag,10.00,0.30\n", "utf-8")
    quotes = directory / "quotes.csv"
    quotes.write_text(
        "symbol,captured_at,bid,ask,bid_size,ask_size\n"
        "AXTI,2026-07-07T13:31:00+00:00,10.00,10.02,100,100\n",
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
def test_the_declare_cli_unblocks_input_that_has_no_generator(tmp_path: Path) -> None:
    """``floats.csv`` and ``latency.csv`` have no generator, so without this they are unreadable.

    A gate with no supported way past it is not a gate, it is an outage — and the documented Q2
    and Q3 commands both failed with exit 3 until this existed.
    """
    latency = tmp_path / "latency.csv"
    latency.write_text("kind,seconds\ndata_to_signal,0.4\n", encoding="utf-8")
    assert q3_latency.main([str(latency)]) == 3

    assert provenance._main([str(latency)]) == 0
    assert q3_latency.main([str(latency)]) == 0
