#!/usr/bin/env python3

import argparse
import importlib

from migen import *
from migen.genlib.io import CRG

from litex.boards.platforms import sim

from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.cores import uart
from litex.soc.integration.soc_core import mem_decoder

from litedram.common import PhySettings
from litedram.modules import IS42S16160
from litedram.phy.model import SDRAMPHYModel
from litedram.core.controller import ControllerSettings

from liteeth.common import convert_ip
from liteeth.phy.model import LiteEthPHYModel
from liteeth.core.mac import LiteEthMAC
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone

from litex.build.sim.config import SimConfig

class BaseSoC(SoCSDRAM):
    interrupt_map = {
        "uart": 2,
    }
    interrupt_map.update(SoCSDRAM.interrupt_map)

    def __init__(self, **kwargs):
        platform = sim.Platform()
        SoCSDRAM.__init__(self, platform,
            clk_freq=int((1/(platform.default_clk_period))*1000000000),
            integrated_rom_size=0x8000,
            ident="LiteX Simulation", ident_version=True,
            with_uart=False,
            **kwargs)
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        self.submodules.uart_phy = uart.RS232PHYModel(platform.request("serial"))
        self.submodules.uart = uart.UART(self.uart_phy)

        if not self.integrated_main_ram_size:
            sdram_module = IS42S16160(self.clk_freq, "1:1")
            phy_settings = PhySettings(
                memtype="SDR",
                dfi_databits=1*16,
                nphases=1,
                rdphase=0,
                wrphase=0,
                rdcmdphase=0,
                wrcmdphase=0,
                cl=2,
                read_latency=4,
                write_latency=0
            )
            self.submodules.sdrphy = SDRAMPHYModel(sdram_module, phy_settings)
            self.register_sdram(self.sdrphy,
                                sdram_module.geom_settings,
                                sdram_module.timing_settings,
                                controller_settings=ControllerSettings(with_refresh=False))
            # reduce memtest size to speed up simulation
            self.add_constant("MEMTEST_DATA_SIZE", 8*1024)
            self.add_constant("MEMTEST_ADDR_SIZE", 8*1024)


class EthernetSoC(BaseSoC):
    csr_map = {
        "ethphy": 18,
        "ethmac": 19,
    }
    csr_map.update(BaseSoC.csr_map)

    interrupt_map = {
        "ethmac": 3,
    }
    interrupt_map.update(BaseSoC.interrupt_map)

    mem_map = {
        "ethmac": 0x30000000,  # (shadow @0xb0000000)
    }
    mem_map.update(BaseSoC.mem_map)

    def __init__(self, *args, **kwargs):
        BaseSoC.__init__(self, *args, **kwargs)

        self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth"))
        self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
            interface="wishbone", endianness=self.cpu_endianness)
        self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
        self.add_memory_region("ethmac", self.mem_map["ethmac"] | self.shadow_base, 0x2000)


class EtherboneSoC(BaseSoC):
    csr_map = {
        "ethphy":  11,
        "ethcore": 12
    }
    csr_map.update(SoCSDRAM.csr_map)
    def __init__(self, mac_address=0x10e2d5000000, ip_address="192.168.1.50", *args, **kwargs):
        BaseSoC.__init__(self, *args, **kwargs)

        # ethernet phy and hw stack
        self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth"))
        self.submodules.ethcore = LiteEthUDPIPCore(self.ethphy, mac_address, convert_ip(ip_address), self.clk_freq)

        # etherbone
        self.submodules.etherbone = LiteEthEtherbone(self.ethcore.udp, 1234, mode="master")
        self.add_wb_master(self.etherbone.wishbone.bus)


def main():
    parser = argparse.ArgumentParser(description="Generic LiteX SoC Simulation")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.add_argument("--with-ethernet", action="store_true",
                        help="enable Ethernet support")
    parser.add_argument("--with-etherbone", action="store_true",
                        help="enable Etherbone support")
    args = parser.parse_args()

    scfg = SimConfig(default_clk="sys_clk")
    scfg.add_module("serial2console", "serial")
    if args.with_ethernet or args.with_etherbone:
        scfg.add_module('ethernet', "eth", args={"interface": "tap1", "ip": "192.168.1.100"})

    if args.with_ethernet:
        cls = EthernetSoC
    elif args.with_etherbone:
        cls = EtherboneSoC
    else:
        cls = BaseSoC
    soc = cls(**soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build(sim_config=scfg)


if __name__ == "__main__":
    main()
