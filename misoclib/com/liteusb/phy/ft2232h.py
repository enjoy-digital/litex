from migen.fhdl.std import *
from migen.flow.actor import *
from migen.actorlib.fifo import AsyncFIFO
from migen.fhdl.specials import *

from misoclib.com.liteusb.common import *


class FT2232HPHYSynchronous(Module):
    def __init__(self, pads, fifo_depth=32, read_time=16, write_time=16):
        dw = flen(pads.data)

        #
        # Read / Write Fifos
        #

        # Read Fifo (Ftdi --> SoC)
        read_fifo = RenameClockDomains(AsyncFIFO(phy_layout, fifo_depth),
            {"write": "ftdi", "read": "sys"})
        read_buffer = RenameClockDomains(SyncFIFO(phy_layout, 4),
            {"sys": "ftdi"})
        self.comb += read_buffer.source.connect(read_fifo.sink)

        # Write Fifo (SoC --> Ftdi)
        write_fifo = RenameClockDomains(AsyncFIFO(phy_layout, fifo_depth),
            {"write": "sys", "read": "ftdi"})

        self.submodules += read_fifo, read_buffer, write_fifo

        #
        # Sink / Source interfaces
        #
        self.sink = write_fifo.sink
        self.source = read_fifo.source

        #
        # Read / Write Arbitration
        #
        wants_write = Signal()
        wants_read = Signal()

        txe_n = Signal()
        rxf_n = Signal()

        self.comb += [
            txe_n.eq(pads.txe_n),
            rxf_n.eq(pads.rxf_n),
            wants_write.eq(~txe_n & write_fifo.source.stb),
            wants_read.eq(~rxf_n & read_fifo.sink.ack),
        ]

        def anti_starvation(timeout):
            en = Signal()
            max_time = Signal()
            if timeout:
                t = timeout - 1
                time = Signal(max=t+1)
                self.comb += max_time.eq(time == 0)
                self.sync += If(~en,
                        time.eq(t)
                    ).Elif(~max_time,
                        time.eq(time - 1)
                    )
            else:
                self.comb += max_time.eq(0)
            return en, max_time

        read_time_en, max_read_time = anti_starvation(read_time)
        write_time_en, max_write_time = anti_starvation(write_time)

        data_w_accepted = Signal(reset=1)

        fsm = FSM(reset_state="READ")
        self.submodules += RenameClockDomains(fsm, {"sys": "ftdi"})

        fsm.act("READ",
            read_time_en.eq(1),
            If(wants_write,
                If(~wants_read | max_read_time, NextState("RTW"))
            )
        )
        fsm.act("RTW",
            NextState("WRITE")
        )
        fsm.act("WRITE",
            write_time_en.eq(1),
            If(wants_read,
                If(~wants_write | max_write_time, NextState("WTR"))
            ),
            write_fifo.source.ack.eq(wants_write & data_w_accepted)
        )
        fsm.act("WTR",
            NextState("READ")
        )

        #
        # Read / Write Actions
        #

        data_w = Signal(dw)
        data_r = Signal(dw)
        data_oe = Signal()

        if hasattr(pads, "oe_n"):
            pads_oe_n = pads.oe_n
        else:
            pads_oe_n = Signal()

        pads_oe_n.reset = 1
        pads.rd_n.reset = 1
        pads.wr_n.reset = 1

        self.sync.ftdi += [
            If(fsm.ongoing("READ"),
                data_oe.eq(0),

                pads_oe_n.eq(0),
                pads.rd_n.eq(~wants_read),
                pads.wr_n.eq(1)

            ).Elif(fsm.ongoing("WRITE"),
                data_oe.eq(1),

                pads_oe_n.eq(1),
                pads.rd_n.eq(1),
                pads.wr_n.eq(~wants_write),

                data_w_accepted.eq(~txe_n)

            ).Else(
                data_oe.eq(1),

                pads_oe_n.eq(~fsm.ongoing("WTR")),
                pads.rd_n.eq(1),
                pads.wr_n.eq(1)
            ),
                read_buffer.sink.stb.eq(~pads.rd_n & ~rxf_n),
                read_buffer.sink.data.eq(data_r),
                If(~txe_n & data_w_accepted,
                    data_w.eq(write_fifo.source.data)
                )
        ]

        #
        # Databus Tristate
        #
        self.specials += Tristate(pads.data, data_w, data_oe, data_r)

        self.debug = Signal(8)
        self.comb += self.debug.eq(data_r)
