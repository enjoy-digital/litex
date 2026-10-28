#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-complex-soc.svg: a Linux-capable SoC built with the cores of the ecosystem, for the
Create-A-complex-SoC and Run-Linux pages: what each add_* call brings, on the Arty A7.

    python3 doc/diagrams/litex-complex-soc.py   # -> doc/wiki/images/litex-complex-soc.svg
"""

from litex_diagram import *

W, H = 1400, 820

DESC = ("A Linux-capable LiteX SoC on the Digilent Arty A7. Inside the FPGA: a VexRiscv (linux "
        "variant, MMU) with its instruction and data buses on the main bus, the ROM with the BIOS, "
        "the SRAM, the CSR bridge, and the cores added by the target: LiteDRAM (add_sdram) with its "
        "L2 cache and the DDR3 PHY driving the board's DDR3 chip, LiteEth (add_ethernet) with the MII "
        "PHY to the Ethernet transceiver of the board, LiteSDCard (add_sdcard) with its DMAs to the "
        "SD card slot, LiteSPI (add_spi_flash) to the configuration flash, the UART, timer, XADC, "
        "LEDs and GPIOs. Each core brings a BIOS command, a boot method, a Linux driver.")

def draw(d):
    d.box(30, 20, 1370, 600, fill=FPGA, c=30)
    d.text(60, 47, "Artix-7 FPGA: Digilent Arty A7", 18, anchor="start", weight="bold", style="italic")

    # CPU and memories (top).
    d.box(60, 60, 380, 150, fill=KEY, lines=[("VexRiscv (linux variant)", 17, "bold"), ("--cpu-type=vexriscv --cpu-variant=linux", 12), ("MMU · caches · ibus / dbus", 12)])
    d.box(420, 60, 640, 150, fill=MEM, lines=[("ROM · SRAM", 16, "bold"), ("BIOS (128 KiB) · 8 KiB", 12), ("integrated_rom / sram", 12)])
    d.box(680, 60, 940, 150, lines=[("UART · Timer · XADC · LEDs", 14, "bold"), ("console, IRQs, temperature", 12), ("--with-xadc, LedChaser", 12)])
    d.box(980, 60, 1340, 150, lines=[("CSR bridge", 16, "bold"), ("csr region 0xf0000000", 12), ("the registers of every core", 12)])
    for x in (220, 530, 810, 1160):
        d.arrow([(x, 150), (x, 210)], double=True, thick=(x in (220,)))

    # Main bus.
    d.box(60, 210, 1340, 270, fill=KEY, c=18, lines=[("Main bus: Wishbone 32-bit, shared, 1 MHz timeout", 17, "bold"), ("masters: cpu_bus0, cpu_bus1, sdcard_block2mem, sdcard_mem2block · slaves: rom, sram, main_ram, ethmac_rx/tx, spiflash, csr", 12)])

    # Ecosystem cores (middle row).
    cores = [(60, 350, "LiteDRAM", "add_sdram(phy, module)", ["L2 cache 8 KiB", "controller + A7DDRPHY", "main_ram 0x40000000, 256 MiB"], True),
             (390, 650, "LiteEth", "add_ethernet(phy, local_ip)", ["MAC, 2+2 slots (ethmac region)", "MII PHY · IRQ", "netboot · ping · Linux liteeth"], False),
             (690, 950, "LiteSDCard", "add_sdcard()", ["block2mem / mem2block DMAs", "4-bit SD, BIST · IRQ", "sdcardboot · Linux litex_mmc"], False),
             (990, 1340, "LiteSPI", "add_spi_flash(mode, module)", ["spiflash region 0x01000000 (XIP)", "4x, 1:2 rate · master", "flashboot · flash_write"], False)]
    for x1, x2, title, call, lines, thick in cores:
        d.box(x1, 330, x2, 470, fill=GROUP, c=18)
        d.text((x1 + x2)/2, 356, title, 17, weight="bold")
        d.text((x1 + x2)/2, 374, call, 12, style="italic")
        d.text_lines((x1 + x2)/2, 425, [(l, 12) for l in lines])
        d.arrow([((x1 + x2)/2, 270), ((x1 + x2)/2, 330)], double=True, thick=thick)

    # Outside the FPGA (bottom row).
    outs = [(60, 350, "DDR3 chip", "MT41K128M16, 16-bit, 800 MT/s"),
            (390, 650, "Ethernet PHY", "TI DP83848, 100 Mbps MII"),
            (690, 950, "SD card slot", "Pmod or on-board, 4-bit"),
            (990, 1340, "SPI flash", "S25FL128L, 16 MiB, QSPI")]
    for x1, x2, t, s in outs:
        d.box(x1, 640, x2, 700, fill=BOARD, lines=[(t, 15, "bold"), (s, 12)])
        d.arrow([((x1 + x2)/2, 470), ((x1 + x2)/2, 500)], double=True, thick=(x1 == 60))
        d.box(x1, 500, x2, 560, fill=HARD, lines=[("PHY · I/Os", 13, "bold"), ("the board's pins", 11)])
        d.arrow([((x1 + x2)/2, 560), ((x1 + x2)/2, 640)], double=True, thick=(x1 == 60))
    d.text(217, 585, "sys4x · sys4x_dqs · idelay clocks", 11, anchor="start", style="italic")
    d.text(532, 585, "eth_clocks (25 MHz ref)", 11, anchor="start", style="italic")
    d.text(832, 585, "sdcard pads", 11, anchor="start", style="italic")
    d.text(1177, 585, "spiflash4x pads", 11, anchor="start", style="italic")

    d.text(700, 732, "python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv --cpu-variant=linux --with-ethernet --with-sdcard --with-spi-flash --with-xadc --build --load", 12, style="italic")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-complex-soc", W, H, "A Linux-capable LiteX SoC with the ecosystem cores", DESC)
