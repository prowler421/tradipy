#!/usr/bin/env python3
"""Regenerate the parameter-registry prose baseline.

``tests/test_parameter_registry.py`` compares every restatement of a registered threshold
in ``docs/PRD.md`` against ``tests/registry_baseline.json``. When the PRD legitimately gains
or loses a restatement, the baseline must be regenerated *deliberately* — the test refuses
to self-heal so that a latent divergence cannot slip in unreviewed.

This wrapper runs that regeneration and reminds you to read the diff before committing.

Usage:
    uv run python scripts/regen_registry_baseline.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    """Run pytest with the regen flag set and report the outcome."""
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_parameter_registry.py::test_prd_prose_restatements_match_baseline",
        "-q",
    ]
    print("Regenerating tests/registry_baseline.json ...")
    # The caller's environment is inherited, not replaced: pytest needs HOME, TMPDIR, and
    # (under `uv run`) VIRTUAL_ENV to resolve the same interpreter and plugins as `make test`.
    result = subprocess.run(
        argv,
        cwd=REPO_ROOT,
        env=os.environ | {"REGEN_REGISTRY_BASELINE": "1"},
        check=False,
    )
    if result.returncode != 0:
        # Said "Done. Review the diff" unconditionally until v0.1.0, including when pytest
        # had failed to collect and no baseline was written. The exit code was right and the
        # message was the opposite of it, which is the wrong way round for a tool whose
        # output is the thing you act on.
        print("\npytest exited non-zero — the baseline was NOT regenerated.")
        return result.returncode

    print("\nDone. Review the diff before committing:")
    print("    git diff -- tests/registry_baseline.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
