"""tradipy — Ross Cameron momentum trading system.

This package contains the invariant layer: the parameter registry, tick rounding with
constraint polarity, the pre-entry gates, the §4 scanner, the three §3 setups, and every PRD
§20 computation that needs no market-data feed to be correct — §20.2 VWAP, §20.3 HOD, §20.4
flagpole geometry, §20.5 EMA, §20.6 tighter/wider, §20.10 composite score and §20.14 quote
validity. It exists so that the rules established over twelve review rounds of docs/PRD.md are
executable rather than prose.

Read docs/PRD.md §20 (Computation Semantics) first. It is normative and governs on any
conflict with code comments.

Run ``python -m tradipy demo`` to replay the three §3 worked examples through the gate chain,
``python -m tradipy setups`` to replay the same three from their **bar series**, or
``python -m tradipy scan`` to run a simulated universe through the §4.2 filters.
"""

from tradipy import (
    bars,
    gates,
    params,
    quotes,
    rejects,
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
]
