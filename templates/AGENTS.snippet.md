## Proving "done" (done-receipt)

Before telling the user that work is finished, fixed, or passing:

1. Run the project's real test command through `test_run_check.py` and read the verdict, not just the exit code.
   An exit code of 0 with 0 tests executed is not a pass.
   - Before changing code: `python path/to/test_run_check.py --save-baseline -- <test command>`
   - After changing code: `python path/to/test_run_check.py -- <test command>`
   - Right before the final message: `python path/to/test_run_check.py --check-receipt` (must say FRESH)
2. Run `python path/to/tamper_scan.py`. Undo any test weakening you made to get green. Explain every
   remaining finding to the user.
3. Write the final message with these headings: Result, Verified, Not verified, Changes to tests or
   test config, Needs your decision. State numbers ("42 passed, 1 skipped"), not adjectives.
   Never claim a pass you did not observe in this session, and never edit a test only because it fails.
