#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Build the prebuilt firmware of the firmware_blob task (../workspace/firmware/sampler.bin) against
# the reference SoC (the workspace target with the reference solution applied):
#   PYTHONPATH=<litex> python3 test/agent_eval/tasks/firmware_blob/firmware_src/make_firmware.py

import os
import sys
import shutil
import tempfile
import subprocess
import importlib.util

SRC_DIR  = os.path.dirname(os.path.abspath(__file__))
TASK_DIR = os.path.dirname(SRC_DIR)

def main():
    with tempfile.TemporaryDirectory() as tmp:
        # Reference target.
        shutil.copy(os.path.join(TASK_DIR, "workspace", "target.py"), tmp)
        spec = importlib.util.spec_from_file_location("solution", os.path.join(TASK_DIR, "solution.py"))
        solution = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(solution)
        solution.solve(tmp)
        spec = importlib.util.spec_from_file_location("target", os.path.join(tmp, "target.py"))
        target = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(target)

        # Software headers/libraries of the reference SoC (no gateware).
        from litex.soc.integration.builder import Builder
        build_dir = os.path.join(tmp, "build")
        soc = target.SamplerSoC(firmware=None)
        Builder(soc, output_dir=build_dir, compile_gateware=False).build(run=False)

        # Firmware.
        fw_dir = os.path.join(tmp, "fw")
        os.makedirs(fw_dir)
        subprocess.run(["make", "-C", fw_dir, "-f", os.path.join(SRC_DIR, "Makefile"),
            f"BUILD_DIR={build_dir}", f"SRC_DIR={SRC_DIR}"], check=True)
        out = os.path.join(TASK_DIR, "workspace", "firmware", "sampler.bin")
        shutil.copy(os.path.join(fw_dir, "sampler.bin"), out)
        print(f"{out}: {os.path.getsize(out)} bytes")

if __name__ == "__main__":
    main()
