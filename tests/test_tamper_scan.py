import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "tamper_scan", ROOT / "skills" / "diff-vs-claim" / "scripts" / "tamper_scan.py"
)
ts = importlib.util.module_from_spec(spec)
sys.modules["tamper_scan"] = ts  # dataclasses needs the module to be registered
spec.loader.exec_module(ts)


def diff(path, removed=(), added=(), deleted=False):
    head = f"diff --git a/{path} b/{path}\n"
    if deleted:
        head += "deleted file mode 100644\n"
    head += f"--- a/{path}\n+++ b/{path}\n"
    body = "@@ -1,%d +1,%d @@\n" % (len(removed) or 1, len(added) or 1)
    body += "".join(f"-{ln}\n" for ln in removed) + "".join(f"+{ln}\n" for ln in added)
    return head + body


def kinds(text):
    return [f.kind for f in ts.scan(ts.parse_diff(text))]


class TamperScanTests(unittest.TestCase):
    def test_clean_source_change_has_no_findings(self):
        self.assertEqual(kinds(diff("src/app.py", ["return 1"], ["return 2"])), [])

    def test_deleted_test_file(self):
        self.assertIn("deleted-test-file", kinds(diff("tests/test_a.py", ["def test_x():"], [], deleted=True)))

    def test_deleting_non_test_file_is_fine(self):
        self.assertEqual(kinds(diff("src/old.py", ["x = 1"], [], deleted=True)), [])

    def test_removed_python_test(self):
        d = diff("tests/test_a.py", ["def test_discount_full():", "    assert f(1) == 2"], [])
        self.assertIn("removed-test", kinds(d))

    def test_renamed_test_is_not_removed(self):
        d = diff("tests/test_a.py", ["def test_old():"], ["def test_old():"])
        self.assertNotIn("removed-test", kinds(d))

    def test_removed_js_test(self):
        d = diff("src/a.test.ts", ["  it('handles empty input', () => {"], [])
        self.assertIn("removed-test", kinds(d))

    def test_removed_go_test(self):
        d = diff("pkg/a_test.go", ["func TestParse(t *testing.T) {"], [])
        self.assertIn("removed-test", kinds(d))

    def test_added_skip_variants(self):
        for line in [
            "@pytest.mark.skip(reason='flaky')",
            "    pytest.skip('later')",
            "@unittest.skip('no')",
            "it.skip('works', () => {})",
            "xit('works', () => {})",
            "    t.Skip(\"later\")",
            "#[ignore]",
            "@Disabled",
            "@pytest.mark.xfail",
        ]:
            with self.subTest(line=line):
                self.assertIn("added-skip", kinds(diff("tests/test_a.py", [], [line])))

    def test_skip_marker_in_source_file_is_ignored(self):
        self.assertEqual(kinds(diff("src/app.py", [], ["@pytest.mark.skip"])), [])

    def test_trivial_assertions(self):
        for line in ["    assert True", "    assert 1 == 1", "    assert x == y or True",
                     "    expect(true).toBe(true)", "    self.assertTrue(True)"]:
            with self.subTest(line=line):
                self.assertIn("trivial-assertion", kinds(diff("tests/test_a.py", [], [line])))

    def test_removed_assertions_net_negative(self):
        d = diff("tests/test_a.py", ["    assert a == 1", "    assert b == 2"], ["    assert a == 1"])
        self.assertIn("removed-assertions", kinds(d))

    def test_balanced_assertions_ok(self):
        d = diff("tests/test_a.py", ["    assert a == 1"], ["    assert a == 2"])
        self.assertNotIn("removed-assertions", kinds(d))

    def test_comment_lines_do_not_count_as_assertions(self):
        d = diff("tests/test_a.py", ["    assert a == 1"], ["    # assert a == 1"])
        self.assertIn("removed-assertions", kinds(d))

    def test_config_weakening(self):
        cases = [
            ("package.json", '"test": "jest || true"'),
            ("pytest.ini", "addopts = --ignore=tests/slow"),
            ("Makefile", "\t-pytest tests/"),
            (".github/workflows/ci.yml", "        continue-on-error: true"),
            ("jest.config.js", "  testPathIgnorePatterns: ['/integration/'],"),
            ("package.json", '"test": "jest --passWithNoTests"'),
        ]
        for path, line in cases:
            with self.subTest(path=path, line=line):
                self.assertIn("config-weakened", kinds(diff(path, [], [line])))

    def test_makefile_dash_rule_only_applies_to_makefiles(self):
        self.assertNotIn("config-weakened", kinds(diff("pyproject.toml", [], ["- pytest"])))

    def test_parse_line_numbers(self):
        text = "diff --git a/tests/test_a.py b/tests/test_a.py\n--- a/tests/test_a.py\n+++ b/tests/test_a.py\n@@ -10,0 +11,1 @@\n+    pytest.skip('x')\n"
        f = ts.scan(ts.parse_diff(text))[0]
        self.assertEqual((f.kind, f.line), ("added-skip", 11))


if __name__ == "__main__":
    unittest.main()
