#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-build-flow.svg: what the Builder does with a platform and a target, for the Build-Backends
and SoC-builder pages: the steps from the Python files to the bitstream and the software support,
and the output directory.

    python3 doc/diagrams/litex-build-flow.py   # -> doc/wiki/images/litex-build-flow.svg
"""

from litex_diagram import *

W, H = 1400, 700

DESC = ("The LiteX build flow. The platform file (pins, I/O standards, connectors, clocks, toolchain, "
        "programmer) and the target file (the SoC: CPU, memories, cores, buses) are Python; the "
        "Builder finalizes the SoC (address map, CSRs, interrupts, constants), generates the software "
        "support (csr.h, soc.h, mem.h, git.h, memory.x, csr.csv/json/svd, documentation), builds the "
        "BIOS with meson and the CPU's GCC, generates the gateware (top.v and the constraints file) and "
        "the toolchain script, runs the vendor or open-source toolchain (or Verilator) to the bitstream, "
        "and loads or flashes it with the programmer. Everything lands in build/<platform>/gateware "
        "and build/<platform>/software.")

def draw(d):
    # Inputs.
    d.box(30, 100, 300, 190, fill=KEY, lines=[("Platform file", 17, "bold"), ("pins · IOStandard · connectors", 13), ("default clock · toolchain · programmer", 13)])
    d.box(30, 230, 300, 320, fill=KEY, lines=[("Target file", 17, "bold"), ("the SoC: CPU, memories, cores,", 13), ("buses, options (--cpu-type, --with-...)", 13)])
    d.box(30, 360, 300, 430, lines=[("Builder options", 15, "bold"), ("--build · --load · --flash · --no-compile-*", 12), ("--soc-csv/json/svd · --doc · --build-bundle", 12)])
    d.arrow([(300, 145), (360, 145)])
    d.arrow([(300, 275), (360, 275)], thick=True)
    d.arrow([(300, 395), (360, 395)])

    # Builder steps.
    d.box(360, 40, 860, 560, fill=FPGA, c=24)
    d.text(610, 70, "Builder", 22, weight="bold")
    d.text(610, 90, "litex/soc/integration/builder.py", 13, style="italic")
    steps = [("1. Finalize the SoC", "address map, CSR banks, IRQs, constants, generated headers"),
             ("2. Software support", "csr.h · soc.h · mem.h · git.h · memory.x · csr.csv / json / svd"),
             ("3. BIOS and libraries", "meson + picolibc + the CPU's GCC (riscv64-unknown-elf-gcc, ...)"),
             ("4. Gateware", "top.v (Migen to Verilog) · constraints (.xdc/.lpf/.cst/.sdc) · toolchain script"),
             ("5. Toolchain", "vendor or open-source flow to the bitstream, or Verilator to a simulation binary"),
             ("6. Load or flash", "programmer: openFPGALoader, OpenOCD, vendor tools, DFU (--load / --flash)")]
    y = 110
    for title, sub in steps:
        d.box(380, y, 840, y + 60, fill=WHITE if "Toolchain" not in title else HARD, lines=[(title, 15, "bold"), (sub, 12)])
        if y > 110:
            pass
        y += 72
    for yy in (170, 242, 314, 386, 458):
        d.arrow([(610, yy), (610, yy + 12)])

    # Outputs.
    d.box(920, 40, 1370, 560, fill=GROUP, c=24)
    d.text(1145, 70, "build/<platform>/", 20, weight="bold")
    d.text(1145, 90, "--output-dir", 13, style="italic")
    d.box(940, 110, 1350, 240, lines=[("gateware/", 15, "bold"), ("<platform>.v · <platform>.xdc / .lpf / .cst / .sdc", 12), ("build_<platform>.sh / .tcl · <platform>.bit / .svf / .fs / .sof", 12), ("mem.init files · litex.log", 12)])
    d.box(940, 260, 1350, 410, lines=[("software/", 15, "bold"), ("include/generated/: csr.h · soc.h · mem.h · git.h · variables.mak", 12), ("include/generated/: output_format.ld · regions.ld · memory.x", 12), ("bios/: bios.elf · bios.bin · libc, liblitedram, libliteeth, ...", 12)])
    d.box(940, 430, 1350, 540, lines=[("csr.csv · csr.json · csr.svd · doc/", 15, "bold"), ("the memory map and registers for litex_cli, litex_term,", 12), ("the DTS generators (Linux, Zephyr, Renode), svd2rust, Sphinx docs", 12)])
    d.arrow([(840, 325), (920, 325)], thick=True)
    d.arrow([(840, 181), (920, 181)], thick=True)
    d.arrow([(840, 485), (920, 485)], thick=True)

    d.caption(700, 610, "From two Python files to a running SoC",
              "python3 target.py --build --load: the Builder generates, compiles, loads; --no-compile-gateware for the software support only")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-build-flow", W, H, "The LiteX build flow", DESC)
