"""Q2 — float and short-interest quality. **Half-answerable, and it says so.**

PHASE-2A-SPIKE.md Q2: *"How fresh and accurate is float and short-interest data on a sample of
recent gappers?"* §7 gives it two pass conditions, and A10 trips on **either**:

1. **Disagreement** — two providers differ by more than ``Q2_DISAGREEMENT_PCT`` on more than
   ``Q2_MAX_DISAGREEING_SYMBOLS_PCT`` of sampled symbols.
2. **Staleness** — more than ``Q2_MAX_STALE_SYMBOLS_PCT`` of symbols carry a float as-of date
   older than ``Q2_MAX_FLOAT_AGE_DAYS``.

**Condition 1 is not runnable on one provider, and this module refuses to pretend otherwise.**
With Finviz alone there is no disagreement rate — not a low one, *none* — so
:func:`disagreement` returns ``None`` rather than zero. A zero would read as agreement and would
mark A10 untripped on evidence that does not exist, which is the exact shape of the fifth defect
class: an answer produced by a check that was not in a position to ask the question.

**Condition 2 is runnable now**, and can trip A10 on its own.

One further note, from §3.3: *"Finviz is A10's assumed source and should be measured, not
inherited."* Treating it as the primary source is the inheriting move. It is the right place to
start and the wrong place to stop, and the report says which of the two it is.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from scripts.spike2a.prereg import (
    Q2_DISAGREEMENT_PCT,
    Q2_MAX_DISAGREEING_SYMBOLS_PCT,
    Q2_MAX_FLOAT_AGE_DAYS,
    Q2_MAX_STALE_SYMBOLS_PCT,
    pct,
)
from scripts.spike2a.provenance import Provenance, ProvenanceError, banner, require


@dataclass(frozen=True)
class FloatReading:
    """One provider's float and short interest for one symbol, with its as-of date."""

    symbol: str
    provider: str
    float_shares: Decimal
    as_of: date
    short_interest_shares: Decimal | None = None

    def age_days(self, measured_on: date) -> int:
        return (measured_on - self.as_of).days


def staleness(readings: list[FloatReading], measured_on: date) -> tuple[Decimal | None, list[str]]:
    """Share of symbols whose float is older than §7 allows, and which ones.

    Computed per **symbol**, not per reading: §7's threshold is a share of sampled symbols, and
    counting readings would let a provider with two rows per symbol dominate the rate.
    """
    by_symbol: dict[str, list[FloatReading]] = {}
    for r in readings:
        by_symbol.setdefault(r.symbol, []).append(r)
    if not by_symbol:
        return None, []

    # Freshest reading per symbol — a symbol is stale only if *nothing* current exists for it.
    stale = sorted(
        sym
        for sym, rs in by_symbol.items()
        if min(r.age_days(measured_on) for r in rs) > Q2_MAX_FLOAT_AGE_DAYS
    )
    return Decimal(len(stale)) / Decimal(len(by_symbol)), stale


def disagreement(readings: list[FloatReading]) -> tuple[Decimal | None, list[str]]:
    """Share of symbols where two providers differ materially — or ``None`` if there is one.

    ``None`` is the load-bearing return value. See the module docstring: with a single provider
    this condition is unmeasured, and unmeasured is not the same as passed.

    Difference is expressed against the **larger** of the two floats, so the rate is symmetric in
    provider order. Dividing by a nominated "reference" provider would make the answer depend on
    which vendor was called primary, which is precisely the inheritance §3.3 warns against.
    """
    providers = {r.provider for r in readings}
    if len(providers) < 2:
        return None, []

    by_symbol: dict[str, dict[str, Decimal]] = {}
    for r in readings:
        by_symbol.setdefault(r.symbol, {})[r.provider] = r.float_shares

    comparable = {s: v for s, v in by_symbol.items() if len(v) >= 2}
    if not comparable:
        return None, []

    threshold = pct(Q2_DISAGREEMENT_PCT)
    disagreeing = []
    for symbol, floats in sorted(comparable.items()):
        values = sorted(floats.values())
        lo, hi = values[0], values[-1]
        if hi > 0 and (hi - lo) / hi > threshold:
            disagreeing.append(symbol)

    return Decimal(len(disagreeing)) / Decimal(len(comparable)), disagreeing


def report(readings: list[FloatReading], measured_on: date, prov: Provenance) -> str:
    """D2, with the unanswerable half marked unanswerable — and the whole thing withheld on
    simulated input.

    Q2's output is entirely threshold comparisons against §7 and a named **A10** disposition, so
    it is the same hazard Q4's verdict was: a line reading "within threshold" beside a PRD
    assumption is the sentence a reader quotes. The first version of D30 wired the *gate* to all
    five entry points and the *withholding* to two, leaving this module printing "A10 not tripped
    by this sample" over fabricated floats.
    """
    providers = sorted({r.provider for r in readings})
    symbols = sorted({r.symbol for r in readings})

    stale_rate, stale_symbols = staleness(readings, measured_on)
    dis_rate, dis_symbols = disagreement(readings)

    stale_trips = stale_rate is not None and stale_rate > pct(Q2_MAX_STALE_SYMBOLS_PCT)
    dis_trips = dis_rate is not None and dis_rate > pct(Q2_MAX_DISAGREEING_SYMBOLS_PCT)

    lines = [
        "Q2 — float and short-interest quality",
        "=" * 62,
        "",
        *banner(prov),
        "",
        f"measured on      {measured_on.isoformat()}",
        f"providers        {', '.join(providers) or '(none)'}",
        f"symbols          {len(symbols)}",
        "",
        f"staleness  (> {Q2_MAX_FLOAT_AGE_DAYS}d as-of)",
    ]

    if stale_rate is None:
        lines.append("  no readings — nothing measured")
    else:
        lines.append(
            f"  {stale_rate * 100:.2f}% of symbols stale "
            f"({len(stale_symbols)}/{len(symbols)}), threshold {Q2_MAX_STALE_SYMBOLS_PCT}%"
            f"  -> {'TRIPS A10' if stale_trips else 'within threshold'}"
        )

    lines += ["", f"disagreement  (> {Q2_DISAGREEMENT_PCT}% between providers)"]
    if dis_rate is None:
        lines += [
            f"  UNANSWERED — needs two independent providers, have {len(providers)}",
            "  Not a pass. §7's condition 1 is unmeasured, and unmeasured is not zero:",
            "  a 0% disagreement rate computed from one provider would mark A10 untripped",
            "  on evidence that does not exist.",
        ]
    else:
        lines.append(
            f"  {dis_rate * 100:.2f}% of symbols disagree ({len(dis_symbols)}), "
            f"threshold {Q2_MAX_DISAGREEING_SYMBOLS_PCT}%"
            f"  -> {'TRIPS A10' if dis_trips else 'within threshold'}"
        )

    if not prov.answers_prereg:
        lines += [
            "",
            "A10 disposition WITHHELD",
            "  These floats were fabricated. A staleness rate over generated as-of dates is a",
            "  property of the generator, so it can neither trip A10 nor clear it, and §7's",
            "  thresholds bind against measured data. Q2 stays unanswered until the ladder",
            "  reaches PAPER (PLAN D30).",
        ]
        return "\n".join(lines)

    lines += ["", "A10 disposition"]
    if stale_trips or dis_trips:
        lines += [
            "  CONFIRMED as a live risk. Options, all three spec decisions: widen the float",
            "  ceiling to absorb error, require two-provider agreement, or downgrade float from",
            "  hard filter to soft. Raise per D7; do not apply.",
        ]
    elif dis_rate is None:
        lines += [
            "  PARTIAL. The staleness half is within threshold; the disagreement half is",
            "  unmeasured. Q2 remains open per §6, which permits finishing with an unanswered",
            "  question provided the reason is recorded. The reason is: one provider.",
        ]
    else:
        lines.append("  Both conditions within threshold. A10 not tripped by this sample.")

    if stale_symbols:
        lines += ["", "stale symbols:", "  " + ", ".join(stale_symbols[:30])]
    if dis_symbols:
        lines += ["", "disagreeing symbols:", "  " + ", ".join(dis_symbols[:30])]
    return "\n".join(lines)


def from_csv_row(row: dict[str, str]) -> FloatReading | None:
    """Parse ``symbol,provider,float_shares,as_of[,short_interest_shares]``."""
    try:
        short = (row.get("short_interest_shares") or "").strip()
        return FloatReading(
            symbol=row["symbol"].strip().upper(),
            provider=row["provider"].strip().lower(),
            float_shares=Decimal(row["float_shares"]),
            as_of=datetime.strptime(row["as_of"].strip(), "%Y-%m-%d").date(),
            short_interest_shares=Decimal(short) if short else None,
        )
    except (KeyError, ValueError, InvalidOperation):
        return None


def main(argv: list[str]) -> int:
    """``python -m scripts.spike2a.q2_float <float_readings.csv> [measured-on YYYY-MM-DD]``"""
    if not argv:
        print(__doc__)
        print("usage: python -m scripts.spike2a.q2_float <float_readings.csv> [YYYY-MM-DD]")
        return 2

    path = Path(argv[0])
    try:
        prov = require(path)
    except ProvenanceError as exc:
        print(f"refusing to read: {exc}", file=sys.stderr)
        return 3

    with path.open(newline="", encoding="utf-8") as fh:
        parsed = [from_csv_row(r) for r in csv.DictReader(fh)]
    readings = [r for r in parsed if r is not None]
    measured_on = datetime.strptime(argv[1], "%Y-%m-%d").date() if len(argv) > 1 else date.today()

    print(report(readings, measured_on, prov))
    if len(parsed) != len(readings):
        print(f"\n{len(parsed) - len(readings)} unparsable row(s) skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
