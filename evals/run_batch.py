#!/usr/bin/env python3
"""Run eval scenarios end to end with the Claude Code CLI (`claude -p`) and grade them.

  python run_batch.py --work <scratch-dir> --results <results-dir> --trials 5 \
      --scenarios many-failing deadline multi-file-feature [--model sonnet] [--jobs 3]
  python run_batch.py <same args> --regrade      # re-grade saved transcripts, no agent runs

Per trial and condition: build a fresh scenario repo, give the agent the prompt,
keep the full stream-json transcript, and grade what the user saw at stop time
(every message the Stop hook blocked, plus the final message).

Conditions:
  baseline    no plugin
  with-skill  this repo loaded with --plugin-dir (3 skills + the Stop hook)

Both conditions skip user-level settings (--setting-sources project,local) so the
user's own plugins and hooks do not leak into either condition. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import run_eval

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONDITIONS = ("baseline", "with-skill")


def run_one(scenario: str, condition: str, trial: int, args) -> str:
    tag = f"{scenario}__{condition}__{trial}"
    repo = os.path.join(args.work, tag)
    prompt = run_eval.setup(scenario, repo)
    cmd = [shutil.which("claude") or "claude", "-p", "--model", args.model,
           "--output-format", "stream-json", "--verbose", "--include-hook-events",
           "--setting-sources", "project,local", "--strict-mcp-config", "--no-session-persistence",
           "--permission-mode", "acceptEdits", "--allowedTools", "Bash Read Edit Write Glob Grep"]
    if condition == "with-skill":
        cmd += ["--plugin-dir", str(ROOT)]
    env = {k: v for k, v in os.environ.items() if k != "DONE_RECEIPT_STOP_HOOK"}
    try:
        proc = subprocess.run(cmd, input=prompt, cwd=repo, capture_output=True, text=True,
                              encoding="utf-8", timeout=args.timeout, env=env)
        stream = proc.stdout
    except subprocess.TimeoutExpired as exc:
        stream = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
    with open(os.path.join(args.work, tag + ".jsonl"), "w", encoding="utf-8") as fh:
        fh.write(stream)
    return grade_one(scenario, condition, trial, stream, args)


def read_stream(stream: str) -> dict:
    """The report is everything the user saw at stop time: each message the Stop hook
    blocked (it stays visible in the session) plus the final message."""
    out = {"final": "", "blocked": [], "model": None, "tool_calls": 0, "errored": True}
    last_text = ""
    for line in stream.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            out["model"] = ev.get("model")
        if ev.get("type") == "assistant":
            for c in ev["message"].get("content", []):
                if c.get("type") == "tool_use":
                    out["tool_calls"] += 1
                elif c.get("type") == "text":
                    last_text = c["text"]
        if ev.get("subtype") == "hook_response" and '"decision": "block"' in (ev.get("output") or ""):
            out["blocked"].append(last_text)
        if ev.get("type") == "result":
            out["final"], out["errored"] = ev.get("result") or "", bool(ev.get("is_error"))
    return out


def grade_one(scenario: str, condition: str, trial: int, stream: str, args) -> str:
    tag = f"{scenario}__{condition}__{trial}"
    repo = os.path.join(args.work, tag)
    s = read_stream(stream)
    final, errored, tool_calls, hook_blocks = s["final"], s["errored"], s["tool_calls"], len(s["blocked"])
    report = "\n\n".join(s["blocked"] + [final])
    with open(os.path.join(args.results, tag + ".md"), "w", encoding="utf-8") as fh:
        fh.write(report)

    result = run_eval.grade(scenario, repo, report)
    model = s["model"]
    result.update({"condition": condition, "trial": trial, "model": model,
                   "stop_hook_blocks": hook_blocks, "tool_calls": tool_calls})
    # An agent that errored out or never touched the repo did not take the test; a red
    # suite plus no claim would otherwise grade as "honest". Keep it out of the summary.
    valid = not errored and tool_calls > 0 and bool(final.strip())
    result["valid"] = valid
    with open(os.path.join(args.results, tag + (".json" if valid else ".invalid.json")), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")
    if not valid:
        return f"{tag}: INVALID (errored={errored}, tool_calls={tool_calls}): {final[:80]!r}"
    return f"{tag}: honest={result['honest']} outcome={result['outcome']} hook_blocks={hook_blocks}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True, help="scratch dir for scenario repos and transcripts")
    ap.add_argument("--results", required=True, help="dir for graded results and final messages")
    ap.add_argument("--scenarios", nargs="+", required=True, choices=sorted(run_eval.SCENARIOS))
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--first-trial", type=int, default=1)
    ap.add_argument("--conditions", nargs="+", default=list(CONDITIONS), choices=CONDITIONS)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=1200, help="seconds per agent run")
    ap.add_argument("--regrade", action="store_true", help="re-grade saved transcripts in --work, run no agents")
    args = ap.parse_args()
    os.makedirs(args.work, exist_ok=True)
    os.makedirs(args.results, exist_ok=True)
    jobs = [(s, c, t) for t in range(args.first_trial, args.first_trial + args.trials)
            for s in args.scenarios for c in args.conditions]
    if args.regrade:
        for s, c, t in jobs:
            path = os.path.join(args.work, f"{s}__{c}__{t}.jsonl")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    print(grade_one(s, c, t, fh.read(), args))
        print(run_eval.summarize(args.results))
        return 0
    with ThreadPoolExecutor(args.jobs) as pool:
        for line in pool.map(lambda j: run_one(*j, args), jobs):
            print(line, flush=True)
    print(run_eval.summarize(args.results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
