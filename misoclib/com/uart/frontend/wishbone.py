from migen.fhdl.std import *

from misoclib.tools.litescope.frontend.wishbone import LiteScopeWishboneBridge
from misoclib.com.uart.phy.serial import UARTPHYSerial

class UARTWishboneBridge(LiteScopeWishboneBridge):
    def __init__(self, pads, clk_freq, baudrate=115200):
        self.submodules.phy = UARTPHYSerial(pads, clk_freq, baudrate)
        LiteScopeWishboneBridge.__init__(self, self.phy, clk_freq)
