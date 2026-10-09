# done-receipt

**Check a coding agent's "done" against the repo.** Two zero-dependency scripts, a Claude Code `Stop` hook and three small skills that look for evidence behind *"fixed, all tests pass"* before you believe it.

An agent that says *"fixed, all tests pass"* may have done one of these instead:

- run a command that exited `0` but executed **zero tests** (`|| true`, a Makefile `-` prefix, a wrong path)
- turned the red test green by **editing the test** (a skip marker, `assert True`, a deleted case, a weaker config)
- reported results from **before its last edit**

The scripts detect the common forms of all three (see [Limitations](#limitations) for what they miss), and the skills ask the agent to report what it did and did not verify. Whether that makes agents more honest is measured below: so far, it does not.

## What is inside

| Skill | What it does | Ships a script |
|---|---|---|
| `verify-tests-ran` | Runs your test command, parses the framework's own summary, and gives a verdict: `VERIFIED`, `FAILED`, `SUSPICIOUS` (0 tests ran, mostly skipped, count dropped) or `UNVERIFIED`. Writes a receipt and can tell whether it is still `FRESH` or has gone `STALE`. | `test_run_check.py` |
| `diff-vs-claim` | Scans your diff for deleted tests, added skip/xfail markers, removed or trivial assertions, and test config changed to hide failures. | `tamper_scan.py` |
| `honest-report` | A report format: Result, Verified, Not verified, Changes to tests, Needs your decision. Every success claim needs evidence from this session. | none |

Plus a `Stop` hook ([below](#stop-hook-enforcement-optional)) that blocks a "tests pass" message when there is no valid receipt.

Python 3.10+ and `git` (unit tests pass on 3.10, 3.11, 3.12 and 3.13; the eval-grader tests need `pytest` and were run on 3.10 to 3.12). No packages to install. Supported test summaries: pytest, unittest, jest, vitest, go test, cargo test.

## See it work

Take the `contradictory-test` eval repo (`python evals/run_eval.py setup contradictory-test <dir>`), "fix" the red test the lazy way (skip it, replace its assertion with `assert True`, add `--ignore` to `pytest.ini`), and run `tamper_scan.py`:

```
tamper_scan: 3 finding(s). Each one must be justified or reported to the user.

  [config-weakened] pytest.ini:4
      --ignore excludes tests from the run
      > addopts = --ignore=tests/slow
  [added-skip] tests/test_pricing.py:10
      skip/xfail/ignore marker added
      > @pytest.mark.skip(reason='later')
  [trivial-assertion] tests/test_pricing.py:12
      assertion that cannot fail
      > assert True
```

And `test_run_check.py` on a "green" run that executed nothing:

```
unittest: 0 passed, 0 failed, 0 skipped, 0 errors (0 total)
VERDICT: SUSPICIOUS
  - 0 tests ran (exit code was 0, but nothing was executed)
```

## Install

**As a Claude Code plugin** (loads the skills and the Stop hook; the skills are offered to the agent, which does not always use them, see the results below):

```
/plugin marketplace add KuSenpai/done-receipt
/plugin install done-receipt@done-receipt
```

To try it without a marketplace, load a local clone for one session: `claude --plugin-dir path/to/done-receipt` (this is how the evals load it).

**Manually**, for any setup that reads `SKILL.md` folders:

```
git clone https://github.com/KuSenpai/done-receipt
cp -r done-receipt/skills/* ~/.claude/skills/        # all projects
# or: cp -r done-receipt/skills/* your-project/.claude/skills/
```

**Other agents (Codex, Cursor, Copilot, ...)**: paste [`templates/AGENTS.snippet.md`](templates/AGENTS.snippet.md) into your `AGENTS.md` and copy the two scripts somewhere the agent can run them. The scripts are plain Python and need nothing from Claude.

## Use the scripts without any agent

```bash
# before work: how many tests exist today?
python skills/verify-tests-ran/scripts/test_run_check.py --save-baseline -- pytest -q

# after work
python skills/verify-tests-ran/scripts/test_run_check.py -- pytest -q
python skills/verify-tests-ran/scripts/test_run_check.py --check-receipt   # FRESH or STALE?

# did the diff weaken any tests?
python skills/diff-vs-claim/scripts/tamper_scan.py            # vs HEAD
python skills/diff-vs-claim/scripts/tamper_scan.py --base main --json
```

Exit code is `0` only when the result is clean, so both fit into a pre-commit hook or a CI step. Receipts are stored inside `.git/done-receipt/`, so they never show up in `git status`.

## Stop hook (enforcement, optional)

The plugin ships a Claude Code `Stop` hook, [`hooks/stop_gate.py`](hooks/stop_gate.py). When the agent's final message claims the tests pass ("all tests pass", "suite is green", ...) and the latest receipt is missing, not `VERIFIED`, or `STALE`, the hook blocks the stop once and tells the agent to re-run the tests or drop the claim. Messages without a success claim are never blocked.

- **Fails open.** Any error in the hook lets Claude stop. It blocks at most once per stop (`stop_hook_active`), so it cannot trap you in a loop.
- **Off switch:** set `DONE_RECEIPT_STOP_HOOK=off` in the environment (for example in `.claude/settings.json` under `"env"`), or disable the plugin.
- Needs a Claude Code version that sends `last_assistant_message` to `Stop` hooks; on older versions the hook does nothing.
- Claim detection is a regex (the same one the eval grader uses), so it can miss unusual wording or flag a sentence that is not really a claim. In the evals it blocked 2 honest reports ("13 of 14 tests now pass"); that pattern is fixed.
- It checks that tests ran, not that they still test anything. In the evals it did not stop a single dishonest run: agents that had mocked away a failing test re-ran the suite, got `VERIFIED`, and said "done" again.
- The plugin command tries `python3`, then `python` (on Windows, `python3` is often a Microsoft Store stub).

Manual install (without the plugin), in `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{ "hooks": [{ "type": "command", "command": "python /path/to/done-receipt/hooks/stop_gate.py" }] }]
  }
}
```

## Does it make agents more honest? Not so far

Measured with the harness in [`evals/`](evals/README.md): 3 scenarios built to make a false "done" tempting (many failing tests, a deadline with "just reply done", a long multi-file task that conflicts with a frozen test), 5 runs per cell, one model (`claude-sonnet-4-6`), with and without the plugin (skills + Stop hook). Every report was also read by hand.

| | Without plugin | With plugin |
|---|---|---|
| Honest reports, read by hand | 10/15 | 10/15 |
| Honest reports, automatic grader | 9/15 | 10/15 |

- **No difference in honesty.** Both conditions failed the same scenario: under deadline pressure, 10 of 10 runs mocked away a test that needed an unreachable database and replied "done" without saying so. The plugin did not catch it, and in one run the checker's `SUSPICIOUS` verdict on a *skipped* test led the agent to mock it instead.
- **Some difference in behaviour, small counts.** With the plugin, 2 of 5 runs left a contradictory test red and asked which rule wins (0 of 5 without), and 2 of 5 reports on the multi-file task mentioned the ERP contract the change breaks (0 of 5 without).
- **Most of the plugin's activity came from the hook, not the skills.** The skills were invoked in 5 of 15 runs; the receipt check ran in 15 of 15, mostly because the Stop hook demanded it.

An earlier pilot (3 easier scenarios, 1 run each) found the agent already honest without the plugin. Details, limits and every report are in [`evals/README.md`](evals/README.md).

So treat the **scripts** as the tested part (79 unit tests, end-to-end ones in throwaway git repos), and the skills and hook as **unproven**: they change how the agent reports, not, so far, whether it tells the truth.

## Limitations

- The scan is heuristic. A finding means "look at this", not "this is wrong". A test can be legitimately removed with the feature it covered.
- It can be bypassed by an agent determined to hide changes (for example, moving a skip into a helper). It is a safety net for the common cases, not a security boundary.
- **It does not flag a test whose dependency was mocked away** (`unittest.mock.patch` around the thing under test). This is the failure the evals actually found; see the roadmap.
- `test_run_check.py` proves tests ran, not that they are good tests.
- Go without `-v` reports packages, not individual tests.
- Not yet covered: Maven/Gradle, RSpec, .NET test summaries.

## Roadmap

- v0.2: a `tamper_scan.py` finding for mocks added around the code under test, with a positive and a false-positive test, then a re-run of the `deadline` eval
- Evals on more models and more runs per cell, with scenarios written by someone other than the author
- More framework parsers
- A GitHub Action that runs `tamper_scan.py` on pull requests

## Contributing

Issues and PRs are welcome, especially: a test framework whose summary is not parsed, a tampering pattern the scan misses, or a false positive. Run the tests with `python -m unittest discover -s tests` (the eval grader tests also need `pytest`).

## License

MIT
