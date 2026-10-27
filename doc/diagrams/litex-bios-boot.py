#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-bios-boot.svg: what happens between the reset and the application, for the BIOS page:
the BIOS start-up, the boot methods in their order and where the application comes from.

    python3 doc/diagrams/litex-bios-boot.py   # -> doc/wiki/images/litex-bios-boot.svg
"""

from litex_diagram import *

W, H = 1400, 700

DESC = ("The LiteX BIOS boot flow. At reset the CPU starts in the ROM where the Builder placed the "
        "BIOS. The BIOS initializes the console, prints the banner and the SoC summary, initializes the "
        "memories and peripherals present in the SoC (DRAM calibration and memtest, Ethernet, flash, "
        "SD card, SATA), then tries the boot methods in order: serial (litex_term --kernel, SFL "
        "protocol), SPI flash image, ROM address, SD card, SATA and network (TFTP), each loading "
        "boot.bin or the images of boot.json into main RAM before jumping to the application: a "
        "bare-metal firmware, an RTOS or OpenSBI + Linux. When nothing boots, the BIOS console is "
        "available with its memory, DRAM, Ethernet, storage and flash commands.")

def draw(d):
    # Left: reset and BIOS.
    d.box(30, 60, 250, 120, fill=HARD, lines=[("Reset", 17, "bold"), ("CPU starts at the reset address", 12)])
    d.arrow([(140, 120), (140, 160)])
    d.box(30, 160, 250, 230, fill=MEM, lines=[("ROM", 17, "bold"), ("bios.bin placed by the Builder", 12), ("(integrated_rom, or SPI flash XIP)", 12)])
    d.arrow([(250, 195), (310, 195)], thick=True)

    d.box(310, 40, 700, 560, fill=GROUP, c=24)
    d.text(505, 70, "LiteX BIOS", 22, weight="bold")
    d.text(505, 90, "litex/soc/software/bios", 13, style="italic")
    steps = [("1. Console and banner", "UART, build date, CRC, git sha1, SoC summary"),
             ("2. Initialization", "DRAM calibration + memtest, HyperRAM, Ethernet (DHCP),"),
             ("", "SPI flash, SD card, SATA, framebuffer: what the SoC has"),
             ("3. Boot sequence", "the boot methods in order of priority, Q/ESC to abort"),
             ("4. Console", "help, mem_*, sdram_*, eth_*, sdcard_*, flash_*, boot, reboot")]
    y = 110
    d.box(330, y, 680, y + 58, fill=WHITE, lines=[(steps[0][0], 15, "bold"), (steps[0][1], 12)]); y += 70
    d.box(330, y, 680, y + 72, fill=WHITE, lines=[(steps[1][0], 15, "bold"), (steps[1][1], 12), (steps[2][1], 12)]); y += 84
    d.box(330, y, 680, y + 58, fill=KEY, lines=[(steps[3][0], 15, "bold"), (steps[3][1], 12)]); y += 70
    d.box(330, y, 680, y + 58, fill=WHITE, lines=[(steps[4][0], 15, "bold"), (steps[4][1], 12)])
    d.arrow([(505, 168), (505, 180)])
    d.arrow([(505, 252), (505, 264)])
    d.arrow([(505, 322), (505, 334)])
    d.text(505, 420, "nothing booted, or aborted", 11, style="italic")
    d.text(505, 460, "the application never returns", 11, style="italic")

    # Right: boot methods.
    d.arrow([(680, 293), (760, 293)], thick=True)
    d.box(760, 40, 1370, 480, fill=FPGA, c=24)
    d.text(1065, 70, "Boot methods, in order", 20, weight="bold")
    d.text(1065, 90, "each one present only when the SoC has the core; priority and disable constants", 12, style="italic")
    methods = [("serial", "litex_term --kernel app.bin: SFL frames over the UART, no media needed"),
               ("flash", "image at FLASH_BOOT_ADDRESS in the SPI flash (8-byte header), copied to RAM"),
               ("rom", "jump to ROM_BOOT_ADDRESS: an application already in a memory"),
               ("sdcard / sata", "FAT partition: boot.json (several images) or boot.bin"),
               ("net", "TFTP from REMOTEIP (DHCP optional): boot.json or boot.bin")]
    y = 110
    for name, sub in methods:
        d.box(780, y, 1350, y + 54, fill=WHITE, lines=[(name, 14, "bold"), (sub, 12)])
        y += 64
    d.text(1065, 450, "boot.json: {\"Image\": \"0x40000000\", \"rv32.dtb\": \"0x40ef0000\", \"opensbi.bin\": \"0x40f00000\", \"bootargs\": {...}}", 11, style="italic")

    # Bottom: the application.
    d.arrow([(1065, 480), (1065, 520)], thick=True)
    d.box(760, 520, 1370, 590, fill=MEM, lines=[("Main RAM: the application", 16, "bold"),
                                                 ("bare-metal firmware · Zephyr / FreeRTOS / NuttX · OpenSBI + Linux + device tree + rootfs", 12)])
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-bios-boot", W, H, "The LiteX BIOS boot flow", DESC)
