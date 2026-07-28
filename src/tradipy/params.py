"""Parameter registry — the single source of truth for every tunable threshold.

Normative sources: PRD §2 (thresholds), §2.0 (previously undefined parameters and mode
presets), §3.1.2 (separation floor), §3.1.3 (spread gates).

**Why this module exists.** Four review rounds of this specification found four distinct
defect classes, and every one was ultimately the same thing: a quantity expressed in more
than one place, where the copies drifted apart. The most expensive was `room_gate_multiple`
raised to 2.5 in two sections while all three setup criteria still read `2 ×`.

The rule this module enforces is therefore: **a threshold is defined here exactly once,
and every consumer reads it by name.** No numeric literal for a registered threshold may
appear anywhere else in the codebase. `tests/test_parameter_registry.py` enforces the same
discipline against the prose in docs/PRD.md.

Each parameter carries its **polarity** (PRD §20.13) where it is used as a gate threshold,
because rounding direction is a property of the constraint, not of the call site.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal

from tradipy.rounding import TICK_SIZE, Polarity, floor_to_tick

__all__ = [
    "Param",
    "PARAMS",
    "Config",
    "MODE_PRESETS",
    "HARD_CAPS",
    "DISCRIMINATING_CAP_TICKS",
    "signal_cap_ticks_at_min_r",
    "min_tradeable_price_from_stop_bounds",
    "validate_couplings",
    "CouplingError",
]


@dataclass(frozen=True)
class Param:
    """A registered threshold: its default, its legal range, and its constraint polarity."""

    name: str
    default: Decimal
    lo: Decimal
    hi: Decimal
    unit: str
    source: str
    polarity: Polarity | None = None

    # A `hard: bool` field lived here, set only on `room_gate_multiple` and read nowhere.
    # It was not merely dead but wrong: it claimed a §7 non-bypassable bound, while
    # `with_overrides(room_gate_multiple=...)` is exercised in two tests. The genuine
    # non-bypassable ceilings are in `HARD_CAPS`, which `validate_couplings` enforces.

    def validate(self, value: Decimal) -> None:
        if not (self.lo <= value <= self.hi):
            raise ValueError(
                f"{self.name}={value} outside legal bounds [{self.lo}, {self.hi}] ({self.source})"
            )


def _p(name: str, default: str, lo: str, hi: str, unit: str, source: str, **kw) -> Param:
    return Param(name, Decimal(default), Decimal(lo), Decimal(hi), unit, source, **kw)


# ---------------------------------------------------------------------------
# Registry. Values and bounds transcribed from the PRD tables cited in `source`.
# ---------------------------------------------------------------------------
PARAMS: dict[str, Param] = {p.name: p for p in [
    # --- §2.0 previously undefined parameters -----------------------------
    _p("start_of_day_equity", "30000", "25000", "10000000", "USD", "PRD §2.0 / A5"),
    _p("session_dd_pct", "0.04", "0.02", "0.10", "fraction", "PRD §2.0"),
    _p("multi_day_dd_pct", "0.08", "0.05", "0.20", "fraction", "PRD §2.0"),
    _p("max_bp_usage_pct", "0.50", "0.10", "1.00", "fraction", "PRD §2.0"),
    _p("max_shares_per_order", "10000", "100", "100000", "shares", "PRD §2.0"),
    _p("max_pct_of_adv", "0.01", "0.001", "0.05", "fraction", "PRD §2.0"),
    _p("room_gate_multiple", "2.5", "2.0", "3.0", "xR", "PRD §2.0 / §3.1.1 / D14",
       polarity=Polarity.MINIMUM),
    _p("min_stop_distance", "0.10", "0.01", "1.00", "USD", "PRD §2.0",
       polarity=Polarity.MINIMUM),
    _p("max_stop_pct", "0.05", "0.01", "0.10", "fraction", "PRD §2.0",
       polarity=Polarity.MAXIMUM),

    # --- §3.1.3 spread gates ----------------------------------------------
    _p("max_spread_abs", "0.02", "0.01", "0.10", "USD", "PRD §2.0 / §3.1.3 / D20",
       polarity=Polarity.MAXIMUM),
    _p("max_spread_pct", "0.005", "0.001", "0.020", "fraction", "PRD §2.0 / §3.1.3 / D20",
       polarity=Polarity.MAXIMUM),
    _p("max_spread_r", "0.15", "0.05", "0.50", "xR", "PRD §2.0 / §3.1.3 / D20",
       polarity=Polarity.MAXIMUM),

    # --- §3.1.2 separation floor ------------------------------------------
    _p("sep_cost_multiple", "3.0", "1.0", "10.0", "x cost", "PRD §2.0 / §3.1.2 / D17"),
    _p("est_round_trip_cost_per_share", "0.015", "0.001", "0.10", "USD",
       "PRD §2.0 / §3.1.2 / A18"),
    _p("min_sep_r", "0.5", "0.0", "2.0", "xR", "PRD §2.0 / §3.1.2"),

    # --- §2 quantitative thresholds ---------------------------------------
    _p("min_gap_premarket_pct", "0.04", "0.01", "0.50", "fraction", "PRD §2 / D3"),
    _p("min_gap_daily_pct", "0.10", "0.01", "0.50", "fraction", "PRD §2 / D3"),
    _p("min_rvol", "5.0", "1.0", "50.0", "x ADV", "PRD §2 / A8 / D2",
       polarity=Polarity.MINIMUM),
    _p("rvol_lookback_days", "30", "5", "200", "sessions", "PRD §2.1 / A8 / D2"),
    _p("max_float_shares", "20000000", "1000000", "500000000", "shares", "PRD §2 / D4",
       polarity=Polarity.MAXIMUM),
    _p("min_price", "1.00", "1.00", "100.00", "USD", "PRD §2"),
    _p("max_price", "20.00", "2.00", "1000.00", "USD", "PRD §2"),
    _p("min_adv_shares", "500000", "50000", "50000000", "shares", "PRD §2",
       polarity=Polarity.MINIMUM),
    _p("max_vwap_extension_pct", "0.03", "0.005", "0.20", "fraction", "PRD §2 / A7",
       polarity=Polarity.MAXIMUM),
    _p("t1_r_multiple", "2.0", "1.0", "5.0", "xR", "PRD §3.1.1 / D12"),

    # PRD §3.4 states this as a bare `VWAP × 0.99` with no named parameter and no entry
    # in §2 or §2.0 — the only threshold in the MVP path that is an unregistered literal.
    # Registered here so the stop chain has a single source of truth; flagged for the PRD
    # in tests/test_parameter_registry.py::test_unregistered_literals_in_prd.
    _p("vwap_stop_band_pct", "0.01", "0.001", "0.10", "fraction", "PRD §3.4 (unnamed literal)",
       polarity=Polarity.MAXIMUM),

    # --- §20.1 bar timing --------------------------------------------------
    _p("bar_close_grace_ms", "750", "100", "5000", "ms", "PRD §2.0 / §20.1"),

    # --- §20.14 spread validity -------------------------------------------
    _p("quote_stale_seconds", "2", "1", "10", "s", "PRD §20.14",
       polarity=Polarity.MAXIMUM),
    _p("min_quote_size", "100", "100", "10000", "shares", "PRD §20.14",
       polarity=Polarity.MINIMUM),
]}


# PRD §2.0 mode presets. `experienced` risk has a hard cap of 2.0% (§2, §7).
MODE_PRESETS: dict[str, dict[str, Decimal]] = {
    "beginner": {
        "max_risk_per_trade_pct": Decimal("0.005"),
        "daily_loss_pct": Decimal("0.02"),
        "max_open_positions": Decimal("1"),
        "max_consecutive_losses": Decimal("2"),
    },
    "experienced": {
        "max_risk_per_trade_pct": Decimal("0.01"),
        "daily_loss_pct": Decimal("0.03"),
        "max_open_positions": Decimal("3"),
        "max_consecutive_losses": Decimal("3"),
    },
}

#: PRD §2 / §7: non-bypassable ceilings, independent of mode.
HARD_CAPS: dict[str, Decimal] = {
    "max_risk_per_trade_pct": Decimal("0.02"),
    "daily_loss_pct": Decimal("0.05"),
    "max_open_positions": Decimal("3"),
}


class CouplingError(ValueError):
    """Raised when two individually-legal parameters cannot both hold.

    This is the v1.3 defect class (PLAN Workstream 11): *joint incoherence*. Every value
    is inside its own bounds and defensible alone, so per-parameter validation passes it
    clean. The §4.2 spread filter admitting 1% of price while §3.1.2's separation floor
    consumed spread as an input was the original instance.
    """


@dataclass(frozen=True)
class Config:
    """A validated parameter set. Every construction path validates; there is no other.

    Three things had to hold together before that sentence was true, and each failed
    separately:

    1. ``frozen=True`` freezes the *attribute binding*, not the dict behind it, so
       ``cfg.values[...] = ...`` mutated a "frozen" config in place.
    2. ``MappingProxyType`` is a **view, not a copy**. Wrapping conditionally — skipping the
       copy when the caller already passed a proxy — let ``Config(MappingProxyType(d))``
       retain a live handle to ``d``, so mutating ``d`` afterwards changed the config. The
       copy is now unconditional; ``dict()`` of a proxy is already a copy, so the guard
       bought nothing and cost the invariant.
    3. Only ``default()`` and ``with_overrides()`` called :func:`validate_couplings`, so
       direct construction accepted any combination — including the exact A25 pair the
       validator exists to reject. Validation now runs in ``__post_init__``, which is the
       only place that cannot be routed around.

    Consequence of (3), accepted deliberately: ``values`` must be **complete**. A partial
    dict now raises ``ValueError`` rather than surfacing a ``KeyError`` from inside the
    validator, on the grounds that a ``Config`` missing ``room_gate_multiple`` is not a
    config. Nothing in the package constructed a partial one.
    """

    values: Mapping[str, Decimal]
    mode: Literal["beginner", "experienced"] = "experienced"

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        missing = sorted(set(PARAMS) - set(self.values))
        if missing:
            raise ValueError(
                f"Config is missing {len(missing)} registered parameter(s): "
                f"{', '.join(missing)}. Build from Config.default() or with_overrides()."
            )
        validate_couplings(self)

    def __getitem__(self, name: str) -> Decimal:
        if name in self.values:
            return self.values[name]
        preset = MODE_PRESETS[self.mode]
        if name in preset:
            return preset[name]
        raise KeyError(f"{name} is not a registered parameter (PRD §2 / §2.0)")

    def polarity(self, name: str) -> Polarity:
        p = PARAMS[name].polarity
        if p is None:
            raise ValueError(
                f"{name} has no declared polarity; PRD §20.13 requires classification "
                "as MINIMUM or MAXIMUM before a rounding function is chosen"
            )
        return p

    @classmethod
    def default(cls, mode: Literal["beginner", "experienced"] = "experienced") -> "Config":
        # __post_init__ validates; no second call needed.
        return cls({n: p.default for n, p in PARAMS.items()}, mode=mode)

    def with_overrides(self, **overrides: str | int | float | Decimal) -> "Config":
        vals = dict(self.values)
        for name, raw in overrides.items():
            if name not in PARAMS:
                raise KeyError(f"{name} is not a registered parameter (PRD §2 / §2.0)")
            value = Decimal(str(raw))
            PARAMS[name].validate(value)
            vals[name] = value
        return Config(vals, mode=self.mode)

    # `with_overrides_unchecked` was removed. It had zero callers, and the use it
    # documented — reaching an unsound combination to assert it is unsound — is served by
    # `with_overrides` plus `pytest.raises(CouplingError)`, which is what
    # `test_coupling_validator_rejects_the_legal_but_unsound_combination` already does. It
    # could not survive validation moving into `__post_init__` anyway: an escape hatch that
    # constructs a `Config` is exactly the hole that change closes.


#: Minimum ticks the signal-time spread cap must be wide for the gate to *discriminate*
#: rather than admit exactly one value. See :func:`signal_cap_ticks_at_min_r` — the shipped
#: defaults yield 1, not 2, so this is recorded as an aspiration and not enforced.
DISCRIMINATING_CAP_TICKS = 2


def signal_cap_ticks_at_min_r(cfg: Config) -> int:
    """How many ticks wide the §3.1.3 signal-time spread cap is at the tightest legal R.

    At the shipped defaults (``max_spread_r`` 0.15, ``min_stop_distance`` $0.10) this is
    **1** — the clamp floor. A one-tick-wide maximum admits exactly one value, so for
    minimum-R trades the gate is pass/fail on a single spread rather than a threshold.
    """
    raw = cfg["max_spread_r"] * cfg["min_stop_distance"]
    return int(max(TICK_SIZE, floor_to_tick(raw)) / TICK_SIZE)


def min_tradeable_price_from_stop_bounds(cfg: Config) -> Decimal:
    """Lowest entry price at which the min-stop floor and max-stop ceiling can both hold.

    ``min_stop_distance / max_stop_pct`` — **$2.00 at shipped defaults.** Below it the floor
    widens every stop to $0.10, which exceeds ``max_stop_pct × entry``, so
    :func:`tradipy.gates.apply_stop_floor_and_ceiling` returns ``STOP_TOO_WIDE`` for *every*
    entry regardless of setup quality. ``min_price`` defaults to $1.00, so §2 admits a
    $1.00–$1.99 band that the stop arithmetic empties.

    **Why this is not a :func:`validate_couplings` check.** It is the same joint-incoherence
    shape as A25 and reaches the same wall: the incoherent combination *is* the shipped
    default set, so raising here would make :meth:`Config.default` throw and take every call
    path in the package with it. A25's recommended factor-2 validator has exactly this
    defect, and this module already declined to enforce it for exactly this reason —
    enforcing this one would be the same mistake with the sign flipped.

    Resolving it is a spec decision, not a module decision: raise ``min_price`` to $2.00,
    make ``max_stop_pct`` price-dependent, or lower ``min_stop_distance`` below
    ``max_stop_pct × min_price`` = $0.05 (which A25's coupling then rejects). Pinned as a
    documented open finding in ``tests/test_boundary.py`` and ``tests/README.md``.
    """
    return cfg["min_stop_distance"] / cfg["max_stop_pct"]


def validate_couplings(cfg: Config) -> None:
    """Reject parameter combinations that are individually legal but jointly incoherent.

    A25 / PRD §3.1.3: the signal-time spread cap is ``floor_to_tick(max_spread_r * R)``,
    which returns $0.00 for any ``R < TICK_SIZE / max_spread_r``. The one-tick clamp in
    :func:`tradipy.rounding.round_threshold` prevents the resulting total outage, but a
    configuration that relies on the clamp is trading sub-$0.07 stops against a spread that
    is ~30% of R round-trip.

    **Discrepancy inside A25, found by implementing it.** A25's prose identifies the outage
    boundary as ``R < tick_size / max_spread_r`` — $0.0667 at defaults, a factor of **1**.
    Its recommended validator, however, is stated as::

        min_stop_distance >= 2 * tick_size / max_spread_r     # factor of 2 -> $0.1333

    The shipped default ``min_stop_distance`` is **$0.10**, so *A25's recommended validator
    rejects the PRD's own default configuration.* Satisfying it would require raising
    ``min_stop_distance`` to $0.14 or ``max_spread_r`` to 0.20 — both of which change trading
    behaviour and are therefore decisions for the spec, not for this module.

    Resolution taken here: **enforce factor 1**, which is the invariant A25's own boundary
    analysis establishes and which the defaults satisfy. The factor-2 property — a cap at
    least two ticks wide, so the gate discriminates instead of admitting a single value — is
    exposed separately via :func:`signal_cap_ticks_at_min_r` and asserted as a *documented
    current state* in ``tests/test_boundary.py``, not silently enforced or silently dropped.
    """
    min_stop = cfg["min_stop_distance"]
    max_spread_r = cfg["max_spread_r"]
    required = TICK_SIZE / max_spread_r
    if min_stop < required:
        raise CouplingError(
            f"min_stop_distance={min_stop} is too tight for max_spread_r={max_spread_r}: "
            f"the signal-time spread cap would floor to $0.00 and reject every trade "
            f"(need min_stop_distance >= {required:.4f}). "
            "See PRD §3.1.3 and A25 — this is a coupling, not two independent bounds."
        )

    # PRD §2 / §7: mode presets may not exceed the non-bypassable hard caps.
    for name, cap in HARD_CAPS.items():
        if MODE_PRESETS[cfg.mode][name] > cap:
            raise CouplingError(
                f"mode '{cfg.mode}' sets {name}={MODE_PRESETS[cfg.mode][name]} above the "
                f"non-bypassable cap {cap} (PRD §7)"
            )

    # PRD §3.1.1: room_gate_multiple cannot go below 2.0, and T1 sits at 2R, so a
    # multiple at or under t1_r_multiple would make the proportional term vacuous.
    if cfg["room_gate_multiple"] <= cfg["t1_r_multiple"]:
        raise CouplingError(
            f"room_gate_multiple={cfg['room_gate_multiple']} must exceed "
            f"t1_r_multiple={cfg['t1_r_multiple']}: T1 is defined at "
            f"{cfg['t1_r_multiple']}R, so an equal multiple leaves T2 no room above T1 "
            "(PRD §3.1.1, §3.1.2)"
        )
