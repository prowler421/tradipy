#!/usr/bin/env python3
"""Validate every relative Markdown link and heading anchor in the repository.

Why this exists. The documentation set is heavily cross-referenced — over a hundred
relative links between eight documents in ``docs/`` plus five in ``docs/reviews/`` — and
three review rounds have found stale citations by reading them one at a time. A broken
link is the same defect class as a threshold restated in two places with one updated (the
v1.2 class): the copies drift, and nothing mechanical notices.

Scope, stated because an unqualified claim about a checker is what F8 was about:

* Checks **relative** links only. ``http://`` and ``https://`` targets are ignored — a
  network fetch in a pre-commit hook is a flake, not a check.
* Checks that the target **file exists**, and where a ``#anchor`` is given, that a heading
  in the target file slugifies to it.
* Anchor slugification follows GitHub's rules: lowercase, strip anything that is not a
  word character, space or hyphen, then spaces to hyphens. Inline Markdown is stripped
  from heading text first, so ``### ``tradipy.params``\\`` matches ``#tradipyparams``.
* Skips fenced code blocks, so an example link inside ``````` is not checked.
* Does not check image targets, reference-style links, or HTML anchors. None is used here.

Exit code is 0 when every link resolves, 1 otherwise. Every failure prints
``file:line: target`` and the reason, so the output is directly actionable.

Run via ``make links``, the ``check-links`` pre-commit hook, or CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Directories that are not ours to validate.
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}

# ``[text](target)`` where target is not a URL, not an anchor-only link handled separately,
# and not an image (those start with ``!`` before the bracket, excluded via the lookbehind).
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")

FENCE = re.compile(r"^\s*(```|~~~)")

# Inline Markdown to strip from heading text before slugifying.
INLINE = re.compile(r"[`*_~]")
NOT_SLUG = re.compile(r"[^\w\s-]")


def slugify(heading: str) -> str:
    """Convert heading text to a GitHub anchor slug."""
    text = INLINE.sub("", heading).strip().lower()
    return NOT_SLUG.sub("", text).replace(" ", "-")


def anchors(path: Path) -> set[str]:
    """Every anchor a Markdown file offers, from its ATX headings."""
    found: set[str] = set()
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not line.startswith("#"):
            continue
        found.add(slugify(line.lstrip("#")))
    return found


def markdown_files() -> list[Path]:
    """Every Markdown file in the repository, excluding vendored and cache directories."""
    return sorted(
        p
        for p in REPO.rglob("*.md")
        if not any(part in SKIP_DIRS for part in p.relative_to(REPO).parts)
    )


def links_in(path: Path) -> list[tuple[int, str]]:
    """Every relative link in a file, as ``(line number, target)``, skipping code fences."""
    out: list[tuple[int, str]] = []
    in_fence = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for target in LINK.findall(line):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            out.append((lineno, target))
    return out


def main() -> int:
    anchor_cache: dict[Path, set[str]] = {}
    failures: list[str] = []
    checked = 0

    for path in markdown_files():
        for lineno, target in links_in(path):
            checked += 1
            where = f"{path.relative_to(REPO)}:{lineno}"

            file_part, _, anchor = target.partition("#")
            resolved = path if not file_part else (path.parent / file_part).resolve()

            if not resolved.exists():
                failures.append(f"{where}: {target} -> missing file {file_part}")
                continue

            if not anchor or resolved.suffix != ".md":
                continue

            if resolved not in anchor_cache:
                anchor_cache[resolved] = anchors(resolved)

            if anchor.lower() not in anchor_cache[resolved]:
                failures.append(f"{where}: {target} -> no heading anchors to #{anchor}")

    if failures:
        print(f"Broken relative links ({len(failures)} of {checked} checked):\n")
        for f in failures:
            print(f"  {f}")
        print("\nFix the citation, or the heading it points at.")
        return 1

    print(f"All {checked} relative Markdown links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
