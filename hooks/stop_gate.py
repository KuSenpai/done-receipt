#!/usr/bin/env python3
"""stop_gate: a Claude Code `Stop` hook that blocks "tests pass" without a valid receipt.

When the agent's final message claims success ("all tests pass", "suite is
green", ...), this hook runs `test_run_check.py --check-receipt`. If the latest
receipt is missing, not VERIFIED, or STALE, the stop is blocked once and the
agent is told why. Messages that make no success claim are never blocked.

Fails open: any error (bad input, missing git, missing files) lets Claude stop.
Blocks at most once per stop: if `stop_hook_active` is set, it always allows.

Off switch: set the environment variable DONE_RECEIPT_STOP_HOOK=off (or 0/false).

Claim detection reuses the eval grader's `claims_success`, so what is enforced
here is exactly what the evals count as a success claim. Standard library only.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECK = ROOT / "skills" / "verify-tests-ran" / "scripts" / "test_run_check.py"
GRADER = ROOT / "evals" / "run_eval.py"


def claims_success(text: str) -> bool:
    spec = importlib.util.spec_from_file_location("done_receipt_grader", GRADER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses in run_eval.py look the module up here
    spec.loader.exec_module(mod)
    return mod.claims_success(text)[0]


def decide(data: dict) -> str | None:
    """Return a block reason, or None to let Claude stop."""
    if os.environ.get("DONE_RECEIPT_STOP_HOOK", "").strip().lower() in ("0", "off", "false", "no"):
        return None
    if data.get("stop_hook_active"):
        return None
    msg = data.get("last_assistant_message")
    if not isinstance(msg, str) or not claims_success(msg):
        return None
    res = subprocess.run([sys.executable, str(CHECK), "--check-receipt"], cwd=data.get("cwd") or None,
                         capture_output=True, text=True, timeout=60)
    if res.returncode == 0:
        return None
    return (
        "done-receipt: your final message claims the tests pass, but the receipt does not back it up:\n"
        f"{res.stdout.strip()}\n"
        f"Either re-run the tests through `python \"{CHECK}\" -- <test command>` and report the real verdict, "
        "or rewrite the report so it does not claim success. "
        "(The user can disable this check with DONE_RECEIPT_STOP_HOOK=off.)"
    )


def main() -> int:
    try:
        reason = decide(json.load(sys.stdin))
    except Exception as exc:  # fail open: never trap the user because the hook broke
        print(f"done-receipt stop hook skipped: {exc}", file=sys.stderr)
        return 0
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
