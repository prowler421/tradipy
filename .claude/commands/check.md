---
description: Run the full quality gate (lint + format check + typecheck + test)
---

Run `make check` and report the result. If anything fails:

- fix lint/format issues with `make format` then re-run,
- for type errors, prefer a real fix over a suppression,
- for test failures, read the failing assertion — it is written against the
  derivation, so a failure usually means a rule changed, not a flaky test.

Do not mark the task done until `make check` is green.
