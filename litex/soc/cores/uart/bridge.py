from migen import *

from litex.soc.interconnect.wishbonebridge import WishboneStreamingBridge
from litex.soc.cores.uart.core import RS232PHY


class UARTWishboneBridge(WishboneStreamingBridge):
    def __init__(self, pads, clk_freq, baudrate=115200):
        self.submodules.phy = RS232PHY(pads, clk_freq, baudrate)
        WishboneStreamingBridge.__init__(self, self.phy, clk_freq)
