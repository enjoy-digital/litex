#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import signal
import subprocess
import unittest
from unittest import mock

from litex.build.sim import verilator


class TestSimVerilatorRun(unittest.TestCase):
    def test_ctrl_c_while_waiting_exits_without_traceback(self):
        proc = mock.Mock()
        proc.wait.side_effect = [KeyboardInterrupt, 0]

        with mock.patch.object(verilator.tools, "write_to_file") as write_to_file:
            with mock.patch.object(verilator.subprocess, "Popen", return_value=proc):
                with self.assertRaises(SystemExit) as cm:
                    verilator._run_sim("sim", interactive=False)

        self.assertEqual(cm.exception.code, 130)
        write_to_file.assert_called_once_with("run_sim.sh", "obj_dir/Vsim", force_unix=True)
        proc.terminate.assert_not_called()
        proc.kill.assert_not_called()

    def test_ctrl_c_terminates_child_when_it_does_not_exit(self):
        proc = mock.Mock()
        proc.wait.side_effect = [
            KeyboardInterrupt,
            subprocess.TimeoutExpired("sim", 2),
            0,
        ]

        with mock.patch.object(verilator.tools, "write_to_file"):
            with mock.patch.object(verilator.subprocess, "Popen", return_value=proc):
                with self.assertRaises(SystemExit) as cm:
                    verilator._run_sim("sim", interactive=False)

        self.assertEqual(cm.exception.code, 130)
        proc.terminate.assert_called_once_with()
        proc.kill.assert_not_called()

    def test_sigint_return_code_exits_without_traceback(self):
        proc = mock.Mock()
        proc.wait.return_value = -signal.SIGINT

        with mock.patch.object(verilator.tools, "write_to_file"):
            with mock.patch.object(verilator.subprocess, "Popen", return_value=proc):
                with self.assertRaises(SystemExit) as cm:
                    verilator._run_sim("sim", interactive=False)

        self.assertEqual(cm.exception.code, 130)
        proc.terminate.assert_not_called()

    def test_nonzero_return_code_is_still_a_failure(self):
        proc = mock.Mock()
        proc.wait.return_value = 1

        with mock.patch.object(verilator.tools, "write_to_file"):
            with mock.patch.object(verilator.subprocess, "Popen", return_value=proc):
                with self.assertRaises(OSError):
                    verilator._run_sim("sim", interactive=False)


if __name__ == "__main__":
    unittest.main()
