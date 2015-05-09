from migen.fhdl.std import *

from misoclib.com.liteusb.common import *
from misoclib.tools.wishbone import WishboneStreamingBridge

class LiteUSBWishboneBridge(WishboneStreamingBridge):
    def __init__(self, port, clk_freq):
        WishboneStreamingBridge.__init__(self, port, clk_freq)
        self.comb += port.sink.dst.eq(port.tag)
