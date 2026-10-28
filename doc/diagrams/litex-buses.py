#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-buses.svg: the Wishbone interconnect of a SoC, for the Wishbone-Bus page: the masters, the
shared bus or crossbar built by the SoC builder, the adapters, the slaves and their regions.

    python3 doc/diagrams/litex-buses.py   # -> doc/wiki/images/litex-buses.svg
"""

from litex_diagram import *

W, H = 1400, 600

DESC = ("The Wishbone main bus of a LiteX SoC. Masters on the left: the CPU's instruction and data "
        "buses, a DMA, the host bridge; each goes through an adapter when its width, addressing or "
        "standard differs from the main bus. The interconnect in the middle, built by the SoC builder "
        "at finalization: an arbiter (round robin on cyc) and a decoder (one slave per address range) "
        "for the shared bus, or a crossbar; a timeout returns an error when a slave does not answer. "
        "Slaves on the right with their regions: ROM, SRAM, the L2 cache and LiteDRAM, the CSR bridge, "
        "a user core, an AXI-Lite vendor IP through a bridge.")

def draw(d):
    # Masters.
    d.text(190, 44, "Masters (bus.add_master)", 15, weight="bold", style="italic")
    masters = [("CPU ibus", "Wishbone 32-bit, word", KEY), ("CPU dbus", "Wishbone 32-bit, word", KEY),
               ("DMA (LiteEth, LitePCIe...)", "AXI 64-bit, byte", WHITE), ("Host bridge", "UARTBone / Etherbone", WHITE)]
    y = 70
    for t, s, f in masters:
        d.box(40, y, 340, y + 70, fill=f, lines=[(t, 15, "bold"), (s, 12)])
        d.arrow([(340, y + 35), (400, y + 35)], thick=True)
        y += 90

    # Adapters.
    d.box(400, 60, 560, 430, fill=GROUP, c=16)
    d.text(480, 84, "Adapters", 14, weight="bold")
    d.text(480, 102, "add_adapter()", 11, style="italic")
    d.box(412, 250, 548, 320, lines=[("AXI to Wishbone", 12, "bold"), ("64 to 32-bit converter", 11), ("byte to word addressing", 11)])
    d.text(480, 150, "none needed", 11, style="italic")
    d.text(480, 240, "none needed", 11, style="italic")
    d.text(480, 370, "none needed", 11, style="italic")
    for yy in (105, 195, 285, 375):
        d.arrow([(560, yy), (620, yy)], thick=True)

    # Interconnect.
    d.box(620, 60, 840, 430, fill=KEY, c=18)
    d.text(730, 90, "Interconnect", 17, weight="bold")
    d.text(730, 110, "built at finalization", 11, style="italic")
    d.box(635, 130, 825, 200, fill=WHITE, lines=[("Arbiter", 14, "bold"), ("round robin on cyc", 11), ("cycle or transaction", 11)])
    d.box(635, 215, 825, 285, fill=WHITE, lines=[("Decoder", 14, "bold"), ("one slave per region", 11), ("sel = adr in range", 11)])
    d.box(635, 300, 825, 350, fill=WHITE, lines=[("Timeout", 14, "bold"), ("err after 1e6 cycles", 11)])
    d.text(730, 385, "InterconnectShared (default)", 12, weight="bold")
    d.text(730, 403, "or Crossbar: --bus-interconnect", 11, style="italic")
    d.arrow([(730, 200), (730, 215)])
    d.arrow([(730, 285), (730, 300)])

    # Slaves.
    d.text(1110, 44, "Slaves (bus.add_slave + SoCRegion)", 15, weight="bold", style="italic")
    slaves = [("ROM (BIOS)", "0x00000000, 128 KiB, rx", MEM), ("SRAM", "0x10000000, 8 KiB, rwx", MEM),
              ("L2 cache + LiteDRAM", "main_ram 0x40000000, 256 MiB", MEM), ("CSR bridge", "csr 0xf0000000, 64 KiB, uncached", WHITE),
              ("Your core", "0x90000000, 4 KiB, uncached", WHITE), ("Vendor AXI-Lite IP", "Wishbone2AXILite bridge", WHITE)]
    y = 70
    for t, s, f in slaves:
        d.box(940, y, 1340, y + 50, fill=f, lines=[(t, 14, "bold"), (s, 11)])
        d.arrow([(840, y + 25), (940, y + 25)], thick=True)
        y += 60

    d.caption(700, 500, "One request, one acknowledge", "Wishbone classic with optional incrementing bursts: cyc · stb · we · adr · sel · dat_w → ack / err · dat_r; the map is exported to mem.h, csr.csv, csr.json")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-buses", W, H, "Wishbone in a LiteX SoC", DESC)
