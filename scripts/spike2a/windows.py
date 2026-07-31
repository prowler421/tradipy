"""§7 window selection — the two sample windows, chosen by rule rather than by eye.

PHASE-2A-SPIKE.md §7: *"Compute daily closing VIX over the 12 months ending the day before the
spike starts. Take the highest-VIX 10 consecutive sessions as the active window and the
lowest-VIX 10 consecutive sessions as the quiet window, non-overlapping; if they overlap, take
the lowest-VIX non-overlapping run."*

**Why a rule and not dates.** Pre-registration requires committing before looking, and you
cannot know which stretch was quiet without looking at something. Routing the choice through VIX
— a series this spike neither measures nor influences — gives windows fixed in advance and still
verifiably quiet. Run the rule twice and it returns the same windows, which is the property that
makes it a pre-registration rather than a preference.

Input is a CSV of ``date,close``. Stdlib only; no vendor, no network, no broker.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from scripts.spike2a.prereg import VIX_LOOKBACK_MONTHS, WINDOW_SESSIONS
from scripts.spike2a.provenance import ProvenanceError, banner, require

#: Days per lookback month. §7 says "12 months"; a calendar-month walk-back and a 365-day
#: walk-back select the same trading sessions to within a day, and the rule's output is
#: insensitive to that day because it picks an extremum over a 10-session run.
_DAYS_PER_MONTH = 30


def _spans_overlap(start: date, end: date, sessions: tuple[date, ...]) -> bool:
    """Whether ``[start, end]`` intersects the span of ``sessions``.

    The one definition of "overlap" in this module. :meth:`Window.overlaps` and
    :func:`select_windows`'s non-overlap filter both route through it — they had the same
    comparison written out twice, which is the shape of defect the registry exists to prevent,
    reproduced in a predicate instead of a threshold.
    """
    return start <= sessions[-1] and sessions[0] <= end


@dataclass(frozen=True)
class Window:
    """A run of ``WINDOW_SESSIONS`` consecutive sessions, with the mean VIX that selected it."""

    label: str
    start: date
    end: date
    mean_vix: Decimal
    sessions: tuple[date, ...]

    def overlaps(self, other: Window) -> bool:
        return _spans_overlap(self.start, self.end, other.sessions)


def read_vix_csv(path: Path) -> list[tuple[date, Decimal]]:
    """Read ``date,close`` rows, sorted ascending, tolerating a header and blank closes.

    Blank or non-numeric closes are skipped rather than interpolated: an interpolated VIX would
    be a value this module invented appearing in a rule whose whole point is to be independent
    of anything the spike controls.
    """
    rows: list[tuple[date, Decimal]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            raw_date = (row.get("date") or row.get("DATE") or "").strip()
            raw_close = (row.get("close") or row.get("CLOSE") or "").strip()
            if not raw_date or not raw_close:
                continue
            try:
                parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
                close = Decimal(raw_close)
            except (ValueError, ArithmeticError):
                continue
            rows.append((parsed, close))
    return sorted(rows)


def _runs(series: list[tuple[date, Decimal]]) -> list[tuple[Decimal, tuple[date, ...]]]:
    """Every ``WINDOW_SESSIONS``-long consecutive run, with its mean close.

    "Consecutive" means consecutive *sessions* in the series, not consecutive calendar days —
    the series is already trading days only, so a weekend is not a gap.
    """
    out: list[tuple[Decimal, tuple[date, ...]]] = []
    for i in range(len(series) - WINDOW_SESSIONS + 1):
        chunk = series[i : i + WINDOW_SESSIONS]
        mean = sum((c for _, c in chunk), Decimal(0)) / Decimal(len(chunk))
        out.append((mean, tuple(d for d, _ in chunk)))
    return out


def select_windows(series: list[tuple[date, Decimal]], as_of: date) -> tuple[Window, Window]:
    """The §7 active and quiet windows.

    ``as_of`` is the day the spike starts; the series is truncated to the 12 months **ending the
    day before**, per §7. Truncation happens here rather than in the caller so that re-running
    with the same ``as_of`` cannot pick up sessions that did not exist when the rule was first
    run.

    The tie-break is §7's: if the extrema overlap, the active window stands and the quiet window
    becomes the lowest-VIX run that does not overlap it.
    """
    cutoff = as_of - timedelta(days=1)
    start = cutoff - timedelta(days=_DAYS_PER_MONTH * VIX_LOOKBACK_MONTHS)
    eligible = [(d, c) for d, c in series if start <= d <= cutoff]

    runs = _runs(eligible)
    if not runs:
        raise ValueError(
            f"need at least {WINDOW_SESSIONS} sessions between {start} and {cutoff}; "
            f"got {len(eligible)}"
        )

    # `max`/`min` on the mean alone would break ties by list order, which is date order — fine,
    # and stated so it is a choice rather than an accident.
    active_mean, active_sessions = max(runs, key=lambda r: (r[0], r[1][0]))
    active = Window("active", active_sessions[0], active_sessions[-1], active_mean, active_sessions)

    non_overlapping = [r for r in runs if not _spans_overlap(active.start, active.end, r[1])]
    if not non_overlapping:
        raise ValueError(
            "every candidate quiet window overlaps the active window; the series is too short "
            f"for two non-overlapping {WINDOW_SESSIONS}-session runs"
        )
    quiet_mean, quiet_sessions = min(non_overlapping, key=lambda r: (r[0], r[1][0]))
    quiet = Window("quiet", quiet_sessions[0], quiet_sessions[-1], quiet_mean, quiet_sessions)

    return active, quiet


def main(argv: list[str]) -> int:
    """``python -m scripts.spike2a.windows <vix.csv> [YYYY-MM-DD]``"""
    if not argv:
        print(__doc__)
        print("usage: python -m scripts.spike2a.windows <vix.csv> [as-of YYYY-MM-DD]")
        return 2

    path = Path(argv[0])
    try:
        prov = require(path)
    except ProvenanceError as exc:
        print(f"refusing to read: {exc}", file=sys.stderr)
        return 3

    series = read_vix_csv(path)
    as_of = datetime.strptime(argv[1], "%Y-%m-%d").date() if len(argv) > 1 else date.today()
    active, quiet = select_windows(series, as_of)

    print("\n".join(banner(prov)))
    print(f"as-of {as_of} — {len(series)} VIX sessions read")
    for w in (active, quiet):
        print(f"  {w.label:>6}: {w.start} .. {w.end}  mean VIX {w.mean_vix:.2f}")
    if active.overlaps(quiet):  # pragma: no cover - select_windows forbids it
        print("  WARNING: windows overlap, which select_windows should have prevented")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
