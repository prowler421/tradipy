"""Declared data origin, and the gate that keeps the project on simulated data.

PLAN **D30**: every dataset this repository reads is simulated until the phase ladder is
advanced deliberately — simulated, then paper, then a funded account. This module is the
mechanism. It is the answer to a hole review round 7 named and declined to close: a
``PROVENANCE.txt`` existed, said "SYNTHETIC", and *nothing read it*, so the Q4 pipeline printed
a §7 verdict over fabricated input in exactly the format it would print over measured input.

Three rules, each enforced here rather than asserted in prose:

1. **Undeclared is not simulated.** A directory with no ``PROVENANCE.txt``, or one whose header
   has no parseable ``origin``, raises :class:`UndeclaredProvenanceError`. Defaulting the
   missing case to ``SIMULATED`` would make the marker decorative again — the file that most
   needs a declaration is the one somebody dropped in without writing one.
2. **The declaration covers named files, not a directory.** Each covered file is listed with
   its SHA-256. A directory marker alone lets an undeclared file sit beside a declared one and
   inherit its claim, which is precisely how ``quotes_real.csv`` used to land next to a
   ``PROVENANCE.txt`` reading "SYNTHETIC".
3. **The permitted set is a constant, not an argument.** :data:`PERMITTED_ORIGINS` is what the
   phase ladder moves. A caller cannot widen it by passing a flag, because a gate whose caller
   chooses its own strictness is not a gate.

**What this module is not.** It says nothing about whether data is *good*, only about where it
came from. A simulated dataset that passes here is still incapable of answering Q1–Q4:
docs/PHASE-2A-SPIKE.md §7 binds its thresholds to measured data and states that a synthetic run
is not a data pull. §7 is untouched by D30 — :attr:`Provenance.answers_prereg` is how callers
ask, so that the distinction lives in one place instead of in each report's wording.

Run as a script to declare hand-authored input, which is how ``floats.csv`` and ``latency.csv``
get past the gate — they have no generator, so without this they could not be read at all::

    python -m scripts.spike2a.provenance data/spike2a/latency.csv
"""

from __future__ import annotations

import hashlib
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

#: The marker file, read from the directory containing the dataset.
PROVENANCE_FILENAME = "PROVENANCE.txt"

_COVERS_HEADING = "covers"
_DIGEST_PREFIX = "sha256:"

#: The only tokens :func:`_parse_header` treats as keys. A closed set, so a line of free text
#: beginning "seed the sample from…" cannot become the seed.
_HEADER_KEYS = ("origin", "generator", "seed")


class DataOrigin(Enum):
    """The phase ladder, in the order D30 commits to walking it.

    Ordering is deliberate and load-bearing: ``SIMULATED`` first because it is the only member
    that requires nothing external, ``LIVE`` last because reaching it means committing capital.
    PRD §18.8 governs the final step and this module does not weaken it.
    """

    SIMULATED = "SIMULATED"
    PAPER = "PAPER"
    LIVE = "LIVE"


#: The origins this repository may read **today**. Advancing the ladder is a decision, recorded
#: in ``docs/PLAN.md`` and paired with the PRD §18.8 evidence that step demands — not an edit
#: made in passing while chasing a measurement.
PERMITTED_ORIGINS: frozenset[DataOrigin] = frozenset({DataOrigin.SIMULATED})


class ProvenanceError(RuntimeError):
    """Base for every refusal in this module, so a caller can catch the category."""


class UndeclaredProvenanceError(ProvenanceError):
    """No parseable declaration covers the dataset. Not the same as "declared simulated"."""


class ForbiddenOriginError(ProvenanceError):
    """The declaration is well-formed and names an origin D30 does not currently permit."""


def digest(path: Path) -> str:
    """SHA-256 of ``path``, in the form the marker file records."""
    return _DIGEST_PREFIX + hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Provenance:
    """Where a dataset came from, as declared beside it."""

    origin: DataOrigin
    generator: str
    #: ``None`` for anything not produced by a seeded generator.
    seed: int | None = None
    #: Filename → ``sha256:…`` for every file this declaration covers.
    files: Mapping[str, str] = field(default_factory=dict)
    #: Free text reproduced verbatim under the header. Never parsed.
    detail: str = ""

    @property
    def is_simulated(self) -> bool:
        return self.origin is DataOrigin.SIMULATED

    @property
    def answers_prereg(self) -> bool:
        """Whether a verdict over this data may be read as a PHASE-2A-SPIKE §7 answer.

        Only measured data can. §7: *"§7's thresholds are binding against measured data; a
        synthetic run is not a data pull."* This property exists so that sentence is applied by
        one expression rather than re-derived, differently, in each report.
        """
        return not self.is_simulated


def _parse_header(text: str) -> tuple[dict[str, str], dict[str, str], str]:
    """Split the marker into ``key → value`` pairs, the ``covers`` block, and the free text.

    The format is deliberately dull — a recognised leading token is a key, the remainder is its
    value, and a line indented under ``covers`` is a covered file. Dull because the alternative
    is a parser with opinions, and a provenance file that can be misread is worse than none.

    Only :data:`_HEADER_KEYS` are treated as keys. Everything after them and before ``covers``
    is free text, returned verbatim so :func:`declare` can carry a generator's own description
    forward instead of overwriting it with "hand-authored". The human-readable banner line above
    ``origin`` is preamble and is dropped, so a ``read`` → ``render`` round trip does not nest
    the file inside itself.
    """
    keys: dict[str, str] = {}
    files: dict[str, str] = {}
    detail: list[str] = []
    in_covers = False
    seen_header = False

    for raw in text.splitlines():
        line = raw.strip()
        if in_covers and raw[:1].isspace() and line:
            parts = line.split()
            if len(parts) >= 2 and parts[1].startswith(_DIGEST_PREFIX):
                files[parts[0]] = parts[1]
            continue
        if line == _COVERS_HEADING:
            in_covers = True
            continue
        in_covers = False

        head, _, tail = line.partition(" ")
        key = head.strip().lower()
        if key in _HEADER_KEYS and key not in keys:
            keys[key] = tail.strip()
            seen_header = True
            continue
        if seen_header:
            detail.append(line)

    return keys, files, "\n".join(detail).strip("\n")


def read(directory: Path) -> Provenance:
    """Parse ``directory/PROVENANCE.txt``.

    Raises :class:`UndeclaredProvenanceError` when the file is absent, unreadable, or carries no
    recognised ``origin``. Every one of those is the undeclared case; distinguishing them in the
    exception type would invite a caller to treat one of them as benign.
    """
    marker = directory / PROVENANCE_FILENAME
    if not marker.is_file():
        raise UndeclaredProvenanceError(
            f"no {PROVENANCE_FILENAME} in {directory} — data with no declared origin is not "
            f"treated as simulated (PLAN D30). Regenerate with "
            f"`uv run python -m scripts.spike2a.synthetic_data_generator`."
        )

    keys, files, detail = _parse_header(marker.read_text(encoding="utf-8"))
    raw_origin = keys.get("origin", "")
    try:
        origin = DataOrigin(raw_origin.upper())
    except ValueError as exc:
        permitted = ", ".join(sorted(o.value for o in DataOrigin))
        raise UndeclaredProvenanceError(
            f"{marker} declares origin {raw_origin!r}; expected one of {permitted}"
        ) from exc

    raw_seed = keys.get("seed", "")
    return Provenance(
        origin=origin,
        generator=keys.get("generator", "unknown"),
        seed=int(raw_seed) if raw_seed.isdigit() else None,
        files=files,
        detail=detail,
    )


def require(*paths: Path) -> Provenance:
    """The gate. Return the declaration covering ``paths``, or refuse.

    Every path must live in one directory and be named — with a matching digest — by that
    directory's declaration, and the declared origin must be in :data:`PERMITTED_ORIGINS`.

    This is the single call a measurement module makes before reading anything. It is one call
    rather than three because the failure that matters is "this ran on data it should not have",
    and three separately-callable checks are three chances to wire up two of them.
    """
    if not paths:
        raise UndeclaredProvenanceError("require() needs at least one data file")

    directories = {p.resolve().parent for p in paths}
    if len(directories) > 1:
        listed = ", ".join(sorted(str(d) for d in directories))
        raise UndeclaredProvenanceError(
            f"inputs span {len(directories)} directories ({listed}); one declaration cannot "
            f"cover them, and picking either would let the other travel undeclared"
        )

    prov = read(directories.pop())

    for path in paths:
        declared = prov.files.get(path.name)
        if declared is None:
            covered = ", ".join(sorted(prov.files)) or "(nothing)"
            raise UndeclaredProvenanceError(
                f"{path.name} is not covered by {PROVENANCE_FILENAME}, which covers {covered}. "
                f"A file beside a declaration does not inherit it (PLAN D30)."
            )
        actual = digest(path)
        if actual != declared:
            raise UndeclaredProvenanceError(
                f"{path.name} does not match the digest in {PROVENANCE_FILENAME} "
                f"({actual} vs {declared}) — the file changed after it was declared, so the "
                f"declaration describes something else"
            )

    if prov.origin not in PERMITTED_ORIGINS:
        permitted = ", ".join(sorted(o.value for o in PERMITTED_ORIGINS))
        raise ForbiddenOriginError(
            f"{prov.origin.value} data is not permitted — this project reads {permitted} data "
            f"only (PLAN D30). Advancing the ladder is a recorded decision, and for LIVE the "
            f"PRD §18.8 evidence bar as well; it is not a change to this line."
        )
    return prov


def banner(prov: Provenance) -> list[str]:
    """The header a report prints so its origin travels with its numbers."""
    seed = "" if prov.seed is None else f", seed {prov.seed}"
    lines = [f"data origin      {prov.origin.value} ({prov.generator}{seed})"]
    if not prov.answers_prereg:
        lines.append(
            "                 a synthetic run is not a data pull — nothing below answers "
            "Q1-Q4 (§7)"
        )
    return lines


def render(
    origin: DataOrigin,
    generator: str,
    seed: int | None,
    covered: Iterable[Path],
    detail: str,
    also: Mapping[str, str] | None = None,
) -> str:
    """The marker file's text, digests computed from the files as written.

    ``also`` carries entries forward from an existing marker, so :func:`declare` can add a file
    without dropping the ones already declared.
    """
    header = [
        f"{origin.value} — written by {generator}.",
        "",
        f"origin            {origin.value}",
        f"generator         {generator}",
    ]
    if seed is not None:
        header.append(f"seed              {seed}")

    files = dict(also or {})
    files.update({p.name: digest(p) for p in covered})
    # The separating space is not cosmetic. Padded to a fixed width with no separator, a name of
    # 18 characters or more runs straight into its digest, `line.split()` returns one token, and
    # the entry is silently dropped on the way back in — which `q3_measurements.csv`, at 19
    # characters, reproduced exactly.
    covers = [f"  {name:<18} {digest_}" for name, digest_ in sorted(files.items())]
    return "\n".join([*header, "", detail.rstrip("\n"), "", _COVERS_HEADING, *covers, ""])


_BY_HAND = "scripts/spike2a/provenance.py (declared by hand)"


def declare(*paths: Path, detail: str = "hand-authored") -> Path:
    """Declare ``paths`` ``SIMULATED``, merging into any existing marker in their directory.

    For input with no generator — ``floats.csv`` and ``latency.csv``, whose sources are a second
    float provider and a measured run.

    **What merging does and does not cover.** Adding a file leaves the entries already declared
    alone, *and* leaves the existing header alone — the generator's name, seed and description
    are carried forward rather than overwritten, because a marker that replaced
    ``generator scripts/spike2a/synthetic_data_generator.py, seed 42`` with "hand-authored"
    would be describing four files it did not produce. The reverse direction is **not** covered
    and must not be claimed: :mod:`scripts.spike2a.synthetic_data_generator` rewrites the marker
    with its own four files, so a hand-authored declaration has to be re-run after a
    regeneration. That asymmetry is deliberate — the generator is authoritative for its own
    output and a stale entry for a file it no longer writes would be a false declaration — and
    it is documented in ``scripts/spike2a/README.md`` where somebody will hit it.

    Refuses two cases rather than resolving them:

    * a marker declaring a non-``SIMULATED`` origin, which would be relabelling data somebody
      declared honestly;
    * a marker that exists but does not parse, which :func:`read` raises on and this function
      deliberately does **not** catch. Only the *missing* marker is the fresh-start case. Treating
      a malformed one as fresh would turn ``origin PAPERR`` — a typo, a truncation, a hand edit —
      into a silent relabelling to ``SIMULATED``, which is precisely the default this module
      exists to refuse.
    """
    if not paths:
        raise UndeclaredProvenanceError("declare() needs at least one file")
    directories = {p.resolve().parent for p in paths}
    if len(directories) > 1:
        raise UndeclaredProvenanceError("declare() takes files from one directory")
    directory = directories.pop()

    marker = directory / PROVENANCE_FILENAME
    generator, seed, text, existing = _BY_HAND, None, detail, {}
    if marker.is_file():
        prior = read(directory)
        if prior.origin is not DataOrigin.SIMULATED:
            raise ForbiddenOriginError(
                f"{directory} is declared {prior.origin.value}; refusing to overwrite it with a "
                f"SIMULATED declaration"
            )
        generator, seed, existing = prior.generator, prior.seed, prior.files
        added = ", ".join(sorted(p.name for p in paths))
        text = f"{prior.detail}\n\nDeclared by hand and added to this marker: {added}."

    marker.write_text(
        render(
            origin=DataOrigin.SIMULATED,
            generator=generator,
            seed=seed,
            covered=paths,
            detail=text,
            also=existing,
        ),
        encoding="utf-8",
    )
    return marker


def _main(argv: list[str]) -> int:
    """``python -m scripts.spike2a.provenance <file> [<file>...]``"""
    if not argv:
        print(__doc__)
        print("usage: python -m scripts.spike2a.provenance <file> [<file>...]")
        return 2
    marker = declare(*(Path(a) for a in argv))
    print(f"declared SIMULATED in {marker}: {', '.join(sorted(Path(a).name for a in argv))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
