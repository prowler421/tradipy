"""Rejection reason codes.

Normative sources: PRD §3.1.2, §3.1.3, §4.2, §20.9, §20.13, §20.14.

These live in their own module because two layers raise them — :mod:`tradipy.gates` for the
pre-entry gates and :mod:`tradipy.quotes` for §20.14 quote validity — and a quote is a lower
level construct than a gate. Putting the enum in ``gates`` would have made ``quotes`` depend
on ``gates``, inverting the layering for no reason. :mod:`tradipy.gates` re-exports ``Reject``
so ``from tradipy.gates import Reject`` continues to work.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Reject"]


class Reject(Enum):
    """Why a candidate was declined.

    Each member names the PRD section that defines the rejection, because a reason code
    invented by the implementation is a rule the specification has not agreed to.
    """

    #: PRD §3.1.3 — spread exceeds the scan-time or signal-time cap.
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"

    #: PRD §3.1.1 / §3.1.2 — the proportional term of the unified room requirement binds.
    INSUFFICIENT_ROOM = "INSUFFICIENT_ROOM"

    #: PRD §3.1.2 — the separation term binds; T1 and T2 would collapse together.
    TARGETS_TOO_CLOSE = "TARGETS_TOO_CLOSE"

    #: PRD §2 / §3.2 / §20.13 — stop distance exceeds ``max_stop_pct`` of entry, so the
    #: trade is skipped rather than the stop tightened. The PRD states the rule ("skip the
    #: trade") without naming a code; this name is the implementation's, and PRD §4.2's
    #: rejection-code table should adopt or replace it.
    STOP_TOO_WIDE = "STOP_TOO_WIDE"

    #: PRD §20.14 — the NBBO quote at signal-bar close was older than
    #: ``quote_stale_seconds``.
    QUOTE_STALE = "QUOTE_STALE"

    #: PRD §20.14 — ``ask <= bid``. Never clamped to zero: a zero spread makes the §3.1.2
    #: separation floor trivially satisfiable, which is exactly wrong during the
    #: dislocations that produce crossed quotes.
    QUOTE_CROSSED = "QUOTE_CROSSED"

    #: PRD §20.9 / §20.14 — a one-sided or odd-lot-only quote, or an unadjustable corporate
    #: action. Not a spread, so it is not gated on.
    DATA_QUALITY_DEGRADED = "DATA_QUALITY_DEGRADED"
