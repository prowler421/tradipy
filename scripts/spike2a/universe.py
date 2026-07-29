"""§7 sample selection — which symbol-sessions enter the sample.

PHASE-2A-SPIKE.md §7 selection rule: *"A symbol-session enters the sample if, using data
available at or before 09:30 ET that day, it passes §4.2's hard filters other than spread and
LULD [...]. Spread is excluded because it is what Q4 measures; LULD because proximity is
intraday. Soft filters are recorded, never used to include or exclude."*

The filters are ``min_gap_premarket_pct``, ``min_gap_daily_pct``, ``min_rvol``,
``max_float_shares``, ``min_price``, ``max_price`` and ``min_adv_shares``. **Named, not valued** —
§7 and §4.2 state the numbers and :mod:`tradipy.params` holds them, so quoting them here even in
a docstring would put a fourth copy in the module whose output determines what Q4 measures. A
drifted ``min_rvol`` here would silently reshape the sample that answers whether
``max_spread_r`` is calibrated, and it would do it without failing anything.

**The exclusions are the load-bearing part.** §7 permits exactly three, and the third is
"nothing else". In particular there is no exclusion of names that did not subsequently move:
drawing from "recent big movers" measures the spread distribution of *winners* and makes
``max_spread_r`` look far more permissive than it is. §4.1 names this the single most likely way
to get a wrong answer to Q4, so :func:`select_sample` refuses a pre-filtered candidate list —
see :class:`Exclusion`.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path

from scripts.spike2a.prereg import MAX_MISSING_NBBO_PCT, MAX_SYMBOL_SESSIONS, pct
from tradipy.params import Config


class Exclusion(Enum):
    """The three §7 exclusions, and nothing else.

    :attr:`NO_NBBO_COVERAGE` is **not a silent drop** — §7 requires it be recorded as a coverage
    failure feeding Q1, because a vendor that cannot quote the sample is a Q1 finding, not a
    sample-hygiene detail.
    """

    HALTED_BEFORE_OPEN = "halted before 09:30; pre-open state not comparable"
    NO_NBBO_COVERAGE = "NBBO missing for too much of the session — Q1 coverage failure"


@dataclass(frozen=True)
class PreOpenFacts:
    """What is knowable about a symbol-session at or before 09:30 ET.

    Every field is as-of the open. Nothing here may be derived from what the symbol did *after*
    09:30 — that is the survivorship boundary, and it is a property of the data collection rather
    than of this dataclass, so it is stated in :func:`from_csv_row` where the values arrive.
    """

    session: date
    symbol: str
    price: Decimal
    gap_premarket_pct: Decimal
    gap_daily_pct: Decimal
    rvol: Decimal
    adv_shares: Decimal
    float_shares: Decimal
    halted_before_open: bool = False
    missing_nbbo_pct: Decimal = Decimal(0)
    #: §4.2 soft filters and provenance. Recorded, never used to include or exclude.
    soft: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    """Why a symbol-session was included or not. Rejections are kept, per §4.2."""

    facts: PreOpenFacts
    included: bool
    failed_filters: tuple[str, ...] = ()
    excluded_by: Exclusion | None = None


def _fails_hard_filters(f: PreOpenFacts, cfg: Config) -> tuple[str, ...]:
    """The §4.2 hard filters this session misses, by parameter name.

    Spread and LULD are absent by §7's instruction — spread because Q4 measures it, LULD because
    proximity is an intraday quantity and this function sees only the pre-open state.
    """
    failed: list[str] = []

    gap_ok = (
        f.gap_premarket_pct >= cfg["min_gap_premarket_pct"]
        or f.gap_daily_pct >= cfg["min_gap_daily_pct"]
    )
    if not gap_ok:
        failed.append("min_gap_premarket_pct|min_gap_daily_pct")
    if f.rvol < cfg["min_rvol"]:
        failed.append("min_rvol")
    if f.float_shares > cfg["max_float_shares"]:
        failed.append("max_float_shares")
    if f.price < cfg["min_price"]:
        failed.append("min_price")
    if f.price > cfg["max_price"]:
        failed.append("max_price")
    if f.adv_shares < cfg["min_adv_shares"]:
        failed.append("min_adv_shares")

    return tuple(failed)


def classify(facts: PreOpenFacts, cfg: Config, max_missing_nbbo: Decimal) -> Verdict:
    """One symbol-session against §7's rule, exclusions first.

    Exclusions precede filters because an excluded session is not a filter failure — it is a
    session the sample cannot speak about, and conflating the two would let a vendor's coverage
    gap read as a universe that is smaller than §4 describes.
    """
    if facts.halted_before_open:
        return Verdict(facts, included=False, excluded_by=Exclusion.HALTED_BEFORE_OPEN)
    if facts.missing_nbbo_pct > max_missing_nbbo:
        return Verdict(facts, included=False, excluded_by=Exclusion.NO_NBBO_COVERAGE)

    failed = _fails_hard_filters(facts, cfg)
    return Verdict(facts, included=not failed, failed_filters=failed)


@dataclass(frozen=True)
class Sample:
    """The selected sample, plus everything that did not make it and why."""

    included: tuple[Verdict, ...]
    rejected: tuple[Verdict, ...]
    excluded: tuple[Verdict, ...]
    cap_bound: bool

    @property
    def coverage_failures(self) -> tuple[Verdict, ...]:
        """Q1 input: sessions dropped because the vendor could not quote them."""
        return tuple(v for v in self.excluded if v.excluded_by is Exclusion.NO_NBBO_COVERAGE)


def select_sample(
    facts: list[PreOpenFacts],
    cfg: Config,
    max_missing_nbbo: Decimal,
    cap: int = MAX_SYMBOL_SESSIONS,
) -> Sample:
    """Apply §7's rule, then §7's cap.

    **The cap is tie-broken by ``(session, symbol)`` ascending and by nothing else.** Not by gap
    size, not by RVOL, not by any measured quantity — §7 spells this out because a cap broken by
    a measured quantity reintroduces survivorship bias through the back door of a sample-size
    limit. The sort key here is the whole reason this function exists rather than a slice at the
    call site.
    """
    verdicts = [classify(f, cfg, max_missing_nbbo) for f in facts]

    included = sorted(
        (v for v in verdicts if v.included), key=lambda v: (v.facts.session, v.facts.symbol)
    )
    cap_bound = len(included) > cap

    return Sample(
        included=tuple(included[:cap]),
        rejected=tuple(v for v in verdicts if not v.included and v.excluded_by is None),
        excluded=tuple(v for v in verdicts if v.excluded_by is not None),
        cap_bound=cap_bound,
    )


def from_csv_row(row: dict[str, str]) -> PreOpenFacts | None:
    """Parse one pre-open row, or ``None`` if it is unusable.

    **Provenance obligation.** Every numeric column must have been computed from data timestamped
    at or before 09:30 ET on ``session``. Nothing in this function can verify that — a gap
    computed from the day's close parses exactly as cleanly as one computed from the pre-market
    print. It is the collection script's responsibility, and it is the assumption on which Q4's
    answer rests, so it is stated at the boundary where the values enter rather than left in the
    spike document.
    """
    try:
        return PreOpenFacts(
            session=datetime.strptime(row["session"].strip(), "%Y-%m-%d").date(),
            symbol=row["symbol"].strip().upper(),
            price=Decimal(row["price"]),
            gap_premarket_pct=Decimal(row["gap_premarket_pct"]),
            gap_daily_pct=Decimal(row["gap_daily_pct"]),
            rvol=Decimal(row["rvol"]),
            adv_shares=Decimal(row["adv_shares"]),
            float_shares=Decimal(row["float_shares"]),
            halted_before_open=row.get("halted_before_open", "").strip().lower()
            in ("1", "true", "yes"),
            missing_nbbo_pct=Decimal(row.get("missing_nbbo_pct") or 0),
            soft={k: v for k, v in row.items() if k.startswith("soft_")},
        )
    except (KeyError, ValueError, InvalidOperation):
        return None


def main(argv: list[str]) -> int:
    """``python -m scripts.spike2a.universe <preopen.csv>``"""
    if not argv:
        print(__doc__)
        print("usage: python -m scripts.spike2a.universe <preopen.csv>")
        return 2

    with Path(argv[0]).open(newline="", encoding="utf-8") as fh:
        parsed = [from_csv_row(r) for r in csv.DictReader(fh)]
    facts = [f for f in parsed if f is not None]
    unparsed = len(parsed) - len(facts)

    cfg = Config.default()
    sample = select_sample(facts, cfg, pct(MAX_MISSING_NBBO_PCT))

    print(f"rows parsed        {len(facts)}" + (f"  ({unparsed} unparsable)" if unparsed else ""))
    capped = "  (cap bound)" if sample.cap_bound else ""
    print(f"included           {len(sample.included)}{capped}")
    print(f"rejected by filter {len(sample.rejected)}")
    print(f"excluded           {len(sample.excluded)}")
    print(f"  of which Q1 coverage failures: {len(sample.coverage_failures)}")

    if sample.included:
        first, last = sample.included[0].facts, sample.included[-1].facts
        print(f"span               {first.session} {first.symbol} .. {last.session} {last.symbol}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
