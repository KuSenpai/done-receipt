---
name: honest-report
description: Write the final report after coding work so every claim is backed by evidence. Use at the end of any task where you changed code, fixed a bug, made tests pass, or are about to say done, complete, fixed, working, all green or ready to merge. Separates what was verified from what was not, and discloses every change to tests.
---

# Write a report the user can trust

The user will act on your last message: merge, deploy, move on. A report that sounds
confident but is not backed by evidence costs them more than a report that says "I
could not verify this". Write for a reader who cannot see what you did and will believe
you.

## The rule

Every success claim needs evidence you actually produced in this session. If you have
no evidence for a claim, either get it or do not make the claim.

| You want to say | You need |
|---|---|
| "Tests pass" / "all green" | A VERIFIED receipt from `verify-tests-ran` that is FRESH, and the number of tests |
| "The bug is fixed" | The failing case that now passes, and which command showed it |
| "I only changed X" | A diff that agrees (`git diff --stat`) |
| "No tests were weakened" | A clean `tamper_scan.py` run, or each finding explained |
| "It works" | What you ran and what you saw. "I read the code" is not "it works" |

If a skill from this set is not installed, do the equivalent by hand: run the real test
command, read the summary line, and look at `git diff` for deleted or skipped tests.

## Report structure

Use these headings in this order. Keep each short.

```
## Result
One or two sentences: what is now true, and whether it is verified.

## Verified
- What was checked, with the command and the result (e.g. "pytest -q: 42 passed, 0 failed, 0 skipped")

## Not verified
- What you did not or could not check, and why (needs a database, no network, no tests exist, ...)

## Changes to tests or test config
- Every test or config change, with the reason. Write "None" only if the scan was clean.

## Needs your decision
- Anything the user should look at: a test you think is wrong, a design choice, a risk.
```

Leave a section out only when it would be empty and the claim above it does not depend
on it. "Not verified" and "Changes to tests" are the sections people skip, and the ones
that matter most.

## Wording

- State numbers, not adjectives: "42 passed, 1 skipped", not "tests look good".
- Say "I could not run X because Y" rather than implying X was fine.
- Do not use "should work", "likely fixed" or "seems to pass" as a substitute for
  checking. If you are unsure, say what you are unsure about.
- If tests were failing before you started and still fail, say that and name them. A
  pre-existing failure you did not cause is not an excuse to say "all tests pass".
- If the task was only partly done, lead with that.

## When the honest answer is disappointing

Sometimes the true report is "I could not make this pass without changing the test,
and I do not think the test is right" or "this needs a service I cannot reach". Say it.
A short, accurate "not done, here is why and here is what I need" is more useful to the
user than a green-looking report they will have to unpick later.

## Example

Bad:

> Fixed the discount bug. All tests pass now.

Good:

> ## Result
> `apply_discount` now clamps the percentage to 0-100. The new test passes; one
> older test still fails (see below), so the suite is not green.
>
> ## Verified
> - `pytest -q`: 12 passed, 1 failed (`test_full_discount`), 0 skipped. Baseline before
>   my change was 11 passed, 1 failed, the same test.
>
> ## Not verified
> - Behaviour with currencies other than USD; there are no tests for it.
>
> ## Changes to tests or test config
> - Added `test_discount_over_100`. No existing test was modified.
>
> ## Needs your decision
> - `test_full_discount` expects 10 for a 100% discount, which contradicts the
>   docstring (should be 0). I left it unchanged; it still fails. Tell me if the test
>   or the docstring is right.

In the good version the suite is not fully green, and the report says so. Honest and
unfinished beats green and false.
