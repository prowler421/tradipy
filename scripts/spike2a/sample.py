"""§7 sample definition — joining the window rule to the selection rule.

PHASE-2A-SPIKE.md §7's sample-size row defines the sample as every symbol-session **in the two
windows** that passes the selection rule, capped at 400 symbol-sessions — tie-broken by
``(date, symbol)`` ascending and never by a measured quantity. :mod:`scripts.spike2a.windows`
computes the windows and :mod:`scripts.spike2a.universe` applies the filters and the cap; until
now nothing joined them, so ``universe.select_sample`` ranged over whatever ``preopen.csv``
contained, inside the windows or not. Review round 7 (H5) reproduced this by execution: on the
repository's own `vix.csv`, 79 of 156 generated rows fell outside both selected windows and the
quiet window held none at all, while ``universe.py`` reported a clean ``156 parsed / 156
included`` — a result over a population §7 does not define.

**Where the join belongs was left as a scope decision rather than fixed** (`docs/CHANGELOG.md`
Unreleased, H5), because each of the three options changes something: inside ``select_sample``
it makes that module the definition of the sample and changes a documented signature; in the
collection script §7 assumes, the binding half of the sample definition would be enforced by a
script the repository does not contain; in a new composing module, the round warned, that is
"the first step of the accretion §8 forbids". This module takes that third option anyway, for a
reason the round did not have in front of it: §8's accretion warning is about spike code growing
into the production scanner by acquiring scanning capability. This module composes two existing
spike modules to implement the sample §7 already commits to — it adds no filter, no threshold,
and no capability neither module already has, and nothing here would be reused by a scanner
built fresh against the PRD per D29. ``windows.py`` and ``universe.py`` are unchanged; this is a
fourth, separately-named thing, the same way ``poc.py`` composes the library's gates without any
gate module knowing about the others.

**Window membership is not a §7 exclusion.** :class:`scripts.spike2a.universe.Exclusion` has
exactly three members, covering a symbol-session that would otherwise be a *candidate* — one
already inside the windows. A session outside the windows was never a candidate: §7's sample-size
row defines the population as sessions in the two windows, so restriction to it happens *before*
exclusions or filters run. Accordingly this module reports out-of-window sessions under their own
names, never folded into ``Sample.rejected`` or ``Sample.excluded``.

**A unit error is a property of the file, not of window membership.**
``PreOpenFacts.check_units()`` is called by ``universe.classify`` before anything else — but
``classify`` only ever sees the rows :func:`select_sample_in_windows` passes it, which, without
care, would be the in-window rows alone. A malformed row (a percentage where a fraction belongs)
that happens to land outside the windows would then run clean, and a §7 sample would be reported
over a file this module never fully validated. So every parsed row is checked here regardless of
which population it ends up in.

**A window's calendar span is not the same as its session list.** A :class:`~scripts.spike2a.
windows.Window` spans ``WINDOW_SESSIONS`` trading days, but ``start``..``end`` covers more
calendar days than that — weekends sit inside it. A pre-open row dated inside a window's span but
absent from its ``sessions`` tuple is not simply "outside the window": it is a day the pre-open
file and the VIX series the window was computed from disagree about, which is a source-quality
question worth its own count rather than being indistinguishable from a session §7's rule
genuinely does not select.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from scripts.spike2a.prereg import MAX_MISSING_NBBO_PCT, MAX_SYMBOL_SESSIONS, pct
from scripts.spike2a.universe import PreOpenFacts, Sample, from_csv_row, select_sample
from scripts.spike2a.windows import Window, read_vix_csv, select_windows
from tradipy.params import Config


def _in_span(session: date, window: Window) -> bool:
    """Whether ``session`` falls within ``window``'s calendar range, in ``sessions`` or not.

    See the module docstring's "calendar span" paragraph — this is the predicate that separates
    a genuine non-candidate from a source disagreement between the pre-open file and the VIX
    series.
    """
    return window.start <= session <= window.end


@dataclass(frozen=True)
class WindowedSample:
    """The §7 sample end to end: the two windows, what fell outside them, and the result within.

    ``span_gap`` and ``out_of_span`` are both "did not enter :attr:`sample`", but they are not the
    same finding. ``out_of_span`` is a session §7's window rule genuinely does not select.
    ``span_gap`` is a session inside a window's calendar range that the *source data* disagrees
    about — present in the pre-open file, absent from the VIX series the window was computed
    from — which is worth a warning distinct from "not a candidate".
    """

    active: Window
    quiet: Window
    in_window: tuple[PreOpenFacts, ...]
    span_gap: tuple[PreOpenFacts, ...]
    out_of_span: tuple[PreOpenFacts, ...]
    sample: Sample

    @property
    def out_of_window(self) -> tuple[PreOpenFacts, ...]:
        """Every session that did not enter the candidate population, both reasons combined."""
        return self.span_gap + self.out_of_span


def select_sample_in_windows(
    facts: list[PreOpenFacts],
    active: Window,
    quiet: Window,
    cfg: Config,
    max_missing_nbbo: Decimal,
    cap: int = MAX_SYMBOL_SESSIONS,
) -> WindowedSample:
    """Restrict ``facts`` to the two windows, then apply §7's selection rule to what remains.

    Every fact is unit-checked here, in-window or not — see the module docstring's "A unit error"
    paragraph. ``universe.classify`` checks units too, redundantly for the in-window rows this
    function passes it; that duplication is harmless and cheaper than trusting a second caller to
    have already done it.
    """
    sessions = set(active.sessions) | set(quiet.sessions)
    in_window: list[PreOpenFacts] = []
    span_gap: list[PreOpenFacts] = []
    out_of_span: list[PreOpenFacts] = []

    for f in facts:
        f.check_units()
        if f.session in sessions:
            in_window.append(f)
        elif _in_span(f.session, active) or _in_span(f.session, quiet):
            span_gap.append(f)
        else:
            out_of_span.append(f)

    sample = select_sample(in_window, cfg, max_missing_nbbo, cap)
    return WindowedSample(
        active=active,
        quiet=quiet,
        in_window=tuple(in_window),
        span_gap=tuple(span_gap),
        out_of_span=tuple(out_of_span),
        sample=sample,
    )


def main(argv: list[str]) -> int:
    """``python -m scripts.spike2a.sample <vix.csv> <preopen.csv> [as-of YYYY-MM-DD]``

    The one command that runs §7's full sample definition end to end: pick the windows from
    ``vix.csv``, restrict ``preopen.csv`` to them, then apply the selection rule.
    ``universe.py``'s own CLI is unchanged and still reports on an unrestricted file — see its
    module docstring — because this module is additive, not a replacement.
    """
    if len(argv) < 2:
        print(__doc__)
        print("usage: python -m scripts.spike2a.sample <vix.csv> <preopen.csv> [as-of YYYY-MM-DD]")
        return 2

    series = read_vix_csv(Path(argv[0]))
    as_of = datetime.strptime(argv[2], "%Y-%m-%d").date() if len(argv) > 2 else date.today()
    active, quiet = select_windows(series, as_of)

    with Path(argv[1]).open(newline="", encoding="utf-8") as fh:
        parsed = [from_csv_row(r) for r in csv.DictReader(fh)]
    facts = [f for f in parsed if f is not None]
    unparsed = len(parsed) - len(facts)

    cfg = Config.default()
    windowed = select_sample_in_windows(facts, active, quiet, cfg, pct(MAX_MISSING_NBBO_PCT))
    sample = windowed.sample

    print(f"as-of              {as_of}")
    print(f"  active window    {active.start}..{active.end}  mean VIX {active.mean_vix:.2f}")
    print(f"  quiet window     {quiet.start}..{quiet.end}  mean VIX {quiet.mean_vix:.2f}")
    print(f"rows parsed        {len(facts)}" + (f"  ({unparsed} unparsable)" if unparsed else ""))
    print(f"in windows         {len(windowed.in_window)}")
    print(
        f"outside windows    {len(windowed.out_of_window)}  (not candidates — not a §7 exclusion)"
    )
    if windowed.span_gap:
        print(
            f"  of which in a window's span but missing from vix.csv: {len(windowed.span_gap)}"
            "  (source disagreement — check preopen.csv against vix.csv)"
        )
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
