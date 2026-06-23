#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2020-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import argparse

from litex.build.tools import replace_in_file


def _update_linker_regions(filename, mem, runtime_mem):
    mem_placeholder         = "__LITEX_DEMO_MEM__"
    runtime_mem_placeholder = "__LITEX_DEMO_RUNTIME_MEM__"
    replacements = [
        ("> sram AT > main_ram", f"> {runtime_mem_placeholder} AT > {mem_placeholder}"),
        ("> sram\n", f"> {runtime_mem_placeholder}\n"),
        (
            "ORIGIN(sram) + LENGTH(sram)",
            f"ORIGIN({runtime_mem_placeholder}) + LENGTH({runtime_mem_placeholder})",
        ),
        ("> main_ram", f"> {mem_placeholder}"),
        (runtime_mem_placeholder, runtime_mem),
        (mem_placeholder, mem),
    ]

    for old, new in replacements:
        replace_in_file(filename, old, new)


def main():
    parser = argparse.ArgumentParser(description="LiteX Bare Metal Demo App.")
    parser.add_argument("--build-path",  required=True,      help="Target's build path (ex build/board_name).")
    parser.add_argument("--with-cxx",    action="store_true", help="Enable CXX support.")
    parser.add_argument("--mem",         default="main_ram",  help="Memory Region where code will be loaded/executed.")
    parser.add_argument("--runtime-mem", default="sram",      help="Memory Region for .data/.bss/stack.")
    args = parser.parse_args()

    # Create demo directory
    os.makedirs("demo", exist_ok=True)

    # Copy contents to demo directory
    os.system(f"cp {os.path.abspath(os.path.dirname(__file__))}/* demo")
    os.system("chmod -R u+w demo") # Nix specific: Allow linker script to be modified.

    # Update memory regions.
    _update_linker_regions("demo/linker.ld", args.mem, args.runtime_mem)

    # Compile demo
    build_path = args.build_path if os.path.isabs(args.build_path) else os.path.join("..", args.build_path)
    os.system(f"export BUILD_DIR={build_path} && {'export WITH_CXX=1 &&' if args.with_cxx else ''} cd demo && make")

    # Copy demo.bin
    os.system("cp demo/demo.bin ./")

    # Prepare flash boot image.
    python3 = sys.executable or "python3" # Nix specific: Reuse current Python executable if available.
    os.system(f"{python3} -m litex.soc.software.crcfbigen demo.bin -o demo.fbi --fbi --little") # FIXME: Endianness.

if __name__ == "__main__":
    main()
