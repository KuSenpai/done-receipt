#!/usr/bin/env python3
"""test_run_check: run a test command and prove that tests actually ran.

"Exit code 0" is not evidence that tests passed. A misconfigured path, an
ignored failure (`|| true`, a Makefile `-` prefix), or a typo in a test
directory can all produce exit code 0 with zero tests executed. This script
runs the command, parses the framework's own summary, and writes a receipt
that a final report can cite.

Usage:

  # before you change anything: record how many tests exist today
  python test_run_check.py --save-baseline -- pytest -q

  # after your changes
  python test_run_check.py -- pytest -q

  # right before you tell the user "tests pass": is the receipt still valid?
  python test_run_check.py --check-receipt

Verdicts:
  VERIFIED     tests ran, none failed, count did not drop below baseline
  FAILED       the command failed or tests failed
  SUSPICIOUS   exit code looked fine but something is off (no tests ran,
               many skipped, fewer tests than baseline)
  UNVERIFIED   output could not be parsed, so nothing can be claimed

Exit code: 0 only for VERIFIED. 1 for FAILED/SUSPICIOUS/UNVERIFIED. 2 for usage errors.
Supported summaries: pytest, unittest, jest, vitest, go test, cargo test.
Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

def _receipt_dir() -> str:
    """Keep receipts inside .git when possible so they never show up in `git status`
    or end up in a commit. Outside a git repo, fall back to ./.done-receipt."""
    try:
        res = subprocess.run(["git", "rev-parse", "--git-dir"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        res = None
    if res is not None and res.returncode == 0 and res.stdout.strip():
        return os.path.join(res.stdout.strip(), "done-receipt")
    return ".done-receipt"


RECEIPT_DIR = _receipt_dir()
LAST = os.path.join(RECEIPT_DIR, "last-run.json")
BASELINE = os.path.join(RECEIPT_DIR, "baseline.json")

PYTEST_TOKEN = re.compile(
    r"(\d+)\s+(passed|failed|skipped|xfailed|xpassed|errors?|deselected|warnings?|rerun)\b"
)


def _blank() -> dict[str, int]:
    return {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "total": 0}


def parse_pytest(text: str) -> dict[str, int] | None:
    if "no tests ran" in text:
        return _blank()
    candidates = [ln for ln in text.splitlines() if PYTEST_TOKEN.search(ln) and re.search(r"\bin\s+[\d.]+s", ln)]
    if not candidates:
        return None
    counts = _blank()
    for num, word in PYTEST_TOKEN.findall(candidates[-1]):
        n = int(num)
        if word == "passed":
            counts["passed"] += n
        elif word == "failed":
            counts["failed"] += n
        elif word in ("skipped", "xfailed"):
            counts["skipped"] += n
        elif word == "xpassed":
            counts["passed"] += n
        elif word.startswith("error"):
            counts["errors"] += n
    counts["total"] = counts["passed"] + counts["failed"] + counts["skipped"] + counts["errors"]
    return counts


def parse_unittest(text: str) -> dict[str, int] | None:
    m = re.search(r"^Ran (\d+) tests? in", text, re.M)
    if not m:
        return None
    total = int(m.group(1))
    counts = _blank()
    counts["total"] = total
    tail = text[m.end():]
    for key, word in (("failed", "failures"), ("errors", "errors"), ("skipped", "skipped")):
        mm = re.search(rf"{word}=(\d+)", tail)
        if mm:
            counts[key] = int(mm.group(1))
    counts["passed"] = max(total - counts["failed"] - counts["errors"] - counts["skipped"], 0)
    return counts


def parse_jest(text: str) -> dict[str, int] | None:
    m = re.search(r"^\s*Tests:\s+(.*)$", text, re.M)
    if m:
        counts = _blank()
        for num, word in re.findall(r"(\d+)\s+(passed|failed|skipped|todo|total)", m.group(1)):
            n = int(num)
            if word == "total":
                counts["total"] = n
            elif word == "passed":
                counts["passed"] = n
            elif word == "failed":
                counts["failed"] = n
            else:
                counts["skipped"] += n
        return counts
    m = re.search(r"^\s*Tests\s+(.*?)\((\d+)\)\s*$", text, re.M)  # vitest
    if m:
        counts = _blank()
        for num, word in re.findall(r"(\d+)\s+(passed|failed|skipped|todo)", m.group(1)):
            n = int(num)
            if word == "passed":
                counts["passed"] = n
            elif word == "failed":
                counts["failed"] = n
            else:
                counts["skipped"] += n
        counts["total"] = int(m.group(2))
        return counts
    return None


def parse_cargo(text: str) -> dict[str, int] | None:
    results = re.findall(r"test result: \w+\.\s+(\d+) passed; (\d+) failed; (\d+) ignored", text)
    if not results:
        return None
    counts = _blank()
    for p, f, i in results:
        counts["passed"] += int(p)
        counts["failed"] += int(f)
        counts["skipped"] += int(i)
    counts["total"] = counts["passed"] + counts["failed"] + counts["skipped"]
    return counts


def parse_go(text: str) -> dict[str, int] | None:
    verbose = re.findall(r"^\s*--- (PASS|FAIL|SKIP):", text, re.M)
    if verbose:
        counts = _blank()
        counts["passed"] = verbose.count("PASS")
        counts["failed"] = verbose.count("FAIL")
        counts["skipped"] = verbose.count("SKIP")
        counts["total"] = len(verbose)
        return counts
    pkgs = re.findall(r"^(ok|FAIL|\?)\s+\S+", text, re.M)
    if not pkgs:
        return None
    # Without -v, go reports packages, not tests. Report package level honestly:
    # a package with "[no test files]" counts as zero tests.
    counts = _blank()
    ok_pkgs = [ln for ln in text.splitlines() if re.match(r"^ok\s+\S+", ln)]
    counts["passed"] = len(ok_pkgs)
    counts["failed"] = len(re.findall(r"^FAIL\s+\S+", text, re.M))
    counts["total"] = counts["passed"] + counts["failed"]
    if "no tests to run" in text:
        counts["passed"] = 0
        counts["total"] = counts["failed"]
    return counts


PARSERS = (
    ("pytest", parse_pytest),
    ("cargo", parse_cargo),
    ("jest/vitest", parse_jest),
    ("unittest", parse_unittest),
    ("go", parse_go),
)


def parse_output(text: str) -> tuple[str, dict[str, int]] | None:
    for name, fn in PARSERS:
        counts = fn(text)
        if counts is not None:
            return name, counts
    return None


def _git(*args: str) -> str:
    try:
        res = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return ""
    return res.stdout if res.returncode == 0 else ""


def tree_fingerprint() -> str:
    """Hash of the working tree state (tracked diff + untracked file contents)."""
    h = hashlib.sha256()
    h.update(_git("rev-parse", "HEAD").encode())
    h.update(_git("diff", "HEAD", "--no-color").encode())
    for path in sorted(_git("ls-files", "--others", "--exclude-standard").split()):
        if path.startswith(".done-receipt/"):
            continue
        h.update(path.encode())
        try:
            with open(path, "rb") as fh:
                h.update(fh.read())
        except OSError:
            pass
    return h.hexdigest()[:16]


def judge(exit_code: int, framework: str | None, counts: dict[str, int] | None,
          baseline: dict | None, max_skip_ratio: float) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if counts is None:
        if exit_code != 0:
            return "FAILED", [f"command exited with {exit_code} and its output could not be parsed"]
        return "UNVERIFIED", ["could not find a test summary in the output; exit code 0 alone proves nothing"]

    if exit_code != 0 or counts["failed"] or counts["errors"]:
        if counts["total"] == 0:
            reasons.append(f"exit code {exit_code} and 0 tests ran (wrong path, empty suite, or collection problem)")
        else:
            reasons.append(f"exit code {exit_code}, {counts['failed']} failed, {counts['errors']} errors")
        return "FAILED", reasons

    suspicious = False
    if counts["total"] == 0:
        reasons.append("0 tests ran (exit code was 0, but nothing was executed)")
        suspicious = True
    elif counts["passed"] == 0:
        reasons.append("no test passed: everything was skipped")
        suspicious = True
    elif counts["skipped"] / counts["total"] > max_skip_ratio:
        reasons.append(
            f"{counts['skipped']} of {counts['total']} tests skipped (more than {max_skip_ratio:.0%})"
        )
        suspicious = True

    if baseline and baseline.get("counts"):
        before = baseline["counts"]["total"]
        if counts["total"] < before:
            reasons.append(f"test count dropped from {before} (baseline) to {counts['total']}")
            suspicious = True
        before_skip = baseline["counts"]["skipped"]
        if counts["skipped"] > before_skip:
            reasons.append(f"skipped tests rose from {before_skip} to {counts['skipped']}")
            suspicious = True

    if suspicious:
        return "SUSPICIOUS", reasons
    return "VERIFIED", reasons or ["tests ran and none failed"]


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def read_json(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def check_receipt() -> int:
    r = read_json(LAST)
    if not r:
        print("No receipt found. Run the tests through test_run_check.py first; nothing can be claimed yet.")
        return 1
    now = tree_fingerprint()
    fresh = now == r.get("tree")
    c = r.get("counts") or {}
    print(f"Receipt: {r.get('verdict')} | {r.get('framework')} | {c.get('passed', '?')} passed, "
          f"{c.get('failed', '?')} failed, {c.get('skipped', '?')} skipped | command: {r.get('command')}")
    print(f"Recorded: {r.get('time')}")
    if not fresh:
        print("STALE: the code or tests changed after this run. Re-run before claiming anything.")
        return 1
    print("FRESH: the working tree is identical to what was tested.")
    return 0 if r.get("verdict") == "VERIFIED" else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, cmd = argv[:i], argv[i + 1:]

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save-baseline", action="store_true", help="store this run's counts as the baseline")
    ap.add_argument("--check-receipt", action="store_true", help="is the last receipt still valid for the current tree?")
    ap.add_argument("--max-skip-ratio", type=float, default=0.2, help="flag if more than this share is skipped (default 0.2)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds before the command is killed (default 900)")
    ap.add_argument("--quiet", action="store_true", help="do not echo the command output tail")
    args = ap.parse_args(argv)

    if args.check_receipt:
        return check_receipt()

    if not cmd:
        ap.error("give the test command after '--', e.g.  test_run_check.py -- pytest -q")

    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
        exit_code, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        print(f"command not found: {cmd[0]}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print(f"timed out after {args.timeout}s", file=sys.stderr)
        return 1
    elapsed = time.time() - start

    parsed = parse_output(out)
    framework, counts = (parsed if parsed else (None, None))
    baseline = None if args.save_baseline else read_json(BASELINE)
    verdict, reasons = judge(exit_code, framework, counts, baseline, args.max_skip_ratio)

    receipt = {
        "command": " ".join(cmd),
        "exit_code": exit_code,
        "framework": framework,
        "counts": counts,
        "verdict": verdict,
        "reasons": reasons,
        "tree": tree_fingerprint(),
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(elapsed, 2),
    }
    write_json(LAST, receipt)
    if args.save_baseline and counts is not None:
        write_json(BASELINE, receipt)

    if not args.quiet:
        tail = [ln for ln in out.splitlines() if ln.strip()][-8:]
        if tail:
            print("--- last lines of test output ---")
            print("\n".join(tail))
            print("---------------------------------")
    if counts is not None:
        print(f"{framework}: {counts['passed']} passed, {counts['failed']} failed, "
              f"{counts['skipped']} skipped, {counts['errors']} errors ({counts['total']} total)")
    print(f"VERDICT: {verdict}")
    for r in reasons:
        print(f"  - {r}")
    if args.save_baseline:
        print(f"Baseline saved to {BASELINE}" if counts is not None else "Baseline NOT saved: could not parse counts.")
    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
