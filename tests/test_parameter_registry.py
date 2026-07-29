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

**The code lint was blind to 7 of 29 parameters until v0.1.0.** Its search set was built from
``Decimal.normalize()``, which renders any trailing-zero value in scientific notation —
``Decimal("30000")`` normalizes to ``3E+4``, a string that cannot occur in hand-written
source. ``start_of_day_equity``, ``max_shares_per_order``, ``max_float_shares``,
``min_adv_shares``, ``rvol_lookback_days``, ``bar_close_grace_ms`` and ``max_price`` were all
unenforced, and six hardcoded literals injected into ``gates.py`` passed the lint clean. See
:func:`test_lint_search_terms_contain_no_scientific_notation`, which is the guard against it
recurring.
"""

from __future__ import annotations

import ast
import json
import os
import re
from decimal import Decimal
from pathlib import Path

import pytest

from tradipy.params import HARD_CAPS, MODE_PRESETS, PARAMS

REPO = Path(__file__).resolve().parents[1]
PRD = REPO / "docs" / "PRD.md"
SRC = REPO / "src" / "tradipy"
BASELINE = Path(__file__).parent / "registry_baseline.json"

#: Sections whose whole purpose is to state values. Definition tables are exempt: that is
#: where a threshold is *supposed* to appear as a literal.
DEFINING_SECTIONS = ("### 2.0", "### 2.1", "### 2.2", "### 3.1.2", "### 3.1.3", "## 2.")

#: Defaults too common to search for: they appear constantly in unrelated code and prose.
_UNDISTINCTIVE = (Decimal("0"), Decimal("1"), Decimal("2"), Decimal("100"))


def _prd_lines() -> list[str]:
    return PRD.read_text(encoding="utf-8").split("\n")


def source_literal_forms(value: Decimal) -> set[str]:
    """Every string a hand-written ``Decimal("...")`` for ``value`` could plausibly use.

    ``str(value)`` is the transcribed form and ``str(int(value))`` the shortened one a
    developer is likely to type for a whole number. ``normalize()`` is deliberately **not**
    used: it is what produced the blind spot this function exists to close.
    """
    forms = {str(value)}
    if value == value.to_integral_value():
        forms.add(str(int(value)))
    normalized = str(value.normalize())
    if "E" not in normalized and "e" not in normalized:
        forms.add(normalized)
    return forms


def _registered_literals() -> dict[str, list[str]]:
    """Map the prose form of each registered default to the parameter(s) it could be.

    Only values distinctive enough to be worth matching. Several parameters share a form —
    ``max_pct_of_adv``, ``vwap_stop_band_pct`` and ``max_risk_per_trade_pct`` are all 1% —
    so the value is a **list**. It was a bare string until v0.1.0, where the last writer won
    and roughly ten baseline entries were attributed to the wrong parameter. Detection was
    unaffected; the failure message named the wrong thing to go and look at.
    """
    out: dict[str, list[str]] = {}
    for name, p in PARAMS.items():
        d = p.default
        key: str | None = None
        if p.unit == "USD" and d < Decimal("1"):
            key = f"${d.normalize()}"  # $0.015, $0.02, $0.10
        elif p.unit == "xR" and d != Decimal("2.0"):
            key = f"{d.normalize()}×"  # 2.5×, 0.15×
        elif p.unit == "fraction" and d < Decimal("0.1"):
            key = f"{(d * 100).normalize()}%"  # 0.5%, 4%, 5%, 1%, 3%
        if key is not None:
            out.setdefault(key, []).append(name)
    return {k: sorted(v) for k, v in out.items()}


@pytest.mark.spec
def test_lint_search_terms_contain_no_scientific_notation() -> None:
    """No search term may be a string that cannot appear in source.

    This is the guard on the guard. A lint whose search set silently excludes a parameter
    reports "clean" for a file that hardcodes it, which is worse than having no lint: the
    green result is what stops anyone checking. Seven parameters were in that state.
    """
    offenders = [
        f"{name}: {form}"
        for name, p in PARAMS.items()
        for form in source_literal_forms(p.default)
        if "E" in form or "e" in form
    ]
    assert not offenders, (
        "search terms in scientific notation can never match source and silently exempt "
        "the parameter:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.spec
def test_every_registered_default_has_a_searchable_form() -> None:
    """Every distinctive default contributes at least one term the lint can actually find."""
    unsearchable = [
        name
        for name, p in PARAMS.items()
        if p.default not in _UNDISTINCTIVE and not source_literal_forms(p.default)
    ]
    assert not unsearchable, f"parameters the code lint cannot search for: {unsearchable}"


#: `TICK_SIZE` is not a tunable threshold — it is a market fact fixed by SEC Rule 612 and
#: stated as invariant in PRD §20.13. Its value ($0.01) coincides numerically with
#: `vwap_stop_band_pct` and `max_risk_per_trade_pct` (1% as a fraction), which is a units
#: collision rather than a restatement. Exempting the *definition only* keeps the check
#: strict everywhere else.
EXEMPT_ASSIGNMENTS = ("TICK_SIZE",)


def _decimal_literals_in(text: str) -> list[tuple[int, str]]:
    """Every ``Decimal("...")`` string literal actually constructed in ``text``.

    Parsed rather than pattern-matched. The regex version had two blind spots and one false
    positive, all found by running it:

    * it matched the spelling ``Decimal(`` only, so the ``D = Decimal`` alias this codebase
      uses everywhere was invisible — ``D("0.5")`` sailed through;
    * it stripped ``#`` comments but not docstrings, so prose *describing* a literal was
      reported as one, which is the kind of noise that gets a lint switched off;
    * it could not see a call split across lines.

    An AST has none of those problems: a `Decimal("0.15")` in a docstring is a string, not a
    call, and the alias is resolved from the assignment that creates it.
    """
    tree = ast.parse(text)
    aliases = {"Decimal"}
    exempt_lines: set[int] = set()

    # `from decimal import Decimal as D2` binds the constructor under another name before any
    # assignment runs, so import aliases are collected first.
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "decimal":
            aliases.update(a.asname or a.name for a in node.names if a.name == "Decimal")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if isinstance(node.value, ast.Name) and node.value.id in aliases:
            aliases.update(targets)  # D = Decimal
        if any(t in EXEMPT_ASSIGNMENTS for t in targets):
            exempt_lines.add(node.lineno)

    def _is_constructor(func: ast.expr) -> bool:
        if isinstance(func, ast.Name):
            return func.id in aliases
        # `decimal.Decimal("0.15")` — the qualified form, which no alias can cover.
        return isinstance(func, ast.Attribute) and func.attr == "Decimal"

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _is_constructor(node.func)
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and node.lineno not in exempt_lines
        ):
            found.append((node.lineno, node.args[0].value))
    return found


@pytest.mark.spec
def test_no_registered_literal_hardcoded_in_source() -> None:
    """Every threshold in ``src/`` must be read from the registry by name.

    ``params.py`` is exempt — it is the definition. Everything else must go through it.
    """
    literals: dict[str, str] = {}
    for name, p in PARAMS.items():
        if p.default in _UNDISTINCTIVE:
            continue
        for form in source_literal_forms(p.default):
            literals.setdefault(form, name)

    offenders = [
        f"{path.name}:{line} hardcodes {lit} (= {literals[lit]})"
        for path in sorted(SRC.glob("*.py"))
        if path.name not in ("params.py", "__init__.py")
        for line, lit in _decimal_literals_in(path.read_text(encoding="utf-8"))
        if lit in literals
    ]
    assert not offenders, (
        "registered thresholds must be read from tradipy.params, not hardcoded:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.spec
def test_the_source_lint_sees_every_way_of_spelling_the_constructor() -> None:
    """Guard on the guard: no spelling of ``Decimal`` may hide a literal from the check.

    Asserted on a synthetic module rather than on the tree, because the tree is (correctly)
    clean — a lint can only be shown to work by giving it something to catch. Each line below
    is a form the regex version missed or misreported.
    """
    module = "\n".join(
        [
            "import decimal",
            "from decimal import Decimal",
            "from decimal import Decimal as D2",
            "D = Decimal",
            'PLAIN = Decimal("0.15")',
            'ASSIGNED_ALIAS = D("0.15")',
            'IMPORT_ALIAS = D2("0.15")',
            'QUALIFIED = decimal.Decimal("0.15")',
            "MULTILINE = Decimal(",
            '    "0.15"',
            ")",
            'IN_A_CALL = round(D("2.5"))',
            '"""A docstring mentioning Decimal("0.99") must not count."""',
            '# nor a comment saying Decimal("0.98")',
            "NOT_A_STRING = Decimal(2)",
        ]
    )
    found = [lit for _, lit in _decimal_literals_in(module)]
    assert found.count("0.15") == 5, f"one per spelling, got {found}"
    assert "2.5" in found, "a constructor nested in another call still counts"
    assert "0.99" not in found and "0.98" not in found, "prose is not code"


def _collect_prose_restatements() -> list[str]:
    literals = _registered_literals()
    hits: list[str] = []
    section = ""
    for line in _prd_lines():
        if line.startswith(("## ", "### ")):
            section = line.strip()
        if any(section.startswith(s) for s in DEFINING_SECTIONS):
            continue
        for lit, names in literals.items():
            if lit in line:
                hits.append(f"{'+'.join(names)}|{lit}|{section.split(' ', 1)[-1][:40]}")
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
        "example (add to baseline) or a latent divergence (fix the doc):\n  " + "\n  ".join(new)
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
def test_code_originated_bounds_are_declared_as_such() -> None:
    """A bound the PRD does not state must say so in its ``source``.

    ``params.py`` claims its values and bounds are transcribed from the cited tables. That
    is true of §2.0, §3.1.2 and §3.1.3, which have a Bounds column, and false of §2, §3.1.1,
    §3.4, §20.10 and §20.14, which state defaults only — so roughly half the ``lo``/``hi``
    pairs in the registry are this module's judgement rather than spec. The distinction is
    invisible to :func:`test_every_registered_param_is_cited_to_the_prd`, which only looks
    for the substring ``PRD §``, so it is asserted separately here.
    """
    bounds_are_stated = ("§2.0", "§3.1.2", "§3.1.3", "configurable range")
    undeclared = [
        name
        for name, p in PARAMS.items()
        if "bounds: code" not in p.source and not any(t in p.source for t in bounds_are_stated)
    ]
    assert not undeclared, (
        "these cite a PRD section with no Bounds column but do not mark their bounds as "
        f"code-originated: {undeclared}"
    )


@pytest.mark.spec
def test_registry_defaults_are_within_their_own_bounds() -> None:
    for name, p in PARAMS.items():
        assert p.lo <= p.default <= p.hi, f"{name} default {p.default} outside [{p.lo}, {p.hi}]"


@pytest.mark.spec
def test_mode_presets_are_within_registry_bounds() -> None:
    """PRD §2.0's presets are overrides, so every value must be a legal value of its param.

    Before D27 the four preset settings had no registry entry at all, so nothing checked
    them against §2's stated configurable ranges.
    """
    for mode, preset in MODE_PRESETS.items():
        for name, value in preset.items():
            assert name in PARAMS, f"preset '{mode}' sets unregistered {name}"
            PARAMS[name].validate(value)


@pytest.mark.spec
def test_hard_caps_match_the_registry_ceilings() -> None:
    """The §7 non-bypassable cap and the §2 configurable ceiling are the same number.

    They are stated in two places — ``HARD_CAPS`` and the ``hi`` of the corresponding
    ``Param`` — which is the restatement this whole module exists to prevent. Keeping both is
    deliberate defence in depth: ``validate_couplings`` checks the effective value against
    ``HARD_CAPS``, and per-parameter validation checks it against ``hi``. This test is what
    stops them drifting, and it is also the alarm that fires if a future change widens a
    registry ceiling past a §7 cap — at which point the coupling check stops being redundant
    and starts binding.
    """
    for name, cap in HARD_CAPS.items():
        assert name in PARAMS, f"HARD_CAPS names {name}, which is not a registered parameter"
        assert PARAMS[name].hi == cap, (
            f"{name}: §7 hard cap {cap} disagrees with the registry ceiling "
            f"{PARAMS[name].hi}. Change both, or state deliberately which one governs."
        )


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
