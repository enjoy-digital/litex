#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-simulation.svg: litex_sim, for the SoC-Simulator page: the SoC compiled by Verilator and
the C models around it, the host tools that talk to it, the QEMU co-simulation.

    python3 doc/diagrams/litex-simulation.py   # -> doc/wiki/images/litex-simulation.svg
"""

from litex_diagram import *

W, H = 1400, 640

DESC = ("litex_sim: the same SoC as on a board (CPU, BIOS, buses, cores) compiled to C++ by Verilator "
        "and run on the host, with C models for the outside world: the clock generator, the serial "
        "console on the terminal or a TCP port, DRAM chips for LiteDRAM, Ethernet on a TAP interface "
        "(MII, GMII or XGMII models), an SD card, an SPI flash, an I2C SPD EEPROM, a video window, "
        "OpenOCD remote_bitbang servers on the CPU's JTAG/SWD, and the QEMU bridge. The host tools work "
        "as on hardware: litex_term, litex_server/litex_cli through Etherbone on the TAP, LiteScope, GDB; "
        "the waveforms are dumped to VCD/FST and opened in GTKWave with a generated save file. With "
        "--cpu-type=qemu the CPU runs in QEMU and the gateware in Verilator.")

def draw(d):
    d.box(30, 40, 1370, 520, fill=BOARD, c=26)
    d.text(700, 70, "Your computer: litex_sim", 22, weight="bold")

    # Verilator box with the SoC.
    d.box(60, 100, 760, 490, fill=FPGA, c=22)
    d.text(410, 128, "Verilator: the SoC compiled to C++", 17, weight="bold")
    d.text(410, 146, "the same gateware as on the board, SimPlatform, 1 MHz sys_clk by default", 12, style="italic")
    d.box(80, 165, 300, 240, fill=KEY, lines=[("CPU + BIOS", 15, "bold"), ("VexRiscv, ..., or any CPU", 12), ("ROM, SRAM, --ram-init", 12)])
    d.box(320, 165, 540, 240, fill=KEY, lines=[("Main bus + CSRs", 15, "bold"), ("Wishbone / AXI, timeout", 12), ("sim_trace · sim_marker · sim_finish", 12)])
    d.box(560, 165, 740, 240, fill=KEY, lines=[("Cores", 15, "bold"), ("LiteDRAM · LiteEth", 12), ("LiteSDCard · LiteSPI · video", 12)])
    d.box(80, 270, 740, 330, fill=WHITE, c=16, lines=[("Sim PHYs and pads: serial, sdram, eth, sdcard, spiflash, i2c, video, jtag, gpio", 13, "bold"),
                                                       ("the pads of the SimPlatform become the signals of the C models", 12)])
    d.arrow([(410, 330), (410, 360)], double=True, thick=True)
    d.box(80, 360, 740, 470, fill=GROUP, c=16)
    d.text(410, 383, "C models (litex/build/sim/core/modules, SimConfig.add_module)", 13, weight="bold")
    d.text(410, 403, "clocker · serial2console / serial2tcp · ethernet / gmii_ethernet / xgmii_ethernet (TAP)", 12)
    d.text(410, 421, "spdeeprom (I2C) · video (SDL window) · jtagremote / swdremote (OpenOCD) · sim_perf · qemu_axi", 12)
    d.text(410, 445, "DRAM chips, SD card and SPI flash are Migen/LiteX models inside the gateware (sdram_init, spi_flash-init)", 11, style="italic")

    # Right: host side.
    d.box(800, 100, 1340, 240, fill=GROUP, c=18)
    d.text(1070, 128, "Host tools, as on hardware", 16, weight="bold")
    d.text(1070, 150, "terminal = the BIOS console (serial2console), or litex_term on --uart-pty / --uart-tcp", 12)
    d.text(1070, 170, "litex_server --udp through the TAP interface (--with-etherbone), litex_cli, LiteScope", 12)
    d.text(1070, 190, "OpenOCD + GDB on --with-jtagremote (remote_bitbang)", 12)
    d.text(1070, 212, "network: TAP tap0, 192.168.1.50 (SoC) / 192.168.1.100 (host), needs sudo", 11, style="italic")
    d.arrow([(760, 170), (800, 170)], double=True, thick=True)

    d.box(800, 270, 1340, 360, fill=GROUP, c=18)
    d.text(1070, 298, "Waveforms", 16, weight="bold")
    d.text(1070, 320, "--trace / --trace-fst, --trace-start / --trace-end (ps), sim_trace CSRs from software", 12)
    d.text(1070, 340, "--gtkwave-savefile: sim.gtkw with the buses and DRAM phases grouped and colored", 12)
    d.arrow([(760, 315), (800, 315)], thick=True)

    d.box(800, 390, 1340, 490, fill=GROUP, c=18)
    d.text(1070, 418, "QEMU co-simulation (--cpu-type=qemu)", 16, weight="bold")
    d.text(1070, 440, "the CPU, CLINT and PLIC in a patched QEMU (rv32 / rv64), the gateware in Verilator,", 12)
    d.text(1070, 458, "bridged on the CPU bus (qemu_axi, TCP); main RAM shared as a file for the DMAs; boots Linux", 12)
    d.arrow([(760, 440), (800, 440)], double=True, thick=True)

    d.caption(700, 575, "A LiteX SoC without a board", "litex_sim --cpu-type=vexriscv --with-sdram --with-ethernet --trace: build, boot the BIOS, run your firmware, look inside")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-simulation", W, H, "LiteX SoC simulation with Verilator", DESC)
