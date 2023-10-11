#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2021 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

# See: https://f4pga-examples.readthedocs.io/en/latest/getting.html#toolchain-installation
# To install toolchain

import os
import sys
import subprocess
import json
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build.generic_toolchain import GenericToolchain
from litex.build import tools
from litex.build.quicklogic import common


# F4PGAToolchain -----------------------------------------------------------------------------------
# Formerly SymbiflowToolchain, Symbiflow has been renamed to F4PGA ---------------------------------

class F4PGAToolchain(GenericToolchain):
    attr_translate = {}

    special_overrides = common.quicklogic_special_overrides

    def __init__(self):
        super().__init__()

    # IO Constraints (.pcf) ------------------------------------------------------------------------

    @classmethod
    def _format_io_pcf(cls, signame, pin, others):
        r = f"set_io {signame} {Pins(pin).identifiers[0]}\n"
        return r

    def build_io_constraints(self):
        pcf = ""
        for sig, pins, others, resname in self.named_sc:
            if len(pins) > 1:
                for i, p in enumerate(pins):
                    pcf += self._format_io_pcf(sig + "(" + str(i) + ")", p, others)
            else:
                pcf += self._format_io_pcf(sig, pins[0], others)
        tools.write_to_file(self._build_name + ".pcf", pcf)
        return (self._build_name + ".pcf", "PCF")

    # Timing constraints (.sdc) --------------------------------------------------------------------

    def build_timing_constraints(self, vns):
        sdc = []
        for clk, [period, name] in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            clk_sig = vns.get_name(clk)
            sdc.append("create_clock -period {} {}".format(str(period), clk_sig))
        tools.write_to_file(self._build_name + "_in.sdc", "\n".join(sdc))
        return (self._build_name + "_in.sdc", "SDC")

    # Build flow.json ------------------------------------------------------------------------------

    def build_script(self):
        part = {"ql-eos-s3": "PU64"}.get(self.platform.device)
        flow = {
            "default_part": "EOS3FF512-PDN64",
            "values": {
                "top": self._build_name
            },
            "dependencies": {
                "sources": [
                    f"{self._build_name}.v"
                ],
                "synth_log": "synth.log",
                "pack_log": "pack.log",
                "analysis_log": "analysis.log"
            },
            "EOS3FF512-PDN64": {
                "default_target": "bitstream",
                "dependencies": {
                    "build_dir": self._build_dir,
                    "pcf": f"{self._build_name}.pcf",
                    "sdc-in": f"{self._build_name}_in.sdc"
                },
                "values": {
                    "part": self.platform.device,
                    "package": part
                }
            }
        };

        tools.write_to_file("flow.json", json.dumps(flow))
        return "flow.json"

    def run_script(self, script):
        make_cmd = ["f4pga", "-vvv", "build", "--flow", "flow.json"]

        if subprocess.call(make_cmd) != 0:
            raise OSError("Error occured during QuickLogic Symbiflow's script execution.")

        make_cmd.append("--target")
        for target in ["bitstream_openocd", "bitstream_jlink", "bitstream_bitheader", "bitstream_binary"]:
            if subprocess.call(make_cmd + [target]) != 0:
                raise OSError(f"Error occured during QuickLogic Symbiflow's script execution for step {target}.")
