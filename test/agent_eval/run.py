#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""LiteX agent evaluation runner.

  run.py list [--tier T]            List the tasks (tier, board).
  run.py setup <task> <workdir>     Create a fresh workspace for task and print the prompt.
  run.py check <task> <workdir>     Check the workspace (JSON result, exit code 0 when passed).
  run.py mcp-config <task> <workdir>
                                    Print an MCP configuration (litex_mcp) for an agent run on
                                    the workspace.
  run.py selftest [--tier T] [task ...]
                                    For each task: setup, check fails, apply the reference
                                    solution, check passes. Hardware tasks: dry run (elaboration,
                                    no board) unless LITEX_AGENT_EVAL_HW=<board>.
  run.py agent <task> <condition> <outdir> [--runs N]
                                    Run Claude Code headless on task, N sequential runs (fresh
                                    workspace each), condition shell (no MCP) or mcp (litex_mcp),
                                    transcripts and check results in outdir.
  run.py score <outdir>             Score the runs of outdir (pass rate, wall time, tool calls
                                    MCP/shell/files, tokens, cost) per task and condition.

Tiers: v1 = fault visible in the source (reading the target finds it), v2 = fault only visible
at runtime (opaque netlist, prebuilt firmware, data-dependent behavior, generated artifacts).
"""

import os
import re
import sys
import json
import time
import tempfile
import argparse
import subprocess
import statistics

# Make the test package importable when run as a script (python3 test/agent_eval/run.py).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from test.agent_eval.common import list_tasks, task_prompt, task_module, task_tier, task_hardware
from test.agent_eval.common import hardware_enabled, setup_task, tcp_listening

# Selftest -----------------------------------------------------------------------------------------

def selftest_task(task):
    """Selftest of task: the check fails on the fresh workspace, passes with the solution.

    Hardware tasks without their board (LITEX_AGENT_EVAL_HW): dry run, the fresh and the solved
    workspaces elaborate (and build with LITEX_AGENT_EVAL_HW_BUILD=1), no load."""
    start   = time.time()
    details = {"task": task}
    check   = task_module(task, "check")
    board   = task_hardware(task)
    dry     = board is not None and not hardware_enabled(board)
    with tempfile.TemporaryDirectory(prefix=f"litex_agent_eval_{task}_") as workdir:
        setup_task(task, workdir)
        if dry:
            broken = check.dry_run(workdir)
            details["mode"] = "dry-run"
        else:
            broken = check.check(workdir)
        details["broken"] = broken.to_dict()
        task_module(task, "solution").solve(workdir)
        fixed  = (check.dry_run if dry else check.check)(workdir)
        details["fixed"]  = fixed.to_dict()
    if dry:
        details["passed"] = broken.passed and fixed.passed
    else:
        details["passed"] = (not broken.passed) and (broken.error is None) and fixed.passed
    details["duration"] = round(time.time() - start, 1)
    return details

# Agent Runs ---------------------------------------------------------------------------------------

CONDITIONS = ["shell", "mcp"]

def agent_run(task, condition, outdir, index, model=None, timeout=3600):
    """One headless Claude Code run of task in a fresh workspace: transcript (stream-json) in
    <outdir>/<task>-<condition>-<index>.jsonl, check result in .check.json, wall time in .json."""
    name    = f"{task}-{condition}-{index}"
    workdir = os.path.join(outdir, "work", name)
    prompt  = setup_task(task, workdir)
    if condition == "mcp":
        mcp = os.path.join(outdir, "work", f"{name}.mcp.json")
        with open(mcp, "w") as f:
            json.dump(mcp_config(task, workdir), f)
    else:
        mcp = json.dumps({"mcpServers": {}})
    cmd = ["claude", "-p", prompt, "--strict-mcp-config", "--mcp-config", mcp,
        "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"]
    if model:
        cmd += ["--model", model]
    start = time.time()
    with open(os.path.join(outdir, f"{name}.jsonl"), "w") as f:
        try:
            subprocess.run(cmd, cwd=workdir, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
    wall  = round(time.time() - start, 1)
    check = task_module(task, "check")
    leftover = [p for p in check.AGENT_PORTS if tcp_listening(p)]
    result   = check.check(workdir).to_dict()
    result["leftover_ports"] = leftover
    with open(os.path.join(outdir, f"{name}.check.json"), "w") as f:
        json.dump(result, f, indent=2)
    with open(os.path.join(outdir, f"{name}.json"), "w") as f:
        json.dump({"task": task, "condition": condition, "index": index, "model": model,
            "wall_s": wall, "timed_out": timed_out}, f, indent=2)
    return result["passed"], wall

# Scoring ------------------------------------------------------------------------------------------

FILE_TOOLS = {"Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "NotebookEdit"}

def parse_transcript(filename):
    """Tool calls (MCP/shell/files/other), tokens and cost of a stream-json transcript."""
    stats = {"mcp": 0, "shell": 0, "files": 0, "other": 0, "cost_usd": None,
        "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
    with open(filename, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get("type") == "assistant":
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") != "tool_use":
                        continue
                    name = block.get("name", "")
                    if name.startswith("mcp__litex__"):
                        stats["mcp"] += 1
                    elif name == "Bash":
                        stats["shell"] += 1
                    elif name in FILE_TOOLS:
                        stats["files"] += 1
                    else:
                        stats["other"] += 1
            elif event.get("type") == "result":
                usage = event.get("usage", {})
                stats["cost_usd"]           = event.get("total_cost_usd")
                stats["input_tokens"]       = usage.get("input_tokens", 0)
                stats["output_tokens"]      = usage.get("output_tokens", 0)
                stats["cache_read_tokens"]  = usage.get("cache_read_input_tokens", 0)
                stats["cache_write_tokens"] = usage.get("cache_creation_input_tokens", 0)
    return stats

def score(outdir):
    """Per (task, condition): runs, pass rate, and medians on the passing runs."""
    runs = {}
    for filename in sorted(os.listdir(outdir)):
        m = re.fullmatch(r"(.+)-(shell|mcp)-(\d+)\.check\.json", filename)
        if m is None:
            continue
        task, condition, index = m.group(1), m.group(2), m.group(3)
        base = os.path.join(outdir, f"{task}-{condition}-{index}")
        with open(base + ".check.json") as f:
            passed = json.load(f)["passed"]
        info = {}
        if os.path.exists(base + ".json"):
            with open(base + ".json") as f:
                info = json.load(f)
        stats = parse_transcript(base + ".jsonl") if os.path.exists(base + ".jsonl") else {}
        runs.setdefault((task, condition), []).append(dict(passed=passed, wall_s=info.get("wall_s"), **stats))

    def median(values):
        values = [v for v in values if v is not None]
        return round(statistics.median(values), 2) if values else None

    rows = []
    for (task, condition), rs in sorted(runs.items()):
        ok = [r for r in rs if r["passed"]]
        rows.append({
            "task"      : task,
            "tier"      : task_tier(task) if task in list_tasks() else "?",
            "condition" : condition,
            "runs"      : len(rs),
            "pass_rate" : round(len(ok)/len(rs), 2),
            "wall_s"    : median([r["wall_s"]   for r in ok]),
            "mcp"       : median([r.get("mcp")   for r in ok]),
            "shell"     : median([r.get("shell") for r in ok]),
            "files"     : median([r.get("files") for r in ok]),
            "cost_usd"  : median([r.get("cost_usd") for r in ok]),
            "out_tokens": median([r.get("output_tokens") for r in ok]),
        })
    return rows

# MCP Configuration ------------------------------------------------------------------------------

def mcp_config(task, workdir):
    """litex_mcp on the second port of the task (the litex_server port of the prompt), with the
    CSR file of the workspace build (check.CSR_CSV, default build/sim/csr.csv) and the write
    tools."""
    check  = task_module(task, "check")
    port   = check.AGENT_PORTS[1]
    csr    = getattr(check, "CSR_CSV", os.path.join("build", "sim", "csr.csv"))
    server = {
        "command" : sys.executable,
        "args"    : ["-m", "litex.tools.litex_mcp", "--allow-write", f"--port={port}",
            f"--csr-csv={os.path.join(workdir, csr)}",
            f"--jobs-dir={os.path.join(workdir, '.litex_mcp')}"],
    }
    if os.environ.get("PYTHONPATH"):
        server["env"] = {"PYTHONPATH": os.environ["PYTHONPATH"]}
    return {"mcpServers": {"litex": server}}

# Main ---------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX agent evaluation runner.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="List the tasks.")
    p.add_argument("--tier", default=None, help="Only the tasks of this tier (v1, v2).")
    p = sub.add_parser("setup", help="Create a fresh workspace and print the prompt.")
    p.add_argument("task")
    p.add_argument("workdir")
    p = sub.add_parser("check", help="Check a workspace (JSON result, exit code 0 when passed).")
    p.add_argument("task")
    p.add_argument("workdir")
    p = sub.add_parser("mcp-config", help="Print an MCP configuration for an agent run.")
    p.add_argument("task")
    p.add_argument("workdir")
    p = sub.add_parser("selftest", help="Validate the checkers with the reference solutions.")
    p.add_argument("--tier", default=None, help="Only the tasks of this tier (v1, v2).")
    p.add_argument("tasks", nargs="*", help="Tasks to test (default: all).")
    p = sub.add_parser("agent", help="Run Claude Code headless on a task (sequential runs).")
    p.add_argument("task")
    p.add_argument("condition", choices=CONDITIONS)
    p.add_argument("outdir")
    p.add_argument("--runs",    default=3, type=int, help="Number of sequential runs.")
    p.add_argument("--model",   default=None,        help="Model (claude --model).")
    p.add_argument("--timeout", default=3600, type=int, help="Timeout of a run (s).")
    p = sub.add_parser("score", help="Score the agent runs of a directory.")
    p.add_argument("outdir")
    p.add_argument("--json", action="store_true", help="JSON output.")
    args = parser.parse_args()

    def tasks_of(tier):
        return [t for t in list_tasks() if tier is None or task_tier(t) == tier]

    # List.
    if args.cmd == "list":
        for task in tasks_of(args.tier):
            board = task_hardware(task) or "sim/offline"
            print(f"{task:16s} {task_tier(task):3s} {board:12s} {task_prompt(task).splitlines()[0].lstrip('# ')}")

    # Setup.
    elif args.cmd == "setup":
        print(setup_task(args.task, os.path.abspath(args.workdir)))

    # Check.
    elif args.cmd == "check":
        check = task_module(args.task, "check")
        # Processes left running by the agent (informative, does not change the result).
        leftover = [p for p in check.AGENT_PORTS if tcp_listening(p)]
        result   = check.check(os.path.abspath(args.workdir)).to_dict()
        result["leftover_ports"] = leftover
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["passed"] else 1)

    # MCP Configuration.
    elif args.cmd == "mcp-config":
        print(json.dumps(mcp_config(args.task, os.path.abspath(args.workdir)), indent=2))

    # Selftest.
    elif args.cmd == "selftest":
        results = []
        for task in (args.tasks or tasks_of(args.tier)):
            r = selftest_task(task)
            results.append(r)
            status = "PASS" if r["passed"] else "FAIL"
            mode   = f" [{r['mode']}]" if "mode" in r else ""
            print(f"{task:16s} {status} ({r['duration']}s){mode}", flush=True)
            if not r["passed"]:
                print(json.dumps(r, indent=2), flush=True)
        sys.exit(0 if all(r["passed"] for r in results) else 1)

    # Agent runs.
    elif args.cmd == "agent":
        outdir = os.path.abspath(args.outdir)
        os.makedirs(os.path.join(outdir, "work"), exist_ok=True)
        for index in range(args.runs):
            passed, wall = agent_run(args.task, args.condition, outdir, index, model=args.model,
                timeout=args.timeout)
            print(f"{args.task}-{args.condition}-{index}: {'PASS' if passed else 'FAIL'} ({wall}s)", flush=True)

    # Score.
    elif args.cmd == "score":
        rows = score(os.path.abspath(args.outdir))
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            keys = ["task", "tier", "condition", "runs", "pass_rate", "wall_s", "mcp", "shell", "files", "cost_usd", "out_tokens"]
            print(" | ".join(keys))
            for r in rows:
                print(" | ".join(str(r[k]) for k in keys))

if __name__ == "__main__":
    main()
