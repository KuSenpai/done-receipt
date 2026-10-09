import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "verify-tests-ran" / "scripts" / "test_run_check.py"
spec = importlib.util.spec_from_file_location("test_run_check", SCRIPT)
trc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trc)


class ParserTests(unittest.TestCase):
    def test_pytest_summary(self):
        _, c = trc.parse_output("....\n3 passed, 1 skipped in 0.12s\n")
        self.assertEqual((c["passed"], c["skipped"], c["total"]), (3, 1, 4))

    def test_pytest_failures_and_errors(self):
        _, c = trc.parse_output("=== 2 failed, 5 passed, 1 error in 1.20s ===\n")
        self.assertEqual((c["failed"], c["passed"], c["errors"], c["total"]), (2, 5, 1, 8))

    def test_pytest_no_tests_ran(self):
        name, c = trc.parse_output("============ no tests ran in 0.01s ============\n")
        self.assertEqual((name, c["total"]), ("pytest", 0))

    def test_unittest(self):
        _, c = trc.parse_output("Ran 5 tests in 0.001s\n\nFAILED (failures=1, skipped=1)\n")
        self.assertEqual((c["total"], c["failed"], c["skipped"], c["passed"]), (5, 1, 1, 3))

    def test_unittest_zero(self):
        _, c = trc.parse_output("Ran 0 tests in 0.000s\n\nNO TESTS RAN\n")
        self.assertEqual(c["total"], 0)

    def test_jest(self):
        _, c = trc.parse_output("Tests:       1 failed, 2 passed, 3 total\n")
        self.assertEqual((c["failed"], c["passed"], c["total"]), (1, 2, 3))

    def test_vitest(self):
        _, c = trc.parse_output("      Tests  2 passed | 1 skipped (3)\n")
        self.assertEqual((c["passed"], c["skipped"], c["total"]), (2, 1, 3))

    def test_cargo_sums_binaries(self):
        out = "test result: ok. 3 passed; 0 failed; 1 ignored; 0 measured\ntest result: ok. 2 passed; 0 failed; 0 ignored; 0 measured\n"
        _, c = trc.parse_output(out)
        self.assertEqual((c["passed"], c["skipped"], c["total"]), (5, 1, 6))

    def test_go_verbose(self):
        _, c = trc.parse_output("--- PASS: TestA (0.00s)\n--- FAIL: TestB (0.00s)\n--- SKIP: TestC (0.00s)\n")
        self.assertEqual((c["passed"], c["failed"], c["skipped"]), (1, 1, 1))

    def test_unparseable(self):
        self.assertIsNone(trc.parse_output("hello world\nall done\n"))


class JudgeTests(unittest.TestCase):
    def c(self, **kw):
        base = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "total": 0}
        base.update(kw)
        if "total" not in kw:
            base["total"] = base["passed"] + base["failed"] + base["skipped"] + base["errors"]
        return base

    def test_verified(self):
        v, _ = trc.judge(0, "pytest", self.c(passed=4), None, 0.2)
        self.assertEqual(v, "VERIFIED")

    def test_zero_tests_with_exit_zero_is_suspicious(self):
        v, r = trc.judge(0, "pytest", self.c(), None, 0.2)
        self.assertEqual(v, "SUSPICIOUS")
        self.assertIn("0 tests ran", r[0])

    def test_failed(self):
        v, _ = trc.judge(1, "pytest", self.c(passed=3, failed=1), None, 0.2)
        self.assertEqual(v, "FAILED")

    def test_all_skipped(self):
        v, _ = trc.judge(0, "pytest", self.c(skipped=4), None, 0.2)
        self.assertEqual(v, "SUSPICIOUS")

    def test_high_skip_ratio(self):
        v, _ = trc.judge(0, "pytest", self.c(passed=2, skipped=3), None, 0.2)
        self.assertEqual(v, "SUSPICIOUS")

    def test_count_dropped_below_baseline(self):
        baseline = {"counts": self.c(passed=10)}
        v, r = trc.judge(0, "pytest", self.c(passed=8), baseline, 0.2)
        self.assertEqual(v, "SUSPICIOUS")
        self.assertTrue(any("dropped" in x for x in r))

    def test_skips_rose_above_baseline(self):
        baseline = {"counts": self.c(passed=10)}
        v, _ = trc.judge(0, "pytest", self.c(passed=10, skipped=1), baseline, 0.2)
        self.assertEqual(v, "SUSPICIOUS")

    def test_unparsed_exit_zero_is_unverified(self):
        v, _ = trc.judge(0, None, None, None, 0.2)
        self.assertEqual(v, "UNVERIFIED")

    def test_unparsed_nonzero_is_failed(self):
        v, _ = trc.judge(3, None, None, None, 0.2)
        self.assertEqual(v, "FAILED")


class EndToEndTests(unittest.TestCase):
    """Run the real script in a throwaway git repo."""

    def run_script(self, cwd, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)

    def make_repo(self, tmp, test_body):
        def git(*a):
            subprocess.run(["git", *a], cwd=tmp, check=True, capture_output=True)
        git("init", "-q")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "t")
        (pathlib.Path(tmp) / "test_sample.py").write_text(textwrap.dedent(test_body))
        git("add", "-A")
        git("commit", "-q", "-m", "init")

    def test_verified_then_stale_after_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_repo(tmp, """
                import unittest
                class T(unittest.TestCase):
                    def test_a(self): self.assertEqual(1, 1)
                    def test_b(self): self.assertEqual(2, 2)
            """)
            r = self.run_script(tmp, "--save-baseline", "--", sys.executable, "-m", "unittest", "-q")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("VERDICT: VERIFIED", r.stdout)
            fresh = self.run_script(tmp, "--check-receipt")
            self.assertEqual(fresh.returncode, 0, fresh.stdout)
            self.assertIn("FRESH", fresh.stdout)
            (pathlib.Path(tmp) / "new.py").write_text("x = 1\n")
            stale = self.run_script(tmp, "--check-receipt")
            self.assertEqual(stale.returncode, 1)
            self.assertIn("STALE", stale.stdout)

    def test_empty_suite_is_not_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_repo(tmp, "x = 1\n")
            r = self.run_script(tmp, "--", sys.executable, "-m", "unittest", "-q")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("0 tests ran", r.stdout)

    def test_exit_zero_but_nothing_ran_is_suspicious(self):
        # A wrapper that swallows the failure: exit 0, yet the summary says 0 tests.
        with tempfile.TemporaryDirectory() as tmp:
            self.make_repo(tmp, "x = 1\n")
            r = self.run_script(tmp, "--", sys.executable, "-c", "print('Ran 0 tests in 0.000s')")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("VERDICT: SUSPICIOUS", r.stdout)

    def test_exit_zero_without_summary_is_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_repo(tmp, "x = 1\n")
            r = self.run_script(tmp, "--", sys.executable, "-c", "print('tests done')")
            self.assertEqual(r.returncode, 1)
            self.assertIn("VERDICT: UNVERIFIED", r.stdout)

    def test_dropped_test_count_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_repo(tmp, """
                import unittest
                class T(unittest.TestCase):
                    def test_a(self): pass
                    def test_b(self): pass
            """)
            self.run_script(tmp, "--save-baseline", "--", sys.executable, "-m", "unittest", "-q")
            (pathlib.Path(tmp) / "test_sample.py").write_text(textwrap.dedent("""
                import unittest
                class T(unittest.TestCase):
                    def test_a(self): pass
            """))
            r = self.run_script(tmp, "--", sys.executable, "-m", "unittest", "-q")
            self.assertEqual(r.returncode, 1)
            self.assertIn("dropped from 2", r.stdout)

    def test_receipts_do_not_dirty_the_working_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_repo(tmp, """
                import unittest
                class T(unittest.TestCase):
                    def test_a(self): pass
            """)
            self.run_script(tmp, "--save-baseline", "--", sys.executable, "-m", "unittest", "-q")
            status = subprocess.run(["git", "status", "--porcelain"], cwd=tmp, capture_output=True, text=True).stdout
            self.assertNotIn("done-receipt", status)
            self.assertTrue((pathlib.Path(tmp) / ".git" / "done-receipt" / "last-run.json").exists())

    def test_receipt_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.make_repo(tmp, "x = 1\n")
            r = self.run_script(tmp, "--check-receipt")
            self.assertEqual(r.returncode, 1)
            self.assertIn("No receipt", r.stdout)

    def test_command_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_script(tmp, "--", "definitely-not-a-real-command-xyz")
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
