"""PRD-adjacent pre-registration constants — PHASE-2A-SPIKE.md §7, transcribed.

§7 is **binding and committed** (2026-07-29, before any data was pulled). This module exists so
that the pass/fail thresholds are read by the measurement code rather than re-typed into it: a
pre-registration that lives only in prose is one refactor away from being retrofitted to a
result, which is the failure §7's own preamble describes.

**These are not registered parameters, and must not become any.** A registered parameter is a
tunable of the *trading system*; these are the acceptance thresholds of one investigation.
Putting them in :mod:`tradipy.params` would give the registry rows with no §2/§2.0 citation,
which :func:`tests.test_parameter_registry.test_every_registered_param_is_cited_to_the_prd`
correctly forbids.

**On the numeric coincidences.** Every value here that collides with a registered default, listed
by computation rather than from memory: **30** (``Q2_MAX_FLOAT_AGE_DAYS`` in days,
``Q3_MAX_DATA_TO_SIGNAL_P95_SECONDS`` in seconds, ``Q4_RECALIBRATE_ABOVE_PCT`` in percent) with
``rvol_lookback_days`` (30 sessions); **5** (``MAX_MISSING_NBBO_PCT`` in percent,
``Q4_CHEAP_STOCK_CEILING_USD`` in dollars) with ``min_rvol`` (5.0, a multiple of ADV); **2**
(``Q3_MAX_SIGNAL_TO_ORDER_P95_SECONDS``, ``Q4_INERT_BELOW_PCT``) with ``t1_r_multiple`` (2.0) and
``quote_stale_seconds`` (2). ``500`` ($, Q1's monthly ceiling) collides with nothing registered,
though it is adjacent to ``min_adv_shares``. Review round 7 found this list naming a collision on
**20**, which no constant in this module has, and omitting the two on **5** — a list whose whole
purpose is to spare a reader the check had not had the check run on it. They
are held as ``int`` percents, seconds and counts, converted at the comparison site, precisely so
that no ``Decimal("0.30")`` appears in this package to be confused with a threshold restatement.
The collisions are unit collisions in the ``TICK_SIZE`` sense: same digits, different quantity.
They are called out here rather than left for a reader to notice.

**Changing a value below** requires amending PHASE-2A-SPIKE.md §7 in a commit that predates the
next data pull, and recording that the change happened after data existed if it did. The point
of the table is that it cannot be quietly retrofitted.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

# --- Sample design (§7 rows 1-5) ------------------------------------------------------

#: Sessions per window. Two windows: highest-VIX run and lowest-VIX run.
WINDOW_SESSIONS: Final = 10

#: Trailing months of daily closing VIX the window rule ranges over.
VIX_LOOKBACK_MONTHS: Final = 12

#: Hard cap on symbol-sessions. Tie-broken by ``(date, symbol)`` ascending — **never** by a
#: measured quantity, which is how a sample-size limit smuggles in the survivorship bias §4.1
#: warns about.
MAX_SYMBOL_SESSIONS: Final = 400

#: A symbol is excluded, and counted as a **coverage failure feeding Q1**, if the chosen vendor
#: has no NBBO for at least this share of the session. Not a silent drop: §7 exclusion (2).
MAX_MISSING_NBBO_PCT: Final = 5

# --- Q1: real-time candidate list -----------------------------------------------------

Q1_MIN_SAMPLE_COVERAGE_PCT: Final = 95
Q1_MIN_CONCURRENT_SYMBOLS: Final = 200
Q1_MAX_REFRESH_SECONDS: Final = 60
Q1_MAX_MONTHLY_USD: Final = 500

# --- Q2: float and short-interest quality ---------------------------------------------

#: Two providers "disagree" on a symbol when their floats differ by more than this share of the
#: larger value. **Unusable with a single provider** — see :mod:`scripts.spike2a.q2_float`.
Q2_DISAGREEMENT_PCT: Final = 10

#: A10 trips if more than this share of sampled symbols disagree.
Q2_MAX_DISAGREEING_SYMBOLS_PCT: Final = 15

#: A10 also trips, independently, if more than ``Q2_MAX_STALE_SYMBOLS_PCT`` of symbols carry a
#: float as-of date older than this. This is the half that **is** runnable on one provider.
Q2_MAX_FLOAT_AGE_DAYS: Final = 30
Q2_MAX_STALE_SYMBOLS_PCT: Final = 10

# --- Q3: latency ----------------------------------------------------------------------

#: §5.5's refresh assumption fails if measured p95 exceeds these. The mean is not the threshold.
Q3_MAX_DATA_TO_SIGNAL_P95_SECONDS: Final = 30
Q3_MAX_SIGNAL_TO_ORDER_P95_SECONDS: Final = 2

# --- Q4: realized spread distribution -------------------------------------------------

#: ``max_spread_r`` is **recalibrated** above this rejection rate, in aggregate or in any single
#: price decile below ``Q4_CHEAP_STOCK_CEILING_USD``.
Q4_RECALIBRATE_ABOVE_PCT: Final = 30

#: ``max_spread_r`` is declared **inert** below this rate in every decile. Between the two the
#: gate is **left alone and reported as calibrated** — a third outcome with its own range, not a
#: default. A one-sided threshold would make "the gate is fine" unfalsifiable, which is the
#: v1.3.1 defect class.
Q4_INERT_BELOW_PCT: Final = 2

#: A21's concern is specifically cheap stocks, and an aggregate rate hides a cheap-stock outage,
#: so the recalibration clause is also evaluated per decile below this price.
Q4_CHEAP_STOCK_CEILING_USD: Final = 5

#: Price deciles for Q4 reporting.
Q4_DECILES: Final = 10

# --- Process (§7 rows 10-11) ----------------------------------------------------------

#: Weeks from first vendor contact. On expiry, whatever is answered is reported and the rest is
#: recorded as unanswered with the reason. The spike does not extend to reach a conclusion.
TIMEBOX_WEEKS: Final = 4

#: Total spend on trials and subscriptions. Q4 runs first because it needs no subscription, so a
#: budget overrun cannot cost the one answer that can invalidate a shipped default.
BUDGET_USD: Final = 600


def pct(whole: int) -> Decimal:
    """An ``int`` percent as a ``Decimal`` fraction.

    Conversion happens here rather than at each comparison so that the fraction is constructed
    from integer arithmetic — ``Decimal(30) / Decimal(100)`` — and never as a ``Decimal("0.30")``
    string literal that would read as a threshold restatement.
    """
    return Decimal(whole) / Decimal(100)


#: §7's Q4 verdict vocabulary. Named rather than stringly-typed at each call site so the dead
#: band cannot be silently collapsed into a two-way test.
Q4_RECALIBRATE: Final = "recalibrate"
Q4_CALIBRATED: Final = "calibrated"
Q4_INERT: Final = "inert"
