#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# 8-bit to 32-bit stream packer.

from migen import *

from litex.gen import *

from litex.soc.interconnect import stream

# Layouts ------------------------------------------------------------------------------------------

byte_layout = [("data",  8)]
word_layout = [("data", 32), ("count", 3)]

# Packer -------------------------------------------------------------------------------------------

class Packer(LiteXModule):
    """Packs the bytes of the sink packets into 32-bit words (first byte in bits 7:0).

    Each source word carries count valid bytes (1-4, always 4 except for the last word of a
    packet) and last on the last word of a packet. The packer accepts one byte per cycle; its
    output is registered, with a skid buffer so that sink.ready does not depend on source.ready
    combinatorially.
    """
    def __init__(self):
        self.sink   = sink   = stream.Endpoint(byte_layout)
        self.source = source = stream.Endpoint(word_layout)

        # # #

        # Word assembly: bytes 0-2 of the word in shift, the word is complete on its 4th byte or
        # on the last byte of the packet.
        shift = Signal(24)
        index = Signal(2)
        self.word = word = stream.Endpoint(word_layout)
        self.comb += [
            word.valid.eq(sink.valid & sink.ready & ((index == 3) | sink.last)),
            word.last.eq(sink.last),
            word.count.eq(index + 1),
            Case(index, {
                0: word.data.eq(sink.data),
                1: word.data.eq(Cat(shift[:8],  sink.data)),
                2: word.data.eq(Cat(shift[:16], sink.data)),
                3: word.data.eq(Cat(shift[:24], sink.data)),
            }),
        ]
        self.sync += [
            If(sink.valid & sink.ready,
                Case(index, {
                    0: shift[ 0: 8].eq(sink.data),
                    1: shift[ 8:16].eq(sink.data),
                    2: shift[16:24].eq(sink.data),
                    3: shift.eq(0),
                }),
                If(sink.last,
                    index.eq(0),
                ).Else(
                    index.eq(index + 1),
                )
            )
        ]

        # Output register and skid buffer: a word produced while the output register is held goes
        # to the skid buffer, the sink is stalled until the skid buffer is drained.
        self.skid = skid = stream.Endpoint(word_layout)
        self.comb += sink.ready.eq(~skid.valid)
        self.sync += [
            If(~source.valid | source.ready,
                If(skid.valid,
                    source.valid.eq(1),
                    source.payload.eq(skid.payload),
                    source.last.eq(skid.last),
                    skid.valid.eq(0),
                ).Elif(word.valid,
                    source.valid.eq(1),
                    source.payload.eq(word.payload),
                    source.last.eq(word.last),
                ).Else(
                    source.valid.eq(0),
                )
            ).Elif(word.valid,
                skid.valid.eq(1),
                skid.payload.eq(word.payload),
            )
        ]
