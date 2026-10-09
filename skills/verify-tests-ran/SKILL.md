---
name: verify-tests-ran
description: Prove that tests actually ran before saying they pass. Use whenever you are about to tell the user that tests pass, CI is green, a fix works, a build is verified, or a task is done after you changed code. Also use before starting a change, to record how many tests exist. Catches "exit code 0 but zero tests ran", ignored failures, skipped tests, and a shrinking test count.
---

# Verify the tests really ran

An exit code of 0 is not evidence that tests passed. Wrong test paths, `|| true`,
a Makefile line starting with `-`, an empty collection and `--passWithNoTests` all
produce a "green" result with nothing executed. Saying "all tests pass" on that
basis is the most common false claim a coding agent makes, and the user finds out
later, at a worse moment.

This skill gives you a receipt you can point to instead of an impression.

## Before you change anything

Record the starting point so that a later drop in test count is visible:

```
python <this-skill-folder>/scripts/test_run_check.py --save-baseline -- <the project's test command>
```

Use the project's own command (`pytest -q`, `npm test`, `go test ./... -v`,
`cargo test`). If the suite is already red at this point, that is useful: note which
tests fail so you do not later claim credit for, or blame yourself for, them.

## After your changes

Run the same command through the script, without `--save-baseline`:

```
python <this-skill-folder>/scripts/test_run_check.py -- <the project's test command>
```

Read the verdict, not just the exit code:

| Verdict | What it means | What you may say |
|---|---|---|
| VERIFIED | Tests ran, none failed, count did not drop, skips did not rise | "N tests passed" with the number |
| FAILED | A test failed, or the command failed | Report the failure honestly and keep working or hand it back |
| SUSPICIOUS | Exit code looked fine but 0 tests ran, most were skipped, or the count dropped | Do not say "pass". Explain what looks wrong |
| UNVERIFIED | No recognisable test summary in the output | Say you could not verify, and say why |

SUSPICIOUS and UNVERIFIED are findings in their own right. When you see one, find the
cause (wrong path, swallowed exit status, deleted tests) before doing anything else.
Do not "fix" it by loosening the check.

## Before the final message

If you edited any file after the last run, the evidence is out of date. Check:

```
python <this-skill-folder>/scripts/test_run_check.py --check-receipt
```

`FRESH` means the code you are about to describe is the code that was tested. `STALE`
means run the tests again. A claim about code that changed afterwards is a guess.

## When the project has no tests, or they cannot run here

Say so plainly. "No test suite exists" and "the suite needs a database that is not
available here" are honest, useful results. Do not substitute a one-off script and call
it verification of the project's tests. If you wrote your own check, call it that.

## What the script does not do

It reads the framework's own summary (pytest, unittest, jest, vitest, go test, cargo
test). It cannot judge whether the tests are good, only whether they ran. Pair it with
`diff-vs-claim` to check that the tests were not weakened, and with `honest-report` for
the final message.
