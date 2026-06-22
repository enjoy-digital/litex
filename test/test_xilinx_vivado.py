#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import unittest
from unittest import mock

from litex.build.xilinx.vivado import XilinxVivadoToolchain, _xdc_separator


class _VNS:
    def __init__(self, names=None):
        self.names = {} if names is None else names

    def get_name(self, signal):
        return self.names[signal]


class _ConstraintManager:
    def get_io_signals(self):
        return set()


class _Platform:
    def __init__(self):
        self.commands           = []
        self.constraint_manager = _ConstraintManager()

    def add_platform_command(self, command, **signals):
        self.commands.append(command)


class TestXilinxVivadoToolchain(unittest.TestCase):
    def test_additional_xdc_commands_are_written_after_generated_clocks(self):
        toolchain             = XilinxVivadoToolchain()
        toolchain._build_name = "top"
        port                  = object()
        toolchain._vns        = _VNS({port: "port1"})
        toolchain.named_sc    = []
        toolchain.named_pc    = [
            "set_property MARK_DEBUG true [get_nets debug]",
            _xdc_separator("Clock constraints"),
            "create_clock -name clock1 -period 10 [get_ports clk]",
        ]
        toolchain.additional_xdc_commands.add(
            "set_input_delay -clock [get_clocks clock1] -max 0.500 [get_ports {{{port}}}]",
            port=port,
        )

        with mock.patch("litex.build.xilinx.vivado.tools.write_to_file") as write_to_file:
            toolchain.build_io_constraints()

        xdc = write_to_file.call_args[0][1]
        self.assertLess(xdc.index("Clock constraints"), xdc.index("Additional XDC constraints"))
        self.assertLess(xdc.index("Additional XDC constraints"), xdc.index("set_input_delay"))
        self.assertIn("[get_ports {port1}]", xdc)

    def test_multireg_false_path_targets_first_stage_cell(self):
        toolchain          = XilinxVivadoToolchain()
        toolchain.platform = _Platform()

        toolchain._build_false_path_constraints()

        multireg_false_path = next(c for c in toolchain.platform.commands if "mr_ff == TRUE" in c)
        self.assertIn("set_false_path -quiet", multireg_false_path)
        self.assertIn("get_cells -hierarchical -filter {{mr_ff == TRUE}}", multireg_false_path)
        self.assertNotIn("REF_PIN_NAME == D", multireg_false_path)
        self.assertNotIn("get_nets -filter {{mr_ff == TRUE}}", multireg_false_path)


if __name__ == "__main__":
    unittest.main()
