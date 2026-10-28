#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-cores-map.svg: the cores shipped in litex/soc/cores/, by theme, for the Cores page: control
and status, communication, memory, video and audio, clocking, and the interrupt and helper layers
every core builds on.

    python3 doc/diagrams/litex-cores-map.py   # -> doc/wiki/images/litex-cores-map.svg
"""

from litex_diagram import *

W, H = 1200, 620

DESC = ("The in-tree cores of LiteX by theme. Control and status: timer, watchdog, GPIO, LED chaser and serial "
        "LEDs, PWM, identifier, frequency meter, device DNA, XADC and temperature sensors, ICAP, 7-segment, "
        "DShot, sigma-delta DAC. Communication: UART with crossover and UARTBone, JTAG (JTAGBone, debug), "
        "SPI master and slave, I2C, bit-bang, SPI and BPI flash, FT245 FIFO, USB OHCI, LUNA CDC-ACM, the soft "
        "USB2 PHY, CAN-FD, EMIF, 8b10b and PRBS. Memory: HyperRAM controllers, on-chip and vendor memories "
        "(SPRAM, LRAM, PSRAM, HBM2), Wishbone DMAs, ECC. Video and audio: timings, framebuffer, terminal, "
        "colour bars, VGA, DVI, LCD and HDMI PHYs, TMDS, SPI LCD, OV5640 camera, I2S. Clocking: the PLLs "
        "and clock managers of Xilinx, Intel, Lattice, Gowin, Efinix and CologneChip behind one API. Under "
        "them, the EventManager for interrupts and the litex.gen helpers (LiteXModule, CDC, Verilog generation).")

def draw(d):
    d.box(30, 40, 1170, 440, fill=GROUP, c=20)
    d.text(600, 68, "litex/soc/cores/: about forty cores, one file or directory each", 18, weight="bold")
    d.text(600, 86, "a LiteXModule with CSRs, an EventManager when it interrupts, streams or a bus when it moves data", 12, style="italic")
    d.box(50, 100, 400, 260, fill=KEY, lines=[
        ("Control and status", 15, "bold"),
        ("timer, watchdog, GPIO", 12),
        ("LED chaser, WS2812, PWM, DShot, DAC", 12),
        ("identifier, frequency meter, device DNA", 12),
        ("XADC and temperature sensors, ICAP", 12),
        ("7-segment display", 12),
    ])
    d.box(420, 100, 780, 260, fill=KEY, lines=[
        ("Communication", 15, "bold"),
        ("UART, crossover, UARTBone, JTAG, JTAGBone", 12),
        ("SPI master and slave, I2C, bit-bang", 12),
        ("SPI, OPI and BPI flash, FT245 FIFO", 12),
        ("USB: OHCI host, LUNA CDC-ACM, soft USB2 PHY", 12),
        ("CAN-FD, EMIF, 8b10b, PRBS", 12),
    ])
    d.box(800, 100, 1150, 260, fill=KEY, lines=[
        ("Memory", 15, "bold"),
        ("HyperRAM controllers and PHYs", 12),
        ("SPRAM, LRAM, PSRAM, async SRAM", 12),
        ("Efinix DDR, UltraScale+ HBM2", 12),
        ("Wishbone DMA reader and writer, ECC", 12),
        ("the big ones: LiteDRAM, LiteSPI (ecosystem)", 12, None, "italic"),
    ])
    d.box(50, 280, 400, 420, fill=KEY, lines=[
        ("Video and audio", 15, "bold"),
        ("timings, framebuffer, terminal, colour bars", 12),
        ("VGA, DVI, LCD and HDMI PHYs, TMDS", 12),
        ("SPI LCD, OV5640 camera", 12),
        ("I2S receiver and transmitter", 12),
    ])
    d.box(420, 280, 780, 420, fill=KEY, lines=[
        ("Clocking", 15, "bold"),
        ("S7PLL, S7MMCM, USPLL, USMMCM, USPPLL", 12),
        ("CycloneVPLL, Max10PLL, Agilex PLLs", 12),
        ("ECP5PLL, iCE40PLL, NXPLL, GW1NPLL, GW2APLL", 12),
        ("TRIONPLL, TITANIUMPLL, GateMatePLL", 12),
        ("one API: register_clkin(), create_clkout()", 12, None, "italic"),
    ])
    d.box(800, 280, 1150, 420, fill=WHITE, lines=[
        ("Under every core", 15, "bold"),
        ("EventManager: interrupts as CSRs", 12),
        ("CSRStorage, CSRStatus, CSRField", 12),
        ("stream.Endpoint, Wishbone and AXI interfaces", 12),
        ("litex.gen: LiteXModule, CDC, Verilog generation", 12),
    ])
    d.caption(600, 530, "The cores inside LiteX, by theme",
              "the building blocks every SoC needs; the protocol cores (DRAM, Ethernet, PCIe, SATA...) live in their own repositories")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-cores-map", W, H, "The in-tree cores of LiteX, by theme", DESC)
