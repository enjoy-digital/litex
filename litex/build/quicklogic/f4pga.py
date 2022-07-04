#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2021 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import subprocess
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build.generic_toolchain import GenericToolchain
from litex.build import tools
from litex.build.quicklogic import common


# F4PGAToolchain -------------------------------------------------------------------------------
# Formerly SymbiflowToolchain, Symbiflow has been renamed to F4PGA -----------------------------

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

    # Build Makefile -------------------------------------------------------------------------------

    def build_script(self):
        makefile = []

        # Define Paths.
        makefile.append("mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))")
        makefile.append("current_dir := $(patsubst %/,%,$(dir $(mkfile_path)))")
        # bit -> h and bit -> bin requires TOP_F
        makefile.append(f"TOP_F={self._build_name}")

        # Create Project.
        # FIXME: Only use top file for now and ignore .init files.
        makefile.append("all: {top}_bit.h {top}.bin build/{top}.bit".format(top=self._build_name))
        # build bit file (default)
        makefile.append(f"build/{self._build_name}.bit:")
        makefile.append("\tql_symbiflow -compile -d {device} -P {part} -v {verilog} -t {top} -p {pcf}".format(
            device  = self.platform.device,
            part    = {"ql-eos-s3": "PU64"}.get(self.platform.device),
            verilog = f"{self._build_name}.v",
            top     = self._build_name,
            pcf     = f"{self._build_name}.pcf"
        ))
        # build header to include in CPU firmware
        makefile.append("{top}_bit.h: build/{top}.bit".format(top=self._build_name))
        makefile.append(f"\t(cd build; TOP_F=$(TOP_F) symbiflow_write_bitheader)")
        # build binary to write in dedicated FLASH area
        makefile.append("{top}.bin: build/{top}.bit".format(top=self._build_name))
        makefile.append(f"\t(cd build; TOP_F=$(TOP_F) symbiflow_write_binary)")

        # Generate Makefile.
        tools.write_to_file("Makefile", "\n".join(makefile))

        return "Makefile"

    def run_script(self, script):
        make_cmd = ["make", "-j1"]

        if which("ql_symbiflow") is None:
            msg = "Unable to find QuickLogic Symbiflow toolchain, please:\n"
            msg += "- Add QuickLogic Symbiflow toolchain to your $PATH."
            raise OSError(msg)

        if subprocess.call(make_cmd) != 0:
            raise OSError("Error occured during QuickLogic Symbiflow's script execution.")
