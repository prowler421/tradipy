"""Session-series computations — PRD §20.1, §20.2, §20.3, §20.5 and §20.6.

Normative sources: PRD §20.1 (bar timing and labeling), §20.2 (VWAP), §20.3 (high of day),
§20.5 (EMA), §20.6 ("tighter" and "wider"). §20 governs on any conflict.

**What this module is.** The §20 computations that need an *ordered series* rather than a
single bar. :mod:`tradipy.bars` holds §20.4's flagpole geometry and deliberately gives
:class:`~tradipy.bars.Bar` no timestamp, because §20.1's timing rules need an ingestion layer.
This module supplies the one ordinal fact those rules actually turn on, and nothing more.

**Why the ordinal is an ``int`` and not a ``datetime``.** §21.1 requires an injectable clock
and forbids ``datetime.now()`` anywhere in strategy code. The §20.1 rules Phase 4 needs are
ordinal in any case — *"pattern counts ('3 consecutive candles') count **available bars**, not
wall-clock minutes; a gap > 2 minutes invalidates any in-progress pattern"* — and §20.2 anchors
the session at a fixed 09:30 ET. So a bar carries the number of minutes from the session open,
which expresses both rules, cannot be read from a clock, and carries no timezone. The UTC
storage and ``America/New_York`` evaluation split is §20.1's last row and §21.4's DST concern,
both of which belong to ingestion.

**What is deliberately not here.**

* **Premarket VWAP.** §20.2 makes it a separate series anchored at 04:00 ET, used only when
  premarket trading is enabled — which D11 disables by default and which
  ``premarket_trading_enabled`` cannot currently express, because ``Param.default`` is
  ``Decimal``-typed (open question **G9** in docs/CHANGELOG.md). A :class:`Session` is a
  regular-session series whose first bar is the 09:30 bar.
* **Bar close detection**, the 750 ms grace and the ``BAR_REVISED`` path (§20.1). Those need a
  feed. Every bar in a :class:`Session` is a closed bar by construction; there is no
  representation of a partial one.
* **ATR (§20.15).** No MVP setup criterion needs it — §4.2's volatility row takes it as an
  input and §14.2's Alt B is not adopted — so implementing it here would be a computation with
  no caller.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from tradipy.bars import Bar
from tradipy.params import Config

__all__ = [
    "SessionBar",
    "Session",
    "bar_sequence",
    "tighter",
    "wider",
]

#: §20.2's typical price divides by three. Named rather than written as a literal at the call
#: site: it is a structural constant of the formula, not a tunable threshold, and the registry
#: is for thresholds (see :mod:`tradipy.params`).
_TYPICAL_PRICE_TERMS = Decimal(3)


@dataclass(frozen=True)
class SessionBar:
    """One closed 1-minute bar, with its position in the regular session.

    ``minute`` is minutes from the session open, so ``0`` is the 09:30 bar — §20.1 states that
    a bar's timestamp *"labels the bar's **open***", which is what makes the index unambiguous.
    A session minute with no trades yields no bar (§20.1), so the sequence of minutes has gaps
    and is not the same as the sequence of list indices. Every count in §3 is over available
    bars; every gap test is over minutes.
    """

    minute: int
    bar: Bar

    def __post_init__(self) -> None:
        if self.minute < 0:
            raise ValueError(
                f"minute must be at or after the session open, got {self.minute}: premarket is "
                "a separate series (PRD §20.2) and is not representable here"
            )


@dataclass(frozen=True)
class Session:
    """An ordered run of closed regular-session bars, from the open.

    Construction validates that minutes are strictly increasing, which is the one property
    every method below relies on. Nothing validates that the series *starts* at minute 0: a
    session that opens with a no-trade minute has no 09:30 bar, and §20.2's rule is about the
    09:30 **anchor**, not about a bar existing there.
    """

    bars: tuple[SessionBar, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "bars", tuple(self.bars))
        minutes = [sb.minute for sb in self.bars]
        # Suppressed below rather than switched to `itertools.pairwise`: this module is held to
        # an import allowlist (test_the_setup_layer_reads_nothing_and_imports_nothing_that_could)
        # that does not include `itertools`, and widening it for one comparison is a bigger
        # change than the lint it would satisfy.
        if any(b <= a for a, b in zip(minutes, minutes[1:], strict=False)):  # noqa: RUF007
            raise ValueError(
                f"session minutes must be strictly increasing, got {minutes}: two bars in one "
                "minute is a duplicate delivery, and a decrease is a mis-ordered series"
            )

    def __len__(self) -> int:
        return len(self.bars)

    # -- indexing ----------------------------------------------------------
    def bar(self, i: int) -> Bar:
        """The OHLCV bar at index ``i``, raising rather than wrapping on a negative index."""
        self._require_index(i)
        return self.bars[i].bar

    def minute(self, i: int) -> int:
        """Minutes from the session open for the bar at index ``i``."""
        self._require_index(i)
        return self.bars[i].minute

    def ohlcv(self) -> tuple[Bar, ...]:
        """The bars alone, for the :mod:`tradipy.bars` functions, which take a plain sequence."""
        return tuple(sb.bar for sb in self.bars)

    def through(self, i: int) -> Session:
        """The series truncated at ``i`` inclusive — the no-look-ahead primitive.

        §21.1 states the property test directly: *"replaying a bar series truncated at time t
        must produce identical signals to the full series evaluated as-of t."* Every derivation
        in :mod:`tradipy.setups` reads the session only at or before its trigger index, so that
        property is a two-line assertion rather than an audit — see
        ``tests/test_setups.py::test_truncating_the_series_changes_no_outcome``.
        """
        self._require_index(i)
        return Session(self.bars[: i + 1])

    def _require_index(self, i: int) -> None:
        if not (0 <= i < len(self.bars)):
            raise IndexError(f"bar index {i} outside the session's 0..{len(self.bars) - 1}")

    # -- §20.2 VWAP --------------------------------------------------------
    def vwap_at(self, i: int) -> Decimal:
        """PRD §20.2 session VWAP as of the **close** of bar ``i``.

        ``Σ(typical_price × volume) / Σ(volume)`` from the session start, with
        ``typical_price = (high + low + close) / 3`` — *"not close-only"*. Never a partial-bar
        value: the caller passes the index of a closed bar and gets the value at its close.

        Not rounded. §20.13 puts tick rounding *once, at level computation*, and a VWAP is an
        input to a level rather than a level itself — :func:`tradipy.gates.vwap_reclaim_stop`
        is where the §3.4 stop candidate derived from it is rounded.
        """
        self._require_index(i)
        volume = sum(sb.bar.volume for sb in self.bars[: i + 1])
        if volume <= 0:
            raise ValueError(
                f"VWAP is undefined through bar {i}: cumulative volume is {volume}. A session "
                "minute with no trades yields no bar at all (PRD §20.1), so this is a "
                "zero-volume bar that should not have been delivered"
            )
        weighted = sum(
            (
                (sb.bar.high + sb.bar.low + sb.bar.close) / _TYPICAL_PRICE_TERMS * sb.bar.volume
                for sb in self.bars[: i + 1]
            ),
            start=Decimal(0),
        )
        return weighted / Decimal(volume)

    def vwap(self) -> Decimal:
        """§20.2 VWAP as of the last closed bar."""
        return self.vwap_at(len(self.bars) - 1)

    # -- §20.3 High of day -------------------------------------------------
    def hod_through(self, i: int) -> Decimal:
        """PRD §20.3: the highest **traded price** (wick) of the session through bar ``i``.

        Highs, not closes — §20.3 tracks HOD on wicks and puts the close requirement on the
        *breakout trigger* instead, which is §3.3 criterion 4's job and not this function's.
        """
        self._require_index(i)
        return max(sb.bar.high for sb in self.bars[: i + 1])

    def hod(self) -> Decimal:
        """§20.3 HOD as of the last closed bar."""
        return self.hod_through(len(self.bars) - 1)

    def hod_established_by(self, i: int) -> bool:
        """PRD §20.3 / §3.3 criterion 2: has a *tradeable* HOD been set through bar ``i``?

        §20.3: *"The 09:30 bar's high does not by itself establish a tradeable HOD; at least
        one **subsequent** bar must set a higher high."* So this is false for a session whose
        high is still the opening bar's, however high that was, and true as soon as any later
        bar exceeds every bar before it.
        """
        self._require_index(i)
        return any(
            self.bars[k].bar.high > max(sb.bar.high for sb in self.bars[:k])
            for k in range(1, i + 1)
        )

    # -- §20.5 EMA ---------------------------------------------------------
    def ema_at(self, i: int, cfg: Config) -> Decimal | None:
        """PRD §20.5's 9 EMA as of bar ``i``, or ``None`` while it is still invalid.

        ``EMA(t) = close_t × k + EMA(t−1) × (1 − k)``, ``k = 2/(period+1)``, seeded with the
        simple average of the first ``ema_period`` available regular-session closes. §20.5:
        *"The EMA is not valid (and no EMA-dependent trail is active) until 9 bars have
        closed"* — hence ``None`` rather than a partial figure, because a trail computed off a
        half-warmed average is a stop at a level nobody specified.

        **This has no caller in ``src/`` and that is deliberate.** Its consumer is §3.1.1's T3
        leg, which D18 requires be mirrored to a resting broker-side stop amended each bar
        close — so the trail belongs to Phase 5/6, not here. It is implemented now because
        §21.1's unit row names *"EMA seeding"* explicitly as a computation needing a
        hand-computed fixture, and because a T3 leg written later against an EMA written later
        has nothing to check itself against. Recorded in tests/README.md alongside
        :func:`tradipy.bars.select_flagpole`'s predicate, which was in the same position until
        §3.2 gained an implementation.
        """
        self._require_index(i)
        period = int(cfg["ema_period"])
        if i + 1 < period:
            return None
        closes = [sb.bar.close for sb in self.bars[: i + 1]]
        k = Decimal(2) / Decimal(period + 1)
        ema = sum(closes[:period], start=Decimal(0)) / Decimal(period)
        for close in closes[period:]:
            ema = close * k + ema * (Decimal(1) - k)
        return ema

    # -- §20.1 missing bars ------------------------------------------------
    def gap_before(self, i: int) -> int:
        """Session minutes with no bar between ``i - 1`` and ``i``; ``0`` at the first bar.

        §20.1: *"A session minute with no trades yields no bar."* The count is of the missing
        minutes themselves, so adjacent bars give ``0``.
        """
        self._require_index(i)
        if i == 0:
            return 0
        return self.bars[i].minute - self.bars[i - 1].minute - 1

    def pattern_intact(self, start: int, end: int, cfg: Config) -> bool:
        """PRD §20.1: is the run ``start..end`` free of a gap wide enough to invalidate it?

        *"A gap > 2 minutes invalidates any in-progress pattern."*

        **Two readings, and §20.1 states neither.** *"A gap > 2 minutes"* can count the
        **missing minutes** — two adjacent bars nine and twelve minutes in have a two-minute
        gap between them — or the **elapsed span**, which would make the same pair a
        three-minute gap. This takes the missing-minute reading, which is the literal one, and
        it is worth naming that this is the one §4.2-style ambiguity where the stricter reading
        was *not* taken: the span reading rejects one minute of absence more than this does.
        Raised in docs/CHANGELOG.md; localised here so a decision changes one comparison.
        """
        self._require_index(start)
        self._require_index(end)
        if end < start:
            raise ValueError(f"pattern run must be ordered, got start={start} end={end}")
        widest = cfg["max_pattern_gap_minutes"]
        return all(Decimal(self.gap_before(k)) <= widest for k in range(start + 1, end + 1))


def tighter(*levels: Decimal) -> Decimal:
    """PRD §20.6: the tighter of several candidate stop prices for a long — ``max()``.

    *"For a long position: **tighter** = higher stop price = smaller ``stop_distance``. Where a
    rule says 'whichever is tighter,' take ``max()`` of the candidate stop prices."*

    Named because §20.6 is a definition and a bare ``max()`` at a call site is a restatement of
    it. The only existing use was inside :func:`tradipy.gates.vwap_reclaim_stop`; §3.3's stop
    needs both this and :func:`wider`, and the pair reads correctly only if neither is spelled
    as the arithmetic.
    """
    if not levels:
        raise ValueError("tighter() needs at least one candidate level (PRD §20.6)")
    return max(levels)


def wider(*levels: Decimal) -> Decimal:
    """PRD §20.6: the wider of several candidate stop prices for a long — ``min()``.

    *"'wider' takes ``min()``."* §3.3's stop is the lower of the consolidation low and the
    breakout candle's low, which is this; A14 then selects the tighter of that and the VWAP
    level, which is :func:`tighter`. Applying the $0.10 floor comes after both, and can only
    widen the result (§20.6, §2).
    """
    if not levels:
        raise ValueError("wider() needs at least one candidate level (PRD §20.6)")
    return min(levels)


def bar_sequence(bars: Sequence[Bar], *, first_minute: int = 0) -> Session:
    """A contiguous :class:`Session` from plain bars, one per minute from ``first_minute``.

    A convenience for fixtures and the ``python -m tradipy setups`` replay, where the point is
    the pattern rather than the gaps. Anything testing §20.1's gap rule must build
    :class:`SessionBar` values itself — which is why this does not accept a minute list.
    """
    return Session(tuple(SessionBar(first_minute + n, b) for n, b in enumerate(bars)))
