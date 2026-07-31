"""Historical NBBO fetch — the swappable half of Q4.

Q4 needs one thing from a vendor: the NBBO in force at a set of instants, for the symbols the §7
rule selected. That is a small enough surface to isolate behind a two-method interface, and
isolating it is the point: **whether IBKR's paper tier will actually serve
``reqHistoricalTicks`` BID_ASK for a 400-symbol-session sample over a 12-month lookback is
unverified.** If it will not, the vendor changes and :mod:`scripts.spike2a.q4_spreads` does not,
because the measurement never sees a broker object.

One implementation ships:

* :class:`CsvQuoteFeed` — offline replay from a CSV. Runs with no broker, no subscription and no
  network, which is what makes the Q4 pipeline verifiable before any vendor answers.

**A broker-backed implementation used to ship beside it and no longer does.** PLAN **D30** puts
the project on simulated data until the phase ladder is advanced, so ``IbkrHistoricalTicksFeed``
— along with the two collection scripts that pulled real IBKR ticks — was removed. It is
recoverable at ``3ca9e7b``, the last commit that contains it. The protocol below is what a
paper-stage implementation would satisfy; writing one is part of advancing the ladder, not a step
that can be taken in passing. ``scripts/spike2a/provenance.py`` is the gate that makes that
ordering real rather than advisory; ``tests/test_enforcement.py`` fails on any of the twenty
import roots it enumerates, across ``src/``, ``scripts/`` and ``tests/``. That is a denylist, so
it makes a
re-entry loud rather than impossible — the provenance gate is the backstop, because it
constrains what may be *read* rather than what may be imported.

**A note on where this interface belongs.** PLAN Workstream 9 is open on interfaces, and its
diagnosis is that the first genuine one will be the market-data feed, to be resolved at this
spike against a real vendor API. :class:`QuoteFeed` is that shape appearing for the first time —
but it is deliberately **here and not in** ``src/tradipy/``. §8 forbids the spike growing into
the scanner, and a feed protocol promoted into the library on the strength of one vendor trial is
exactly that growth. Let it prove itself against a chosen vendor first — which D30 defers, so
WS9 stays open, and the protocol below stays a one-implementation shape that has not yet met the
thing it abstracts.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol, runtime_checkable

from tradipy.quotes import Quote


def quote_at_or_before(samples: list[QuoteSample], instant: datetime) -> QuoteSample | None:
    """Return the last NBBO observation at or before ``instant``, with derived ``age_seconds``.

    §20.14's staleness test applies to the quote in force at the signal instant, not to an
    arbitrary last tick of the session — which is what ``samples[-1]`` produced when several
    setups shared one symbol-session bucket (review round 7, H4). When ``age_seconds`` is not
    supplied in the CSV, it is derived from ``instant - captured_at`` so the validity half of
    Q4 can fire on measured input (H6).
    """
    if not samples:
        return None
    eligible = [s for s in samples if s.captured_at <= instant]
    if not eligible:
        return None
    chosen = eligible[-1]
    age = Decimal(str(max((instant - chosen.captured_at).total_seconds(), 0)))
    return QuoteSample(
        symbol=chosen.symbol,
        captured_at=chosen.captured_at,
        bid=chosen.bid,
        ask=chosen.ask,
        bid_size=chosen.bid_size,
        ask_size=chosen.ask_size,
        age_seconds=age,
    )


@dataclass(frozen=True)
class QuoteSample:
    """One NBBO observation, with the instant it was in force.

    ``captured_at`` is timezone-aware UTC per §20.1. The spike carries timestamps because the
    library deliberately does not — §8's second guardrail keeps ``datetime`` out of
    ``src/tradipy/`` so that the eventual ``Bar`` is shaped by the feed that gets chosen rather
    than by whichever one happened to be under trial.
    """

    symbol: str
    captured_at: datetime
    bid: Decimal
    ask: Decimal
    bid_size: int
    ask_size: int
    age_seconds: Decimal = Decimal(0)

    def as_quote(self) -> Quote:
        """The library's §20.14 quote type.

        ``estimated`` stays ``False`` — including for simulated input, which is worth stating
        because it looks like the obvious place to record that the data is fabricated. It is not.
        §20.14 reserves that flag for the backtest's *spread substitute*, whose trades §18.7
        excludes from the viability gate; setting it here would move Q4's whole sample into that
        excluded population and answer a question about §18.7 rather than about §3.1.3. Simulated
        input is declared in ``PROVENANCE.txt`` and enforced by
        :mod:`scripts.spike2a.provenance` — one flag, one meaning, in the layer that owns it.
        """
        return Quote(
            bid=self.bid,
            ask=self.ask,
            bid_size=self.bid_size,
            ask_size=self.ask_size,
            age_seconds=self.age_seconds,
        )


@runtime_checkable
class QuoteFeed(Protocol):
    """What Q4 needs from a data source, and nothing more."""

    name: str

    def nbbo_for_session(self, symbol: str, session_date: str) -> list[QuoteSample]:
        """Every NBBO observation available for ``symbol`` on ``session_date`` (``YYYY-MM-DD``).

        An empty list means *no coverage*, which §7 exclusion (2) turns into a Q1 coverage
        failure rather than a silent drop. Implementations must not fabricate a quote to avoid
        returning empty.
        """
        ...


class CsvQuoteFeed:
    """Replay from ``symbol,captured_at,bid,ask,bid_size,ask_size[,age_seconds]``.

    ``captured_at`` is ISO 8601. Rows that do not parse are counted in :attr:`unparsed` rather
    than dropped quietly — a malformed quote file that silently yields no coverage would read as
    a vendor coverage failure and be reported against Q1, which is the wrong finding.
    """

    def __init__(self, path: Path) -> None:
        self.name = f"csv:{path.name}"
        self.unparsed = 0
        #: Rows seen, so a caller can report ``unparsed`` as a share rather than a bare count.
        #: "4,620 unparsed" and "4,620 of 9,240 unparsed" are different findings.
        self.rows_read = 0
        self._by_key: dict[tuple[str, str], list[QuoteSample]] = {}

        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.rows_read += 1
                sample = self._parse(row)
                if sample is None:
                    self.unparsed += 1
                    continue
                key = (sample.symbol, sample.captured_at.date().isoformat())
                self._by_key.setdefault(key, []).append(sample)

        for samples in self._by_key.values():
            samples.sort(key=lambda s: s.captured_at)

    @staticmethod
    def _parse(row: dict[str, str]) -> QuoteSample | None:
        try:
            return QuoteSample(
                symbol=row["symbol"].strip().upper(),
                captured_at=datetime.fromisoformat(row["captured_at"].strip()),
                bid=Decimal(row["bid"]),
                ask=Decimal(row["ask"]),
                bid_size=int(row["bid_size"]),
                ask_size=int(row["ask_size"]),
                age_seconds=Decimal(row.get("age_seconds") or 0),
            )
        except (KeyError, ValueError, InvalidOperation):
            return None

    def nbbo_for_session(self, symbol: str, session_date: str) -> list[QuoteSample]:
        return list(self._by_key.get((symbol.upper(), session_date), ()))
