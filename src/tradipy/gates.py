"""Pre-entry gates and position sizing.

Normative sources: PRD §2.2 (position sizing), §3.1.1 (exit ladder and room gate),
§3.1.2 (separation floor and the unified room requirement), §3.1.3 (spread gates),
§20.13 (rounding), §20.14 (spread definition — see :mod:`tradipy.quotes`).

No numeric threshold appears as a literal in this module. Every value comes from
:mod:`tradipy.params` by name — that is the mechanism that makes "§20 governs" true in
code rather than aspirational in prose.

**Rounding direction comes from the registry too.** Until v0.1.0 each ``round_threshold``
call named a :class:`~tradipy.rounding.Polarity` member directly, so polarity had two
definitions — the registry field and the literal here — and nothing reconciled them.
Flipping a registry polarity broke no test. Every rounded threshold below now goes through
:meth:`tradipy.params.Config.round_for`, which reads the direction from the parameter that
governs it. That method lived here as ``_rounded`` until Phase 3 added a second consumer;
see its docstring for why sharing it as a private import was the wrong of the two options.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from tradipy.params import Config
from tradipy.rejects import Reject
from tradipy.rounding import TICK_SIZE, ceil_to_tick, floor_to_tick

__all__ = [
    "Reject",
    "SpreadCaps",
    "RoomRequirement",
    "Ladder",
    "scan_spread_cap",
    "spread_caps",
    "check_spread",
    "min_separation",
    "required_room",
    "check_room",
    "exit_ladder",
    "exceeds_max_stop",
    "position_size",
    "vwap_reclaim_stop",
    "apply_stop_floor_and_ceiling",
]


# ---------------------------------------------------------------------------
# §3.1.3 Spread gates
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SpreadCaps:
    """The two caps from PRD §3.1.3, both MAXIMUM-polarity and therefore clamped."""

    scan: Decimal
    signal: Decimal

    @property
    def binding(self) -> Decimal:
        return min(self.scan, self.signal)


def scan_spread_cap(price: Decimal, cfg: Config) -> Decimal:
    """The scan-time half of §3.1.3, which PRD §4.2 makes a hard scanner filter::

        max_spread_scan = max(tick, floor_to_tick(min(max_spread_abs, max_spread_pct * price)))

    Split out from :func:`spread_caps` for Phase 3. §4.2's Liquidity/Spread row is evaluated
    over the whole universe, where no setup has formed and therefore no R exists, so the
    scanner cannot call :func:`spread_caps` without inventing one. Deriving the cap twice —
    once here, once there — is the v1.2 defect class, so :func:`spread_caps` delegates.
    """
    raw = min(cfg["max_spread_abs"], cfg["max_spread_pct"] * price)
    return cfg.round_for(raw, "max_spread_abs", "max_spread_pct")


def spread_caps(price: Decimal, r: Decimal, cfg: Config) -> SpreadCaps:
    """Return the scan-time and signal-time spread caps.

    PRD §3.1.3::

        max_spread_scan   = max(tick, floor_to_tick(min(max_spread_abs,
                                                        max_spread_pct * price)))
        max_spread_signal = max(tick, floor_to_tick(max_spread_r * R))

    Both are **maxima**, so both round *down* and both are clamped to one tick
    (§20.13, A25) — but that direction is read from the registry, not asserted here. At scan
    time R does not exist yet — the setup has not formed — which is why there are two gates
    rather than one.
    """
    signal_raw = cfg["max_spread_r"] * r
    return SpreadCaps(
        scan=scan_spread_cap(price, cfg),
        signal=cfg.round_for(signal_raw, "max_spread_r"),
    )


def check_spread(spread: Decimal, price: Decimal, r: Decimal, cfg: Config) -> Reject | None:
    """None if the spread passes both §3.1.3 gates, else ``Reject.SPREAD_TOO_WIDE``.

    §3.1.3 states one requirement at signal time — ``spread_at_signal <= max_spread_signal``
    — while §4.2 makes the scan cap a hard filter. Both are applied here, i.e. against
    ``caps.binding``: a name whose spread has widened past the scan cap by the time the setup
    forms would no longer pass the scanner, and taking it anyway would mean the scan filter
    binds only on a stale quote. On all three §3 worked examples the two produce identical
    verdicts; where they differ this is the stricter reading.
    """
    caps = spread_caps(price, r, cfg)
    return None if spread <= caps.binding else Reject.SPREAD_TOO_WIDE


# ---------------------------------------------------------------------------
# §3.1.2 Separation floor and unified room requirement
# ---------------------------------------------------------------------------
def min_separation(r: Decimal, spread: Decimal, cfg: Config) -> Decimal:
    """Minimum permissible ``T2 - T1``, in dollars.

    PRD §3.1.2::

        round_trip_cost_per_share = spread_at_signal + est_round_trip_cost_per_share
        min_separation = max(min_sep_r * R,
                             sep_cost_multiple * round_trip_cost_per_share)

    A **minimum**, so it rounds up (§20.13). The cost term is what binds on cheap stocks,
    which is the whole point: ``room_gate_multiple`` alone cannot express this because R
    shrinks with price while costs do not.
    """
    round_trip = spread + cfg["est_round_trip_cost_per_share"]
    raw = max(cfg["min_sep_r"] * r, cfg["sep_cost_multiple"] * round_trip)
    return cfg.round_for(raw, "min_sep_r", "sep_cost_multiple", "est_round_trip_cost_per_share")


@dataclass(frozen=True)
class RoomRequirement:
    required: Decimal
    binding: Reject  # which term set the requirement
    proportional_term: Decimal
    separation_term: Decimal


def required_room(r: Decimal, spread: Decimal, cfg: Config) -> RoomRequirement:
    """Distance from entry to nearest overhead resistance that a setup must have.

    PRD §3.1.2 (unified room requirement)::

        required_room = max(room_gate_multiple * R,        # proportional  (§3.1.1)
                            t1_r_multiple * R + min_separation)  # T1 + floor (§3.1.2)

    The two constraints act on the same quantity, and on wide-spread names the separation
    term is the stricter. Evaluating them independently obscures which one binds, so the
    PRD combines them and records the binding reason on the signal.

    Because ``min_separation`` is a MINIMUM-polarity threshold over a strictly positive
    quantity, it is at least one tick at every legal configuration, so the separation term
    strictly exceeds ``t1_r_multiple * R``. That is why D26 could remove the
    ``room_gate_multiple > t1_r_multiple`` coupling: the ordering ``entry < T1 < T2`` is
    guaranteed here, not by the proportional multiple. (Not via ``min_sep_r * R``, which §2.0
    permits to be exactly zero — see :func:`tradipy.params.validate_couplings`.)
    """
    proportional = cfg["room_gate_multiple"] * r
    separation = cfg["t1_r_multiple"] * r + min_separation(r, spread, cfg)

    # The reason code is chosen from the **unrounded** terms, deliberately. Review flagged
    # the asymmetry (compare raw, return rounded) as a possible defect, and §3.3 is the case
    # that decides it: proportional $0.375 vs separation $0.380 — a half-tick apart, both
    # ceiling to $0.38. Comparing rounded terms there reports INSUFFICIENT_ROOM, i.e. that
    # the proportional constraint is what the setup failed. That is false; the separation
    # term is genuinely stricter and rounding merely erased the gap. The returned
    # requirement is identical either way, so the only thing at stake is attribution, and
    # the raw terms are the ones that carry it. Both are exposed on RoomRequirement so a
    # caller can see the tie for itself.
    if separation > proportional:
        return RoomRequirement(
            cfg.round_for(separation, "t1_r_multiple"),
            Reject.TARGETS_TOO_CLOSE,
            proportional,
            separation,
        )
    return RoomRequirement(
        cfg.round_for(proportional, "room_gate_multiple"),
        Reject.INSUFFICIENT_ROOM,
        proportional,
        separation,
    )


def check_room(
    entry: Decimal, resistance: Decimal, r: Decimal, spread: Decimal, cfg: Config
) -> Reject | None:
    """None if there is enough room to entry's nearest resistance, else the binding code."""
    req = required_room(r, spread, cfg)
    return None if (resistance - entry) >= req.required else req.binding


# ---------------------------------------------------------------------------
# §3.1.1 Exit ladder
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Ladder:
    t1: Decimal
    t2: Decimal

    def ordered_above(self, entry: Decimal) -> bool:
        """PRD §3.1.1 hard ordering constraint: ``entry < T1 < T2``."""
        return entry < self.t1 < self.t2


def exit_ladder(entry: Decimal, r: Decimal, structural_target: Decimal, cfg: Config) -> Ladder:
    """T1 at exactly ``t1_r_multiple`` R; T2 at the structural level.

    Targets round **up** (away from entry) per §20.13, so rounding never flatters
    backtested R. This is a price level rather than a gate threshold, so it uses
    ``ceil_to_tick`` directly: §20.13 states the direction for *targets* as such, not by
    reference to any parameter's polarity.
    """
    return Ladder(
        t1=ceil_to_tick(entry + cfg["t1_r_multiple"] * r),
        t2=ceil_to_tick(structural_target),
    )


# ---------------------------------------------------------------------------
# §20.13 stop level construction, §2.2 sizing
# ---------------------------------------------------------------------------
def exceeds_max_stop(entry: Decimal, stop: Decimal, cfg: Config) -> bool:
    """PRD §2 / §20.13: is this stop further than ``max_stop_pct`` of entry?

    Extracted so :func:`apply_stop_floor_and_ceiling` and :func:`position_size` share one
    definition of the ceiling. Writing the comparison twice would be a restatement of a rule
    rather than of a literal, which the registry lint cannot see and which is how the v1.2
    class arose in the first place.
    """
    return entry - stop > cfg["max_stop_pct"] * entry


def apply_stop_floor_and_ceiling(
    entry: Decimal, raw_stop: Decimal, cfg: Config
) -> tuple[Decimal, Reject | None]:
    """Apply tick rounding, then the min-stop floor, then the max-stop skip test.

    PRD §20.13 ordering: *"Tick rounding is applied before the $0.10 minimum-stop floor
    and before the 5% maximum-stop skip test, so both tests operate on the level that will
    actually be sent."*

    A stop wider than ``max_stop_pct`` of entry means **skip the trade** — never tighten
    it, because tightening puts the stop inside the pattern and guarantees a noise
    stop-out (§2, §3.2).
    """
    stop = floor_to_tick(raw_stop)  # stops round away from the position (§20.13)
    if entry - stop < cfg["min_stop_distance"]:
        stop = floor_to_tick(entry - cfg["min_stop_distance"])
    if exceeds_max_stop(entry, stop, cfg):
        return stop, Reject.STOP_TOO_WIDE
    return stop, None


def vwap_reclaim_stop(
    entry: Decimal, dip_low: Decimal, vwap: Decimal, cfg: Config
) -> tuple[Decimal, Reject | None]:
    """The §3.4 stop chain, which is the PRD's own worked reference for rounding.

    PRD §3.4 / §20.13::

        raw_stop = round_down_to_tick(max(dip_low, VWAP * 0.99)) - 1 tick
        then the $0.10 minimum-stop floor widens it if needed

    Worked reference (§20.13): ``VWAP * 0.99 = $3.762`` -> ``floor_to_tick`` -> ``$3.76``
    -> ``- 1 tick`` -> ``$3.75``; the $0.10 floor then widens it to ``$3.73``.

    **Returns the ceiling verdict, not just the level.** An earlier version returned a bare
    ``Decimal`` and discarded the ``Reject`` from
    :func:`apply_stop_floor_and_ceiling`, so a $1.50 entry returned a live $1.40 stop for a
    trade §20.13 requires be skipped. The gate existed, was correct, and was unreachable —
    and because this was its only caller, *mutation testing could not detect it*: deleting
    the ceiling changed no observable behaviour. Any future caller must destructure both
    elements; a bare-``Decimal`` return is what made dropping the verdict silent.
    """
    # PRD §3.4 writes this as `VWAP × 0.99`. That 1% is the only threshold on the MVP path
    # stated as a bare literal with no §2/§2.0 entry, so it is registered as
    # `vwap_stop_band_pct` and read by name here.
    #
    # §3.4 writes the tick rounding around the whole `max()`; it is applied to the VWAP
    # branch alone here. The two agree whenever `dip_low` is a whole tick, which §20.13
    # guarantees for a bar low, and `apply_stop_floor_and_ceiling` floors the result again
    # immediately. Kept this way so the VWAP band is a whole tick before it is compared.
    vwap_band = floor_to_tick(vwap * (Decimal(1) - cfg["vwap_stop_band_pct"]))
    raw = max(dip_low, vwap_band) - TICK_SIZE
    return apply_stop_floor_and_ceiling(entry, raw, cfg)


def position_size(
    entry: Decimal,
    effective_stop: Decimal,
    cfg: Config,
    *,
    buying_power: Decimal | None = None,
    adv_shares: Decimal | None = None,
) -> int:
    """Shares to buy, per PRD §2.2.

    ``max_dollar_risk = start_of_day_equity * max_risk_per_trade_pct`` — deliberately the
    **frozen start-of-day** figure (§7.1, D16), so intraday gains cannot compound size
    within a session.

    ``buying_power`` and ``adv_shares`` are optional because this layer has no broker and no
    market-data feed to supply them. PRD §8.1 requires the backtester to pass both: *"the
    simulator applies the full §2.2 constraint set, including the 1%-of-ADV liquidity
    guard… omitting the sizing cap would let the backtest take positions the live system
    would refuse."* Omitting them here yields the risk-and-order-size-capped figure only.

    **One remaining Phase 2 gap, recorded here because the signature is where it gets
    closed.** A budget too small for one share returns ``0`` rather than a rejection, so "no
    size" and "skip this trade" are the same value. Callers that treat 0 as falsy behave
    correctly by accident; anything summing fills does not.

    The other gap recorded here previously — that this function never consulted
    ``max_stop_pct``, so a stop the §20.13 ceiling rejects could still be sized — is closed:
    it now raises. That makes honouring the ceiling an invariant rather than a convention.
    """
    stop_distance = entry - effective_stop
    if stop_distance <= 0:
        raise ValueError("effective_stop must be below entry for a long")
    if exceeds_max_stop(entry, effective_stop, cfg):
        raise ValueError(
            f"stop distance {stop_distance} exceeds max_stop_pct "
            f"({cfg['max_stop_pct']}) of entry {entry}: PRD §20.13 requires skipping this "
            "trade, not sizing it. Check the Reject from apply_stop_floor_and_ceiling."
        )

    max_dollar_risk = cfg["start_of_day_equity"] * cfg["max_risk_per_trade_pct"]
    shares = int(max_dollar_risk / stop_distance)  # floor

    shares = min(shares, int(cfg["max_shares_per_order"]))
    if buying_power is not None:
        shares = min(shares, int((buying_power * cfg["max_bp_usage_pct"]) / entry))
    if adv_shares is not None:
        shares = min(shares, int(cfg["max_pct_of_adv"] * adv_shares))
    return shares
