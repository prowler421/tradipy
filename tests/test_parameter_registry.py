"""Parameter-registry lint — PRD §21.1, PLAN Workstream 11 registry check.

The v1.2 defect class was: *a threshold restated as a literal in more than one place, and
only one copy updated.* ``room_gate_multiple`` was raised to 2.5 in §2.0 and §3.1.1 while all
three setup criteria still read ``2 ×``; §15 carried a scaling-in rule §7.1.1 had overturned.

Two checks here:

1. **Code**: no registered threshold may appear as a numeric literal in ``src/`` outside the
   registry itself.
2. **Prose**: numeric literals in docs/PRD.md that match a registered default are collected
   and compared against a committed baseline. Some are legitimate — worked examples must
   state numbers — so the lint's job is to fail on *new* occurrences, not to demand zero.

The baseline is the honest design. Demanding zero would be unachievable and would get
disabled; a frozen baseline makes every future restatement a deliberate, visible decision.
"""

from __future__ import annotations

import json
import os
import re
from decimal import Decimal
from pathlib import Path

import pytest

from tradipy.params import PARAMS

REPO = Path(__file__).resolve().parents[1]
PRD = REPO / "docs" / "PRD.md"
SRC = REPO / "src" / "tradipy"
BASELINE = Path(__file__).parent / "registry_baseline.json"

#: Sections whose whole purpose is to state values. Definition tables are exempt: that is
#: where a threshold is *supposed* to appear as a literal.
DEFINING_SECTIONS = ("### 2.0", "### 2.1", "### 2.2", "### 3.1.2", "### 3.1.3", "## 2.")


def _prd_lines() -> list[str]:
    return PRD.read_text(encoding="utf-8").split("\n")


def _registered_literals() -> dict[str, str]:
    """Map the string form of each registered default to its parameter name.

    Only values distinctive enough to be worth matching. Small integers and round
    percentages appear constantly in unrelated prose and would drown the signal.
    """
    out: dict[str, str] = {}
    for name, p in PARAMS.items():
        d = p.default
        if p.unit == "USD" and d < Decimal("1"):
            out[f"${d.normalize()}"] = name          # $0.015, $0.02, $0.10
        elif p.unit == "xR" and d != Decimal("2.0"):
            out[f"{d.normalize()}×"] = name          # 2.5×, 0.15×
        elif p.unit == "fraction" and d < Decimal("0.1"):
            pct = (d * 100).normalize()
            out[f"{pct}%"] = name                    # 0.5%, 4%, 5%, 1%, 3%
    return out


@pytest.mark.spec
def test_no_registered_literal_hardcoded_in_source() -> None:
    """Every threshold in ``src/`` must be read from the registry by name.

    ``params.py`` is exempt — it is the definition. Everything else must go through it.
    """
    offenders: list[str] = []
    literals = {
        str(p.default.normalize()): name
        for name, p in PARAMS.items()
        if p.default not in (Decimal("0"), Decimal("1"), Decimal("2"), Decimal("100"))
    }
    # `TICK_SIZE` is not a tunable threshold — it is a market fact fixed by SEC Rule 612
    # and stated as invariant in PRD §20.13. Its value ($0.01) coincides numerically with
    # `vwap_stop_band_pct` (1% as a fraction), which is a units collision rather than a
    # restatement. Exempting the *definition line only* keeps the check strict elsewhere.
    exempt_assignments = ("TICK_SIZE",)
    for path in sorted(SRC.glob("*.py")):
        if path.name in ("params.py", "__init__.py"):
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            code = line.split("#", 1)[0]
            if "Decimal(" not in code:
                continue
            if any(re.match(rf"\s*{c}\s*[:=]", code) for c in exempt_assignments):
                continue
            for lit, name in literals.items():
                if re.search(rf'Decimal\(\s*["\']{re.escape(lit)}["\']\s*\)', code):
                    offenders.append(f"{path.name}:{i} hardcodes {lit} (= {name})")
    assert not offenders, (
        "registered thresholds must be read from tradipy.params, not hardcoded:\n  "
        + "\n  ".join(offenders)
    )


def _collect_prose_restatements() -> list[str]:
    literals = _registered_literals()
    hits: list[str] = []
    section = ""
    for line in _prd_lines():
        if line.startswith(("## ", "### ")):
            section = line.strip()
        if any(section.startswith(s) for s in DEFINING_SECTIONS):
            continue
        for lit, name in literals.items():
            if lit in line:
                hits.append(f"{name}|{lit}|{section.split(' ', 1)[-1][:40]}")
    return sorted(set(hits))


@pytest.mark.spec
def test_prd_prose_restatements_match_baseline() -> None:
    """Fail when the PRD restates a registered threshold somewhere new.

    Each entry is either a legitimate worked-example value or a latent divergence of exactly
    the kind that produced the v1.2 defect. Regenerate deliberately with::

        REGEN_REGISTRY_BASELINE=1 pytest tests/test_parameter_registry.py

    and read the diff before committing it.
    """
    current = _collect_prose_restatements()
    if os.environ.get("REGEN_REGISTRY_BASELINE"):
        BASELINE.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        pytest.skip("baseline regenerated")

    assert BASELINE.exists(), (
        "no baseline committed; run REGEN_REGISTRY_BASELINE=1 pytest to create one"
    )
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    new = sorted(set(current) - set(baseline))
    gone = sorted(set(baseline) - set(current))

    assert not new, (
        "new restatements of registered thresholds in PRD prose — each is either a worked "
        "example (add to baseline) or a latent divergence (fix the doc):\n  "
        + "\n  ".join(new)
    )
    assert not gone, (
        f"{len(gone)} baseline entries are no longer present in the PRD. This is usually "
        "good — a restatement was removed — but it must be confirmed, not skipped past, "
        "because a shrinking PRD silently degrades this check. Re-run with "
        "REGEN_REGISTRY_BASELINE=1 to accept:\n  " + "\n  ".join(gone)
    )


@pytest.mark.spec
def test_every_registered_param_is_cited_to_the_prd() -> None:
    """Each registry entry must name the PRD section that defines it.

    Without this the registry becomes a second source of truth rather than a mirror of one.
    """
    missing = [n for n, p in PARAMS.items() if "PRD §" not in p.source]
    assert not missing, f"parameters lacking a PRD citation: {missing}"


@pytest.mark.spec
def test_registry_defaults_are_within_their_own_bounds() -> None:
    for name, p in PARAMS.items():
        assert p.lo <= p.default <= p.hi, f"{name} default {p.default} outside [{p.lo}, {p.hi}]"


@pytest.mark.spec
def test_unregistered_literals_in_prd_mvp_path() -> None:
    """Known thresholds the PRD states as bare literals with no §2/§2.0 entry.

    Found while writing :func:`tradipy.gates.vwap_reclaim_stop`: §3.4 writes the stop band as
    ``VWAP × 0.99`` — a 1% threshold with no name, no bounds, and no row in any definition
    table, sitting directly on the MVP path. It is registered here as ``vwap_stop_band_pct``
    so the code has a single source of truth, but the PRD should give it a §2.0 row.

    This test documents the gap and fails if a *new* bare multiplier of the same shape
    appears in §3.
    """
    lines = _prd_lines()
    section = ""
    bare = []
    for i, line in enumerate(lines, 1):
        if line.startswith(("## ", "### ")):
            section = line.strip()
        if not section.startswith("### 3."):
            continue
        # A price multiplied by a bare decimal factor, e.g. "VWAP × 0.99".
        for m in re.finditer(r"×\s*(0\.9\d|1\.0\d)\b", line):
            bare.append(f"L{i} {section.split(' ', 1)[-1][:30]}: × {m.group(1)}")

    known = {"× 0.99"}
    unknown = [b for b in bare if b.split(": ")[-1] not in known]
    assert not unknown, (
        "new bare multiplier(s) in §3 with no registered parameter:\n  " + "\n  ".join(unknown)
    )
    assert bare, (
        "expected to still find the §3.4 `VWAP × 0.99` literal; if it has been given a "
        "named parameter, delete this test and drop vwap_stop_band_pct's 'unnamed' note"
    )
