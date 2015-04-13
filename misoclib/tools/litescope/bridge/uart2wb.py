from misoclib.tools.litescope.common import *
from migen.bus import wishbone
from migen.genlib.misc import chooser
from migen.genlib.cdc import MultiReg
from migen.bank.description import *
from migen.bank.eventmanager import *
from migen.genlib.record import Record
from migen.flow.actor import Sink, Source

from misoclib.com.uart.phy.serial import UARTPHYSerial


class UARTPads:
    def __init__(self):
        self.rx = Signal()
        self.tx = Signal()


class UARTMux(Module):
    def __init__(self, pads):
        self.sel = Signal(max=2)
        self.shared_pads = UARTPads()
        self.bridge_pads = UARTPads()

    ###
        # Route rx pad:
        # when sel==0, route it to shared rx and bridge rx
        # when sel==1, route it only to bridge rx
        self.comb += \
            If(self.sel==0,
                self.shared_pads.rx.eq(pads.rx),
                self.bridge_pads.rx.eq(pads.rx)
            ).Else(
                self.bridge_pads.rx.eq(pads.rx)
            )

        # Route tx:
        # when sel==0, route shared tx to pads tx
        # when sel==1, route bridge tx to pads tx
        self.comb += \
            If(self.sel==0,
                pads.tx.eq(self.shared_pads.tx)
            ).Else(
                pads.tx.eq(self.bridge_pads.tx)
            )


class LiteScopeUART2WB(Module, AutoCSR):
    cmds = {
        "write"    : 0x01,
        "read"    : 0x02
    }
    def __init__(self, pads, clk_freq, baudrate=115200, share_uart=False):
        self.wishbone = wishbone.Interface()
        if share_uart:
            self._sel = CSRStorage()
        ###
        if share_uart:
            mux = UARTMux(pads)
            uart = UARTPHYSerial(mux.bridge_pads, clk_freq, baudrate)
            self.submodules += mux, uart
            self.shared_pads = mux.shared_pads
            self.comb += mux.sel.eq(self._sel.storage)
        else:
            uart = UARTPHYSerial(pads, clk_freq, baudrate)
            self.submodules += uart

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
            If(cmd_ce, cmd.eq(uart.source.data)),
            If(length_ce, length.eq(uart.source.data)),
            If(address_ce, address.eq(Cat(uart.source.data, address[0:24]))),
            If(rx_data_ce,
                data.eq(Cat(uart.source.data, data[0:24]))
            ).Elif(tx_data_ce,
                data.eq(self.wishbone.dat_r)
            )
        ]

        ###
        fsm = InsertReset(FSM(reset_state="IDLE"))
        timeout = Timeout(clk_freq//10)
        self.submodules += fsm, timeout
        self.comb += [
            timeout.ce.eq(1),
            fsm.reset.eq(timeout.reached)
        ]
        fsm.act("IDLE",
            timeout.reset.eq(1),
            If(uart.source.stb,
                cmd_ce.eq(1),
                If(    (uart.source.data == self.cmds["write"]) |
                    (uart.source.data == self.cmds["read"]),
                    NextState("RECEIVE_LENGTH")
                ),
                byte_counter.reset.eq(1),
                word_counter.reset.eq(1)
            )
        )
        fsm.act("RECEIVE_LENGTH",
            If(uart.source.stb,
                length_ce.eq(1),
                NextState("RECEIVE_ADDRESS")
            )
        )
        fsm.act("RECEIVE_ADDRESS",
            If(uart.source.stb,
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
            If(uart.source.stb,
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
            chooser(data, byte_counter.value, uart.sink.data, n=4, reverse=True)
        fsm.act("SEND_DATA",
            uart.sink.stb.eq(1),
            If(uart.sink.ack,
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
