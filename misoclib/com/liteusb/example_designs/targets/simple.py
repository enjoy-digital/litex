from migen.genlib.io import CRG
from migen.actorlib.fifo import SyncFIFO

from misoclib.soc import SoC

from misoclib.com.liteusb.common import *
from misoclib.com.liteusb.phy.ft245 import FT245PHY
from misoclib.com.liteusb.core import LiteUSBCore
from misoclib.com.liteusb.frontend.wishbone import LiteUSBWishboneBridge

from misoclib.com.gpio import GPIOOut

class LiteUSBSoC(SoC):
    csr_map = {}
    csr_map.update(SoC.csr_map)

    usb_map = {
        "bridge": 0
    }

    def __init__(self, platform):
        clk_freq = int((1/(platform.default_clk_period))*1000000000)
        SoC.__init__(self, platform, clk_freq,
            cpu_type="none",
            with_csr=True, csr_data_width=32,
            with_uart=False,
            with_identifier=True,
            with_timer=False
        )
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        self.submodules.usb_phy = FT245PHY(platform.request("usb_fifo"), self.clk_freq)
        self.submodules.usb_core = LiteUSBCore(self.usb_phy, self.clk_freq, with_crc=False)


        # Wishbone Bridge
        usb_bridge_port = self.usb_core.crossbar.get_port(self.usb_map["bridge"])
        self.add_cpu_or_bridge(LiteUSBWishboneBridge(usb_bridge_port, self.clk_freq))
        self.add_wb_master(self.cpu_or_bridge.wishbone)

        # Leds
        leds = Cat(iter([platform.request("user_led", i) for i in range(8)]))
        self.submodules.leds = GPIOOut(leds)

default_subtarget = LiteUSBSoC
