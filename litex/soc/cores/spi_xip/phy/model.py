from migen import *
from migen.genlib.fsm import FSM, NextState

from litex.soc.cores.spi_xip.common import *
from litex.soc.interconnect import stream

class LiteSPIPHYModel(Module):
    def __init__(self, size, init=None):
        self.source = source = stream.Endpoint(spi_phy_data_layout)
        self.sink   = sink   = stream.Endpoint(spi_phy_ctl_layout)


        self.mem = mem = Memory(32, size//4, init=init)

        read_port  = mem.get_port(async_read=True)
        read_addr  = Signal(32)
        self.comb += read_port.adr.eq(read_addr),
        self.cs_n  = Signal()

        self.specials += mem, read_port

        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            sink.ready.eq(1),
            If(sink.ready & sink.valid,
                If(sink.cmd,
                    NextValue(read_addr, sink.addr[2:31]), # word addressed memory
                ).Else(
                    NextState("DATA"),
                ),
            ),
        )
        fsm.act("DATA",
            source.valid.eq(1),
            source.data.eq(read_port.dat_r),
            If(source.ready & source.valid,
                NextValue(read_addr, read_addr+1),
                NextState("IDLE"),
            ),
        )
