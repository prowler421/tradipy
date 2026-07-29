"""Historical NBBO fetch — the swappable half of Q4.

Q4 needs one thing from a vendor: the NBBO in force at a set of instants, for the symbols the §7
rule selected. That is a small enough surface to isolate behind a two-method interface, and
isolating it is the point: **whether IBKR's paper tier will actually serve
``reqHistoricalTicks`` BID_ASK for a 400-symbol-session sample over a 12-month lookback is
unverified.** If it will not, the vendor changes and :mod:`scripts.spike2a.q4_spreads` does not,
because the measurement never sees a broker object.

Two implementations ship:

* :class:`CsvQuoteFeed` — offline replay from a CSV. Runs with no broker, no subscription and no
  network, which is what makes the Q4 pipeline verifiable before any vendor answers.
* :class:`IbkrHistoricalTicksFeed` — ``ib_insync`` against a paper gateway. ``ib_insync`` is
  imported **inside** the constructor, not at module scope, so the rest of the spike keeps
  working when it is not installed. The package's runtime stays stdlib-only (CLAUDE.md); this is
  throwaway code with a stated external prerequisite, not a new dependency.

**A note on where this interface belongs.** PLAN Workstream 9 is open on interfaces, and its
diagnosis is that the first genuine one will be the market-data feed, to be resolved at this
spike against a real vendor API. :class:`QuoteFeed` is that shape appearing for the first time —
but it is deliberately **here and not in** ``src/tradipy/``. §8 forbids the spike growing into
the scanner, and a feed protocol promoted into the library on the strength of one vendor trial is
exactly that growth. Let it prove itself against a chosen vendor first.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol, runtime_checkable

from tradipy.quotes import Quote


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

        ``estimated`` stays ``False``: these are real NBBO observations, and §20.14 reserves the
        estimated flag for the backtest substitute, whose trades §18.7 excludes. Setting it here
        would quietly move Q4's sample into the excluded population.
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
        self._by_key: dict[tuple[str, str], list[QuoteSample]] = {}

        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
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


class IbkrHistoricalTicksFeed:
    """``ib_insync.IB.reqHistoricalTicks(..., whatToShow="BID_ASK")`` against a paper gateway.

    **Unverified against the paper tier.** Three limits could each sink it, and the failure is
    the same shape in all three cases — partial coverage that looks like a thin market rather
    than a missing subscription:

    * ``reqHistoricalTicks`` returns at most 1000 ticks per call, so a session needs paging;
    * historical tick depth is shorter than the 12-month VIX lookback the §7 window rule ranges
      over, and is not uniform across symbols;
    * pacing violations arrive as empty responses, not as errors, which is why
      :attr:`empty_responses` is counted separately from a genuine no-coverage result.

    If any of those bites, the finding belongs in **Q1** — "IBKR paper cannot serve the sample" is
    a data-availability answer — and the fix is a different :class:`QuoteFeed`, not a change to
    :mod:`scripts.spike2a.q4_spreads`.
    """

    #: IBKR's documented per-request tick ceiling.
    TICKS_PER_REQUEST = 1000

    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 2) -> None:
        # Imported here rather than at module scope, deliberately: see the module docstring.
        # `pyproject.toml` puts `scripts/` in basedpyright's scope, and ib_insync is correctly
        # absent from the project's dependencies, so the missing import is expected rather than
        # a mistake — the type-check analogue of the `pragma: no cover` two lines below.
        try:
            from ib_insync import IB  # pyright: ignore[reportMissingImports]
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "IbkrHistoricalTicksFeed needs ib_insync, which is a spike-only prerequisite "
                "and deliberately not a package dependency. Install it into a throwaway "
                "environment (`uv pip install ib_insync`) or use CsvQuoteFeed."
            ) from exc

        # Port 7497 is the TWS *paper* socket; 7496 is live. The default is paper on purpose —
        # §3.2 of the spike doc forbids live trading of any size for any reason, and a default
        # that points at the live socket is one typo from violating it.
        self.name = f"ibkr-paper:{host}:{port}"
        self.empty_responses = 0
        self._ib = IB()
        self._ib.connect(host, port, clientId=client_id, readonly=True)

    def nbbo_for_session(self, symbol: str, session_date: str) -> list[QuoteSample]:
        """Page BID_ASK ticks across the session, oldest first.

        Not implemented as a single call: see :attr:`TICKS_PER_REQUEST`. Paging is left as the
        first thing to write once the tier is confirmed to serve the data at all — writing it
        before that is building against a capability nobody has checked, which is the §5.5 waste
        one level down.
        """
        raise NotImplementedError(
            "confirm reqHistoricalTicks BID_ASK coverage and pacing on the paper tier first, "
            "then implement paging here. Until then run Q4 with CsvQuoteFeed. See the class "
            "docstring for the three limits to check and where a negative result belongs (Q1)."
        )

    def disconnect(self) -> None:  # pragma: no cover - environment-dependent
        self._ib.disconnect()
