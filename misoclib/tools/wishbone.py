from migen.fhdl.std import *
from migen.bus import wishbone
from migen.genlib.misc import chooser, Counter, Timeout
from migen.genlib.record import Record
from migen.genlib.fsm import FSM, NextState
from migen.flow.actor import Sink, Source


class WishboneStreamingBridge(Module):
    cmds = {
        "write": 0x01,
        "read": 0x02
    }

    def __init__(self, phy, clk_freq):
        self.wishbone = wishbone.Interface()

        # # #

        byte_counter = Counter(3)
        word_counter = Counter(8)
        self.submodules += byte_counter, word_counter

        cmd = Signal(8)
        cmd_ce = Signal()

        length = Signal(8)
        length_ce = Signal()

        address = Signal(32)
        address_ce = Signal()

        data = Signal(32)
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

        fsm = InsertReset(FSM(reset_state="IDLE"))
        timeout = Timeout(clk_freq//10)
        self.submodules += fsm, timeout
        self.comb += [
            timeout.ce.eq(1),
            fsm.reset.eq(timeout.reached),
            phy.source.ack.eq(1)
        ]
        fsm.act("IDLE",
            timeout.reset.eq(1),
            If(phy.source.stb,
                cmd_ce.eq(1),
                If((phy.source.data == self.cmds["write"]) |
                   (phy.source.data == self.cmds["read"]),
                    NextState("RECEIVE_LENGTH")
                ),
                byte_counter.reset.eq(1),
                word_counter.reset.eq(1)
            )
        )
        fsm.act("RECEIVE_LENGTH",
            If(phy.source.stb,
                length_ce.eq(1),
                NextState("RECEIVE_ADDRESS")
            )
        )
        fsm.act("RECEIVE_ADDRESS",
            If(phy.source.stb,
                address_ce.eq(1),
                byte_counter.ce.eq(1),
                If(byte_counter.value == 3,
                    If(cmd == self.cmds["write"],
                        NextState("RECEIVE_DATA")
                    ).Elif(cmd == self.cmds["read"],
                        NextState("READ_DATA")
                    ),
                    byte_counter.reset.eq(1),
                )
            )
        )
        fsm.act("RECEIVE_DATA",
            If(phy.source.stb,
                rx_data_ce.eq(1),
                byte_counter.ce.eq(1),
                If(byte_counter.value == 3,
                    NextState("WRITE_DATA"),
                    byte_counter.reset.eq(1)
                )
            )
        )
        self.comb += [
            self.wishbone.adr.eq(address + word_counter.value),
            self.wishbone.dat_w.eq(data),
            self.wishbone.sel.eq(2**flen(self.wishbone.sel)-1)
        ]
        fsm.act("WRITE_DATA",
            self.wishbone.stb.eq(1),
            self.wishbone.we.eq(1),
            self.wishbone.cyc.eq(1),
            If(self.wishbone.ack,
                word_counter.ce.eq(1),
                If(word_counter.value == (length-1),
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
            chooser(data, byte_counter.value, phy.sink.data, n=4, reverse=True)
        fsm.act("SEND_DATA",
            phy.sink.stb.eq(1),
            If(phy.sink.ack,
                byte_counter.ce.eq(1),
                If(byte_counter.value == 3,
                    word_counter.ce.eq(1),
                    If(word_counter.value == (length-1),
                        NextState("IDLE")
                    ).Else(
                        NextState("READ_DATA"),
                        byte_counter.reset.eq(1)
                    )
                )
            )
        )

        if phy.sink.description.packetized:
            self.comb += [
                phy.sink.sop.eq((byte_counter.value == 0) & (word_counter.value == 0)),
                phy.sink.eop.eq((byte_counter.value == 3) & (word_counter.value == (length-1)))
            ]
            if hasattr(phy.sink, "length"):
                self.comb += phy.sink.length.eq(4*length)
