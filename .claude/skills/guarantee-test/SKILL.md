---
name: guarantee-test
description: Write the test that breaks a stated guarantee. Use whenever code, a docstring, or a doc asserts that something cannot happen, is non-bypassable, is always/never true, or is enforced — and when reviewing whether an existing guarantee is actually enforced. Covers CLAUDE.md convention 6 and the fifth defect class.
---

# Writing the test that breaks a guarantee

This is `CLAUDE.md` convention 6, as a procedure. It exists because **four guarantees were
unenforced at once** in tradipy v0.0.1, three of them with a passing test sitting immediately
beside the hole. A test that confirms the happy path passes whether or not the guarantee is
enforced. Only a test that *performs the forbidden thing* can tell the difference.

## When this applies

Any sentence of the form:

- "X cannot happen" / "there is no way to X"
- "non-bypassable", "hard cap", "always", "never", "in every case", "uniformly"
- "every construction path validates; there is no other"
- "the registry decides Y, not the call site"

If you are **writing** such a sentence, the test is part of the same change. If you are
**reviewing** one, the first question is not whether the mechanism exists but whether anything
calls it.

## Procedure

### 1. Restate the guarantee as an attack

Turn the claim into an imperative you can execute. Be specific about the *path*, because the
v0.0.1 defects were all reachable paths the guarantee's author had not enumerated.

| Guarantee | The attack |
|---|---|
| "`Config` is frozen and validated" | Mutate the module dict it reads from, after construction |
| "Every construction path validates" | Enumerate the paths. Call each. `Config(values)` was the one nobody listed |
| "The registry decides rounding direction" | Flip a registry polarity and assert the gate's output *changes* |
| "`max_risk_per_trade_pct` cannot exceed 2%" | Construct a config at 50% and assert it raises |

If you cannot phrase an attack, the guarantee is probably vacuous — say so rather than writing
a test that cannot fail.

### 2. Prove the attack would succeed without the guard

This is the step that gets skipped, and skipping it is how you get a test that passes for the
wrong reason. Temporarily remove or invert the mechanism, run your new test, and **confirm it
fails**. Then restore the mechanism and confirm it passes.

```
1. write test_hard_cap_rejects_50_percent  ->  run it, it passes
2. comment out the HARD_CAPS loop in validate_couplings
3. run it again. IF IT STILL PASSES, the test is not testing the guard.
4. restore, re-run
```

A test that passes in both states is worse than no test: it is false assurance, and false
assurance is what stopped anyone noticing `Config.polarity()` had zero callers.

### 3. Assert the derivation, not the value

Convention 4. `assert cap == Decimal("0.01")` passes under a wrong rule that happens to agree
at that input. Write `assert cap == floor_to_tick(x) and cap <= x` — the second clause is the
actual guarantee.

For polarity guarantees, assert *directionally*: that flipping the registry declaration moves
the output the corresponding way. `tests/test_enforcement.py`'s `_with_flipped_polarity`
helper is the pattern to copy.

### 4. Beware degenerate fixtures

The three PRD §3 worked examples are numerically degenerate: every level is already a whole
tick and all three risk divisions are exact, so `ceil`, `floor` and `round` agree on every one.
**Twelve rounding mutations survived the entire suite** because of this, under a PRD §19 row
that had just been ticked green.

So when the guarantee concerns rounding, truncation or direction, add a fixture where the naive
alternatives give *different* answers. The `NON_TICK_R` / `NON_TICK_CFG` block in
`tests/test_boundary.py` is the existing one — extend it rather than starting a new one.

### 5. Add the guard on the guard, if the guarantee is a lint

If what you are enforcing is itself a checker, write a test asserting the checker can still
*see* what it claims to check. The registry lint was blind to 7 of 29 parameters because
`Decimal.normalize()` renders `Decimal("30000")` as `3E+4`, a string that cannot occur in
source; six hardcoded thresholds passed it clean.

`test_lint_search_terms_contain_no_scientific_notation` and
`test_the_source_lint_sees_every_way_of_spelling_the_constructor` are the existing examples.

### 6. Place and mark it

- Enforcement tests live in `tests/test_enforcement.py`, grouped with the guarantee they attack.
- Boundary and degenerate-fixture tests go in `tests/test_boundary.py`.
- Apply the markers that fit: `spec`, `boundary`, `polarity`. `--strict-markers` is on, so a
  typo fails rather than silently doing nothing.
- Name the test after the violation, not the mechanism:
  `test_mode_preset_mutation_cannot_reach_a_live_config`, not `test_mode_presets`.

### 7. If the guarantee cannot be enforced yet, say so in the document

Some guarantees have no mechanism because the layer they need does not exist — `daily_loss_pct`
is marked non-bypassable in PRD §7 and nothing in the package tracks realized P&L. **Do not
write a test that pretends otherwise, and do not quietly drop the finding.** Qualify the claim
in the normative document — that is a spec question, so raise it — and record it in
`docs/CHANGELOG.md` under Unreleased.

## Checklist

- [ ] The guarantee is restated as an executable attack on a specific path.
- [ ] All construction and entry paths enumerated, not just the obvious one.
- [ ] The test was proved to fail with the mechanism removed.
- [ ] Assertions test the derivation, not a literal a wrong rule would also produce.
- [ ] If rounding or direction is involved, a non-degenerate fixture covers it.
- [ ] If the guarantee is a checker, it has a guard on the guard.
- [ ] Correct marker applied; test named after the violation.
- [ ] `make check` green, and `uv run python -m tradipy demo` still exits 0.

## Further reading

- `CLAUDE.md` conventions 4 and 6
- `tests/test_enforcement.py` — all 17 existing examples
- `docs/reviews/REVIEW-2026-07-28.md` — findings F1–F4, the four unenforced guarantees, each
  with its reproduction
- `docs/PLAN.md` — the five-defect-classes table, and the second population of the fifth class
  (parameters registered and read by nothing)
