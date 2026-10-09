#!/usr/bin/env python3
"""tamper_scan: look for signs that tests were weakened instead of code being fixed.

Reads a git diff and reports patterns that often show up when an agent makes a
red test suite green by changing the tests rather than the code:

  deleted-test-file     a test file was removed
  removed-test          a test function/case disappeared (and did not reappear)
  added-skip            a skip / xfail / ignore marker was added
  removed-assertions    a test file has fewer assertions than before
  trivial-assertion     an assertion that cannot fail (assert True, 1 == 1, ...)
  config-weakened       test config or CI changed so failures are ignored or
                        tests are excluded

These are heuristics. A finding means "look at this", not "this is wrong":
a test may be legitimately removed along with the feature it covered. The point
is that every finding must be either justified or reported to the user.

Standard library only. Usage:

  python tamper_scan.py                 # working tree vs HEAD
  python tamper_scan.py --base main     # working tree vs another ref
  python tamper_scan.py --diff-file x.patch
  python tamper_scan.py --json

Exit code: 0 = no findings, 1 = findings, 2 = could not read the diff.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field

TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|specs?)(/|$)"
    r"|(^|/)test_[^/]*\.py$"
    r"|_test\.(py|go|rb|rs)$"
    r"|\.(test|spec)\.[cm]?[jt]sx?$"
    r"|(^|/)[^/]*Tests?\.(java|kt|cs|swift)$"
    r"|_spec\.rb$"
)

CONFIG_PATH = re.compile(
    r"(^|/)(pytest\.ini|tox\.ini|setup\.cfg|pyproject\.toml|conftest\.py|Makefile|"
    r"package\.json|jest\.config\.[cm]?[jt]s|vitest\.config\.[cm]?[jt]s|"
    r"Cargo\.toml|\.coveragerc|noxfile\.py|justfile)$"
    r"|(^|/)\.github/workflows/[^/]+\.ya?ml$"
    r"|(^|/)\.gitlab-ci\.ya?ml$"
)

SKIP_ADDED = [
    r"@pytest\.mark\.(skip|skipif|xfail)\b",
    r"\bpytest\.(skip|xfail)\s*\(",
    r"@unittest\.(skip|skipIf|skipUnless|expectedFailure)\b",
    r"\bself\.skipTest\s*\(",
    r"\b(it|test|describe)\.(skip|todo|failing)\b",
    r"\b(xit|xtest|xdescribe)\s*\(",
    r"\bt\.Skip(f|Now)?\s*\(",
    r"#\[ignore\]",
    r"@Disabled\b",
    r"@Ignore\b",
    r"\bskip\s+['\"]",  # rspec/minitest style
    r"\bpending\s*\(",
]

TRIVIAL_ASSERT = [
    r"\bassert\s+True\b",
    r"\bassert\s+(\d+)\s*==\s*\1\b",
    r"\bassert\s+.+\s+or\s+True\b",
    r"\bassertTrue\(\s*(True|true|1)\s*\)",
    r"expect\(\s*true\s*\)\s*\.toBe(Truthy)?\(\s*(true)?\s*\)",
    r"expect\(\s*(\d+)\s*\)\s*\.toBe\(\s*\1\s*\)",
    r"\bassert\s+not\s+False\b",
]

ASSERT_LINE = re.compile(
    r"\bassert\b|\bassert[A-Z_]\w*\s*\(|\bexpect\s*\(|\.should\b|\bt\.(Error|Errorf|Fatal|Fatalf)\s*\("
    r"|\bassert_(eq|ne|matches)!\s*\(|\brequire\.\w+\s*\(|\bpytest\.raises\b"
)

CONFIG_WEAKENING = [
    (r"\|\|\s*true\b", "command now ignores a non-zero exit status (|| true)"),
    (r"^\s*-\s*(pytest|python|npm|npx|go|cargo|jest|vitest)\b", "Makefile '-' prefix ignores failures"),
    (r"--passWithNoTests", "--passWithNoTests lets an empty test run succeed"),
    (r"--ignore[= ]", "--ignore excludes tests from the run"),
    (r"--deselect\b", "--deselect excludes tests from the run"),
    (r"-k\s+['\"]?not\s", "-k 'not ...' deselects tests"),
    (r"testPathIgnorePatterns|testIgnore|modulePathIgnorePatterns", "test path ignore pattern added"),
    (r"\bnorecursedirs\b|\bcollect_ignore", "pytest collection exclusion added"),
    (r"continue-on-error:\s*true", "CI step is allowed to fail"),
    (r"fail_under\s*=\s*\d", "coverage threshold changed"),
    (r"--no-fail-fast\b|--exit-zero\b|--suppress-exit-code\b", "exit status suppressed"),
    (r"\bif:\s*false\b", "CI step disabled with 'if: false'"),
]

PY_TEST_NAME = re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)\s*\(")
JS_TEST_NAME = re.compile(r"""\b(?:it|test)\s*\(\s*(['"`])(.+?)\1""")
GO_TEST_NAME = re.compile(r"^\s*func\s+(Test\w+)\s*\(")
RB_TEST_NAME = re.compile(r"""^\s*(?:it|specify|test)\s+(['"])(.+?)\1""")
RUST_TEST_NAME = re.compile(r"^\s*(?:async\s+)?fn\s+(\w+)\s*\(")
ATTR_TEST = re.compile(r"^\s*(?:@Test\b|#\[test\]|\[Fact\]|\[Test\])")


@dataclass
class Finding:
    kind: str
    file: str
    detail: str
    line: int | None = None
    evidence: str | None = None


@dataclass
class FileChange:
    path: str
    deleted: bool = False
    added: list[tuple[int, str]] = field(default_factory=list)
    removed: list[tuple[int, str]] = field(default_factory=list)


def is_test_path(path: str) -> bool:
    return bool(TEST_PATH.search(path))


def parse_diff(text: str) -> list[FileChange]:
    """Parse `git diff -U0` output into per-file added/removed lines."""
    files: list[FileChange] = []
    cur: FileChange | None = None
    old_no = new_no = 0
    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*?) b/(.*)$", raw)
            path = m.group(2) if m else raw
            cur = FileChange(path=path)
            files.append(cur)
            continue
        if cur is None:
            continue
        if raw.startswith("deleted file mode"):
            cur.deleted = True
        elif raw.startswith("--- "):
            if raw.startswith("--- a/"):
                cur.path = cur.path or raw[6:]
        elif raw.startswith("+++ "):
            if raw.startswith("+++ b/"):
                cur.path = raw[6:]
        elif raw.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
            if m:
                old_no, new_no = int(m.group(1)), int(m.group(2))
        elif raw.startswith("+") and not raw.startswith("+++"):
            cur.added.append((new_no, raw[1:]))
            new_no += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            cur.removed.append((old_no, raw[1:]))
            old_no += 1
    return files


def test_names(line: str) -> list[str]:
    names: list[str] = []
    for pat, grp in (
        (PY_TEST_NAME, 1),
        (GO_TEST_NAME, 1),
    ):
        m = pat.match(line)
        if m:
            names.append(m.group(grp))
    for m in JS_TEST_NAME.finditer(line):
        names.append(m.group(2))
    m = RB_TEST_NAME.match(line)
    if m:
        names.append(m.group(2))
    return names


def count_asserts(lines: list[tuple[int, str]]) -> int:
    n = 0
    for _, text in lines:
        stripped = text.strip()
        if stripped.startswith(("#", "//", "*", "/*")):
            continue
        if ASSERT_LINE.search(text):
            n += 1
    return n


def scan(changes: list[FileChange]) -> list[Finding]:
    findings: list[Finding] = []

    removed_names: dict[str, tuple[str, int]] = {}
    added_names: set[str] = set()
    attr_removed = attr_added = 0
    attr_removed_file = ""

    for ch in changes:
        test_file = is_test_path(ch.path)

        if ch.deleted and test_file:
            findings.append(Finding("deleted-test-file", ch.path, "test file was deleted"))

        if test_file:
            for no, text in ch.removed:
                for name in test_names(text):
                    removed_names.setdefault(name, (ch.path, no))
                if ATTR_TEST.match(text):
                    attr_removed += 1
                    attr_removed_file = attr_removed_file or ch.path
            for _, text in ch.added:
                for name in test_names(text):
                    added_names.add(name)
                if ATTR_TEST.match(text):
                    attr_added += 1

            for no, text in ch.added:
                for pat in SKIP_ADDED:
                    if re.search(pat, text):
                        findings.append(Finding("added-skip", ch.path, "skip/xfail/ignore marker added", no, text.strip()))
                        break
                for pat in TRIVIAL_ASSERT:
                    if re.search(pat, text):
                        findings.append(Finding("trivial-assertion", ch.path, "assertion that cannot fail", no, text.strip()))
                        break

            if not ch.deleted:
                removed_a = count_asserts(ch.removed)
                added_a = count_asserts(ch.added)
                if removed_a > added_a:
                    findings.append(
                        Finding(
                            "removed-assertions",
                            ch.path,
                            f"{removed_a} assertion line(s) removed, {added_a} added (net {added_a - removed_a:+d})",
                        )
                    )

        if CONFIG_PATH.search(ch.path):
            for no, text in ch.added:
                for pat, why in CONFIG_WEAKENING:
                    if why.startswith("Makefile") and not ch.path.endswith(("Makefile", "justfile")):
                        continue
                    if re.search(pat, text):
                        findings.append(Finding("config-weakened", ch.path, why, no, text.strip()))
                        break

    for name, (path, no) in removed_names.items():
        if name not in added_names:
            findings.append(Finding("removed-test", path, f"test '{name}' no longer exists", no))
    if attr_removed > attr_added:
        findings.append(
            Finding(
                "removed-test",
                attr_removed_file,
                f"{attr_removed - attr_added} more test attribute(s) removed than added (@Test / #[test] / [Fact])",
            )
        )

    return findings


def git_diff(base: str, staged_only: bool) -> str:
    cmd = ["git", "diff", "-U0", "--no-color"]
    if staged_only:
        cmd.append("--cached")
    else:
        cmd.append(base)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise SystemExit("git is not installed or not on PATH")
    if res.returncode != 0:
        raise SystemExit(f"git diff failed: {res.stderr.strip()}")
    diff = res.stdout

    # Brand-new untracked files are invisible to `git diff`; they cannot weaken
    # existing tests, but a new conftest.py or config file can. Include them.
    if not staged_only:
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        for path in untracked:
            if CONFIG_PATH.search(path) or is_test_path(path):
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        body = fh.read().splitlines()
                except OSError:
                    continue
                diff += f"\ndiff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n"
                diff += f"@@ -0,0 +1,{len(body)} @@\n" + "\n".join("+" + ln for ln in body) + "\n"
    return diff


def format_text(findings: list[Finding]) -> str:
    if not findings:
        return "tamper_scan: no suspicious test changes found.\n"
    out = [f"tamper_scan: {len(findings)} finding(s). Each one must be justified or reported to the user.\n"]
    for f in findings:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        out.append(f"  [{f.kind}] {loc}\n      {f.detail}")
        if f.evidence:
            out.append(f"      > {f.evidence}")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="HEAD", help="ref to diff the working tree against (default: HEAD)")
    ap.add_argument("--staged", action="store_true", help="only look at staged changes")
    ap.add_argument("--diff-file", help="read a unified diff from this file instead of running git")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.diff_file:
        try:
            with open(args.diff_file, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as exc:
            print(f"cannot read {args.diff_file}: {exc}", file=sys.stderr)
            return 2
    else:
        try:
            text = git_diff(args.base, args.staged)
        except SystemExit as exc:
            print(exc, file=sys.stderr)
            return 2

    findings = scan(parse_diff(text))
    if args.json:
        print(json.dumps({"findings": [asdict(f) for f in findings], "count": len(findings)}, indent=2))
    else:
        sys.stdout.write(format_text(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
