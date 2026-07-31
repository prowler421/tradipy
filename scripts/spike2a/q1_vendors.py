"""Q1 — real-time candidate list feasibility (vendor trial matrix).

PHASE-2A-SPIKE.md Q1: *"Can a real-time candidate list matching §4.2's hard filters be obtained,
from which provider, at what cost and what refresh interval?"* A negative answer rewrites PRD §4
and gates Phase 3 (PLAN D29).

There is no wire to pull here — vendor trials are a documentation-and-spreadsheet exercise until
the ladder reaches ``PAPER``. This module reads a pre-registered trial matrix (``vendors.csv``)
and applies §7's Q1 pass thresholds from :mod:`scripts.spike2a.prereg`, the same way
:mod:`scripts.spike2a.q4_spreads` applies §7's Q4 thresholds to spread rows.

On ``SIMULATED`` input the outcome is a **pipeline outcome, not a §7 verdict**, for the same
reason as Q2–Q4: fabricated numbers must not license a D7 disposition or a Phase 3 go-ahead.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from decimal import InvalidOperation
from pathlib import Path

from scripts.spike2a.prereg import (
    Q1_MAX_MONTHLY_USD,
    Q1_MAX_REFRESH_SECONDS,
    Q1_MIN_CONCURRENT_SYMBOLS,
    Q1_MIN_SAMPLE_COVERAGE_PCT,
)
from scripts.spike2a.provenance import Provenance, ProvenanceError, banner, require


@dataclass(frozen=True)
class VendorTrial:
    """One row of a vendor evaluation matrix."""

    provider: str
    monthly_cost_usd: int
    concurrent_symbols: int
    refresh_seconds: int
    sample_coverage_pct: int
    hard_filters_expressible: bool
    notes: str = ""


def evaluate(trial: VendorTrial) -> tuple[bool, list[str]]:
    """Apply §7's Q1 pass thresholds. Any single failure is a Q1 negative for that provider."""
    failures: list[str] = []
    if trial.sample_coverage_pct < Q1_MIN_SAMPLE_COVERAGE_PCT:
        failures.append(f"coverage {trial.sample_coverage_pct}% < {Q1_MIN_SAMPLE_COVERAGE_PCT}%")
    if not trial.hard_filters_expressible:
        failures.append("does not express or client-side-filter the full §4.2 hard set")
    if trial.concurrent_symbols < Q1_MIN_CONCURRENT_SYMBOLS:
        failures.append(
            f"concurrent symbols {trial.concurrent_symbols} < {Q1_MIN_CONCURRENT_SYMBOLS}"
        )
    if trial.refresh_seconds > Q1_MAX_REFRESH_SECONDS:
        failures.append(f"refresh {trial.refresh_seconds}s > {Q1_MAX_REFRESH_SECONDS}s")
    if trial.monthly_cost_usd > Q1_MAX_MONTHLY_USD:
        failures.append(f"cost ${trial.monthly_cost_usd}/mo > ${Q1_MAX_MONTHLY_USD}")
    return not failures, failures


def from_csv_row(row: dict[str, str]) -> VendorTrial | None:
    """Parse ``provider,monthly_cost_usd,concurrent_symbols,refresh_seconds,sample_coverage_pct,hard_filters_expressible[,notes]``."""
    try:
        expressible_raw = row["hard_filters_expressible"].strip().lower()
        expressible = expressible_raw in {"1", "true", "yes", "y"}
        notes = (row.get("notes") or "").strip()
        return VendorTrial(
            provider=row["provider"].strip(),
            monthly_cost_usd=int(row["monthly_cost_usd"]),
            concurrent_symbols=int(row["concurrent_symbols"]),
            refresh_seconds=int(row["refresh_seconds"]),
            sample_coverage_pct=int(row["sample_coverage_pct"]),
            hard_filters_expressible=expressible,
            notes=notes,
        )
    except (KeyError, ValueError, InvalidOperation):
        return None


def report(trials: list[VendorTrial], prov: Provenance) -> str:
    """D1-style matrix with pass/fail per provider."""
    lines = [
        "Q1 — real-time candidate list feasibility",
        "=" * 62,
        "",
        *banner(prov),
        "",
        f"providers evaluated   {len(trials)}",
        "",
        "per provider (§7 Q1 pass thresholds)",
    ]

    any_pass = False
    for trial in trials:
        ok, failures = evaluate(trial)
        any_pass = any_pass or ok
        status = "PASS" if ok else "FAIL"
        lines.append(f"  {trial.provider:<20} {status}")
        if failures:
            for f in failures:
                lines.append(f"    - {f}")
        if trial.notes:
            lines.append(f"    note: {trial.notes}")

    headline = (
        "§7 verdict: at least one provider passes Q1"
        if prov.answers_prereg and any_pass
        else "§7 verdict: no provider passes Q1"
        if prov.answers_prereg
        else "pipeline outcome (NOT a §7 verdict): "
        + (
            "at least one provider passes Q1 thresholds"
            if any_pass
            else "no provider passes Q1 thresholds"
        )
    )

    lines += ["", headline]
    if not prov.answers_prereg:
        lines += [
            "",
            "This run exercises the pipeline. It does not answer Q1, and no PRD §4 rewrite",
            "follows from it: §7's thresholds bind against measured vendor trials, and a",
            "synthetic matrix is not a trial. See docs/PHASE-2A-SPIKE.md §7 and PLAN D30.",
        ]
    elif not any_pass:
        lines += [
            "",
            "Implication per §6: PRD §4 is rewritten before Phase 3 (scanner) starts.",
        ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    """``python -m scripts.spike2a.q1_vendors <vendors.csv>``"""
    if not argv:
        print(__doc__)
        print("usage: python -m scripts.spike2a.q1_vendors <vendors.csv>")
        return 2

    path = Path(argv[0])
    try:
        prov = require(path)
    except ProvenanceError as exc:
        print(f"refusing to read: {exc}", file=sys.stderr)
        return 3

    with path.open(newline="", encoding="utf-8") as fh:
        parsed = [from_csv_row(r) for r in csv.DictReader(fh)]
    trials = [t for t in parsed if t is not None]

    print(report(trials, prov))
    if len(parsed) != len(trials):
        print(f"\n{len(parsed) - len(trials)} unparsable row(s) skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
