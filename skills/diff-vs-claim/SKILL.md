---
name: diff-vs-claim
description: Check your own diff for weakened tests before you report success. Use after making a failing test pass, after fixing CI, after any edit that touched test files or test config, and before saying "done", "fixed" or "all green". Detects deleted tests, added skip/xfail markers, removed or trivial assertions, and test configs changed to ignore failures.
---

# Check the diff against what you are about to claim

There are two ways to turn a red test suite green. One fixes the code. The other
changes the tests, the test config or the CI settings until nothing can fail. Both
end with a green result; only the first is what the user wanted. When you are under
pressure to make something pass, the second path can look reasonable from the inside,
so do not rely on your own judgement in the moment. Look at the diff.

## Run the scan

From the repository root, after your edits and before your final message:

```
python <this-skill-folder>/scripts/tamper_scan.py
```

It compares the working tree to `HEAD` (use `--base <ref>` for another base, `--json`
for machine-readable output). It reports:

- `deleted-test-file`, `removed-test`: tests that no longer exist
- `added-skip`: skip, xfail, ignore or disabled markers
- `removed-assertions`, `trivial-assertion`: fewer checks, or checks that cannot fail
- `config-weakened`: `|| true`, `--ignore`, `--passWithNoTests`, `continue-on-error`,
  path ignore patterns, and similar settings that hide failures

Exit code 0 means nothing suspicious was found. Exit code 1 means there are findings.

## Handling a finding

A finding is a prompt to look, not a verdict. For each one, decide which of these is
true and act on it:

1. **It is a real weakening you made to get green.** Undo it and fix the code instead.
   If the code cannot be fixed within the task, stop and tell the user.
2. **It is legitimate.** For example, a test was removed together with the feature it
   covered, or a test was wrong and the spec says so. Keep the change, but say so in
   your final message: which test, what you changed, and why the old one was wrong.
3. **You are not sure.** Treat it as case 2 and let the user decide. They can say "fine"
   in one line; they cannot recover from a silent change.

Never edit a test merely because it fails. First work out whether the test or the code
is wrong. If the test contradicts the documented behaviour, that is worth telling the
user even when you are confident.

## Fix the cause, not the scanner

Do not rename tests, split an assertion, or move a skip into another file to make the
scan quiet. The scan exists to protect the user's trust, so a quieter scan with the
same weakened tests is worse than a loud one.

## Do not claim what the diff does not show

Before saying "I only changed X", compare with the diff. If the diff touches files you
did not mention, either explain them or revert them. Use `honest-report` to write the
final message and `verify-tests-ran` to prove the tests executed.
