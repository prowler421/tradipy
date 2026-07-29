"""Phase 2a data feasibility spike — **throwaway investigative code**.

Scope and pre-registration: [docs/PHASE-2A-SPIKE.md](../../docs/PHASE-2A-SPIKE.md). Its §8
governs this package:

* it is **not** imported by ``src/tradipy/`` and must never be;
* it carries **no test-coverage obligation**;
* if Q1 comes back positive, Phase 3 is written fresh against the PRD rather than grown from
  here. "The spike code works, and it becomes the scanner by accretion" is the failure mode §8
  names as the more likely of the two.

**No registered threshold appears as a literal anywhere in this package.** Every §4.2 filter
value and every §3.1.3 cap is read from :mod:`tradipy.params` by name, and the caps themselves
come from :func:`tradipy.gates.spread_caps` rather than a second implementation — §4.3's
instruction, on the grounds that a reimplementation of the cap arithmetic would silently absorb
the very disagreement the spike is measuring. As of this package the registry lint scans
``scripts/`` recursively, so that rule is mechanical here and not merely stated.

Run order is Q4 first — see :mod:`scripts.spike2a.prereg` for why the §7 budget clause makes
that ordering binding rather than advisory.
"""

from __future__ import annotations
