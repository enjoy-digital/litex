from migen.fhdl.std import *

from misoclib.com.liteusb.common import *
from misoclib.tools.litescope.frontend.wishbone import LiteScopeWishboneBridge

class LiteUSBWishboneBridge(LiteScopeWishboneBridge):
    def __init__(self, port, clk_freq):
        LiteScopeWishboneBridge.__init__(self, port, clk_freq)
        self.comb += [
            port.sink.sop.eq(1),
            port.sink.eop.eq(1),
            port.sink.length.eq(1),
            port.sink.dst.eq(port.tag)
        ]
