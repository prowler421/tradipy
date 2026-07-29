"""Composite score (PRD §20.10) and the §14.2 conviction gate.

::

    score = 0.30 x norm_pct_change
          + 0.30 x norm_rvol
          + 0.20 x float_inverse
          + 0.10 x norm_premarket_vol
          + 0.10 x catalyst_confirmed

    norm_pct_change     = min(pct_change / 50.0, 1.0)        # 50% daily change = full marks
    norm_rvol           = min(rvol / 20.0, 1.0)              # 20x RVOL = full marks
    float_inverse       = max(0, (20e6 - float) / 20e6)      # already 0-1
    norm_premarket_vol  = min(premarket_volume / 1e6, 1.0)   # 1M shares = full marks
    catalyst_confirmed  = 1.0 confirmed | 0.5 headline only | 0.0 none

Every literal above is registered: five ``score_weight_*``, four ``score_cap_*`` and
``score_catalyst_headline``. §20.10 calls the caps *"configurable and should be revisited
against real scanner output in Phase 3"*, which is what makes them parameters rather than
constants.

**A coincidence worth watching.** ``score_cap_float`` is 20,000,000 — the same number as
``max_float_shares``. §20.10 states its own normalizer independently of the §2 scanner
filter, so they are two parameters, not one restated; but they are two parameters that mean
almost the same thing and will drift. ``test_score_float_cap_currently_equals_the_scan_filter``
pins the equality so a change to either becomes a visible decision.

§20.10's closing claim, ``score in [0, 1]``, holds only if the five weights sum to 1. That is
enforced in :func:`tradipy.params.validate_couplings` rather than assumed here — it is a
cross-parameter coupling, which is exactly what that validator is for.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from tradipy.params import Config

__all__ = ["Catalyst", "ScoreInputs", "Score", "composite_score", "meets_conviction_gate"]


class Catalyst(Enum):
    """PRD §20.10's three-level catalyst input.

    The endpoints are structural — 0 and 1 are the range every normalized input maps into —
    so only the midpoint is a registered parameter (``score_catalyst_headline``). "A headline
    nobody confirmed is worth half" is a judgement; "confirmed is full marks" is a definition.
    """

    CONFIRMED = "confirmed"
    HEADLINE_ONLY = "headline_only"
    NONE = "none"

    def weight(self, cfg: Config) -> Decimal:
        if self is Catalyst.CONFIRMED:
            return Decimal(1)
        if self is Catalyst.HEADLINE_ONLY:
            return cfg["score_catalyst_headline"]
        return Decimal(0)


@dataclass(frozen=True)
class ScoreInputs:
    """The five §20.10 inputs, in the units §20.10 states them in.

    ``pct_change`` is in **percent units** (7.29 for a 7.29% move), because §20.10's cap is
    written ``pct_change / 50.0`` with the comment "50% daily change = full marks". Every
    ``_pct`` parameter in the registry is a fraction, so this is the one place the two
    conventions meet, and getting it backwards silently divides the score's largest
    component by 100.
    """

    pct_change: Decimal
    rvol: Decimal
    float_shares: Decimal
    premarket_volume: Decimal
    catalyst: Catalyst


@dataclass(frozen=True)
class Score:
    """A composite score with its five normalized components kept alongside the total.

    §14.4 records the objection that *"a high score can be earned entirely on premarket
    volume"*. Returning the components rather than only the total is what lets a caller —
    or a journal entry — see when that has happened.
    """

    total: Decimal
    pct_change: Decimal
    rvol: Decimal
    float_inverse: Decimal
    premarket_vol: Decimal
    catalyst: Decimal


def _capped(value: Decimal, cap: Decimal) -> Decimal:
    """``min(value / cap, 1.0)``, floored at 0 so a negative input cannot subtract score."""
    return max(Decimal(0), min(value / cap, Decimal(1)))


def composite_score(inputs: ScoreInputs, cfg: Config) -> Score:
    """PRD §20.10, normalized to [0, 1].

    The floor at 0 in :func:`_capped` is this module's, not §20.10's: §20.10 writes
    ``max(0, ...)`` only on ``float_inverse``. A negative ``pct_change`` (a red name that
    somehow reached the scanner) would otherwise contribute negative score and could push the
    total below the range §20.10 promises, which §14.2's gate compares against.
    """
    pct_change = _capped(inputs.pct_change, cfg["score_cap_pct_change"])
    rvol = _capped(inputs.rvol, cfg["score_cap_rvol"])
    premarket_vol = _capped(inputs.premarket_volume, cfg["score_cap_premarket_vol"])
    catalyst = inputs.catalyst.weight(cfg)

    cap_float = cfg["score_cap_float"]
    float_inverse = max(Decimal(0), (cap_float - inputs.float_shares) / cap_float)

    total = (
        cfg["score_weight_pct_change"] * pct_change
        + cfg["score_weight_rvol"] * rvol
        + cfg["score_weight_float"] * float_inverse
        + cfg["score_weight_premarket_vol"] * premarket_vol
        + cfg["score_weight_catalyst"] * catalyst
    )
    return Score(total, pct_change, rvol, float_inverse, premarket_vol, catalyst)


def meets_conviction_gate(score: Score, cfg: Config) -> bool:
    """PRD §14.2: ``score >= min_conviction_score`` (0.7 by default).

    ``min_conviction_score`` is declared ``Polarity.MINIMUM``, but no rounding happens here:
    §20.13's tick rounding applies to prices, and a score is not one. The polarity is
    recorded because the *comparison* direction is part of the threshold's meaning, and
    because :meth:`Config.polarity` raising on an unclassified gate threshold is the check
    that stops one being added without thinking about it.
    """
    return score.total >= cfg["min_conviction_score"]
