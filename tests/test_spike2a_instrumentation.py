"""Calibrate Phase 2a instrumentation against the library.

Sixth defect class: code that *produces* a number deciding a spec question is exempt from
every check that protects the code the number is *about*. These tests point at
``scripts/spike2a/`` the way ``test_parameter_registry.py`` points at threshold literals —
not full spike coverage (PHASE-2A-SPIKE §8), but the guarantees the spike docstrings make
about library derivation.
"""

from __future__ import annotations

import ast
import random
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.spike2a.synthetic_data_generator import (
    _ENTRY_PREMIUM,
    SEED,
    generate_signal_bars,
)
from tradipy.gates import apply_stop_floor_and_ceiling
from tradipy.params import Config
from tradipy.quotes import spread_at_signal
from tradipy.rejects import Reject
from tradipy.rounding import ceil_to_tick

REPO = Path(__file__).resolve().parent.parent

_STOP_PCT_BY_SETUP = {
    "bull_flag": Decimal("0.97"),
    "hod_breakout": Decimal("0.96"),
    "vwap_reclaim": Decimal("0.975"),
}


def _sample_preopen() -> list[
    tuple[date, str, Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]
]:
    return [
        (
            date(2026, 7, 29),
            "AXTI",
            Decimal("10.00"),
            Decimal("0.12"),
            Decimal("0.08"),
            Decimal("8"),
            Decimal("1500000"),
            Decimal("5000000"),
        )
    ]


@pytest.fixture
def seeded() -> None:
    random.seed(SEED)


def test_generate_signal_bars_calls_apply_stop_floor_and_ceiling() -> None:
    """``generate_signal_bars`` must call the library stop function, not only mention it."""
    path = REPO / "scripts" / "spike2a" / "synthetic_data_generator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    func = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "generate_signal_bars"
    )
    called: set[str] = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
    assert "apply_stop_floor_and_ceiling" in called, (
        "generate_signal_bars must derive stops via apply_stop_floor_and_ceiling, "
        "not a hand-written fraction"
    )


def test_signal_bar_r_equals_entry_minus_library_stop(seeded: None) -> None:
    """Each emitted R must be entry − stop for the library-constructed stop."""
    cfg = Config.default()
    bars = generate_signal_bars(_sample_preopen())
    assert bars, "fixture pre-open row should yield at least one signal bar"

    for _symbol, _session, setup, price, r in bars:
        stop_pct = _STOP_PCT_BY_SETUP[setup]
        entry = ceil_to_tick(price * _ENTRY_PREMIUM)
        stop, reject = apply_stop_floor_and_ceiling(entry, price * stop_pct, cfg)
        assert reject is None
        assert r == entry - stop


def test_signal_bars_drop_stops_the_library_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bars whose stop ``apply_stop_floor_and_ceiling`` rejects must not appear in output."""
    random.seed(SEED)

    def reject_all(entry: Decimal, raw_stop: Decimal, cfg: Config) -> tuple[Decimal, Reject | None]:
        _ = (entry, raw_stop, cfg)
        return raw_stop, Reject.STOP_TOO_WIDE

    monkeypatch.setattr(
        "scripts.spike2a.synthetic_data_generator.apply_stop_floor_and_ceiling",
        reject_all,
    )
    assert generate_signal_bars(_sample_preopen()) == []


def test_q4_spreads_uses_library_cap_and_spread_functions() -> None:
    """Q4 must import the shipped cap and spread functions, not reimplement them."""
    from scripts.spike2a import q4_spreads
    from tradipy.gates import spread_caps

    assert q4_spreads.spread_caps is spread_caps
    assert q4_spreads.spread_at_signal is spread_at_signal
