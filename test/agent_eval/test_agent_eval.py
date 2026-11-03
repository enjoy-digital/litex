#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Selftest of the agent evaluation tasks: the checker fails on the fresh workspace and passes with
# the reference solution. The offline tasks always run; the simulation tasks (Verilator, ~10s to
# ~1min each) only with LITEX_AGENT_EVAL_SIM=1.

import os
import shutil

import pytest

from test.agent_eval.common import list_tasks, task_module
from test.agent_eval.run import selftest_task

def _is_sim_task(task):
    return hasattr(task_module(task, "check"), "UART_PORT")

SIM_TASKS     = [t for t in list_tasks() if _is_sim_task(t)]
OFFLINE_TASKS = [t for t in list_tasks() if not _is_sim_task(t)]

def test_tasks_layout():
    for task in list_tasks():
        assert hasattr(task_module(task, "check"),    "check")
        assert hasattr(task_module(task, "solution"), "solve")
    # Each simulation task has its own TCP ports.
    ports = [p for t in SIM_TASKS for p in (task_module(t, "check").UART_PORT, task_module(t, "check").SERVER_PORT)]
    assert len(ports) == len(set(ports))

@pytest.mark.parametrize("task", OFFLINE_TASKS)
def test_offline_task(task):
    r = selftest_task(task)
    assert r["passed"], r

@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("LITEX_AGENT_EVAL_SIM") != "1",
    reason="Agent evaluation simulations only run with LITEX_AGENT_EVAL_SIM=1.")
@pytest.mark.skipif(shutil.which("verilator") is None, reason="Verilator not found.")
@pytest.mark.parametrize("task", SIM_TASKS)
def test_sim_task(task):
    r = selftest_task(task)
    assert r["passed"], r
