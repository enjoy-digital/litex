from migen.fhdl.std import *
from migen.bus import wishbone
from migen.genlib.io import CRG

from misoclib.soc import SoC, mem_decoder
from misoclib.com.liteeth.phy import LiteEthPHY
from misoclib.com.liteeth.mac import LiteEthMAC


class BaseSoC(SoC):
    def __init__(self, platform, **kwargs):
        SoC.__init__(self, platform,
            clk_freq=int((1/(platform.default_clk_period))*1000000000),
            integrated_rom_size=0x8000,
            integrated_main_ram_size=16*1024,
            **kwargs)
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))


class MiniSoC(BaseSoC):
    csr_map = {
        "ethphy": 20,
        "ethmac": 21
    }
    csr_map.update(BaseSoC.csr_map)

    interrupt_map = {
        "ethmac": 2,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    mem_map = {
        "ethmac": 0x30000000,  # (shadow @0xb0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, platform, **kwargs):
        BaseSoC.__init__(self, platform, **kwargs)

        self.submodules.ethphy = LiteEthPHY(platform.request("eth_clocks"),
                                            platform.request("eth"))
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
                                            interface="wishbone",
                                            with_hw_preamble_crc=False)
        self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
        self.add_memory_region("ethmac", self.mem_map["ethmac"]+0x80000000, 0x2000)

default_subtarget = BaseSoC
