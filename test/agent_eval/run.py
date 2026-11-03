#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""LiteX agent evaluation runner.

  run.py list                       List the tasks.
  run.py setup <task> <workdir>     Create a fresh workspace for task and print the prompt.
  run.py check <task> <workdir>     Check the workspace (JSON result, exit code 0 when passed).
  run.py mcp-config <task> <workdir>
                                    Print an MCP configuration (litex_mcp) for an agent run on
                                    the workspace.
  run.py selftest [task ...]        For each task: setup, check fails, apply the reference
                                    solution, check passes.
"""

import os
import sys
import json
import time
import tempfile
import argparse

# Make the test package importable when run as a script (python3 test/agent_eval/run.py).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from test.agent_eval.common import list_tasks, task_prompt, task_module, setup_task, tcp_listening

# Selftest -----------------------------------------------------------------------------------------

def selftest_task(task):
    """Selftest of task: the check fails on the fresh workspace, passes with the solution."""
    start   = time.time()
    details = {"task": task}
    with tempfile.TemporaryDirectory(prefix=f"litex_agent_eval_{task}_") as workdir:
        setup_task(task, workdir)
        broken = task_module(task, "check").check(workdir)
        details["broken"] = broken.to_dict()
        task_module(task, "solution").solve(workdir)
        fixed  = task_module(task, "check").check(workdir)
        details["fixed"]  = fixed.to_dict()
    details["passed"]   = (not broken.passed) and (broken.error is None) and fixed.passed
    details["duration"] = round(time.time() - start, 1)
    return details

# MCP Configuration ------------------------------------------------------------------------------

def mcp_config(task, workdir):
    """litex_mcp on the second port of the task (the litex_server port of the prompt), with the
    CSR file of the workspace build and the write tools."""
    port   = task_module(task, "check").AGENT_PORTS[1]
    server = {
        "command" : sys.executable,
        "args"    : ["-m", "litex.tools.litex_mcp", "--allow-write", f"--port={port}",
            f"--csr-csv={os.path.join(workdir, 'build', 'sim', 'csr.csv')}",
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
    sub.add_parser("list", help="List the tasks.")
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
    p.add_argument("tasks", nargs="*", help="Tasks to test (default: all).")
    args = parser.parse_args()

    # List.
    if args.cmd == "list":
        for task in list_tasks():
            print(f"{task:16s} {task_prompt(task).splitlines()[0].lstrip('# ')}")

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
        for task in (args.tasks or list_tasks()):
            r = selftest_task(task)
            results.append(r)
            status = "PASS" if r["passed"] else "FAIL"
            print(f"{task:16s} {status} ({r['duration']}s)", flush=True)
            if not r["passed"]:
                print(json.dumps(r, indent=2), flush=True)
        sys.exit(0 if all(r["passed"] for r in results) else 1)

if __name__ == "__main__":
    main()
