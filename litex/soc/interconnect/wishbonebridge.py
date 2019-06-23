# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *

from migen.genlib.misc import chooser, WaitTimer
from migen.genlib.record import Record
from migen.genlib.fsm import FSM, NextState

from litex.soc.interconnect import wishbone
from litex.soc.interconnect import stream


class WishboneStreamingBridge(Module):
    cmds = {
        "write": 0x01,
        "read": 0x02
    }

    def __init__(self, phy, clk_freq):
        self.wishbone = wishbone.Interface()

        # # #

        byte_counter = Signal(3, reset_less=True)
        byte_counter_reset = Signal()
        byte_counter_ce = Signal()
        self.sync += \
            If(byte_counter_reset,
                byte_counter.eq(0)
            ).Elif(byte_counter_ce,
                byte_counter.eq(byte_counter + 1)
            )

        word_counter = Signal(3, reset_less=True)
        word_counter_reset = Signal()
        word_counter_ce = Signal()
        self.sync += \
            If(word_counter_reset,
                word_counter.eq(0)
            ).Elif(word_counter_ce,
                word_counter.eq(word_counter + 1)
            )

        cmd = Signal(8, reset_less=True)
        cmd_ce = Signal()

        length = Signal(8, reset_less=True)
        length_ce = Signal()

        address = Signal(32, reset_less=True)
        address_ce = Signal()

        data = Signal(32, reset_less=True)
        rx_data_ce = Signal()
        tx_data_ce = Signal()

        self.sync += [
            If(cmd_ce, cmd.eq(phy.source.data)),
            If(length_ce, length.eq(phy.source.data)),
            If(address_ce, address.eq(Cat(phy.source.data, address[0:24]))),
            If(rx_data_ce,
                data.eq(Cat(phy.source.data, data[0:24]))
            ).Elif(tx_data_ce,
                data.eq(self.wishbone.dat_r)
            )
        ]

        fsm = ResetInserter()(FSM(reset_state="IDLE"))
        timer = WaitTimer(clk_freq//10)
        self.submodules += fsm, timer
        self.comb += [
            fsm.reset.eq(timer.done),
            phy.source.ready.eq(1)
        ]
        fsm.act("IDLE",
            If(phy.source.valid,
                cmd_ce.eq(1),
                If((phy.source.data == self.cmds["write"]) |
                   (phy.source.data == self.cmds["read"]),
                    NextState("RECEIVE_LENGTH")
                ),
                byte_counter_reset.eq(1),
                word_counter_reset.eq(1)
            )
        )
        fsm.act("RECEIVE_LENGTH",
            If(phy.source.valid,
                length_ce.eq(1),
                NextState("RECEIVE_ADDRESS")
            )
        )
        fsm.act("RECEIVE_ADDRESS",
            If(phy.source.valid,
                address_ce.eq(1),
                byte_counter_ce.eq(1),
                If(byte_counter == 3,
                    If(cmd == self.cmds["write"],
                        NextState("RECEIVE_DATA")
                    ).Elif(cmd == self.cmds["read"],
                        NextState("READ_DATA")
                    ),
                    byte_counter_reset.eq(1),
                )
            )
        )
        fsm.act("RECEIVE_DATA",
            If(phy.source.valid,
                rx_data_ce.eq(1),
                byte_counter_ce.eq(1),
                If(byte_counter == 3,
                    NextState("WRITE_DATA"),
                    byte_counter_reset.eq(1)
                )
            )
        )
        self.comb += [
            self.wishbone.adr.eq(address + word_counter),
            self.wishbone.dat_w.eq(data),
            self.wishbone.sel.eq(2**len(self.wishbone.sel) - 1)
        ]
        fsm.act("WRITE_DATA",
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(1),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                word_counter_ce.eq(1),
                If(word_counter == (length-1),
                    NextState("IDLE")
                ).Else(
                    NextState("RECEIVE_DATA")
                )
            )
        )
        fsm.act("READ_DATA",
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(0),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                tx_data_ce.eq(1),
                NextState("SEND_DATA")
            )
        )
        self.comb += \
            chooser(data, byte_counter, phy.sink.data, n=4, reverse=True)
        fsm.act("SEND_DATA",
            phy.sink.valid.eq(1),
            If(phy.sink.ready,
                byte_counter_ce.eq(1),
                If(byte_counter == 3,
                    word_counter_ce.eq(1),
                    If(word_counter == (length-1),
                        NextState("IDLE")
                    ).Else(
                        NextState("READ_DATA"),
                        byte_counter_reset.eq(1)
                    )
                )
            )
        )

        self.comb += timer.wait.eq(~fsm.ongoing("IDLE"))

        self.comb += phy.sink.last.eq((byte_counter == 3) & (word_counter == length - 1))

        if hasattr(phy.sink, "length"):
            self.comb += phy.sink.length.eq(4*length)
