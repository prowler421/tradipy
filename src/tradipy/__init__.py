"""tradipy — Ross Cameron momentum trading system.

This package contains the invariant layer: the parameter registry, tick rounding with
constraint polarity, the pre-entry gates, the §4 scanner, the three §3 setups, §7's pre-order
risk rules with §6's order construction, and every PRD §20 computation that needs no
market-data feed to be correct — §20.2 VWAP, §20.3 HOD, §20.4 flagpole geometry, §20.5 EMA,
§20.6 tighter/wider, §20.10 composite score, §20.12's state machine and §20.14 quote validity.
It exists so that the rules established over thirteen review rounds of docs/PRD.md are
executable rather than prose.

**Nothing here can reach a market.** PLAN D30 puts every dataset at the ``SIMULATED`` rung, so
no module imports a broker SDK, a vendor client or the network stack — which is also why
:mod:`tradipy.orders` builds an order draft and stops there. See docs/PHASE-5-DESIGN.md §1.1.

Read docs/PRD.md §20 (Computation Semantics) first. It is normative and governs on any
conflict with code comments.

Run ``python -m tradipy demo`` to replay the three §3 worked examples through the gate chain,
``python -m tradipy setups`` to replay the same three from their **bar series**,
``python -m tradipy scan`` to run a simulated universe through the §4.2 filters, or
``python -m tradipy risk`` to take the §3 signals through §7's pre-order rules to a bracket.
"""

from tradipy import (
    bars,
    gates,
    orders,
    params,
    positions,
    quotes,
    rejects,
    risk,
    rounding,
    scanner,
    score,
    session,
    setups,
)

__all__ = [
    "rounding",
    "rejects",
    "params",
    "bars",
    "quotes",
    "score",
    "gates",
    "scanner",
    "session",
    "setups",
    "positions",
    "risk",
    "orders",
]
