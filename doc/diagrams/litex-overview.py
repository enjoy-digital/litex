#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-overview.svg: the LiteX design flow, for the wiki Home page. What goes in (Migen, the
LiteX framework and its cores ecosystem, the CPUs, the platform and target files you write), what
comes out (gateware for the FPGA toolchains or Verilator, the BIOS and software support files)
and how the result is used (FPGA board, host tools).

    python3 doc/diagrams/litex-overview.py            # -> doc/wiki/images/litex-overview.svg
    python3 doc/diagrams/build.py --only litex-overview   # + lint + PNG
"""

from litex_diagram import *

W, H = 1400, 760

DESC = ("The LiteX design flow. Inputs on the left: Migen (the Python HDL), the LiteX framework "
        "(SoC builder, interconnect, cores, build backends, software, tools), the LiteX cores "
        "ecosystem (LiteDRAM, LiteEth, LitePCIe, LiteSATA, LiteSDCard, LiteICLink, LiteJESD204, "
        "LiteSPI, LiteI2C, LiteScope), the CPUs (VexRiscv, VexiiRiscv, NaxRiscv, Rocket, Microwatt, "
        "SERV and more) and, at the bottom, the two files you write: the platform (board pins, "
        "clocks, toolchain, programmer) and the target (your SoC). The LiteX Builder in the middle "
        "produces the gateware (Verilog and constraints, compiled by the vendor or open-source "
        "toolchain to a bitstream, or by Verilator for simulation) and the software (BIOS, headers, "
        "memory map, CSR descriptions). On the right the bitstream runs on the FPGA board, which "
        "the host controls with the LiteX tools: litex_term for the console, litex_server and "
        "litex_cli through a UART, JTAG, Ethernet or PCIe bridge, LiteScope for signal capture.")

def draw(d):
    # Columns: inputs 20..320 | LiteX 370..760 | outputs 800..1100 | use 1140..1390.
    # Rows (box centres): 110 | 215 | 320 | 425 | 530.

    # Inputs: what LiteX is made of.
    d.box(20, 70, 320, 150, lines=[("Migen", 18, "bold"), ("Python HDL: Modules, Signals, FSMs", 13), ("simulation, Verilog generation", 13)])
    d.box(20, 175, 320, 255, lines=[("LiteX cores ecosystem", 18, "bold"), ("LiteDRAM · LiteEth · LitePCIe · LiteSATA", 13), ("LiteSDCard · LiteICLink · LiteJESD204 · LiteSPI", 13)])
    d.box(20, 280, 320, 360, lines=[("CPUs", 18, "bold"), ("VexRiscv · VexiiRiscv · NaxRiscv · Rocket", 13), ("Microwatt · SERV · Zynq/Agilex HPS · ...", 13)])
    d.box(20, 385, 320, 465, fill=KEY, lines=[("Platform file", 18, "bold"), ("board: pins, clocks, connectors,", 13), ("toolchain, programmer (LiteX-Boards)", 13)])
    d.box(20, 490, 320, 570, fill=KEY, lines=[("Target file", 18, "bold"), ("your SoC: CPU, memories, peripherals,", 13), ("cores, buses, software options", 13)])
    for y in (110, 215, 320, 425, 530):
        d.arrow([(320, y), (370, y)], thick=(y >= 425))

    # LiteX.
    d.box(370, 40, 760, 600, fill=FPGA, c=24)
    d.text(565, 72, "LiteX", 24, weight="bold")
    d.text(565, 92, "SoC builder framework", 14, style="italic")
    d.box(388, 110, 742, 170, fill=WHITE, lines=[("SoC builder", 16, "bold"), ("SoCCore · bus/CSR/IRQ handlers · add_*() API", 13)])
    d.box(388, 180, 742, 240, fill=WHITE, lines=[("Interconnect", 16, "bold"), ("Wishbone · AXI/AXI-Lite · CSR · Streams", 13)])
    d.box(388, 250, 742, 310, fill=WHITE, lines=[("Cores", 16, "bold"), ("UART · Timer · GPIO · SPI · I2C · Video · USB · ...", 13)])
    d.box(388, 320, 742, 380, fill=WHITE, lines=[("Build backends", 16, "bold"), ("Xilinx · Intel · Lattice · Gowin · Efinix · ... · Verilator", 13)])
    d.box(388, 390, 742, 450, fill=WHITE, lines=[("Software", 16, "bold"), ("BIOS · libc · generated headers · demo", 13)])
    d.box(388, 460, 742, 520, fill=WHITE, lines=[("Tools", 16, "bold"), ("litex_sim · litex_server · litex_term · litex_cli · ...", 13)])
    d.box(388, 530, 742, 580, fill=KEY, lines=[("Builder", 16, "bold"), ("generates, compiles, loads", 13)])

    # Outputs.
    d.arrow([(760, 215), (800, 215)], thick=True)
    d.arrow([(760, 425), (800, 425)], thick=True)
    d.box(800, 140, 1100, 290, fill=GROUP, c=18)
    d.text(950, 166, "Gateware", 18, weight="bold")
    d.box(815, 180, 1085, 230, lines=[("Verilog + constraints", 15, "bold"), ("top.v · .xdc/.lpf/.cst/.sdc", 13)])
    d.box(815, 236, 1085, 280, lines=[("Bitstream", 15, "bold"), ("vendor or open-source toolchain", 13)])
    d.box(800, 350, 1100, 500, fill=GROUP, c=18)
    d.text(950, 376, "Software", 18, weight="bold")
    d.box(815, 390, 1085, 440, lines=[("BIOS", 15, "bold"), ("boot: serial · Ethernet · flash · SD · SATA", 13)])
    d.box(815, 446, 1085, 490, lines=[("csr.h · soc.h · mem.h · memory.x", 14, "bold"), ("csr.csv/json/svd · DTS for Linux/Zephyr", 13)])

    # Use: board and host.
    d.arrow([(1100, 215), (1140, 215)], thick=True)
    d.text(1120, 203, "load", 12, style="italic")
    d.arrow([(1100, 425), (1140, 425)], thick=True)
    d.text(1120, 413, "boot", 12, style="italic")
    d.box(1140, 150, 1390, 290, fill=BOARD, c=18)
    d.text(1265, 176, "FPGA board", 18, weight="bold")
    d.box(1155, 190, 1375, 280, fill=HARD, lines=[("Your SoC", 15, "bold"), ("CPU + cores + memories", 13), ("Verilator for a simulation", 13)])
    d.box(1140, 360, 1390, 500, fill=BOARD, c=18)
    d.text(1265, 386, "Host", 18, weight="bold")
    d.box(1155, 400, 1375, 490, lines=[("litex_term · litex_server", 14, "bold"), ("UART/JTAG/Ethernet/PCIe bridges", 13), ("litex_cli · LiteScope · GDB", 13)])
    d.arrow([(1265, 360), (1265, 290)], double=True)
    d.text(1283, 330, "console, debug", 12, style="italic", anchor="start")

    # Caption and logo.
    d.caption(705, 660, "LiteX: build your hardware, easily!",
              "Describe the SoC in Python, LiteX generates the gateware and the software support, the toolchain builds the bitstream",
              "same SoC on Xilinx, Intel, Lattice, Gowin, Efinix, ... FPGAs, or in Verilator: open-source, BSD-2-Clause")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-overview", W, H, "LiteX design flow: from Python to a running SoC", DESC)
