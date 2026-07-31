"""Guarantee test for `scripts/spike2a/sample.py`'s join (H5).

`scripts/spike2a/` carries no test-coverage obligation (PHASE-2A-SPIKE.md §8) — narrowing that
exemption is itself an open spec question (H2) this file does not settle either way. It exists
regardless because `sample.py`'s central claim is exactly the shape CLAUDE.md convention 6 asks
for an attack on: out-of-window sessions are "never folded into `Sample.rejected` or
`Sample.excluded`". A test that only ever feeds the join in-window facts cannot distinguish a real
restriction from one that accidentally passes everything through — the same test-shaped absence
review round 6 found beside three of the four v0.0.1 defects.

Each test below was run against `select_sample_in_windows` with the corresponding guard removed —
the window filter, the per-fact `check_units()` call, and the span/out-of-span split — and failed
in each case before the guard was restored.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from scripts.spike2a.sample import select_sample_in_windows
from scripts.spike2a.universe import PreOpenFacts, UnitError
from scripts.spike2a.windows import Window
from tradipy.params import Config

#: Ten consecutive weekdays, 2026-07-06..2026-07-17 (a Mon-Fri, Mon-Fri run), leaving the weekend
#: of 2026-07-11..12 inside the calendar span but out of `sessions` — the fixture `span_gap` needs.
_ACTIVE = Window(
    label="active",
    start=date(2026, 7, 6),
    end=date(2026, 7, 17),
    mean_vix=Decimal("20"),
    sessions=(
        date(2026, 7, 6),
        date(2026, 7, 7),
        date(2026, 7, 8),
        date(2026, 7, 9),
        date(2026, 7, 10),
        date(2026, 7, 13),
        date(2026, 7, 14),
        date(2026, 7, 15),
        date(2026, 7, 16),
        date(2026, 7, 17),
    ),
)

#: Far away in time from `_ACTIVE` and from any date used as "genuinely outside both windows"
#: below, so the two windows can never accidentally overlap a test fixture.
_QUIET = Window(
    label="quiet",
    start=date(2026, 1, 5),
    end=date(2026, 1, 16),
    mean_vix=Decimal("12"),
    sessions=(
        date(2026, 1, 5),
        date(2026, 1, 6),
        date(2026, 1, 7),
        date(2026, 1, 8),
        date(2026, 1, 9),
        date(2026, 1, 12),
        date(2026, 1, 13),
        date(2026, 1, 14),
        date(2026, 1, 15),
        date(2026, 1, 16),
    ),
)

_MAX_MISSING_NBBO = Decimal("0.05")


def _fact(session: date, **overrides: object) -> PreOpenFacts:
    """A fact that clears every §4.2 hard filter at the registry defaults, unless overridden."""
    cfg = Config.default()
    defaults: dict[str, object] = {
        "session": session,
        "symbol": "TEST",
        "price": Decimal("5.00"),
        "gap_premarket_pct": cfg["min_gap_premarket_pct"] + Decimal("0.01"),
        "gap_daily_pct": Decimal("0"),
        "rvol": cfg["min_rvol"] + Decimal("1"),
        "adv_shares": cfg["min_adv_shares"] + Decimal("1"),
        "float_shares": cfg["max_float_shares"] - Decimal("1"),
    }
    defaults.update(overrides)
    return PreOpenFacts(**defaults)  # type: ignore[arg-type]


def test_out_of_window_session_never_enters_rejected_or_excluded() -> None:
    """Attack: give an out-of-span row values that would fail a hard filter *if classified at
    all*, then assert it lands in `out_of_span` rather than in `Sample.rejected` — which is what
    a join that classified every row regardless of window membership would do. Fails without the
    window restriction: without it, `bad_but_out_of_span` is exactly the kind of row
    `Sample.rejected` exists to hold, and this assertion would find it there instead.
    """
    bad_but_out_of_span = _fact(date(2020, 1, 1), rvol=Decimal("0"))  # fails min_rvol
    good_and_in_window = _fact(date(2026, 7, 8))

    windowed = select_sample_in_windows(
        [bad_but_out_of_span, good_and_in_window],
        _ACTIVE,
        _QUIET,
        Config.default(),
        _MAX_MISSING_NBBO,
    )

    assert bad_but_out_of_span in windowed.out_of_span
    rejected_facts = [v.facts for v in windowed.sample.rejected]
    excluded_facts = [v.facts for v in windowed.sample.excluded]
    assert bad_but_out_of_span not in rejected_facts
    assert bad_but_out_of_span not in excluded_facts
    included_facts = [v.facts for v in windowed.sample.included]
    assert good_and_in_window in included_facts


def test_span_gap_is_distinguished_from_out_of_span() -> None:
    """A session inside a window's calendar span but missing from its `sessions` tuple (here, the
    weekend `_ACTIVE` spans) must not be counted the same as a session nowhere near either window.
    Fails without the span/out-of-span split: before it, both land in one undifferentiated
    "outside windows" bucket and this assertion cannot tell them apart.
    """
    in_span_gap = _fact(date(2026, 7, 11))  # inside _ACTIVE's range, not one of its sessions
    nowhere_near_either_window = _fact(date(2015, 6, 1))

    windowed = select_sample_in_windows(
        [in_span_gap, nowhere_near_either_window],
        _ACTIVE,
        _QUIET,
        Config.default(),
        _MAX_MISSING_NBBO,
    )

    assert in_span_gap in windowed.span_gap
    assert in_span_gap not in windowed.out_of_span
    assert nowhere_near_either_window in windowed.out_of_span
    assert nowhere_near_either_window not in windowed.span_gap
    # Both are "outside windows" from the combined view the CLI prints. Compared as a list, not a
    # set: `PreOpenFacts.soft` is a `dict`, which is unhashable, and frozen-dataclass equality
    # does not need hashing.
    combined = windowed.out_of_window
    assert in_span_gap in combined
    assert nowhere_near_either_window in combined
    assert len(combined) == 2


def test_unit_error_on_an_out_of_window_row_is_not_silently_bypassed() -> None:
    """Attack: a unit error (a whole-number percentage where the registry expects a fraction) on
    a row that falls outside both windows must still raise. Fails if `check_units()` is only
    called on in-window rows — which is what happens if this check is left to
    `universe.classify`, the guard's only other caller, since `classify` never sees a row this
    module does not pass it.
    """
    bad_row_outside_every_window = _fact(date(2020, 1, 1), gap_premarket_pct=Decimal("12"))

    with pytest.raises(UnitError):
        select_sample_in_windows(
            [bad_row_outside_every_window], _ACTIVE, _QUIET, Config.default(), _MAX_MISSING_NBBO
        )
