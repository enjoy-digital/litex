#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

# I2S Audio ---------------------------------------------------------------------------------------

class I2SAudio(LiteXModule):
    """Simple I2S transmitter.

    Generates BCLK/LRCLK from the system clock and serializes stereo samples
    from a LiteX stream endpoint.
    """
    def __init__(self, pads, sys_clk_freq, sample_rate=48000, data_width=16, bits_per_channel=None, with_csr=True):
        if bits_per_channel is None:
            bits_per_channel = data_width

        self.pads = pads
        self.sink = sink = stream.Endpoint([("data", data_width*2)])
        if with_csr:
            self.enable = CSRStorage(reset=1)
            enabled = self.enable.storage
        else:
            enabled = 1

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
        self.comb += pads.dout.eq(Array(tx_shift)[bits_per_channel - 1 - tx_bit] & enabled)
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
            self.comb += pads.bclk.eq(bclk & enabled)
        if hasattr(pads, "lrck"):
            self.comb += pads.lrck.eq(lrck & enabled)

        # Receive path.
        if hasattr(pads, "din"):
            self.source = stream.Endpoint([("data", data_width*2)])
            rx_shift = Signal(data_width*2)
            rx_bit   = Signal(max=data_width*2)

            rx_fsm = FSM(reset_state="IDLE")
            rx_fsm.act("IDLE",
                If(bclk_rise & enabled,
                    NextValue(rx_shift, Cat(rx_shift[1:], pads.din)),
                    NextValue(rx_bit, 1),
                    NextState("CAPTURE"),
                )
            )
            rx_fsm.act("CAPTURE",
                If(bclk_rise & enabled,
                    If(rx_bit == (data_width*2 - 1),
                        self.source.valid.eq(1),
                        If(self.source.ready,
                            NextState("IDLE"),
                        ).Else(
                            NextState("WAIT"),
                        )
                    ).Else(
                        NextValue(rx_shift, Cat(rx_shift[1:], pads.din)),
                        NextValue(rx_bit, rx_bit + 1),
                    )
                )
            )
            rx_fsm.act("WAIT",
                self.source.valid.eq(1),
                If(self.source.ready,
                    NextState("IDLE"),
                )
            )
            self.comb += self.source.data.eq(Cat([
                rx_shift[data_width*2 - 1 - i] for i in range(data_width*2)
            ]))
