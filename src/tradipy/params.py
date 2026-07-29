"""Parameter registry — the single source of truth for every tunable threshold.

Normative sources: PRD §2 (thresholds), §2.0 (previously undefined parameters and mode
presets), §3.1.2 (separation floor), §3.1.3 (spread gates), §20.10 (composite score),
§20.14 (quote validity).

**Why this module exists.** Four review rounds of this specification found four distinct
defect classes, and every one was ultimately the same thing: a quantity expressed in more
than one place, where the copies drifted apart. The most expensive was `room_gate_multiple`
raised to 2.5 in two sections while all three setup criteria still read `2 ×`.

The rule this module enforces is therefore: **a threshold is defined here exactly once,
and every consumer reads it by name.** No numeric literal for a registered threshold may
appear anywhere else in the codebase. `tests/test_parameter_registry.py` enforces the same
discipline against the prose in docs/PRD.md.

Each parameter carries its **polarity** (PRD §20.13) where it is used as a gate threshold,
because rounding direction is a property of the constraint, not of the call site. As of
v0.1.0 :mod:`tradipy.gates` reads that field rather than naming a `Polarity` member at the
call site, so the declaration below is load-bearing rather than documentary.

**Immutability.** ``PARAMS``, ``MODE_PRESETS`` and ``HARD_CAPS`` are read-only mappings, and
the inner preset dicts are wrapped too. Before v0.1.0 they were plain dicts read *live* by
``Config.__getitem__``, so a single assignment could raise an already-validated config's
risk-per-trade past the §7 non-bypassable cap without any validator re-running. A frozen
dataclass in front of a mutable module global is not frozen.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Literal, get_args

from tradipy.rounding import TICK_SIZE, Polarity, floor_to_tick

__all__ = [
    "Param",
    "PARAMS",
    "Mode",
    "MODES",
    "Config",
    "MODE_PRESETS",
    "HARD_CAPS",
    "DISCRIMINATING_CAP_TICKS",
    "signal_cap_ticks_at_min_r",
    "min_tradeable_price_from_stop_bounds",
    "validate_couplings",
    "CouplingError",
]

#: PRD §2.0. ``beginner`` is the declared default; see :meth:`Config.default`.
Mode = Literal["beginner", "experienced"]

#: The legal mode strings, derived from :data:`Mode` so the two cannot drift apart.
MODES: tuple[str, ...] = get_args(Mode)


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
# Registry. Values and bounds transcribed from the PRD tables cited in `source`, **except**
# where the cited table has no bounds column — §2, §3.1.1, §3.4, §20.10 and §20.14 state
# defaults only, so the `lo`/`hi` on those rows are code-originated and are marked
# `(bounds: code)` in `source`. The distinction matters: a transcribed bound is a spec fact,
# an originated one is this module's judgement and can be revised here.
#
# Formatting is fenced off here, and only here. This is a transcription of the PRD tables,
# and reviewing it means reading it against them row by row; one call per line keeps the
# columns comparable. Ruff's formatter expands any call carrying a `polarity=` keyword to
# one argument per line, which turns 47 rows into ~300 lines and hides the grouping comments.
# Everything outside this fence is Ruff's to format — do not widen the exemption.
# ---------------------------------------------------------------------------
# fmt: off
_REGISTRY: list[Param] = [
    # --- §2.0 previously undefined parameters -----------------------------
    _p("start_of_day_equity", "30000", "25000", "10000000", "USD",
       "PRD §2.0 / A5 (upper bound: code)"),
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
    # All three are MINIMUM: the floor they define is a bar that T2-T1 must clear, so
    # rounding any of them down would weaken it. `est_round_trip_cost_per_share` is an
    # estimate rather than a gate, but understating a cost weakens the same constraint,
    # so it carries the same polarity (PRD §20.13's "classify before choosing").
    _p("sep_cost_multiple", "3.0", "1.0", "10.0", "x cost", "PRD §2.0 / §3.1.2 / D17",
       polarity=Polarity.MINIMUM),
    _p("est_round_trip_cost_per_share", "0.015", "0.001", "0.10", "USD",
       "PRD §2.0 / §3.1.2 / A18", polarity=Polarity.MINIMUM),
    _p("min_sep_r", "0.5", "0.0", "2.0", "xR", "PRD §2.0 / §3.1.2",
       polarity=Polarity.MINIMUM),

    # --- §2 quantitative thresholds ---------------------------------------
    # §2 has no bounds column; every lo/hi in this block is code-originated.
    _p("min_gap_premarket_pct", "0.04", "0.01", "0.50", "fraction",
       "PRD §2 / D3 (bounds: code)"),
    _p("min_gap_daily_pct", "0.10", "0.01", "0.50", "fraction", "PRD §2 / D3 (bounds: code)"),
    _p("min_rvol", "5.0", "1.0", "50.0", "x ADV", "PRD §2 (bounds: code)",
       polarity=Polarity.MINIMUM),
    _p("rvol_lookback_days", "30", "5", "200", "sessions",
       "PRD §2.1 / A8 / D2 (bounds: code)"),
    _p("max_float_shares", "20000000", "1000000", "500000000", "shares",
       "PRD §2 / D4 (bounds: code)", polarity=Polarity.MAXIMUM),
    _p("min_price", "1.00", "1.00", "100.00", "USD", "PRD §2 (bounds: code)"),
    _p("max_price", "20.00", "2.00", "1000.00", "USD", "PRD §2 (bounds: code)"),
    _p("min_adv_shares", "500000", "50000", "50000000", "shares", "PRD §2 (bounds: code)",
       polarity=Polarity.MINIMUM),
    _p("min_premarket_volume", "100000", "10000", "10000000", "shares",
       "PRD §2 (bounds: code)", polarity=Polarity.MINIMUM),
    _p("max_vwap_extension_pct", "0.03", "0.005", "0.20", "fraction",
       "PRD §2 / A7 (bounds: code)", polarity=Polarity.MAXIMUM),
    _p("max_vwap_extension_open_pct", "0.05", "0.005", "0.30", "fraction",
       "PRD §2 first-30-min branch (bounds: code)", polarity=Polarity.MAXIMUM),
    _p("hod_proximity_pct", "0.005", "0.001", "0.05", "fraction",
       "PRD §2 Max Extension from HOD (bounds: code)", polarity=Polarity.MAXIMUM),
    # Lower bound 2.0, not 1.0: §2 states "Target 1: 2R (**minimum**)" and §1 makes the
    # 2:1 reward-to-risk floor non-bypassable. At 1.0 the ladder put T1 at 1R and nothing
    # rejected it — D26 removed the last check that incidentally constrained this.
    _p("t1_r_multiple", "2.0", "2.0", "5.0", "xR", "PRD §2 / §3.1.1 / D12 (bounds: code)",
       polarity=Polarity.MINIMUM),

    # --- §2 risk settings (D27) -------------------------------------------
    # Registered so §2's "User-Configurable (within …)" column is true in code. The mode
    # preset overlays the default; `with_overrides` reaches them like any other parameter.
    # The `hi` on the first three is the §7 non-bypassable cap and is asserted equal to
    # `HARD_CAPS` by `test_hard_caps_match_the_registry_ceilings`.
    _p("max_risk_per_trade_pct", "0.01", "0.0025", "0.02", "fraction",
       "PRD §2 configurable range 0.25–2% / §7 / D27", polarity=Polarity.MAXIMUM),
    _p("daily_loss_pct", "0.03", "0.01", "0.05", "fraction",
       "PRD §2 configurable range 1–5% / §7 / D27", polarity=Polarity.MAXIMUM),
    _p("max_open_positions", "1", "1", "3", "positions",
       "PRD §2 configurable range, hard ceiling 3 / §7 / D27", polarity=Polarity.MAXIMUM),
    _p("max_consecutive_losses", "3", "2", "5", "losses",
       "PRD §2 configurable range 2–5 / D27", polarity=Polarity.MAXIMUM),

    # PRD §3.4 states this as a bare `VWAP × 0.99` with no named parameter and no entry
    # in §2 or §2.0 — the only threshold in the MVP path that is an unregistered literal.
    # Registered here so the stop chain has a single source of truth; flagged for the PRD
    # in tests/test_parameter_registry.py::test_unregistered_literals_in_prd_mvp_path.
    _p("vwap_stop_band_pct", "0.01", "0.001", "0.10", "fraction",
       "PRD §3.4 (unnamed literal; bounds: code)", polarity=Polarity.MAXIMUM),

    # --- §20.1 bar timing --------------------------------------------------
    _p("bar_close_grace_ms", "750", "100", "5000", "ms", "PRD §2.0 / §20.1"),

    # --- §20.10 composite score -------------------------------------------
    # Five weights and four normalization caps, all stated as literals in §20.10's code
    # block. §20.10 calls the caps "configurable and should be revisited against real
    # scanner output in Phase 3", which is what makes them parameters rather than constants.
    _p("score_weight_pct_change", "0.30", "0.0", "1.0", "weight", "PRD §20.10 (bounds: code)"),
    _p("score_weight_rvol", "0.30", "0.0", "1.0", "weight", "PRD §20.10 (bounds: code)"),
    _p("score_weight_float", "0.20", "0.0", "1.0", "weight", "PRD §20.10 (bounds: code)"),
    _p("score_weight_premarket_vol", "0.10", "0.0", "1.0", "weight",
       "PRD §20.10 (bounds: code)"),
    _p("score_weight_catalyst", "0.10", "0.0", "1.0", "weight", "PRD §20.10 (bounds: code)"),
    _p("score_cap_pct_change", "50.0", "1.0", "1000.0", "percent",
       "PRD §20.10 (bounds: code)"),
    _p("score_cap_rvol", "20.0", "1.0", "200.0", "x ADV", "PRD §20.10 (bounds: code)"),
    _p("score_cap_float", "20000000", "1000000", "500000000", "shares",
       "PRD §20.10 (bounds: code)"),
    _p("score_cap_premarket_vol", "1000000", "10000", "100000000", "shares",
       "PRD §20.10 (bounds: code)"),
    # §20.10 encodes the catalyst input as 1.0 confirmed / 0.5 headline-only / 0.0 none.
    # The endpoints are structural — they are the range of a normalized input — but the
    # midpoint is a judgement ("a headline nobody confirmed is worth half"), so it is the
    # one of the three that is registered.
    _p("score_catalyst_headline", "0.5", "0.0", "1.0", "weight", "PRD §20.10 (bounds: code)"),
    _p("min_conviction_score", "0.7", "0.0", "1.0", "score",
       "PRD §14.2 conviction gate (bounds: code)", polarity=Polarity.MINIMUM),

    # --- §20.14 spread validity -------------------------------------------
    _p("quote_stale_seconds", "2", "1", "10", "s", "PRD §20.14 (bounds: code)",
       polarity=Polarity.MAXIMUM),
    _p("min_quote_size", "100", "100", "10000", "shares", "PRD §20.14 (bounds: code)",
       polarity=Polarity.MINIMUM),
]
# fmt: on

#: The registry. Read-only: a threshold is defined here and nowhere else, and nothing
#: outside this module may add, remove or rebind a row.
PARAMS: Mapping[str, Param] = MappingProxyType({p.name: p for p in _REGISTRY})


#: PRD §2.0 mode presets — a **bundle of overrides** applied on top of the registry
#: defaults by :meth:`Config.default`, which is what §2.0 calls them ("Preset bundle").
#: Every value here must lie inside its own :class:`Param` bounds; asserted by
#: ``test_mode_presets_are_within_registry_bounds``.
MODE_PRESETS: Mapping[str, Mapping[str, Decimal]] = MappingProxyType(
    {
        "beginner": MappingProxyType(
            {
                "max_risk_per_trade_pct": Decimal("0.005"),
                "daily_loss_pct": Decimal("0.02"),
                "max_open_positions": Decimal("1"),
                "max_consecutive_losses": Decimal("2"),
            }
        ),
        "experienced": MappingProxyType(
            {
                "max_risk_per_trade_pct": Decimal("0.01"),
                "daily_loss_pct": Decimal("0.03"),
                "max_open_positions": Decimal("3"),
                "max_consecutive_losses": Decimal("3"),
            }
        ),
    }
)

#: PRD §2 / §7: non-bypassable ceilings, independent of mode. Each is also the ``hi`` of the
#: corresponding :class:`Param`, so :func:`validate_couplings` cannot currently fire on a
#: config that passed per-parameter validation. That redundancy is deliberate defence in
#: depth and is held in place by ``test_hard_caps_match_the_registry_ceilings``: widening
#: either number without the other breaks CI, and the coupling check starts binding the
#: moment a registry ceiling is raised above a §7 cap.
HARD_CAPS: Mapping[str, Decimal] = MappingProxyType(
    {
        "max_risk_per_trade_pct": Decimal("0.02"),
        "daily_loss_pct": Decimal("0.05"),
        "max_open_positions": Decimal("3"),
    }
)


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

    Four things had to hold together before that sentence was true, and each failed
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
    4. ``__post_init__`` checked *couplings* but never per-parameter **ranges**, which lived
       only in ``with_overrides``. ``Config({**defaults, "max_spread_r": Decimal("99")})``
       was therefore accepted, and the §3.1.3 signal-time gate silently went to $14.85 on a
       $0.15 R. Ranges are now checked here too, before the couplings — a coupling validator
       reasoning about out-of-range inputs produces misleading errors.

    Consequence of (3), accepted deliberately: ``values`` must be **complete**. A partial
    dict now raises ``ValueError`` rather than surfacing a ``KeyError`` from inside the
    validator, on the grounds that a ``Config`` missing ``room_gate_multiple`` is not a
    config. Nothing in the package constructed a partial one.
    """

    values: Mapping[str, Decimal]
    mode: Mode = "beginner"

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        if self.mode not in MODES:
            # `Literal` is a static hint with no runtime effect, and the alternative is a
            # bare `KeyError: 'typo'` escaping from inside validate_couplings — the same
            # failure the completeness check below exists to prevent.
            raise ValueError(f"mode must be one of {MODES}, not {self.mode!r} (PRD §2.0)")

        missing = sorted(set(PARAMS) - set(self.values))
        if missing:
            raise ValueError(
                f"Config is missing {len(missing)} registered parameter(s): "
                f"{', '.join(missing)}. Build from Config.default() or with_overrides()."
            )
        unknown = sorted(set(self.values) - set(PARAMS))
        if unknown:
            raise ValueError(
                f"Config carries {len(unknown)} unregistered name(s): {', '.join(unknown)}. "
                "Every value must correspond to a row in PARAMS (PRD §2 / §2.0)."
            )
        for name, value in self.values.items():
            PARAMS[name].validate(value)
        validate_couplings(self)

    def __getitem__(self, name: str) -> Decimal:
        try:
            return self.values[name]
        except KeyError:
            raise KeyError(f"{name} is not a registered parameter (PRD §2 / §2.0)") from None

    def polarity(self, name: str) -> Polarity:
        """The declared rounding direction for ``name`` (PRD §20.13).

        :mod:`tradipy.gates` routes every ``round_threshold`` call through this rather than
        naming a :class:`~tradipy.rounding.Polarity` member, so the registry field is the
        single source of truth for direction as well as for value. Naming the member at the
        call site gave polarity two definitions that nothing reconciled — the v1.3.1 defect
        class reproduced inside the mechanism built to close it.
        """
        p = PARAMS[name].polarity
        if p is None:
            raise ValueError(
                f"{name} has no declared polarity; PRD §20.13 requires classification "
                "as MINIMUM or MAXIMUM before a rounding function is chosen"
            )
        return p

    @classmethod
    def default(cls, mode: Mode = "beginner") -> Config:
        """Registry defaults with the PRD §2.0 mode preset overlaid.

        ``beginner`` is the default because PRD §2.0 says so. The PRD's own worked examples
        (§2.2, §3.2, §3.3, §3.4) all compute risk as 1% × $30,000, which is the *experienced*
        preset, so they pass ``mode="experienced"`` explicitly — see D28 in
        docs/CHANGELOG.md for why the document's declared default won over its examples.
        """
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, not {mode!r} (PRD §2.0)")
        values = {n: p.default for n, p in PARAMS.items()}
        values.update(MODE_PRESETS[mode])
        # __post_init__ validates; no second call needed.
        return cls(values, mode=mode)

    def with_overrides(self, **overrides: str | int | float | Decimal) -> Config:
        vals = dict(self.values)
        for name, raw in overrides.items():
            if name not in PARAMS:
                raise KeyError(f"{name} is not a registered parameter (PRD §2 / §2.0)")
            vals[name] = Decimal(str(raw))
        # Range and coupling validation both run in __post_init__, so overriding cannot
        # reach a state that direct construction could not. Validating here as well would
        # be a second definition of "valid".
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

    **What is deliberately *not* checked here.** Until v0.1.0 this function also rejected
    ``room_gate_multiple <= t1_r_multiple``, which made the 2.0 that PRD §1, §2.0, §3.1.1 and
    §7 all declare legal raise instead. The check could not be justified from the section it
    cited, and it was unnecessary: the §3.1.2 separation term is ``t1_r_multiple * R +
    min_separation``, and ``min_separation >= TICK_SIZE`` at **every** legal configuration —
    it is a MINIMUM-polarity threshold, so it is the ceiling-to-tick of
    ``max(min_sep_r * R, sep_cost_multiple * (spread + est_round_trip_cost_per_share))``,
    whose cost term is strictly positive because ``sep_cost_multiple >= 1.0`` and
    ``est_round_trip_cost_per_share >= 0.001``. So the unified requirement strictly exceeds
    ``t1_r_multiple * R`` whatever the proportional multiple is, and at 2.0 the proportional
    term is inert rather than unsafe. Removed as D26; the inertness remains a documented open
    finding.

    Note the derivation deliberately does **not** run through ``min_sep_r * R``, which is the
    obvious route and is wrong: §2.0 bounds ``min_sep_r`` at ``[0.0, 2.0]``, so that product
    is exactly zero at a legal configuration. An earlier draft of D26 argued from it in six
    places — the v1.3.1 class (a rule generalized past its justification) restated the v1.2
    way (in more than one copy), inside the fix for a finding about unenforced guarantees.
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

    # PRD §2 / §7: the effective risk settings may not exceed the non-bypassable caps.
    # Checked against `cfg[name]`, not against `MODE_PRESETS[cfg.mode][name]`: the preset is
    # only the default, and D27 makes all three reachable through `with_overrides`.
    for name, cap in HARD_CAPS.items():
        if cfg[name] > cap:
            raise CouplingError(
                f"{name}={cfg[name]} exceeds the non-bypassable cap {cap} (PRD §2, §7)"
            )

    # PRD §20.10: the five composite-score weights are a convex combination, so the score
    # cannot land in [0, 1] — and cannot be compared to §14.2's 0.7 conviction gate — unless
    # they sum to exactly 1.
    weights = [n for n in PARAMS if n.startswith("score_weight_")]
    total = sum((cfg[n] for n in weights), start=Decimal(0))
    if total != Decimal(1):
        raise CouplingError(
            f"composite-score weights sum to {total}, not 1: "
            f"{', '.join(f'{n}={cfg[n]}' for n in sorted(weights))}. "
            "PRD §20.10 requires score in [0, 1] so it is comparable to the §14.2 gate."
        )
