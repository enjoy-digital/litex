#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-cpu-families.svg: the CPUs LiteX supports, by family, for Choosing-A-CPU: the Linux-capable
RISC-V cores, the MCU-class ones, the tiny ones, the other ISAs, the hard CPUs and the emulator.
The names are the ones of litex/soc/cores/cpu/ (--cpu-type).

    python3 doc/diagrams/litex-cpu-families.py   # -> doc/wiki/images/litex-cpu-families.svg
"""

from litex_diagram import *

W, H = 1200, 600

DESC = ("The CPU families of LiteX. Linux-capable RISC-V: vexriscv_smp (32-bit, 1 to 8 cores), naxriscv "
        "(out-of-order, 64-bit), vexiiriscv (64-bit, Debian), rocket (RV64GC), cva6, openc906, blackparrot, "
        "and the linux variant of vexriscv. MCU-class RISC-V: vexriscv (the default), neorv32, ibex, "
        "cv32e40p and cv32e41p, cva5, veer_eh1, picorv32, coreblocks, kianv, urv, minerva, firev. Tiny "
        "RISC-V: serv (bit-serial), fazyrv, femtorv, sentinel. Other ISAs: mor1kx and marocchino (OpenRISC), "
        "lm32, microwatt (POWER), cdim and gs232 (MIPS), cortex_m1 and cortex_m3 (Arm). Hard CPUs: zynq7000, "
        "zynqmp, cyclonev_hps, agilex_hps, eos_s3, gowin_emcu, gowin_ae350. Emulator: qemu. --cpu-type picks "
        "one, --cpu-variant its configuration; the BIOS, the firmware and the tools follow.")

def draw(d):
    # Soft RISC-V, three classes.
    d.box(30, 40, 1170, 330, fill=GROUP, c=20)
    d.text(600, 68, "Soft RISC-V cores", 18, weight="bold")
    d.text(600, 86, "synthesized in the fabric, one pythondata-cpu-* package or generated at build time", 12, style="italic")
    d.box(50, 100, 410, 310, fill=KEY, lines=[
        ("Linux-capable", 15, "bold"),
        ("vexriscv_smp: 32-bit, 1 to 8 cores, FPU, coherent DMA", 12),
        ("naxriscv: out-of-order, 32 or 64-bit", 12),
        ("vexiiriscv: 64-bit, Linux and Debian, the current line", 12),
        ("rocket: RV64GC, Chisel, upstream Linux", 12),
        ("cva6: RV64GC, OpenHW", 12),
        ("openc906: RV64GCV, T-Head", 12),
        ("blackparrot: RV64, multicore", 12),
        ("vexriscv linux: 32-bit, the historical one", 12),
    ])
    d.box(430, 100, 790, 310, fill=KEY, lines=[
        ("MCU-class", 15, "bold"),
        ("vexriscv: the default, ~1000 LUTs and up", 12),
        ("neorv32: its own peripherals, Zephyr, VHDL", 12),
        ("ibex, cv32e40p, cv32e41p: lowRISC and OpenHW", 12),
        ("cva5, veer_eh1: multicore, AXI", 12),
        ("picorv32: small, slow, robust", 12),
        ("coreblocks, minerva, sentinel: Amaranth", 12),
        ("kianv, urv, firev: Verilog, Silice", 12),
    ])
    d.box(810, 100, 1150, 310, fill=KEY, lines=[
        ("Tiny", 15, "bold"),
        ("serv: bit-serial, a few hundred LUTs", 12),
        ("fazyrv: chunked, between serial and full", 12),
        ("femtorv quark to petitbateau: teaching cores", 12),
        ("sentinel: microcoded", 12),
        ("", 12),
        ("for the BIOS and control firmware", 12, None, "italic"),
        ("on the smallest FPGAs", 12, None, "italic"),
    ])

    # Other ISAs, hard CPUs, emulator.
    d.box(30, 350, 500, 490, fill=GROUP, c=18, lines=[
        ("Other soft ISAs", 15, "bold"),
        ("mor1kx, marocchino: OpenRISC, upstream Linux", 12),
        ("microwatt: POWER, VHDL, upstream Linux", 12),
        ("lm32: the MiSoC CPU", 12),
        ("cdim, gs232: MIPS", 12),
        ("cortex_m1, cortex_m3: Arm DesignStart, your own RTL", 12),
    ])
    d.box(520, 350, 920, 490, fill=HARD, c=18, lines=[
        ("Hard CPUs of SoC-FPGAs", 15, "bold"),
        ("zynq7000, zynqmp: Arm Cortex-A9, A53 and R5", 12),
        ("cyclonev_hps, agilex_hps: Intel HPS", 12),
        ("eos_s3, gowin_emcu: Cortex-M4F and M3", 12),
        ("gowin_ae350: AndesCore RISC-V", 12),
        ("the BIOS runs on them too", 12, None, "italic"),
    ])
    d.box(940, 350, 1170, 490, fill=BOARD, c=18, lines=[
        ("Emulator", 15, "bold"),
        ("qemu: the CPU in QEMU,", 12),
        ("the SoC in Verilator", 12),
        ("(co-simulation)", 12),
    ])

    d.caption(600, 530, "Thirty-two soft CPUs, seven hard ones, one emulator",
              "--cpu-type picks one, --cpu-variant its configuration; the BIOS, the firmware and the tools follow")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-cpu-families", W, H, "The CPU families supported by LiteX", DESC)
