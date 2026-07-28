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
    print("\nDone. Review the diff before committing:")
    print("    git diff -- tests/registry_baseline.json")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
