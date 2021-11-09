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
from litex.build import tools
from litex.build.quicklogic import common


# IO Constraints (.pcf) ----------------------------------------------------------------------------

def _format_io_pcf(signame, pin, others):
    r = f"set_io {signame} {Pins(pin).identifiers[0]}\n"
    return r

def _build_io_pcf(named_sc, named_pc, build_name):
    pcf = ""
    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                pcf += _format_io_pcf(sig + "(" + str(i) + ")", p, others)
        else:
            pcf += _format_io_pcf(sig, pins[0], others)
    tools.write_to_file(build_name + ".pcf", pcf)

# Build Makefile -----------------------------------------------------------------------------------

def _build_makefile(platform, sources, build_dir, build_name):
    makefile = []

    # Define Paths.
    makefile.append("mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))")
    makefile.append("current_dir := $(patsubst %/,%,$(dir $(mkfile_path)))")
    # bit -> h and bit -> bin requires TOP_F
    makefile.append(f"TOP_F={build_name}")

    # Create Project.
    # FIXME: Only use top file for now and ignore .init files.
    makefile.append("all: {top}_bit.h {top}.bin build/{top}.bit".format(top=build_name))
    # build bit file (default)
    makefile.append(f"build/{build_name}.bit:")
    makefile.append("\tql_symbiflow -compile -d {device} -P {part} -v {verilog} -t {top} -p {pcf}".format(
        device  = platform.device,
        part    = {"ql-eos-s3": "PU64"}.get(platform.device),
        verilog = f"{build_name}.v",
        top     = build_name,
        pcf     = f"{build_name}.pcf"
    ))
    # build header to include in CPU firmware
    makefile.append("{top}_bit.h: build/{top}.bit".format(top=build_name))
    makefile.append(f"\t(cd build; TOP_F=$(TOP_F) symbiflow_write_bitheader)")
    # build binary to write in dedicated FLASH area
    makefile.append("{top}.bin: build/{top}.bit".format(top=build_name))
    makefile.append(f"\t(cd build; TOP_F=$(TOP_F) symbiflow_write_binary)")

    # Generate Makefile.
    tools.write_to_file("Makefile", "\n".join(makefile))

def _run_make():
    make_cmd = ["make", "-j1"]

    if which("ql_symbiflow") is None:
        msg = "Unable to find QuickLogic Symbiflow toolchain, please:\n"
        msg += "- Add QuickLogic Symbiflow toolchain to your $PATH."
        raise OSError(msg)

    if subprocess.call(make_cmd) != 0:
        raise OSError("Error occured during QuickLogic Symbiflow's script execution.")


# SymbiflowToolchain -------------------------------------------------------------------------------

class SymbiflowToolchain:
    attr_translate = {}

    special_overrides = common.quicklogic_special_overrides

    def __init__(self):
        self.clocks      = dict()
        self.false_paths = set()

    def build(self, platform, fragment,
            build_dir  = "build",
            build_name = "top",
            run        = False,
            **kwargs):

        # Create build directory.
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # Finalize design.
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        # Generate verilog.
        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        named_sc, named_pc = platform.resolve_signals(v_output.ns)
        top_file = build_name + ".v"
        v_output.write(top_file)
        platform.add_source(top_file)

        # Generate .pcf IO constraints file.
        _build_io_pcf(named_sc, named_pc, build_name)

        # Generate Makefie.
        _build_makefile(platform, platform.sources, build_dir, build_name)

        # Run.
        if run:
            _run_make()

        os.chdir(cwd)

        return v_output.ns
