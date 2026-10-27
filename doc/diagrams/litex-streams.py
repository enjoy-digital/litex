#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-streams.svg: a stream endpoint and a stream pipeline, for the Streams page.

    python3 doc/diagrams/litex-streams.py   # -> doc/wiki/images/litex-streams.svg
"""

from litex_diagram import *

W, H = 1400, 560

DESC = ("LiteX streams. Top: a source endpoint connected to a sink endpoint, with the signals of the "
        "handshake (valid from the source, ready from the sink, a transfer on each cycle where both "
        "are set), the packet delimiters first and last, the payload record (data, byte enables...) "
        "that changes on every transfer and the param record that changes at each start of packet. "
        "Bottom: a pipeline of generic blocks between a PHY and a DMA: a width converter, a FIFO, a "
        "clock domain crossing, a packetizer adding a header, each with its sink and source.")

def draw(d):
    # Top: an endpoint pair.
    d.text(700, 44, "An endpoint: source.connect(sink)", 17, weight="bold")
    d.box(120, 70, 460, 230, fill=KEY, lines=[("Source", 18, "bold"), ("a module's .source", 13), ("drives valid, first, last, payload, param", 13), ("waits for ready", 13)])
    d.box(940, 70, 1280, 230, fill=KEY, lines=[("Sink", 18, "bold"), ("a module's .sink", 13), ("drives ready", 13), ("samples the word when valid & ready", 13)])
    sig = [(100, "valid", "a word is present", False),
           (130, "ready", "the sink accepts it", True),
           (160, "first · last", "packet delimiters (optional)", False),
           (190, "payload: data, be, ...", "a Record, new on each transfer", False),
           (220, "param: length, ...", "a Record, new at each packet (optional)", False)]
    for y, name, desc, back in sig:
        if back:
            d.arrow([(940, y), (460, y)])
        else:
            d.arrow([(460, y), (940, y)])
        d.text(700, y - 10, f"{name}: {desc}", 12, style="italic")
    d.text(700, 258, "stream.Endpoint([(\"data\", 32), (\"be\", 4)])   ·   stream.EndpointDescription(payload_layout, param_layout)", 12, style="italic")

    # Bottom: a pipeline.
    d.text(700, 310, "A pipeline: stream.Pipeline(phy, Converter(8, 32), SyncFIFO(layout, 64), ClockDomainCrossing(...), Packetizer(...), dma.sink)", 14, weight="bold")
    blocks = [("PHY", "source: 8-bit bytes", "rx clock domain", MEM),
              ("Converter(8, 32)", "8 to 32 bits", "keeps first / last / be", WHITE),
              ("SyncFIFO(layout, 64)", "64 words", "buffering, backpressure", WHITE),
              ("ClockDomainCrossing", "rx to sys", "AsyncFIFO inside", WHITE),
              ("Packetizer(header)", "adds the header", "length, destination, ...", WHITE),
              ("DMA", "sink: words to memory", "Wishbone / AXI master", MEM)]
    x = 40
    w = 195
    gap = 30
    for i, (t, l1, l2, fill) in enumerate(blocks):
        d.box(x, 340, x + w, 430, fill=fill, lines=[(t, 14, "bold"), (l1, 12), (l2, 12)])
        if i < len(blocks) - 1:
            d.arrow([(x + w, 385), (x + w + gap, 385)], thick=True)
        x += w + gap
    d.text(700, 462, "every arrow is a full stream: valid / ready / first / last / payload (/ param), connected by .source -> .sink", 12, style="italic")
    d.caption(700, 510, "Streams: one interface for every data path", "AXI-Stream and Avalon-ST map to it directly: tvalid/tready/tlast/tdata/tkeep/tuser are valid/ready/last/data/be/param")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-streams", W, H, "LiteX streams", DESC)
