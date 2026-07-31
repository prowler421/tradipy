"""Q4 — realized NBBO spread distribution and the implied rejection rate.

PHASE-2A-SPIKE.md Q4: *"What is the realized NBBO spread distribution on qualifying names, and
what rejection rate does ``max_spread_r = 0.15`` imply per MVP setup?"* It directly tests **A21**,
whose worst case is that the §3.1.3 signal-time cap effectively disables VWAP Reclaim — one of
the three MVP setups.

**This is the question that matters most, and the one that can run first.** It needs historical
quote data on a known symbol list: no real-time subscription, no scanner, no vendor commitment.
§7's budget clause makes the ordering binding — Q4 runs before any money is spent, so a budget
overrun cannot cost the one answer that can invalidate a shipped default.

**The caps come from the library.** §4.3: *"Use the library, not a reimplementation — the point
is to test the shipped thresholds, and a second implementation of the cap arithmetic would be a
second definition of a registered threshold."* So :func:`tradipy.gates.spread_caps` computes the
caps and :func:`tradipy.quotes.spread_at_signal` computes the spread, including the §20.14
validity tests. If this module disagreed with the library by a tick, the measurement would report
the disagreement as a property of the market.

**Rejections are recorded, not dropped** (§4.2, §20.14): a rejection-rate question cannot be
answered from accepted candidates, and §20.14 requires ``spread_at_signal`` persisted for every
signal including rejected ones.

**Nothing here runs without a declared origin.** :func:`scripts.spike2a.provenance.require` gates
:func:`main`, and under PLAN **D30** the only permitted origin is ``SIMULATED``. That has a
consequence this module has to carry rather than paper over: §7's thresholds bind against
*measured* data, so on simulated input the three-way outcome below is a **pipeline outcome, not a
§7 verdict**, and the D7 disposition block does not fire. The wording is not cosmetic — round 7
found this pipeline printing "§7 verdict: INERT" over fabricated quotes, twice, with different
answers, and PLAN's own rule is that any value capable of triggering a D7 disposition must be
reproducible from a provenance-marked input.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from scripts.spike2a.feeds import CsvQuoteFeed, QuoteFeed, QuoteSample
from scripts.spike2a.prereg import (
    Q4_CALIBRATED,
    Q4_CHEAP_STOCK_CEILING_USD,
    Q4_DECILES,
    Q4_INERT,
    Q4_INERT_BELOW_PCT,
    Q4_RECALIBRATE,
    Q4_RECALIBRATE_ABOVE_PCT,
    pct,
)
from scripts.spike2a.provenance import Provenance, ProvenanceError, banner, require
from tradipy.gates import spread_caps
from tradipy.params import MODE_PRESETS, Config
from tradipy.quotes import spread_at_signal

#: The three MVP setups (D1). Q4 reports per setup because A21's concern is setup-specific.
MVP_SETUPS = ("bull_flag", "hod_breakout", "vwap_reclaim")


@dataclass(frozen=True)
class SignalBar:
    """A sampled signal instant: what the setup was, and what R it implies.

    ``r`` is supplied rather than derived here, and that is a real limitation stated plainly.
    Deriving it needs the per-setup stop rule applied to bar geometry — ``vwap_reclaim_stop``
    for §3.4, the flag low for §3.2, the pullback low for §3.3 — which needs bars this module
    does not read. The collection script computes it with the library's own stop functions and
    passes it in; **if it ever computes it by hand, Q4 is measuring a stop rule that is not the
    shipped one.** That is the single most likely way for this measurement to be quietly wrong.
    """

    symbol: str
    session: str
    setup: str
    price: Decimal
    r: Decimal
    quote: QuoteSample


@dataclass(frozen=True)
class Classification:
    """One signal bar against the §3.1.3 caps."""

    bar: SignalBar
    spread: Decimal | None
    signal_cap: Decimal
    scan_cap: Decimal
    #: ``None`` when the quote itself failed §20.14, in which case there is no spread to gate.
    rejected: bool | None
    reason: str


def classify(bar: SignalBar, cfg: Config) -> Classification:
    """Gate one signal bar, keeping quote-invalid apart from spread-too-wide.

    The distinction matters for the rate Q4 reports. A quote that fails §20.14 validity is not
    evidence about ``max_spread_r`` — folding it into the rejection rate would inflate the number
    that decides whether a shipped threshold gets recalibrated, using observations the threshold
    never saw.
    """
    caps = spread_caps(bar.price, bar.r, cfg)
    spread, quote_reject = spread_at_signal(bar.quote.as_quote(), cfg)

    if spread is None:
        return Classification(
            bar=bar,
            spread=None,
            signal_cap=caps.signal,
            scan_cap=caps.scan,
            rejected=None,
            reason=quote_reject.name if quote_reject else "NO_SPREAD",
        )

    too_wide = spread > caps.signal
    return Classification(
        bar=bar,
        spread=spread,
        signal_cap=caps.signal,
        scan_cap=caps.scan,
        rejected=too_wide,
        reason="SPREAD_TOO_WIDE" if too_wide else "PASS",
    )


@dataclass(frozen=True)
class Rate:
    """A rejection rate over a subpopulation, with the counts that produced it.

    ``lo``/``hi`` are set for price deciles and ``None`` otherwise. They exist so
    :func:`verdict` can apply §7's cheap-stock clause from the bucket's actual bounds — an
    earlier version parsed the price back out of ``label``, which made a display string
    load-bearing for a threshold decision.
    """

    label: str
    gated: int
    rejected: int
    quote_invalid: int
    lo: Decimal | None = None
    hi: Decimal | None = None

    @property
    def rate(self) -> Decimal | None:
        """Rejected over *gated*, excluding quote-invalid bars. ``None`` when nothing was gated."""
        if self.gated == 0:
            return None
        return Decimal(self.rejected) / Decimal(self.gated)

    def __str__(self) -> str:
        r = self.rate
        shown = "     n/a" if r is None else f"{r * 100:7.2f}%"
        return (
            f"{self.label:<22} {shown}  ({self.rejected}/{self.gated} gated"
            f"{f', {self.quote_invalid} quote-invalid' if self.quote_invalid else ''})"
        )


def _rate(
    label: str,
    rows: list[Classification],
    lo: Decimal | None = None,
    hi: Decimal | None = None,
) -> Rate:
    return Rate(
        label=label,
        gated=sum(1 for c in rows if c.rejected is not None),
        rejected=sum(1 for c in rows if c.rejected),
        quote_invalid=sum(1 for c in rows if c.rejected is None),
        lo=lo,
        hi=hi,
    )


def price_deciles(rows: list[Classification], buckets: int = Q4_DECILES) -> list[Rate]:
    """Rejection rate per price decile, cheapest first.

    Deciles are cut on the observed price distribution rather than on fixed dollar bands, so the
    buckets carry roughly equal weight. The §7 recalibration clause is evaluated per decile
    *below* ``Q4_CHEAP_STOCK_CEILING_USD``; :func:`verdict` applies that, not this function.

    Boundaries are computed by proportional index so that ``buckets`` buckets come back for any
    sample size — a fixed chunk width returns twelve "deciles" at n=45, and a per-decile
    threshold applied to twelve buckets is not the threshold §7 committed to.
    """
    if not rows:
        return []
    ordered = sorted(rows, key=lambda c: c.bar.price)
    n = len(ordered)
    out: list[Rate] = []
    for b in range(min(buckets, n)):
        start = b * n // min(buckets, n)
        end = (b + 1) * n // min(buckets, n)
        chunk = ordered[start:end]
        if not chunk:
            continue
        lo, hi = chunk[0].bar.price, chunk[-1].bar.price
        span = f"${lo}" if lo == hi else f"${lo}-${hi}"
        out.append(_rate(f"d{b + 1} {span}", chunk, lo=lo, hi=hi))
    return out


def verdict(overall: Rate, deciles: list[Rate]) -> tuple[str, str]:
    """§7's three-way Q4 outcome, with the clause that decided it.

    Order is deliberate. The cheap-stock decile clause is checked **before** the inert test, so a
    negligible aggregate rate cannot overrule a cheap-stock outage — which is the whole reason
    §7 states the clause per decile. Reversing these two lines would reproduce A21 while
    reporting that A21 did not occur.
    """
    recalibrate_at = pct(Q4_RECALIBRATE_ABOVE_PCT)
    inert_below = pct(Q4_INERT_BELOW_PCT)
    cheap = Decimal(Q4_CHEAP_STOCK_CEILING_USD)

    rate = overall.rate
    if rate is None:
        return Q4_CALIBRATED, "no gated bars — nothing measured, so nothing is claimed"

    if rate > recalibrate_at:
        return Q4_RECALIBRATE, f"aggregate {rate * 100:.2f}% > {Q4_RECALIBRATE_ABOVE_PCT}%"

    for d in deciles:
        d_rate = d.rate
        lo = d.lo
        if lo is not None and lo < cheap and d_rate is not None and d_rate > recalibrate_at:
            return (
                Q4_RECALIBRATE,
                f"decile {d.label} at {d_rate * 100:.2f}% > {Q4_RECALIBRATE_ABOVE_PCT}% "
                f"(below ${Q4_CHEAP_STOCK_CEILING_USD})",
            )

    if all((d.rate or Decimal(0)) < inert_below for d in deciles) and rate < inert_below:
        return Q4_INERT, f"every decile below {Q4_INERT_BELOW_PCT}% — the gate is decoration"

    # The fall-through said "aggregate X% inside the 2%-30% dead band", which is false whenever a
    # low aggregate is held out of INERT by a single hot decile — the case A21 is *about*. Round 7
    # reached it on the first corrected run: 1.36% aggregate, 14.29% in the cheapest decile, and a
    # message asserting 1.36% was inside a band starting at 2%. A verdict has to name the clause
    # that decided it, or the next reader recalibrates against a sentence rather than a rule.
    if rate < inert_below:
        hot = [d for d in deciles if (d.rate or Decimal(0)) >= inert_below]
        worst = max(hot, key=lambda d: d.rate or Decimal(0)) if hot else None
        detail = "" if worst is None else f"; worst {worst.label} at {(worst.rate or 0) * 100:.2f}%"
        return (
            Q4_CALIBRATED,
            f"aggregate {rate * 100:.2f}% is below {Q4_INERT_BELOW_PCT}% but {len(hot)} "
            f"decile(s) are not — not inert, so calibrated by elimination{detail}",
        )

    return (
        Q4_CALIBRATED,
        f"aggregate {rate * 100:.2f}% inside the "
        f"{Q4_INERT_BELOW_PCT}%-{Q4_RECALIBRATE_ABOVE_PCT}% dead band",
    )


def load_signal_bars(path: Path, feed: QuoteFeed) -> tuple[list[SignalBar], list[str]]:
    """Read sampled signal bars and attach the NBBO in force at each.

    Returns the bars and a list of coverage failures — symbol-sessions the feed could not quote.
    Per §7 exclusion (2) those are a **Q1 finding**, so they are returned rather than logged and
    forgotten.
    """
    bars: list[SignalBar] = []
    missing: list[str] = []

    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            symbol = row["symbol"].strip().upper()
            session = row["session"].strip()
            samples = feed.nbbo_for_session(symbol, session)
            if not samples:
                missing.append(f"{session} {symbol}")
                continue
            # The quote in force at the signal instant. With one sample per signal bar this is
            # that sample; with a full session of ticks the collection script narrows it first.
            bars.append(
                SignalBar(
                    symbol=symbol,
                    session=session,
                    setup=row.get("setup", "").strip() or "unknown",
                    price=Decimal(row["price"]),
                    r=Decimal(row["r"]),
                    quote=samples[-1],
                )
            )
    return bars, missing


def report(rows: list[Classification], missing: list[str], prov: Provenance) -> str:
    """D4, in the three cuts §4.3 requires: overall, per setup, per price decile.

    ``prov`` is required, not optional. A default would make the un-declared call the easy one
    to write, and the whole failure this parameter exists to prevent is a report that does not
    say what produced it.
    """
    overall = _rate("overall", rows)
    by_setup = {
        setup: _rate(setup, [c for c in rows if c.bar.setup == setup])
        for setup in sorted({c.bar.setup for c in rows} | set(MVP_SETUPS))
    }
    deciles = price_deciles(rows)
    outcome, why = verdict(overall, deciles)
    decile_lines = [f"  {r}" for r in deciles] or ["  (none)"]

    # §7 binds to measured data. On simulated input the same arithmetic runs and the same three
    # outcomes are reachable, but the label must not be one a reader can act on — see the module
    # docstring for what happened when it was.
    headline = (
        f"§7 verdict: {outcome.upper()} — {why}"
        if prov.answers_prereg
        else f"pipeline outcome (NOT a §7 verdict): {outcome.upper()} — {why}"
    )

    lines = [
        "Q4 — realized spread vs the §3.1.3 signal-time cap",
        "=" * 62,
        "",
        *banner(prov),
        "",
        f"signal bars      {len(rows)}",
        f"coverage gaps    {len(missing)}  (Q1 finding, per §7 exclusion 2)",
        "",
        "rejection rate",
        f"  {overall}",
        "",
        "per setup",
        *(f"  {r}" for r in by_setup.values()),
        "",
        "per price decile (cheapest first)",
        *decile_lines,
        "",
        headline,
        "",
    ]

    if not prov.answers_prereg:
        lines += [
            "This run exercises the pipeline. It does not answer Q4, and no D7 disposition",
            "follows from it: §7's thresholds are binding against measured data, and a synthetic",
            "run is not a data pull. See docs/PHASE-2A-SPIKE.md §7 and PLAN D30.",
            "",
        ]
        if missing:
            lines += [f"coverage gaps ({len(missing)}) describe the generator, not a vendor.", ""]
        return "\n".join(lines)

    if outcome == Q4_RECALIBRATE:
        lines += [
            "D7: raise as a spec decision, do not apply. Recalibrating max_spread_r needs a",
            "§2.0 row, a PLAN decision with its rejected alternative, a docs/CHANGELOG.md entry,",
            "and the 'changes trading behaviour' marker D20/D21/D27/D28 all carry.",
            "",
        ]
    elif outcome == Q4_INERT:
        lines += [
            "An inert gate is documented as inert, not left reading as protection — the state",
            "room_gate_multiple is already in at its default (D26).",
            "",
        ]

    if missing:
        lines += ["coverage gaps:", *(f"  {m}" for m in missing[:20])]
        if len(missing) > 20:
            lines.append(f"  ... and {len(missing) - 20} more")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    """``python -m scripts.spike2a.q4_spreads <signal_bars.csv> <quotes.csv>``

    Both inputs are CSVs, read through :class:`~scripts.spike2a.feeds.CsvQuoteFeed`, with no
    broker and no subscription — which under D30 is the only shape there is. Both must be covered
    by a ``PROVENANCE.txt`` declaring a permitted origin; the gate runs **before** the data is
    read, so a refusal cannot be mistaken for a measurement of an empty sample.
    """
    if len(argv) < 2:
        print(__doc__)
        print("usage: python -m scripts.spike2a.q4_spreads <signal_bars.csv> <quotes.csv>")
        return 2

    bars_path, quotes_path = Path(argv[0]), Path(argv[1])
    try:
        prov = require(bars_path, quotes_path)
    except ProvenanceError as exc:
        print(f"refusing to measure: {exc}", file=sys.stderr)
        return 3

    # The §2.0 mode preset is immaterial to Q4 and the default is used deliberately rather than
    # the `experienced` preset the §3 examples and `python -m tradipy demo` pass. None of
    # `max_spread_abs`, `max_spread_pct` or `max_spread_r` appears in MODE_PRESETS, so no cap
    # moves with mode — asserted below rather than assumed, because "it does not matter" is the
    # kind of claim that stops being true when a preset gains a row.
    cfg = Config.default()
    assert not (set(MODE_PRESETS["beginner"]) | set(MODE_PRESETS["experienced"])) & {
        "max_spread_abs",
        "max_spread_pct",
        "max_spread_r",
    }, "a mode preset now moves a spread cap; Q4 must state which mode it measured"

    feed = CsvQuoteFeed(quotes_path)
    bars, missing = load_signal_bars(bars_path, feed)
    rows = [classify(b, cfg) for b in bars]

    print(report(rows, missing, prov))
    # `CsvQuoteFeed.unparsed` exists so a malformed quote file cannot read as a vendor coverage
    # failure. It was written and never read: the first generated sample had 4,620 of 9,240 rows
    # timestamped 09:60-09:89, exactly half the tape was dropped, and the run printed a clean
    # verdict. A counter nothing prints is not a diagnostic.
    if feed.unparsed:
        print(
            f"WARNING  {feed.unparsed} of {feed.rows_read} quote rows did not parse and were "
            f"not measured — fix the file, not the verdict"
        )
    by_reason: dict[str, int] = defaultdict(int)
    for c in rows:
        by_reason[c.reason] += 1
    print("reason counts:", dict(sorted(by_reason.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
