"""Assert that counts stated in prose match the code they describe.

Why this file exists. The v1.2 defect class is *a quantity stated in two places, one of
them updated*. It was found in the PRD, fixed there, and then recurred inside the
documentation set itself: ``tests/README.md`` carried a heading reading "Four open spec
discrepancies" above a list of six, and a fixture docstring said eleven surviving mutations
where three other documents said twelve. Both were live at package v0.1.0, in a repository
whose parameter registry exists specifically to stop this.

The registry lint solves the problem for *thresholds*. Nothing solved it for the counts the
documentation quotes about itself — how many parameters are registered, how many entries the
frozen baseline holds, how many modules the package has. Those are restated in six documents
and drift for free.

Scope, stated because an unqualified claim about a checker is what F8 was about:

* This checks counts that are **mechanically derivable from the code**. It does not check
  prose claims about behaviour, and it cannot.
* It checks the documents under ``docs/`` and the repository-root Markdown files. It
  deliberately does **not** check ``docs/reviews/`` — reviews are kept unedited as the record
  of what was found at the time, so a stale count in a review is correct-as-of and fixing it
  would falsify the record.
* Where a count appears in prose in more than one phrasing, each phrasing needs its own
  pattern here. A phrasing this file does not know about is not checked, which is why
  ``test_every_document_that_states_a_registry_count_is_covered`` exists as the guard on the
  guard.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tradipy import params

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
BASELINE = REPO / "tests" / "registry_baseline.json"

# Documents whose self-describing counts are checked. Reviews are excluded on purpose (see the
# module docstring): they are a historical record, not a live description.
CHECKED_DOCS: tuple[Path, ...] = (
    DOCS / "README.md",
    DOCS / "PLAN.md",
    DOCS / "api.md",
    DOCS / "architecture.md",
    DOCS / "development.md",
    DOCS / "CHANGELOG.md",
    DOCS / "PHASE-2A-SPIKE.md",
    REPO / "CLAUDE.md",
    REPO / "README.md",
    REPO / "CONTRIBUTING.md",
    REPO / "tests" / "README.md",
)

WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}


def _library_modules() -> set[str]:
    """The library modules — every ``src/tradipy/*.py`` except the CLI and the package init."""
    return {
        p.stem
        for p in (REPO / "src" / "tradipy").glob("*.py")
        if p.stem not in {"__init__", "__main__"}
    }


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _docs_stating(pattern: re.Pattern[str]) -> list[Path]:
    return [p for p in CHECKED_DOCS if p.exists() and pattern.search(_text(p))]


# ---------------------------------------------------------------------------
# Registered parameter count
# ---------------------------------------------------------------------------

# Matches "47 registered thresholds", "47 entries", "**47** entries", "17 of 47 registered".
#
# "rows" is deliberately NOT an alternative here. PRD §2 is a 14-row threshold *table* and the
# PLAN quotes that figure; matching "rows" made this test fail on a true statement about a
# different thing. A pattern that is too greedy produces false failures, which get suppressed,
# which is how a lint stops being trusted.
_REGISTRY_COUNT = re.compile(
    r"\*{0,2}(\d{2})\*{0,2}\s+(?:registered\s+thresholds?|entries\b)"
    r"|of\s+\*{0,2}(\d{2})\*{0,2}\s+registered"
)

# Lines that describe what ``tradipy/__init__.py`` re-exports rather than what the package
# contains. Seven modules are re-exported and eight exist, because ``poc`` is deliberately not
# part of what ``import tradipy`` means — so both counts are true and each needs its own test.
_REEXPORT_CONTEXT = ("re-export", "imports", "advertis", "__all__", "binds")


@pytest.mark.spec
def test_documented_registry_count_matches_the_registry() -> None:
    """Every stated count of registered parameters equals ``len(params.PARAMS)``.

    The registry is the artifact this project points at when asked whether a rule is
    implemented. A document quoting the wrong size for it is the v1.2 class applied to the
    v1.2 fix.
    """
    actual = len(params.PARAMS)
    wrong: list[str] = []

    for path in CHECKED_DOCS:
        if not path.exists():
            continue
        for lineno, line in enumerate(_text(path).splitlines(), start=1):
            for match in _REGISTRY_COUNT.finditer(line):
                stated = int(match.group(1) or match.group(2))
                if stated != actual:
                    rel = path.relative_to(REPO)
                    wrong.append(f"{rel}:{lineno}: states {stated}, registry holds {actual}")

    assert not wrong, "registry count drifted:\n  " + "\n  ".join(wrong)


@pytest.mark.spec
def test_every_document_that_states_a_registry_count_is_covered() -> None:
    """Guard on the guard: the pattern above must actually match something.

    A lint that silently matches nothing passes forever. The registry lint was blind to 7 of
    29 parameters for exactly this reason, and six hardcoded thresholds passed it clean.
    """
    stating = _docs_stating(_REGISTRY_COUNT)
    assert stating, (
        "no document matched the registry-count pattern — either every mention was removed "
        "(update this test) or the pattern no longer matches the phrasing in use"
    )


# ---------------------------------------------------------------------------
# Frozen baseline size
# ---------------------------------------------------------------------------

_BASELINE_COUNT = re.compile(r"(\d{2})[- ](?:entry|frozen)|(\d{2})\s+frozen")


@pytest.mark.spec
def test_documented_baseline_size_matches_the_baseline_file() -> None:
    """Every stated size of the frozen PRD-prose baseline matches the JSON on disk.

    The baseline is the list of PRD literals that already restate a registered default. Its
    size is quoted in the PLAN as evidence that the registry check is complete, so a wrong
    figure there is a status claim that is not checkable — which is what F7 was.
    """
    import json

    entries = json.loads(_text(BASELINE))
    actual = len(entries)
    wrong: list[str] = []

    for path in CHECKED_DOCS:
        if not path.exists():
            continue
        for lineno, line in enumerate(_text(path).splitlines(), start=1):
            if "baseline" not in line.lower() and "frozen" not in line.lower():
                continue
            for match in _BASELINE_COUNT.finditer(line):
                stated = int(match.group(1) or match.group(2))
                if stated != actual:
                    rel = path.relative_to(REPO)
                    wrong.append(f"{rel}:{lineno}: states {stated}, baseline holds {actual}")

    assert not wrong, "baseline size drifted:\n  " + "\n  ".join(wrong)


# ---------------------------------------------------------------------------
# Module count
# ---------------------------------------------------------------------------


@pytest.mark.spec
def test_documented_module_count_matches_the_package() -> None:
    """"Eight library modules" must be however many there actually are.

    ``architecture.md`` and ``api.md`` both open with this count and both draw a dependency
    graph beneath it. The graph is the thing a reader trusts; the count is what tells them
    whether it is complete.
    """
    actual = len(_library_modules())
    word = WORDS[actual]
    pattern = re.compile(r"\b(\w+)\s+(?:small,\s+pure\s+modules|library\s+modules)", re.I)

    wrong: list[str] = []
    for path in CHECKED_DOCS:
        if not path.exists():
            continue
        for lineno, line in enumerate(_text(path).splitlines(), start=1):
            if any(marker in line for marker in _REEXPORT_CONTEXT):
                continue  # that sentence is about __all__; the next test owns it
            for match in pattern.finditer(line):
                stated = match.group(1).lower()
                if stated != word and stated != str(actual):
                    rel = path.relative_to(REPO)
                    wrong.append(
                        f"{rel}:{lineno}: states {stated!r} library modules, package has "
                        f"{actual} ({word})"
                    )

    assert not wrong, "module count drifted:\n  " + "\n  ".join(wrong)


@pytest.mark.spec
def test_the_re_exported_module_count_matches_package_all() -> None:
    """"the seven library modules" refers to ``tradipy.__all__``, which excludes ``poc``.

    Two different true counts sit two paragraphs apart in ``architecture.md``: eight modules
    exist, seven are re-exported, because ``poc`` is deliberately not part of what
    ``import tradipy`` means. Both are correct and the pair is exactly the configuration that
    invites someone to "fix" one of them.
    """
    import tradipy

    actual = len(tradipy.__all__)
    word = WORDS[actual]
    pattern = re.compile(r"\b(\w+)\s+library\s+modules\b", re.I)

    wrong: list[str] = []
    for path in CHECKED_DOCS:
        if not path.exists():
            continue
        for lineno, line in enumerate(_text(path).splitlines(), start=1):
            if not any(marker in line for marker in _REEXPORT_CONTEXT):
                continue
            for match in pattern.finditer(line):
                stated = match.group(1).lower()
                if stated not in {word, str(actual)}:
                    rel = path.relative_to(REPO)
                    wrong.append(
                        f"{rel}:{lineno}: states {stated!r} re-exported modules, "
                        f"__all__ has {actual} ({word})"
                    )

    assert not wrong, "re-exported module count drifted:\n  " + "\n  ".join(wrong)


# ---------------------------------------------------------------------------
# Reject codes
# ---------------------------------------------------------------------------


@pytest.mark.spec
def test_reject_enum_members_are_all_documented_in_api_md() -> None:
    """Every ``Reject`` member appears in ``docs/api.md``.

    G3 found that nothing compares the enum to the spec's rejection-code namespace in either
    direction. This is the cheap half of that: the API reference must at least name every
    code the enum defines, so a new member cannot ship undocumented.
    """
    from tradipy.rejects import Reject

    api = _text(DOCS / "api.md")
    missing = sorted(m.name for m in Reject if m.name not in api)
    assert not missing, f"Reject members absent from docs/api.md: {missing}"


# ---------------------------------------------------------------------------
# Pytest markers
# ---------------------------------------------------------------------------


@pytest.mark.spec
def test_every_registered_marker_is_documented_and_used() -> None:
    """Markers declared in ``pyproject.toml`` are documented and actually applied.

    ``--strict-markers`` catches a marker that is *used* without being declared. Nothing
    catches the reverse — a marker declared, documented as meaningful, and applied to no
    test. That is a mechanism built and not wired, which is the fifth defect class.
    """
    pyproject = _text(REPO / "pyproject.toml")
    block = pyproject.split("markers = [", 1)[1].split("]", 1)[0]
    declared = set(re.findall(r'"(\w+):', block))

    suite = "\n".join(
        _text(p) for p in sorted((REPO / "tests").glob("test_*.py"))
    )
    unused = sorted(m for m in declared if f"@pytest.mark.{m}" not in suite)
    assert not unused, f"markers declared but applied to no test: {unused}"

    tests_readme = _text(REPO / "tests" / "README.md")
    undocumented = sorted(m for m in declared if m not in tests_readme)
    assert not undocumented, f"markers not documented in tests/README.md: {undocumented}"
