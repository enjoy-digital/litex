#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-axi.svg: AXI in LiteX, for the AXI-Bus page: the three flavours and their channels, and
the bridges and converters the SoC builder inserts between standards and widths.

    python3 doc/diagrams/litex-axi.py   # -> doc/wiki/images/litex-axi.svg
"""

from litex_diagram import *

W, H = 1400, 600

DESC = ("AXI in LiteX. Top: the three flavours with their channels. AXI4-Lite: aw, w, b, ar, r "
        "without bursts, for control. AXI4: the same five channels with bursts and IDs, for memory "
        "traffic. AXI4-Stream: one channel, a LiteX stream endpoint. Bottom: a mixed SoC where the SoC "
        "builder inserts the bridges: a Wishbone CPU and an AXI DMA on an AXI-Lite main bus, LiteDRAM "
        "reached through an AXI port, a vendor AXI-Lite IP, the CSR bridge, with the width converters.")

def draw(d):
    # Top: flavours.
    cols = [("AXI4-Lite", "AXILiteInterface(data_width, address_width)", ["aw: addr, prot", "w: data, strb", "b: resp", "ar: addr, prot", "r: data, resp"], "control: CSRs, vendor IP control ports, --bus-standard=axi-lite"),
            ("AXI4", "AXIInterface(data_width, address_width, id_width, version)", ["aw: addr, len, size, burst, id, ...", "w: data, strb, last", "b: resp, id", "ar: addr, len, size, burst, id, ...", "r: data, resp, last, id"], "memory: DMAs, LiteDRAM, HPS bridges, big CPUs, --bus-standard=axi"),
            ("AXI4-Stream", "AXIStreamInterface(data_width, keep/id/dest/user widths)", ["tvalid / tready", "tdata, tkeep, tlast", "tid, tdest, tuser", "= a LiteX stream endpoint", "payload data/keep, params id/dest/user"], "data paths: standalone cores, vendor IPs, DSP")]
    x = 40
    for title, ctor, chans, use in cols:
        d.box(x, 50, x + 420, 290, fill=GROUP, c=18)
        d.text(x + 210, 78, title, 18, weight="bold")
        d.text(x + 210, 96, ctor, 11, style="italic")
        for i, c in enumerate(chans):
            d.box(x + 20, 110 + 30*i, x + 400, 134 + 30*i, fill=KEY if i < 5 else WHITE, c=8, shadow=False, lines=[(c, 12)])
        d.text(x + 210, 275, use, 11, style="italic")
        x += 440

    # Bottom: a mixed SoC.
    d.text(700, 330, "A mixed SoC: the SoC builder inserts the bridges and converters (SoCBusHandler.add_adapter)", 14, weight="bold")
    d.box(40, 350, 260, 420, fill=KEY, lines=[("Wishbone CPU", 14, "bold"), ("ibus / dbus 32-bit", 11)])
    d.box(300, 350, 500, 420, lines=[("Wishbone2AXILite", 12, "bold"), ("word to byte addressing", 11)])
    d.arrow([(260, 385), (300, 385)], thick=True)
    d.arrow([(500, 385), (540, 385)], thick=True)
    d.box(40, 440, 260, 510, fill=KEY, lines=[("AXI DMA (vendor IP)", 14, "bold"), ("AXI4 64-bit, bursts", 11)])
    d.box(300, 440, 500, 510, lines=[("AXI2AXILite + converter", 12, "bold"), ("bursts to beats, 64 to 32-bit", 11)])
    d.arrow([(260, 475), (300, 475)], thick=True)
    d.arrow([(500, 475), (540, 475)], thick=True)
    d.box(540, 350, 860, 510, fill=KEY, c=18, lines=[("Main bus: AXI4-Lite 32-bit", 15, "bold"), ("AXILiteInterconnectShared", 12), ("or AXILiteCrossbar", 12), ("timeout, decoder, arbiter", 12)])
    d.box(900, 350, 1120, 400, fill=MEM, lines=[("LiteDRAM", 13, "bold"), ("AXILite2AXI, 128-bit AXI port", 11)])
    d.box(900, 410, 1120, 460, lines=[("Vendor AXI-Lite IP", 13, "bold"), ("direct, same standard", 11)])
    d.box(900, 470, 1120, 520, lines=[("CSR bridge", 13, "bold"), ("AXILite2CSR", 11)])
    d.box(1160, 350, 1360, 400, fill=WHITE, lines=[("SRAM", 13, "bold"), ("AXILiteSRAM", 11)])
    d.box(1160, 410, 1360, 460, fill=WHITE, lines=[("Wishbone core", 13, "bold"), ("AXILite2Wishbone", 11)])
    for yy in (375, 435, 495):
        d.arrow([(860, yy), (900, yy)], thick=True)
    d.arrow([(1120, 375), (1160, 375)], thick=True)
    d.arrow([(1120, 435), (1160, 435)], thick=True)

    d.caption(700, 560, "AXI4, AXI4-Lite and AXI4-Stream, mixed freely with Wishbone", "every channel is a stream: FIFOs, clock domain crossings and pipelines apply to AXI as to any LiteX stream")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-axi", W, H, "AXI in LiteX", DESC)
