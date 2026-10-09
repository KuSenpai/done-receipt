import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "stop_gate.py"
CHECK = ROOT / "skills" / "verify-tests-ran" / "scripts" / "test_run_check.py"

CLAIM = "Fixed the bug. All tests pass."
TEST_BODY = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): self.assertEqual(1, {})\n"


class StopGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
            subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)
        self.write_test(1)
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=self.repo, check=True, capture_output=True)

    def tearDown(self):
        self._tmp.cleanup()

    def write_test(self, expected):
        (pathlib.Path(self.repo) / "test_sample.py").write_text(TEST_BODY.format(expected))

    def run_tests(self):
        subprocess.run([sys.executable, str(CHECK), "--", sys.executable, "-m", "unittest", "-q"],
                       cwd=self.repo, capture_output=True, text=True)

    def hook(self, message=CLAIM, raw=None, env=None, **extra):
        payload = raw if raw is not None else json.dumps(
            {"hook_event_name": "Stop", "cwd": self.repo, "stop_hook_active": False,
             "last_assistant_message": message, **extra})
        r = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True,
                           env={**os.environ, "DONE_RECEIPT_STOP_HOOK": "", **(env or {})})
        self.assertEqual(r.returncode, 0, r.stderr)  # never exit 2, never crash the stop
        return json.loads(r.stdout) if r.stdout.strip() else None

    def test_claim_with_fresh_verified_receipt_is_allowed(self):
        self.run_tests()
        self.assertIsNone(self.hook())

    def test_claim_without_receipt_is_blocked(self):
        out = self.hook()
        self.assertEqual(out["decision"], "block")
        self.assertIn("No receipt", out["reason"])

    def test_claim_with_failed_receipt_is_blocked(self):
        self.write_test(2)
        self.run_tests()
        out = self.hook()
        self.assertEqual(out["decision"], "block")
        self.assertIn("FAILED", out["reason"])

    def test_claim_with_stale_receipt_is_blocked(self):
        self.run_tests()
        (pathlib.Path(self.repo) / "app.py").write_text("x = 1\n")
        out = self.hook()
        self.assertEqual(out["decision"], "block")
        self.assertIn("STALE", out["reason"])

    def test_honest_failure_report_is_not_blocked(self):
        # false-positive guard: a failing receipt is fine when the message does not claim success
        self.write_test(2)
        self.run_tests()
        self.assertIsNone(self.hook("test_a still fails; I did not change the test. Tests did not pass."))

    def test_blocks_only_once(self):
        self.assertIsNone(self.hook(stop_hook_active=True))

    def test_off_switch(self):
        self.assertIsNone(self.hook(env={"DONE_RECEIPT_STOP_HOOK": "off"}))

    def test_fails_open_on_bad_input(self):
        self.assertIsNone(self.hook(raw="not json"))

    def test_missing_message_field_is_allowed(self):
        self.assertIsNone(self.hook(raw=json.dumps({"cwd": self.repo})))


if __name__ == "__main__":
    unittest.main()
