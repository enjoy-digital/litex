#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-ecosystem-map.svg: the LiteX ecosystem at a glance, for the Home and Cores-Ecosystem
pages: the framework in the middle, the cores ecosystem, the CPUs, the boards, the software
running on the SoCs, the host tools, and the two GitHub homes (enjoy-digital, litex-hub).

    python3 doc/diagrams/litex-ecosystem-map.py       # -> doc/wiki/images/litex-ecosystem-map.svg
"""

from litex_diagram import *

W, H = 1400, 720

DESC = ("The LiteX ecosystem. In the centre, the LiteX framework (SoC builder, interconnect, in-tree "
        "cores, build backends, BIOS and software support, tools). Around it: the cores ecosystem "
        "(LiteDRAM, LiteEth, LitePCIe, LiteSATA, LiteSDCard, LiteICLink, LiteJESD204, LiteScope, "
        "LiteSPI, LiteI2C, LiteNVMe, LiteDSP, LiteHyperBus), the CPUs (soft RISC-V, OpenRISC, LM32, "
        "PowerPC, MIPS cores packaged as pythondata, and the hard CPUs of Zynq, Agilex and Cyclone V), "
        "LiteX-Boards with the platform and target files of 200+ boards, the software that runs on the "
        "SoCs (BIOS and bare metal, Linux, Zephyr, FreeRTOS, NuttX, MicroPython/CircuitPython, "
        "Renode and QEMU simulation) and the host tools. Enjoy-Digital maintains LiteX and most cores, "
        "LiteX-Hub hosts the collaborative projects.")

def draw(d):
    # Centre: the framework.
    d.box(460, 150, 940, 470, fill=FPGA, c=24)
    d.text(700, 186, "LiteX", 26, weight="bold")
    d.text(700, 208, "SoC builder framework · github.com/enjoy-digital/litex", 13, style="italic")
    d.box(480, 225, 700, 290, fill=WHITE, lines=[("SoC builder", 15, "bold"), ("SoCCore · add_*() · Builder", 12)])
    d.box(700, 225, 920, 290, fill=WHITE, lines=[("Interconnect", 15, "bold"), ("Wishbone · AXI · CSR · Streams", 12)])
    d.box(480, 290, 700, 355, fill=WHITE, lines=[("Cores", 15, "bold"), ("UART · Timer · GPIO · SPI · I2C · Video", 12)])
    d.box(700, 290, 920, 355, fill=WHITE, lines=[("Build backends", 15, "bold"), ("Xilinx · Intel · Lattice · Gowin · Efinix", 12)])
    d.box(480, 355, 700, 420, fill=WHITE, lines=[("Software", 15, "bold"), ("BIOS · libc · headers · DTS", 12)])
    d.box(700, 355, 920, 420, fill=WHITE, lines=[("Tools", 15, "bold"), ("litex_sim · litex_server · litex_term", 12)])
    d.text(700, 448, "Migen: the Python HDL underneath", 13, style="italic")

    # Left: cores ecosystem and CPUs.
    d.box(40, 60, 405, 330, fill=GROUP, c=18)
    d.text(222, 88, "LiteX cores ecosystem", 18, weight="bold")
    d.text(222, 106, "one repository per core, standalone generators", 12, style="italic")
    d.box(55, 120, 220, 165, fill=KEY, lines=[("LiteDRAM", 14, "bold"), ("SDRAM to DDR4, LPDDR4", 11)])
    d.box(225, 120, 390, 165, fill=KEY, lines=[("LiteEth", 14, "bold"), ("10M to 100G Ethernet", 11)])
    d.box(55, 170, 220, 215, fill=KEY, lines=[("LitePCIe · LiteNVMe", 13, "bold"), ("Gen1/2/3 DMA, NVMe host", 11)])
    d.box(225, 170, 390, 215, fill=KEY, lines=[("LiteSATA", 14, "bold"), ("Gen1/2/3, RAID", 11)])
    d.box(55, 220, 220, 265, fill=KEY, lines=[("LiteSDCard", 14, "bold"), ("SD card, eMMC", 11)])
    d.box(225, 220, 390, 265, fill=KEY, lines=[("LiteSPI · LiteI2C", 14, "bold"), ("(Q)SPI flash, I2C", 11)])
    d.box(55, 270, 220, 315, fill=KEY, lines=[("LiteICLink · LiteJESD204", 12, "bold"), ("SerDes links, JESD204B/C", 11)])
    d.box(225, 270, 390, 315, fill=KEY, lines=[("LiteScope · LiteDSP", 13, "bold"), ("logic analyzer, RF/DSP", 11)])
    d.arrow([(405, 240), (460, 240)], thick=True)

    d.box(40, 370, 405, 560, fill=GROUP, c=18)
    d.text(222, 398, "CPUs", 18, weight="bold")
    d.text(222, 416, "pythondata-cpu-* packages, --cpu-type / --cpu-variant", 12, style="italic")
    d.box(55, 430, 390, 485, lines=[("Soft RISC-V", 14, "bold"), ("VexRiscv · VexiiRiscv · NaxRiscv · Rocket", 11), ("SERV · Ibex · CVA6 · PicoRV32 · ...", 11)])
    d.box(55, 490, 220, 545, lines=[("Other soft ISAs", 13, "bold"), ("Microwatt (POWER) · Mor1kx", 11), ("LM32 · MIPS", 11)])
    d.box(225, 490, 390, 545, fill=HARD, lines=[("Hard CPUs", 13, "bold"), ("Zynq · ZynqMP", 11), ("Agilex · Cyclone V HPS", 11)])
    d.arrow([(405, 400), (460, 400)], thick=True)

    # Right: boards, software, host.
    d.box(1000, 60, 1360, 200, fill=GROUP, c=18)
    d.text(1180, 88, "LiteX-Boards", 18, weight="bold")
    d.text(1180, 106, "github.com/litex-hub/litex-boards", 12, style="italic")
    d.box(1015, 120, 1180, 185, fill=KEY, lines=[("Platforms", 14, "bold"), ("pins, clocks, connectors,", 11), ("toolchain, programmer", 11)])
    d.box(1185, 120, 1345, 185, fill=KEY, lines=[("Targets", 14, "bold"), ("reference SoCs: 200+", 11), ("boards, 9 FPGA vendors", 11)])
    d.arrow([(1000, 130), (900, 130), (900, 150)])

    d.box(1000, 240, 1360, 480, fill=GROUP, c=18)
    d.text(1180, 268, "Runs on the SoC", 18, weight="bold")
    d.box(1015, 285, 1180, 340, lines=[("BIOS · bare metal", 13, "bold"), ("demo app, libc,", 11), ("your firmware", 11)])
    d.box(1185, 285, 1345, 340, lines=[("Linux", 13, "bold"), ("VexRiscv-SMP, NaxRiscv,", 11), ("VexiiRiscv, Rocket, ...", 11)])
    d.box(1015, 345, 1180, 400, lines=[("RTOSes", 13, "bold"), ("Zephyr · FreeRTOS", 11), ("NuttX", 11)])
    d.box(1185, 345, 1345, 400, lines=[("MicroPython", 13, "bold"), ("Rust · MQuickJS", 11), ("OpenWrt, Debian, Xous", 11)])
    d.box(1015, 405, 1345, 460, lines=[("Simulation", 13, "bold"), ("Verilator (litex_sim) · Renode · QEMU co-simulation", 11)])
    d.arrow([(940, 360), (1000, 360)], thick=True)

    d.box(1000, 510, 1360, 600, fill=BOARD, c=18)
    d.text(1180, 538, "Host tools", 18, weight="bold")
    d.box(1015, 550, 1345, 590, lines=[("litex_term · litex_server · litex_cli · LiteScope", 13, "bold"),
                                       ("UART / JTAG / Ethernet / PCIe bridges, GDB over JTAG", 11)])
    d.arrow([(1180, 510), (1180, 480)], double=True)

    # Bottom: GitHub homes.
    d.box(460, 520, 690, 600, fill=BOARD, lines=[("github.com/enjoy-digital", 14, "bold"), ("LiteX, the cores, the products", 12), ("maintained by Enjoy-Digital", 12)])
    d.box(710, 520, 940, 600, fill=BOARD, lines=[("github.com/litex-hub", 14, "bold"), ("boards, pythondata, Linux/Zephyr ports", 12), ("collaborative projects", 12)])

    d.caption(700, 650, "The LiteX ecosystem",
              "a SoC builder, a family of cores with standalone generators, CPUs, 200+ boards, OSes and host tools: open source, BSD-2-Clause")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-ecosystem-map", W, H, "The LiteX ecosystem", DESC)
