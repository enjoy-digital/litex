#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect import stream

# I2S Audio ---------------------------------------------------------------------------------------

class I2SAudio(LiteXModule):
    """Simple I2S transmitter.

    Generates BCLK/LRCLK from the system clock and serializes stereo samples
    from a LiteX stream endpoint.
    """
    def __init__(self, pads, sys_clk_freq, sample_rate=48000, data_width=16, bits_per_channel=None):
        if bits_per_channel is None:
            bits_per_channel = data_width

        self.pads = pads
        self.sink = sink = stream.Endpoint([("data", data_width*2)])

        # # #

        bclk_divider = max(2, int(round(sys_clk_freq / (sample_rate * bits_per_channel * 2))))

        bclk_counter = Signal(max=bclk_divider//2)
        bclk         = Signal()
        bclk_tick    = Signal()
        bclk_rise    = Signal()
        bclk_fall    = Signal()
        lrck         = Signal()
        bit_counter  = Signal(max=bits_per_channel)

        tx_shift     = Signal(data_width*2)
        tx_bit       = Signal(max=bits_per_channel)

        self.sync += [
            If(bclk_counter == (bclk_divider//2 - 1),
                bclk_counter.eq(0),
                bclk_tick.eq(1),
            ).Else(
                bclk_counter.eq(bclk_counter + 1),
                bclk_tick.eq(0),
            )
        ]
        self.comb += [
            bclk_rise.eq(bclk_tick & ~bclk),
            bclk_fall.eq(bclk_tick &  bclk),
        ]
        self.sync += If(bclk_tick, bclk.eq(~bclk))

        self.sync += If(bclk_rise,
            If(bit_counter == (bits_per_channel - 1),
                bit_counter.eq(0),
                lrck.eq(~lrck),
            ).Else(
                bit_counter.eq(bit_counter + 1),
            )
        )

        # Transmit MSB first.
        self.comb += pads.dout.eq(Array(tx_shift)[bits_per_channel - 1 - tx_bit])
        self.sync += If(bclk_fall,
            If(tx_bit == (bits_per_channel - 1),
                tx_bit.eq(0),
                sink.ready.eq(1),
            ).Else(
                tx_bit.eq(tx_bit + 1),
                sink.ready.eq(0),
            )
        )
        self.sync += If(sink.valid & sink.ready, tx_shift.eq(sink.data))

        if hasattr(pads, "bclk"):
            self.comb += pads.bclk.eq(bclk)
        if hasattr(pads, "lrck"):
            self.comb += pads.lrck.eq(lrck)
