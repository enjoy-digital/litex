# This file is Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>$
# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *

from litex.soc.interconnect import stream

# Altera Atlantic JTAG -----------------------------------------------------------------------------

class JTAGAtlantic(Module):
    def __init__(self):
        self.sink = sink = stream.Endpoint([("data", 8)])
        self.source = source = stream.Endpoint([("data", 8)])

        # # #

        self.specials += Instance("alt_jtag_atlantic",
            # Parameters
            p_LOG2_RXFIFO_DEPTH="5", # FIXME: expose?
            p_LOG2_TXFIFO_DEPTH="5", # FIXME: expose?
            p_SLD_AUTO_INSTANCE_INDEX="YES",
            # Clk/Rst
            i_clk=ClockSignal("sys"),
            i_rst_n=~ResetSignal("sys"),
            # TX
            i_r_dat=sink.data,
            i_r_val=sink.valid,
            o_r_ena=sink.ready,
            # RX
            o_t_dat=source.data,
            i_t_dav=source.ready,
            o_t_ena=source.valid,
        )
