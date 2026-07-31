"""Phase 2a data feasibility spike — **throwaway investigative code**.

Scope and pre-registration: [docs/PHASE-2A-SPIKE.md](../../docs/PHASE-2A-SPIKE.md). Its §8
governs this package:

* it is **not** imported by ``src/tradipy/`` and must never be;
* it carries **no test-coverage obligation** — which is a decision with a cost, paid in review
  round 7: the first defect in this package was a timestamp expression emitting ``09:60``
  through ``09:89``, which discarded exactly half of a quote file with no test to notice.
  :mod:`scripts.spike2a.provenance` is the one exception, and it is an exception in fact rather
  than by an amendment to §8: it is the PLAN **D30** gate, ``tests/test_enforcement.py`` tests
  it, and no measurement module runs without it. Whether §8 should be narrowed to say so is
  raised as an open question in ``docs/CHANGELOG.md`` and is not settled here;
* if Q1 comes back positive, Phase 3 is written fresh against the PRD rather than grown from
  here. "The spike code works, and it becomes the scanner by accretion" is the failure mode §8
  names as the more likely of the two.

**No registered threshold may appear as a literal anywhere in this package**, and since the
registry lint's roots were extended to walk ``scripts/`` recursively, that is mechanical rather
than merely stated. Every §4.2 filter value and every §3.1.3 cap is read from
:mod:`tradipy.params` by name, and the caps themselves come from
:func:`tradipy.gates.spread_caps` rather than a second implementation — §4.3's instruction, on the
grounds that a reimplementation of the cap arithmetic would silently absorb the very disagreement
the spike is measuring.

**The rule and the state of the tree are two different claims, and this docstring used to make
the second one.** It read "no registered threshold appears as a literal anywhere in this
package" — a status assertion, which was false from the commit that added
:mod:`scripts.spike2a.synthetic_data_generator` (five offenders) until review round 7 fixed them.
The lint reports the state; a docstring that reports it too is a second copy that goes stale, and
the copy is what stops anyone running the lint.

**Every dataset this package reads is simulated** (PLAN **D30**, ``CLAUDE.md`` convention 9), and
each entry point calls :func:`scripts.spike2a.provenance.require` before reading anything.
§7 binds its thresholds to *measured* data, so nothing here can answer Q1–Q4 while that holds:
:mod:`scripts.spike2a.q4_spreads` prints a pipeline outcome rather than a §7 verdict, and
:mod:`scripts.spike2a.q3_latency` withholds its disposition entirely.

Run order is Q4 first — see :mod:`scripts.spike2a.prereg` for why the §7 budget clause makes
that ordering binding rather than advisory.
"""

from __future__ import annotations
