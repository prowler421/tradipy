"""tradipy — Ross Cameron momentum trading system.

This package currently contains only the invariant layer: the parameter registry, tick
rounding with constraint polarity, and the pre-entry gates. It exists so that the rules
established over four review rounds of docs/PRD.md are executable rather than prose.

Read docs/PRD.md §20 (Computation Semantics) first. It is normative and governs on any
conflict with code comments.
"""

from tradipy import gates, params, rounding

__all__ = ["gates", "params", "rounding"]
