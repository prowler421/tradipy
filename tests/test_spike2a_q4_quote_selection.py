"""Guarantee tests for Q4 quote selection (H4/H6).

Review round 7 found ``load_signal_bars`` using ``samples[-1]``, so every setup on a
symbol-session shared the session's last tick — often an hour after the signal. These tests
attack :func:`scripts.spike2a.feeds.quote_at_or_before` and the ``signal_at`` column the fix
requires.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from scripts.spike2a.feeds import QuoteSample, quote_at_or_before


def _sample(at: str, bid: str = "10.00", ask: str = "10.01") -> QuoteSample:
    return QuoteSample(
        symbol="TEST",
        captured_at=datetime.fromisoformat(at),
        bid=Decimal(bid),
        ask=Decimal(ask),
        bid_size=500,
        ask_size=500,
    )


def test_quote_at_or_before_selects_last_tick_not_session_end() -> None:
    """Two setups at 09:35 and 09:50 must not both receive the 10:29 tick."""
    samples = [
        _sample("2026-07-08T09:30:00+00:00"),
        _sample("2026-07-08T09:35:00+00:00", bid="10.10", ask="10.11"),
        _sample("2026-07-08T09:50:00+00:00", bid="10.20", ask="10.21"),
        _sample("2026-07-08T10:29:00+00:00", bid="10.99", ask="11.00"),
    ]
    early = quote_at_or_before(samples, datetime(2026, 7, 8, 9, 35, tzinfo=UTC))
    late = quote_at_or_before(samples, datetime(2026, 7, 8, 9, 50, tzinfo=UTC))
    assert early is not None and early.bid == Decimal("10.10")
    assert late is not None and late.bid == Decimal("10.20")
    assert early.bid != late.bid


def test_quote_at_or_before_derives_age_seconds_from_signal_instant() -> None:
    """§20.14 staleness must be computable without a CSV ``age_seconds`` column (H6)."""
    samples = [_sample("2026-07-08T09:30:00+00:00")]
    signal = datetime(2026, 7, 8, 9, 35, tzinfo=UTC)
    chosen = quote_at_or_before(samples, signal)
    assert chosen is not None
    assert chosen.age_seconds == Decimal("300")
