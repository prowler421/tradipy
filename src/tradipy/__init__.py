"""tradipy — Ross Cameron momentum trading system.

This package contains the invariant layer: the parameter registry, tick rounding with
constraint polarity, the pre-entry gates, the §4 scanner, and the three PRD §20 computations
that need no market-data feed to be correct (§20.4 flagpole geometry, §20.10 composite score,
§20.14 quote validity). It exists so that the rules established over ten review rounds of
docs/PRD.md are executable rather than prose.

Read docs/PRD.md §20 (Computation Semantics) first. It is normative and governs on any
conflict with code comments.

Run ``python -m tradipy demo`` to replay the three §3 worked examples end to end, or
``python -m tradipy scan`` to run a simulated universe through the §4.2 filters.
"""

from tradipy import bars, gates, params, quotes, rejects, rounding, scanner, score

__all__ = ["rounding", "rejects", "params", "bars", "quotes", "score", "gates", "scanner"]
