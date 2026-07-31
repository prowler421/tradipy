"""The §4 scanner — PRD §4.2's hard filters, §4.2's soft flags, and §4.3's ranking.

Normative sources: PRD §4.1 (pipeline), §4.2 (filter definitions), §4.3 (composite
scoring), §3.1.3 (the scan-time spread cap §4.2 adopts), §20.10 (the score), §20.13
(rounding). §20 governs on any conflict.

**What this is.** PRD §4.1's pipeline, minus its ends::

    Universe (external screening provider)   <- not here: Phase 2 ingestion
      -> Hard Filters (reject immediately)   <- here
      -> Soft Filters (score/rank)           <- here
      -> Catalyst Check (manual or NLP)      <- an *input*, per §12.2
      -> Watchlist (top 3-5 by composite)    <- here

It is a pure function of the candidates handed to it. There is no feed, no file read and no
network call in this module, and PLAN **D30** is why: the project is on the ``SIMULATED``
rung of the data ladder, so nothing in ``src/`` may import a broker SDK or a market-data
client, and data whose origin is undeclared is refused rather than assumed. A scanner that
*sources* its universe is Phase 2's job; this one applies §4.2 to a universe it is given.

**Two things §4 asks for that are deliberately absent**, named here because an omission
nobody wrote down is indistinguishable from an oversight:

* **§4.4's scan schedule** — 30/60/120-second cadences across four session windows — needs a
  clock, a session calendar and a loop, none of which a pure function has and none of which
  D30 permits this module to acquire. It belongs to whatever drives the scanner, and Phase 2a
  Q3 currently treats those cadences as a *latency assumption to be measured* rather than as
  an implemented requirement.
* **§4.1's "US equities, common stock"** is a universe predicate, and :class:`ScanCandidate`
  carries no security type. Nothing here excludes an ETF, a warrant or an ADR; the screening
  provider is assumed to have. That assumption is unenforced and is worth knowing about
  before the first real universe arrives.

**Written fresh against the PRD**, not grown from ``scripts/spike2a/`` — PHASE-2A-SPIKE §8
names accretion from the spike as the failure mode this phase had to avoid, because the
spike's code is measurement scaffolding that happens to work rather than an implementation
of §4.

**What simulated-only validation does not establish.** Every threshold below is applied
correctly and is tested to be; none of them is *calibrated*, because PLAN D29 gates
calibration on Phase 2a Q1 answered on measured data and D32 opened this phase without it.
Q1 asks whether the §4.2 input contract is obtainable from any provider at any price. If the
answer turns out to be no, the filters that survive are a subset of these and the arithmetic
here is still right; what changes is the table, not the mechanism. See
docs/PHASE-3-READINESS.md.

**Where §4.2 admits more than one reading**, this module takes one because it has to be
executable, and every such choice is raised in docs/CHANGELOG.md's spec-question table rather
than settled here. That table is the count; this docstring deliberately does not restate one,
because a number stated in five places above a list that grows is convention 8's own example.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from tradipy.gates import scan_spread_cap
from tradipy.params import Config
from tradipy.rejects import Reject, SoftFlag
from tradipy.score import Catalyst, Score, ScoreInputs, composite_score

__all__ = [
    "ScanCandidate",
    "HardFilter",
    "SoftFilter",
    "HardResult",
    "SoftResult",
    "ScanResult",
    "ScanReport",
    "HARD_FILTERS",
    "SOFT_FILTERS",
    "evaluate_candidate",
    "scan",
]

#: §20.10 states ``pct_change`` in **percent units** (7.29 for a 7.29% move) while every
#: ``_pct`` parameter in the registry is a fraction. §4.2's daily Gap % is a fraction, and
#: this module identifies it with §20.10's daily change rather than taking a second input.
#:
#: **That identification is this module's, not the PRD's.** §4.2 says "Gap %" and §20.10 says
#: "50% daily change = full marks"; nothing states they are the same quantity. Taking them as
#: two inputs was the alternative, and it is worse: two numbers describing one move, free to
#: disagree, with a units trap between them that :mod:`tradipy.score` already warns silently
#: divides the score's largest component by 100. Raised as a spec question in
#: docs/CHANGELOG.md and pinned by ``test_daily_gap_is_what_feeds_the_score`` so a future
#: decision to separate them is visible rather than accidental.
PERCENT_PER_UNIT = Decimal(100)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScanCandidate:
    """One symbol from the screening universe, with the §4.2 inputs it is filtered on.

    **The required/optional split is a rule, not a convenience.** Every hard-filter input is
    required, because a hard filter run on a fabricated input is worse than no filter: it
    reports a verdict it did not earn. Every input §4.3's ranking needs is required for the
    same reason. The six that are ``None``-able feed *soft* rows only, and ``None`` there
    means "not available", which raises no flag — asserting a name is thinly traded when
    nobody knows its premarket volume is an invention, and §4.2 marks these rows advisory
    precisely because they are the ones a provider is likely to be missing (Phase 2a Q1).
    """

    symbol: str

    # --- §4.2 hard-filter inputs (all required) ---------------------------
    #: Last / reference price, in dollars. §4.2 Price Range and Liquidity / Spread.
    price: Decimal
    #: Premarket gap from prior close, as a **fraction** (0.04 = 4%).
    premarket_gap_pct: Decimal
    #: Daily gap from prior close, as a **fraction** (0.10 = 10%). Also what feeds §20.10 —
    #: see :data:`PERCENT_PER_UNIT`.
    daily_gap_pct: Decimal
    #: Relative volume, x the ``rvol_lookback_days`` average (§20.7 governs its as-of
    #: semantics; this layer receives the ratio, it does not compute it).
    rvol: Decimal
    float_shares: Decimal
    adv_shares: Decimal
    #: Limit-up and limit-down band prices (§4.2 Circuit Breakers).
    luld_upper: Decimal
    luld_lower: Decimal
    #: NBBO spread and bid depth at scan time. §20.14's *validity* rules are a signal-time
    #: concern and are applied by :mod:`tradipy.quotes`, not here.
    spread: Decimal
    bid_size: int

    # --- §4.3 ranking inputs (required: §20.10 consumes them) -------------
    premarket_volume: Decimal
    #: §12.2 keeps catalyst confirmation the one manual step in the MVP loop, so this is an
    #: input to the scanner rather than something the scanner decides.
    catalyst: Catalyst

    # --- §4.2 soft-flag inputs (None = not available = no flag) -----------
    market_cap: Decimal | None = None
    #: ATR(14) and its trailing 30-session average. The period and the window are §4.2 input
    #: contract, computed in Phase 2 ingestion; only the *multiple* between them is a
    #: registered threshold.
    atr: Decimal | None = None
    avg_atr: Decimal | None = None
    #: Sessions since the most recent trading halt; ``None`` if the name has not halted
    #: within whatever history the provider returned.
    sessions_since_halt: int | None = None
    institutional_ownership_pct: Decimal | None = None
    short_interest_pct: Decimal | None = None


# ---------------------------------------------------------------------------
# Filter definitions — one record per §4.2 row
# ---------------------------------------------------------------------------
#: A filter body: given a candidate and a config, return ``(fired, detail)``. For a hard
#: filter ``fired`` means *passed*; for a soft one it means *flag raised*. The detail string
#: carries the arithmetic, so a rejection can be read without re-deriving it.
HardCheck = Callable[[ScanCandidate, Config], tuple[bool, str]]
SoftCheck = Callable[[ScanCandidate, Config], tuple[bool, str]]


@dataclass(frozen=True)
class HardFilter:
    """One Hard row of §4.2. Failing it rejects the candidate outright."""

    #: Verbatim from §4.2's Filter column. ``tests/test_scanner.py`` parses the table out of
    #: docs/PRD.md and compares it to :data:`HARD_FILTERS` in both directions, so a row added
    #: to the spec and not to the code — or the reverse — fails rather than passing quietly.
    #: G3 found nothing did this in either direction.
    name: str
    code: Reject
    check: HardCheck


@dataclass(frozen=True)
class SoftFilter:
    """One Soft row of §4.2. Raising it flags the candidate and **never rejects it.**

    The type is what enforces that: :attr:`code` is a :class:`~tradipy.rejects.SoftFlag`,
    and nothing in the rejection path accepts one. See :mod:`tradipy.rejects` for why the
    namespace is split at all (round 10, finding K5).
    """

    name: str
    code: SoftFlag
    check: SoftCheck


def _check_gap(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2: ``>= 4% premarket OR >= 10% daily``.

    An **OR**, so a name that gapped hard overnight qualifies on the daily figure even if
    premarket is quiet, and a name moving now qualifies on premarket even if it opened flat.
    Reading it as an AND would empty the universe on most mornings; the row states one code
    for both because either alone is sufficient.

    Neither threshold is rounded. Both are ratios, and a ratio has no tick to round to — they
    carry a MINIMUM polarity because the comparison direction is part of what they mean, not
    because anything rounds them (see :meth:`tradipy.params.Config.round_for`).
    """
    pm_floor, day_floor = cfg["min_gap_premarket_pct"], cfg["min_gap_daily_pct"]
    passed = c.premarket_gap_pct >= pm_floor or c.daily_gap_pct >= day_floor
    return passed, (
        f"premarket {c.premarket_gap_pct} vs {pm_floor} OR daily {c.daily_gap_pct} vs {day_floor}"
    )


def _check_relative_volume(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2: ``>= 5x 30-day ADV``. The ratio arrives computed; §20.7 defines its as-of rule."""
    floor = cfg["min_rvol"]
    return c.rvol >= floor, f"rvol {c.rvol} vs floor {floor} (x {cfg['rvol_lookback_days']}-day)"


def _check_float(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2 / D4: ``<= 20M shares``, the supply side of the "20-20 rule"."""
    ceiling = cfg["max_float_shares"]
    return c.float_shares <= ceiling, f"float {c.float_shares} vs ceiling {ceiling}"


def _check_price_range(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2: ``$1.00 - $20.00``.

    Both ends are compared against a price, so both are rounded to a whole tick in the
    direction the registry declares — the floor up, the ceiling down, so neither bound is
    widened by rounding (§20.13). At the shipped defaults both are already whole ticks and
    the rounding changes nothing, which is precisely the configuration in which a missing
    classification would never be noticed.
    """
    lo = cfg.round_for(cfg["min_price"], "min_price")
    hi = cfg.round_for(cfg["max_price"], "max_price")
    return lo <= c.price <= hi, f"price {c.price} vs [{lo}, {hi}]"


def _check_average_daily_volume(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2: ``>= 500K shares/day``, the exit-liquidity floor.

    Distinct from §2.2's ``max_pct_of_adv``, which caps *size* on a name that already passed
    this. One says whether to look at the symbol at all; the other says how much of it you
    may take.
    """
    floor = cfg["min_adv_shares"]
    return c.adv_shares >= floor, f"adv {c.adv_shares} vs floor {floor}"


def _check_circuit_breakers(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2: ``Not within 10% of LULD band``.

    **Two readings, and §4.2 states neither.** "Within 10%" could be 10% of the price or 10%
    of the band's own width, and "band" could mean the limit-up level only — the one a
    gapping long actually runs into — or both. This module takes 10% **of price**, measured
    against **both** bands: the proportional reading because every other §4.2 threshold that
    is a percentage is a percentage of price, and both bands because the stricter of two
    readings is the one that cannot admit a candidate the spec meant to exclude. Raised in
    docs/CHANGELOG.md; if the spec settles it the other way this function changes and its
    tests change with it, which is the point of it being one function.

    The required distance is a **minimum** over a price, so it rounds up: a candidate exactly
    at the unrounded boundary is rejected rather than admitted by a rounding artifact.
    """
    required = cfg.round_for(cfg["min_luld_distance_pct"] * c.price, "min_luld_distance_pct")
    to_upper = c.luld_upper - c.price
    to_lower = c.price - c.luld_lower
    nearest = min(to_upper, to_lower)
    return nearest >= required, (
        f"nearest band {nearest} (up {to_upper}, down {to_lower}) vs required {required} "
        f"({cfg['min_luld_distance_pct']} x {c.price})"
    )


def _check_liquidity_spread(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2: ``spread <= min(max_spread_abs, max_spread_pct x price) AND bid size >= 100``.

    The cap is :func:`tradipy.gates.scan_spread_cap` — the same function §3.1.3's scan-time
    gate uses, not a second copy of the formula. §4.2 re-states the arithmetic in prose and
    adds a depth condition under the same code, so a bid nobody will fill in size rejects
    exactly as a quote nobody will fill at a fair price does.

    ``min_quote_size`` is §20.14's, reused rather than re-registered: §4.2's "100 shares" and
    §20.14's odd-lot floor are the same number meaning the same thing, and registering it
    twice is the v1.2 defect class.
    """
    cap = scan_spread_cap(c.price, cfg)
    depth_floor = cfg["min_quote_size"]
    wide = c.spread > cap
    thin = Decimal(c.bid_size) < depth_floor
    return not (wide or thin), (
        f"spread {c.spread} vs cap {cap}, bid size {c.bid_size} vs floor {depth_floor}"
        + (" [WIDE]" if wide else "")
        + (" [THIN]" if thin else "")
    )


def _flag_premarket_volume(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2 Soft: premarket volume below ``min_premarket_volume``. Also a §20.10 input."""
    floor = cfg["min_premarket_volume"]
    return c.premarket_volume < floor, f"premarket volume {c.premarket_volume} vs floor {floor}"


def _flag_market_cap(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2 Soft: market cap above ``max_market_cap`` (small-cap focus)."""
    ceiling = cfg["max_market_cap"]
    if c.market_cap is None:
        return False, f"market cap not available (ceiling {ceiling})"
    return c.market_cap > ceiling, f"market cap {c.market_cap} vs ceiling {ceiling}"


def _flag_volatility(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2 Soft: ``ATR(14) >= 1.5x 30-day avg ATR``; flagged when it is not.

    Both inputs must be present. Flagging on a missing ATR would report low volatility on a
    name whose volatility nobody measured.
    """
    multiple = cfg["min_atr_multiple"]
    if c.atr is None or c.avg_atr is None:
        return False, f"ATR not available (floor {multiple}x avg)"
    floor = multiple * c.avg_atr
    return c.atr < floor, f"ATR {c.atr} vs floor {floor} ({multiple} x avg {c.avg_atr})"


def _flag_catalyst(c: ScanCandidate, _cfg: Config) -> tuple[bool, str]:
    """§4.2 Soft: no headline.

    Ross Cameron requires a catalyst and §14 gates on one, but the scanner does not reject
    here: §12.2 makes catalyst confirmation the single manual step the MVP keeps in the loop,
    so a scanner that threw away every unconfirmed name would discard the candidates the
    human is meant to confirm. §20.10 scores it at zero instead, which ranks it down.
    """
    return c.catalyst is Catalyst.NONE, f"catalyst {c.catalyst.value}"


def _flag_recent_halt(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2 Soft (flag): halted within ``recent_halt_lookback_days``.

    §4.2's rationale column reads "Elevated risk/opportunity" — the one row whose rationale
    points both ways, which is why it is a flag rather than either a filter or a bonus.
    """
    window = cfg["recent_halt_lookback_days"]
    if c.sessions_since_halt is None:
        return False, f"no halt in the window (lookback {window} sessions)"
    return Decimal(c.sessions_since_halt) <= window, (
        f"halted {c.sessions_since_halt} session(s) ago vs lookback {window}"
    )


def _flag_institutional_ownership(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2 Soft, **disabled by default** (D24 / A22).

    §4.2's own note calls the premise doubtful: institutional ownership at or above 80% in a
    universe capped at 20M float and $2B market cap is rare, no source in Appendix A states
    the threshold, and where it does fire the causation is unclear. D24 kept the row off
    rather than deleting it so the hypothesis survives to be tested in Phase 4b.

    The enable check comes **first and unconditionally**, so with the shipped default no
    ownership figure can raise this flag. ``tests/test_enforcement.py`` attempts it at the
    threshold, above it and at 100% and asserts nothing is raised — and then enables the row
    and asserts it *is*, so the first assertion is not passing vacuously.
    """
    threshold = cfg["min_institutional_ownership_pct"]
    if cfg["institutional_ownership_enabled"] == Decimal(0):
        return False, f"disabled by default (D24); threshold {threshold}"
    if c.institutional_ownership_pct is None:
        return False, f"institutional ownership not available (threshold {threshold})"
    return c.institutional_ownership_pct >= threshold, (
        f"institutional ownership {c.institutional_ownership_pct} vs threshold {threshold}"
    )


def _flag_short_interest(c: ScanCandidate, cfg: Config) -> tuple[bool, str]:
    """§4.2 Soft: ``>= 5%``, explicitly "flag only, not reject" — squeeze fuel cuts both ways."""
    threshold = cfg["min_short_interest_pct"]
    if c.short_interest_pct is None:
        return False, f"short interest not available (threshold {threshold})"
    return c.short_interest_pct >= threshold, (
        f"short interest {c.short_interest_pct} vs threshold {threshold}"
    )


#: §4.2's seven Hard rows, **in table order**. The order is the evaluation order and the
#: order :attr:`ScanResult.reject` reports, so it is part of the observable behaviour rather
#: than a listing convenience.
HARD_FILTERS: tuple[HardFilter, ...] = (
    HardFilter("Gap %", Reject.GAP_TOO_SMALL, _check_gap),
    HardFilter("Relative Volume", Reject.RVOL_TOO_LOW, _check_relative_volume),
    HardFilter("Float", Reject.FLOAT_TOO_HIGH, _check_float),
    HardFilter("Price Range", Reject.PRICE_OUT_OF_RANGE, _check_price_range),
    HardFilter("Average Daily Volume", Reject.ADV_TOO_LOW, _check_average_daily_volume),
    HardFilter("Circuit Breakers", Reject.NEAR_LULD, _check_circuit_breakers),
    HardFilter("Liquidity / Spread", Reject.SPREAD_TOO_WIDE, _check_liquidity_spread),
)

#: §4.2's seven Soft rows, in table order. None of these can reject anything.
SOFT_FILTERS: tuple[SoftFilter, ...] = (
    SoftFilter("Premarket Volume", SoftFlag.PREMARKET_THIN, _flag_premarket_volume),
    SoftFilter("Market Cap", SoftFlag.MARKET_CAP_HIGH, _flag_market_cap),
    SoftFilter("Volatility (ATR)", SoftFlag.ATR_LOW, _flag_volatility),
    SoftFilter("News / Catalyst", SoftFlag.NO_CATALYST, _flag_catalyst),
    SoftFilter("Recent Halts", SoftFlag.RECENT_HALT, _flag_recent_halt),
    SoftFilter("Institutional Ownership", SoftFlag.INST_OWN_HIGH, _flag_institutional_ownership),
    SoftFilter("Short Interest", SoftFlag.HIGH_SHORT_INTEREST, _flag_short_interest),
)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HardResult:
    """One hard filter's verdict, with the arithmetic that produced it."""

    filter: str
    code: Reject
    passed: bool
    detail: str


@dataclass(frozen=True)
class SoftResult:
    """One soft filter's verdict. ``raised`` is advisory — it rejects nothing."""

    filter: str
    code: SoftFlag
    raised: bool
    detail: str


@dataclass(frozen=True)
class ScanResult:
    """A candidate's full §4.2 evaluation, plus its §20.10 score if it survived.

    **Every hard filter is evaluated, not just up to the first failure.** A scanner that
    stops at the first reject tells you a name is out; one that reports all seven tells you
    whether it was marginal or nowhere near, which is what a threshold being recalibrated
    against measured data (Phase 2a Q1) needs to be readable from.
    """

    candidate: ScanCandidate
    hard: tuple[HardResult, ...]
    soft: tuple[SoftResult, ...]
    #: §20.10 composite score — ``None`` for a rejected candidate, **deliberately**. §4.1
    #: orders the pipeline hard-filters-then-score, and a score sitting on a rejected name is
    #: an invitation to rank on it. The rejection is the answer; there is nothing to rank.
    score: Score | None = None

    @property
    def rejects(self) -> tuple[Reject, ...]:
        """Every hard code this candidate failed, in §4.2 table order."""
        return tuple(h.code for h in self.hard if not h.passed)

    @property
    def reject(self) -> Reject | None:
        """The first hard failure in §4.2 table order, or ``None`` if the candidate passed."""
        return self.rejects[0] if self.rejects else None

    @property
    def passed(self) -> bool:
        return not self.rejects

    @property
    def flags(self) -> tuple[SoftFlag, ...]:
        """Every soft flag raised, in §4.2 table order. Never affects :attr:`passed`."""
        return tuple(s.code for s in self.soft if s.raised)


@dataclass(frozen=True)
class ScanReport:
    """The outcome of one pass over a universe."""

    #: Every candidate evaluated, in the order supplied. Rejections included — §4.2's whole
    #: purpose is the rejections, and a report that dropped them could not be audited.
    results: tuple[ScanResult, ...]
    #: §4.1 / §4.3: survivors ranked by §20.10 score, truncated to ``watchlist_size``.
    watchlist: tuple[ScanResult, ...]

    @property
    def survivors(self) -> tuple[ScanResult, ...]:
        """Every candidate that passed all seven hard filters, in the order supplied.

        Not ranked and not truncated — :attr:`watchlist` is both. The pair is what makes
        "why is this name not on the watchlist" answerable: absent here means a filter
        rejected it, present here but absent there means it was outranked.
        """
        return tuple(r for r in self.results if r.passed)


def _rank_key(result: ScanResult) -> tuple[Decimal, str]:
    """Descending score, then symbol ascending.

    **The tiebreak is this module's, not §4.3's.** §4.3 says "Return top 5 by score" and
    stops. Ties are not hypothetical: ``norm_rvol`` saturates at 1 for anything above
    ``score_cap_rvol``, so two names 60x apart on relative volume score identically. Without a
    tiebreak the watchlist would depend on the order the universe arrived in, which is a
    scanner that returns different answers for the same market.

    An earlier draft of this paragraph also cited ``float_inverse`` saturating at 0, which is
    wrong *among survivors*: ``score_cap_float`` and ``max_float_shares`` are the same number,
    so the only float that saturates the normalizer and still passes §4.2's Float filter is
    the cap exactly. That is the coincidence :mod:`tradipy.score` flags, seen from the other
    side — and it means the float half of the argument becomes true the moment either
    parameter moves. ``test_two_different_candidates_can_score_identically`` pins both halves.
    """
    if result.score is None:
        raise ValueError(
            f"{result.candidate.symbol} was rejected and has no score; only survivors are "
            "ranked (PRD §4.1 orders hard filters before scoring)"
        )
    return (-result.score.total, result.candidate.symbol)


def evaluate_candidate(candidate: ScanCandidate, cfg: Config) -> ScanResult:
    """Apply §4.2's seven hard filters and seven soft flags to one candidate.

    Scores survivors per §20.10 and leaves rejects unscored, per §4.1's ordering.

    **The soft rows are evaluated unconditionally, including on a rejected candidate.** §4.1's
    pipeline diagram reads sequentially — ``Hard Filters (reject immediately) -> Soft Filters
    (score/rank)`` — which can be read as soft evaluation happening only on survivors. This is
    a third reading, and it is taken this way for the same reason all seven hard filters are
    evaluated rather than stopping at the first failure: a rejection you can only see one
    dimension of is not readable, and Phase 2a's recalibration has to read them. It costs
    nothing correctness-wise, because a flag is a different type from a rejection and cannot
    enter :attr:`ScanResult.rejects`; ``tests/test_enforcement.py`` performs that violation.
    What §4.1 unambiguously orders is the *scoring*, and scoring is withheld from rejects.
    Recorded in docs/CHANGELOG.md's spec-question table.
    """
    hard = tuple(HardResult(f.name, f.code, *f.check(candidate, cfg)) for f in HARD_FILTERS)
    soft = tuple(SoftResult(f.name, f.code, *f.check(candidate, cfg)) for f in SOFT_FILTERS)
    if any(not h.passed for h in hard):
        return ScanResult(candidate, hard, soft)

    score = composite_score(
        ScoreInputs(
            pct_change=candidate.daily_gap_pct * PERCENT_PER_UNIT,
            rvol=candidate.rvol,
            float_shares=candidate.float_shares,
            premarket_volume=candidate.premarket_volume,
            catalyst=candidate.catalyst,
        ),
        cfg,
    )
    return ScanResult(candidate, hard, soft, score)


def scan(candidates: Iterable[ScanCandidate], cfg: Config) -> ScanReport:
    """Run PRD §4.1's pipeline over a universe and return the ranked watchlist.

    The watchlist is the survivors sorted by §20.10 score and cut to ``watchlist_size``.
    Nothing is dropped from :attr:`ScanReport.results`, so why a name is absent from the
    watchlist is always answerable: it failed a filter, or it was outranked.
    """
    results: tuple[ScanResult, ...] = tuple(evaluate_candidate(c, cfg) for c in candidates)
    ranked: Sequence[ScanResult] = sorted((r for r in results if r.passed), key=_rank_key)
    return ScanReport(results, tuple(ranked[: int(cfg["watchlist_size"])]))
