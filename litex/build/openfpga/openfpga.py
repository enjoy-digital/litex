#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import subprocess
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.openfpga import common

# Check Setup --------------------------------------------------------------------------------------

def _check_setup():
    if os.getenv("LITEX_ENV_OPENFPGA", False) == False:
        msg = "Unable to find OpenFPGA toolchain, please:\n"
        msg += "- Set LITEX_ENV_OPENFPGA environment variant to OpenFPGA's settings path.\n"
        raise OSError(msg)

    if os.getenv("LITEX_ENV_OPENFPGA_SOFA", False) == False:
        msg = "Unable to find OpenFPGA's SOFA project, please:\n"
        msg += "- Set LITEX_ENV_OPENFPGA_SOFA environment variant to OpenFPGA's SOFA settings path.\n"
        raise OSError(msg)

# Task Config  -------------------------------------------------------------------------------------

def _build_task_conf(platform, sources, build_dir, build_name):
    # Get Environnment variables.
    openfpga_path      = os.getenv("LITEX_ENV_OPENFPGA")
    openfpga_sofa_path = os.getenv("LITEX_ENV_OPENFPGA_SOFA")

    # Get PnR/Task directories from OPENFPGA/SOFA paths.
    pnr_path  = os.path.join(openfpga_sofa_path, platform.device + "_PNR")
    task_path = os.path.join(pnr_path, platform.device + "_task")

    # Get Config file.
    task_conf = os.path.join(task_path, "config", "task_simulation.conf")

    # Helpers.
    def replace_openfpga_task_section(filename, section, contents):
        lines = []
        # Read file and replace section with contents.
        copy  = True
        for line in open(filename, "r"):
            if not copy and line.startswith("["):
                copy = True
            if line.startswith(section):
                copy = False
                lines.append(section + "\n")
                for l in contents:
                    lines.append(l + "\n")
                lines.append("\n")
            if copy:
                lines.append(line)

        # Save file to .orig.
        os.system(f"mv {filename} {filename}.orig")

        # Write file with replaced section.
        with open(filename, "w") as f:
            f.write("".join(lines))

    # Add sources.
    bench_sources = []
    for filename, language, library in sources:
        if language is None:
            continue
        if language not in ["verilog"]:
            raise ValueError("OpenFPGA flow only supports verilog")
        bench_sources.append(filename)
    replace_openfpga_task_section(task_conf, "[BENCHMARKS]", [f"bench0={' '.join(bench_sources)}"])

    # Set Top-Level.
    replace_openfpga_task_section(task_conf, "[SYNTHESIS_PARAM]", [f"bench0_top={build_name}"])

def _run_task(device):
    # Get Environnment variables.
    openfpga_path      = os.getenv("LITEX_ENV_OPENFPGA")
    openfpga_sofa_path = os.getenv("LITEX_ENV_OPENFPGA_SOFA")

    # Get PnR/Task directories from OPENFPGA/SOFA paths.
    pnr_path  = os.path.join(openfpga_sofa_path, device + "_PNR")
    task_path = os.path.join(pnr_path, device + "_task")

    # Set OPENFPGA_PATH.
    os.environ["OPENFPGA_PATH"] = os.getenv("LITEX_ENV_OPENFPGA")

    # Run OpenFPGA flow.
    build_cmd = ["make", "-C", pnr_path, "clean", "runOpenFPGA"]
    if subprocess.call(build_cmd) != 0:
        raise OSError("Error occured during OpenFPGA's flow execution.")

    # Copy artifacts.
    os.system("rm -rf run001")
    os.system(f"cp -r {task_path}/run001 run001")

    # Display log. FIXME: Do it during build?
    os.system("cat run001/vpr_arch/top/MIN_ROUTE_CHAN_WIDTH/openfpgashell.log")

# OpenFPGAToolchain --------------------------------------------------------------------------------

class OpenFPGAToolchain:
    attr_translate = {}

    special_overrides = common.openfpga_special_overrides

    def __init__(self):
        self.clocks      = dict()
        self.false_paths = set()

    def build(self, platform, fragment,
        build_dir  = "build",
        build_name = "top",
        run        = False,
        **kwargs):

        # Create Build Directory.
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # Finalize Design.
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        # Generate Verilog.
        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        named_sc, named_pc = platform.resolve_signals(v_output.ns)
        top_file = build_name + ".v"
        v_output.write(top_file)
        platform.add_source(top_file)

        # Check Setup.
        _check_setup()

        # Generate Task Config.
        _build_task_conf(platform, platform.sources, build_dir, build_name)

        # Run Task.
        if run:
            _run_task(platform.device)

        os.chdir(cwd)

        return v_output.ns
