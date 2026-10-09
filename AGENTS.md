# Working on done-receipt

- Scripts are standard library only. Do not add dependencies.
- Run the tests with `python -m unittest discover -s tests`. The eval grader tests need `pytest` installed.
- Every new heuristic in `tamper_scan.py` needs a positive test and a false-positive test.
- Every new framework parser in `test_run_check.py` needs a test using real output copied from that framework.
- Do not put numbers in the README that did not come from a run you can reproduce. Eval results go in `evals/README.md` with the number of runs.
- Skills should stay short. Explain why a rule matters instead of shouting it.
