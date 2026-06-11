#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import signal
import subprocess
import unittest
from unittest import mock

from litex.build.sim.config import SimConfig
from litex.build.sim import verilator


class TestSimVerilatorTrace(unittest.TestCase):
    def test_parse_trace_timescale(self):
        self.assertEqual(verilator._parse_trace_timescale("1ps"),   ("1ps",   1))
        self.assertEqual(verilator._parse_trace_timescale("100ps"), ("100ps", 100))
        self.assertEqual(verilator._parse_trace_timescale("1ns"),   ("1ns",   1_000))
        self.assertEqual(verilator._parse_trace_timescale("10us"),  ("10us",  10_000_000))

    def test_parse_trace_timescale_rejects_invalid_values(self):
        invalid_timescales = ["2ps", "1fs", "1ns/1ps", "100 ps", "abc"]
        for timescale in invalid_timescales:
            with self.subTest(timescale=timescale):
                with self.assertRaises(ValueError):
                    verilator._parse_trace_timescale(timescale)

    def test_trace_timescale_must_represent_sim_timebase(self):
        sim_config = SimConfig()
        sim_config.add_clocker("sys_clk", freq_hz=int(1e6))

        verilator._validate_trace_timescale("100ps", 100, sim_config)

        with self.assertRaisesRegex(ValueError, "cannot represent simulation timebase"):
            verilator._validate_trace_timescale("1us", 1_000_000, sim_config)

    def test_generate_sim_cpp_passes_trace_timescale(self):
        platform = mock.Mock()
        platform.sim_requested = []

        with mock.patch.object(verilator.tools, "write_to_file") as write_to_file:
            verilator._generate_sim_cpp(
                platform,
                trace              = True,
                trace_start        = 0,
                trace_end          = -1,
                trace_timescale    = "100ps",
                trace_timescale_ps = 100,
            )

        content = write_to_file.call_args.args[1]
        self.assertIn('litex_sim_init_tracer(sim, 0, -1, "100ps", 100);', content)


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
