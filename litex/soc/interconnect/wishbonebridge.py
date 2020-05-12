# This file is Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from math import log2

from migen import *

from migen.genlib.misc import WaitTimer

from litex.soc.interconnect import wishbone
from litex.soc.interconnect import stream

# Wishbone Streaming Bridge ------------------------------------------------------------------------

CMD_WRITE = 0x01
CMD_READ  = 0x02

class WishboneStreamingBridge(Module):
    def __init__(self, phy, clk_freq, data_width=32, address_width=32):
        self.wishbone = wishbone.Interface()
        self.comb += phy.source.ready.eq(1) # Always accept incoming stream.

        # # #

        cmd         = Signal(8,                        reset_less=True)
        length      = Signal(8,                        reset_less=True)
        address     = Signal(address_width,            reset_less=True)
        data        = Signal(data_width,               reset_less=True)
        bytes_count = Signal(int(log2(data_width//8)), reset_less=True)
        words_count = Signal(8,                        reset_less=True)

        bytes_count_done  = (bytes_count == (data_width//8 - 1))
        words_count_done  = (words_count == (length - 1))

        fsm   = ResetInserter()(FSM(reset_state="RECEIVE-CMD"))
        timer = WaitTimer(int(100e-3*clk_freq))
        self.comb += timer.wait.eq(~fsm.ongoing("RECEIVE-CMD"))
        self.submodules += fsm, timer
        self.comb += fsm.reset.eq(timer.done)
        fsm.act("RECEIVE-CMD",
            NextValue(bytes_count, 0),
            NextValue(words_count, 0),
            If(phy.source.valid,
                NextValue(cmd, phy.source.data),
                NextState("RECEIVE-LENGTH")
            )
        )
        fsm.act("RECEIVE-LENGTH",
            If(phy.source.valid,
                NextValue(length, phy.source.data),
                NextState("RECEIVE-ADDRESS")
            )
        )
        fsm.act("RECEIVE-ADDRESS",
            If(phy.source.valid,
                NextValue(address, Cat(phy.source.data, address)),
                NextValue(bytes_count, bytes_count + 1),
                If(bytes_count_done,
                    If(cmd == CMD_WRITE,
                        NextState("RECEIVE-DATA")
                    ).Elif(cmd == CMD_READ,
                        NextState("READ-DATA")
                    ).Else(
                        NextState("RECEIVE-CMD")
                    )
                )
            )
        )
        fsm.act("RECEIVE-DATA",
            If(phy.source.valid,
                NextValue(data, Cat(phy.source.data, data)),
                NextValue(bytes_count, bytes_count + 1),
                If(bytes_count_done,
                    NextState("WRITE-DATA")
                )
            )
        )
        self.comb += [
            self.wishbone.adr.eq(address),
            self.wishbone.dat_w.eq(data),
            self.wishbone.sel.eq(2**(data_width//8) - 1)
        ]
        fsm.act("WRITE-DATA",
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(1),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                NextValue(words_count, words_count + 1),
                NextValue(address, address + 1),
                If(words_count_done,
                    NextState("RECEIVE-CMD")
                ).Else(
                    NextState("RECEIVE-DATA")
                )
            )
        )
        fsm.act("READ-DATA",
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(0),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                NextValue(data, self.wishbone.dat_r),
                NextState("SEND-DATA")
            )
        )
        cases = {}
        for i, n in enumerate(reversed(range(data_width//8))):
            cases[i] = phy.sink.data.eq(data[8*n:])
        self.comb += Case(bytes_count, cases)
        fsm.act("SEND-DATA",
            phy.sink.valid.eq(1),
            If(phy.sink.ready,
                NextValue(bytes_count, bytes_count + 1),
                If(bytes_count_done,
                    NextValue(words_count, words_count + 1),
                    NextValue(address, address + 1),
                    If(words_count_done,
                        NextState("RECEIVE-CMD")
                    ).Else(
                        NextState("READ-DATA")
                    )
                )
            )
        )
        self.comb += phy.sink.last.eq(bytes_count_done & words_count_done)
        if hasattr(phy.sink, "length"):
            self.comb += phy.sink.length.eq((data_width//8)*length)
