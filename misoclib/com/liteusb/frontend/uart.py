from migen.fhdl.std import *

from misoclib.com.liteusb.common import *
from misoclib.com.uart import UART

class LiteUSBUARTPHY:
    def __init__(self):
        self.sink = Sink([("data", 8)])
        self.source = Source([("data", 8)])

class LiteUSBUART(UART):
    def __init__(self, port,
                 tx_fifo_depth=16,
                 rx_fifo_depth=16):

        phy = LiteUSBUARTPHY()
        UART.__init__(self, phy, tx_fifo_depth, rx_fifo_depth)

        # TX
        self.comb += [
            port.sink.stb.eq(phy.sink.stb),
            port.sink.sop.eq(1),
            port.sink.eop.eq(1),
            port.sink.length.eq(1),
            port.sink.dst.eq(port.tag),
            port.sink.data.eq(phy.sink.data),
            phy.sink.ack.eq(port.sink.ack)
        ]

        # RX
        self.comb += [
            phy.source.stb.eq(port.source.stb),
            phy.source.data.eq(port.source.data),
            port.source.ack.eq(phy.source.ack)
        ]
