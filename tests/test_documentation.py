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
    # The two design records were **outside** this tuple until Phase 5, which is a gap of exactly
    # the shape this file exists to close: they are the documents that state the most counts about
    # the code, and none of those counts was checked. Found by the adversarial fact-check of
    # PHASE-5-DESIGN, which turned up a registry-row claim, a boundary-fixture claim and a
    # test-count claim that a reader had to verify by hand. A guard that omits the documents most
    # likely to drift is a guard whose scope nobody stated.
    DOCS / "PHASE-4-DESIGN.md",
    DOCS / "PHASE-5-DESIGN.md",
    DOCS / "PHASE-6-DESIGN.md",
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
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
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
# contains. One fewer is re-exported than exists, because ``poc`` is deliberately not part of
# what ``import tradipy`` means — so both counts are true and each needs its own test. Neither
# number is written here: this file exists to catch counts stated in prose that drift from the
# code, and it had two of its own wrong within one change of the package growing a module.
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
    """Every stated count of *library modules* equals what ``src/tradipy/`` contains.

    ``architecture.md`` and ``api.md`` both open with this count and draw a dependency
    graph beneath it. The graph is what a reader trusts; the count tells them whether
    it is complete. The count itself is derived below, never written here.
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
    """Every stated count of *re-exported* modules equals ``len(tradipy.__all__)``.

    Two different true counts sit two paragraphs apart in ``architecture.md``: every library
    module exists, one fewer is re-exported, because ``poc`` is deliberately not part of what
    ``import tradipy`` means. Both are correct; the pair exactly matches the configuration
    that invites someone to "fix" one of them — which is why the numbers are derived and not
    named here.
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

    suite = "\n".join(_text(p) for p in sorted((REPO / "tests").glob("test_*.py")))
    unused = sorted(m for m in declared if f"@pytest.mark.{m}" not in suite)
    assert not unused, f"markers declared but applied to no test: {unused}"

    tests_readme = _text(REPO / "tests" / "README.md")
    undocumented = sorted(m for m in declared if m not in tests_readme)
    assert not undocumented, f"markers not documented in tests/README.md: {undocumented}"


# ---------------------------------------------------------------------------
# Spec-question table sizes — the count stated as a word above its own table
# ---------------------------------------------------------------------------
#
# `_REGISTRY_COUNT` above matches **digits**, so a heading reading `**Fourteen**` over a list of
# fifteen is invisible to it. That is not hypothetical: it happened twice inside one changeset in
# `docs/CHANGELOG.md`'s Phase 5 section — once in the first draft, and again when a review
# disposition added a row to the table and left the number alone, in the paragraph that had just
# finished explaining the first instance. Six occurrences of this shape are now on record (L1, K6
# row 3, PLAN's round count, PHASE-5-DESIGN §6's first draft, its boundary-fixture claim, and this
# one), and prose calling the shape out has demonstrably not stopped it.
#
# Scope, stated because an unqualified claim about a checker is what F8 was about: this counts the
# **rows** of each `### Spec questions` table in `docs/CHANGELOG.md` and compares them against the
# first spelled-out number in the paragraph beneath the heading. It does not check the changelog's
# other tables, it does not check any other document, and it cannot tell whether a row *should*
# exist. A table whose heading states no number at all is skipped and reported by the guard below.

_WORD_TO_INT = {word: value for value, word in WORDS.items()}

#: A count stated as a word, in **count position**: the first token of a bold run opening a line,
#: as in ``**Fifteen, plus the two findings above.**``. Deliberately narrow. The first version of
#: this took the first number-word anywhere in the paragraph and read *"localised to **one**
#: function"* as a claim that the table had one row — a pattern too greedy produces false failures,
#: which get suppressed, which is how a lint stops being trusted. That warning is already written
#: above ``_REGISTRY_COUNT``; this is what ignoring it looks like.
_STATED_WORD_COUNT = re.compile(r"^\*\*(" + "|".join(_WORD_TO_INT) + r")\b", re.I | re.MULTILINE)


def _changelog_question_tables() -> list[tuple[str, int, int | None]]:
    """Every ``### Spec questions`` section: its heading, its row count, and its stated number."""
    lines = _text(DOCS / "CHANGELOG.md").splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("### Spec questions")]
    out: list[tuple[str, int, int | None]] = []
    for start in starts:
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].startswith("#")), len(lines)
        )
        body = lines[start + 1 : end]
        rows = [
            line
            for line in body
            if line.startswith("|")
            and not re.fullmatch(r"\|[\s\-|:]+\|", line)
            and not line.startswith("| Where |")
        ]
        prose = "\n".join(line for line in body if not line.startswith("|"))
        found = _STATED_WORD_COUNT.search(prose)
        stated = _WORD_TO_INT[found.group(1).lower()] if found else None
        out.append((lines[start], len(rows), stated))
    return out


@pytest.mark.spec
def test_each_spec_question_table_matches_the_count_stated_above_it() -> None:
    """A ``### Spec questions`` heading's number must equal the rows beneath it.

    The count is the table, everywhere it is quoted — ``docs/PHASE-4-DESIGN.md`` §6 and
    ``docs/PHASE-5-DESIGN.md`` §6 both defer to ``docs/CHANGELOG.md`` for the number rather than
    restating it, precisely so that this is the only place it can drift.
    """
    wrong = [
        f"{heading!r}: states {stated}, table has {rows}"
        for heading, rows, stated in _changelog_question_tables()
        if stated is not None and stated != rows
    ]
    assert not wrong, "spec-question count drifted:\n  " + "\n  ".join(wrong)


@pytest.mark.spec
def test_the_spec_question_count_check_is_live() -> None:
    """Guard on the guard: the check above must be evaluating at least one real count.

    A lint that matches nothing passes forever, which is how the registry lint stayed blind to 7 of
    29 parameters. Sections that state **no** count in count position are simply not checked, and
    that is the scope statement rather than a defect — most of these sections are short enough that
    a stated total adds nothing. What must not happen is *every* section going unchecked, because
    then the mechanism is decorative.
    """
    tables = _changelog_question_tables()
    assert tables, "no '### Spec questions' section found — check the parser, not the result"
    counted = [(h, r, s) for h, r, s in tables if s is not None]
    assert counted, (
        "no spec-question section states a count in count position — either the phrasing changed "
        "or _STATED_WORD_COUNT no longer matches it, and the check above is now inert"
    )
    # And the parser must be reading rows, not zero of them.
    assert all(rows > 0 for _, rows, _ in counted), (
        f"a counted section parsed to zero rows: {[(h, r) for h, r, _ in counted if r == 0]}"
    )
