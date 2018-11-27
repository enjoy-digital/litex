#!/usr/bin/env python3

import argparse

from migen import *
from migen.genlib.io import CRG

from litex.build.generic_platform import *
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig

from litex.soc.integration.soc_core import *
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

from litescope import LiteScopeAnalyzer


class SimPins(Pins):
    def __init__(self, n):
        Pins.__init__(self, "s "*n)

_io = [
    ("sys_clk", 0, SimPins(1)),
    ("sys_rst", 0, SimPins(1)),
    ("serial", 0,
        Subsignal("source_valid", SimPins(1)),
        Subsignal("source_ready", SimPins(1)),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins(1)),
        Subsignal("sink_ready", SimPins(1)),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("eth_clocks", 0,
        Subsignal("none", SimPins(1)),
    ),
    ("eth", 0,
        Subsignal("source_valid", SimPins(1)),
        Subsignal("source_ready", SimPins(1)),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins(1)),
        Subsignal("sink_ready", SimPins(1)),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("eth_clocks", 1,
        Subsignal("none", SimPins(1)),
    ),
    ("eth", 1,
        Subsignal("source_valid", SimPins(1)),
        Subsignal("source_ready", SimPins(1)),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins(1)),
        Subsignal("sink_ready", SimPins(1)),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("vga", 0,
        Subsignal("de", SimPins(1)),
        Subsignal("hsync", SimPins(1)),
        Subsignal("vsync", SimPins(1)),
        Subsignal("r", SimPins(8)),
        Subsignal("g", SimPins(8)),
        Subsignal("b", SimPins(8)),
    ),
]


class Platform(SimPlatform):
    default_clk_name = "sys_clk"
    default_clk_period = 1000  # on modern computers simulate at ~ 1MHz

    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

    def do_finalize(self, fragment):
        pass



def csr_map_update(csr_map, csr_peripherals):
    csr_map.update(dict((n, v)
        for v, n in enumerate(csr_peripherals, start=max(csr_map.values()) + 1)))


class SimSoC(SoCSDRAM):
    csr_peripherals = [
        "ethphy",
        "ethmac",

        "etherbonephy",
        "etherbonecore",

        "analyzer",
    ]
    csr_map_update(SoCSDRAM.csr_map, csr_peripherals)

    interrupt_map = {
        "ethmac": 3,
    }
    interrupt_map.update(SoCSDRAM.interrupt_map)

    mem_map = {
        "ethmac": 0x30000000,  # (shadow @0xb0000000)
    }
    mem_map.update(SoCSDRAM.mem_map)

    def __init__(self,
        with_sdram=False,
        with_ethernet=False,
        with_etherbone=False, etherbone_mac_address=0x10e2d5000000, etherbone_ip_address="192.168.1.50",
        with_analyzer=False,
        **kwargs):
        platform = Platform()
        sys_clk_freq = int(1e9/platform.default_clk_period)
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
            integrated_rom_size=0x8000,
            ident="LiteX Simulation", ident_version=True,
            with_uart=False,
            **kwargs)
        # crg
        self.submodules.crg = CRG(platform.request(platform.default_clk_name))

        # serial
        self.submodules.uart_phy = uart.RS232PHYModel(platform.request("serial"))
        self.submodules.uart = uart.UART(self.uart_phy)

        # sdram
        if with_sdram:
            sdram_module = IS42S16160(sys_clk_freq, "1:1")
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
            self.register_sdram(
                self.sdrphy,
                sdram_module.geom_settings,
                sdram_module.timing_settings,
                controller_settings=ControllerSettings(with_refresh=False))
            # reduce memtest size for simulation speedup
            self.add_constant("MEMTEST_DATA_SIZE", 8*1024)
            self.add_constant("MEMTEST_ADDR_SIZE", 8*1024)

        assert not (with_ethernet and with_etherbone) # FIXME: fix simulator with 2 ethernet interfaces

        # ethernet
        if with_ethernet:
            # eth phy
            self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
            # eth mac
            ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
                interface="wishbone", endianness=self.cpu.endianness)
            if with_etherbone:
                ethmac = ClockDomainsRenamer({"eth_tx": "ethphy_eth_tx", "eth_rx":  "ethphy_eth_rx"})(ethmac)
            self.submodules.ethmac = ethmac
            self.add_wb_slave(mem_decoder(self.mem_map["ethmac"]), self.ethmac.bus)
            self.add_memory_region("ethmac", self.mem_map["ethmac"] | self.shadow_base, 0x2000)

        # etherbone
        if with_etherbone:
            # eth phy
            self.submodules.etherbonephy = LiteEthPHYModel(self.platform.request("eth", 0)) # FIXME
            # eth core
            etherbonecore = LiteEthUDPIPCore(self.etherbonephy,
                etherbone_mac_address, convert_ip(etherbone_ip_address), sys_clk_freq)
            if with_ethernet:
                etherbonecore = ClockDomainsRenamer({"eth_tx": "etherbonephy_eth_tx", "eth_rx":  "etherbonephy_eth_rx"})(etherbonecore)
            self.submodules.etherbonecore = etherbonecore
            # etherbone
            self.submodules.etherbone = LiteEthEtherbone(self.etherbonecore.udp, 1234, mode="master")
            self.add_wb_master(self.etherbone.wishbone.bus)

        # analyzer
        if with_analyzer:
            analyzer_signals = [
                # FIXME: find interesting signals to probe
                self.cpu.ibus,
                self.cpu.dbus
            ]
            self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals, 512)


def main():
    parser = argparse.ArgumentParser(description="Generic LiteX SoC Simulation")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.add_argument("--threads", default=1,
                        help="set number of threads (default=1)")
    parser.add_argument("--rom-init", default=None,
                        help="rom_init file")
    parser.add_argument("--ram-init", default=None,
                        help="ram_init file")
    parser.add_argument("--with-sdram", action="store_true",
                        help="enable SDRAM support")
    parser.add_argument("--with-ethernet", action="store_true",
                        help="enable Ethernet support")
    parser.add_argument("--with-etherbone", action="store_true",
                        help="enable Etherbone support")
    parser.add_argument("--with-analyzer", action="store_true",
                        help="enable Analyzer support")
    parser.add_argument("--trace", action="store_true",
                        help="enable VCD tracing")
    args = parser.parse_args()

    soc_kwargs = soc_sdram_argdict(args)
    builder_kwargs = builder_argdict(args)

    sim_config = SimConfig(default_clk="sys_clk")
    sim_config.add_module("serial2console", "serial")
    if args.rom_init:
        soc_kwargs["integrated_rom_init"] = get_mem_data(args.rom_init)
    if not args.with_sdram:
        soc_kwargs["integrated_main_ram_size"] = 0x10000
        if args.ram_init is not None:
            soc_kwargs["integrated_main_ram_init"] = get_mem_data(args.ram_init)
            soc_kwargs["integrated_main_ram_size"] = max(len(soc_kwargs["integrated_main_ram_init"]), 0x10000)
    else:
        soc_kwargs["integrated_main_ram_size"] = 0x0
    if args.with_ethernet:
        sim_config.add_module("ethernet", "eth", args={"interface": "tap0", "ip": "192.168.1.100"})
    if args.with_etherbone:
        sim_config.add_module('ethernet', "eth", args={"interface": "tap1", "ip": "192.168.1.101"})

    soc = SimSoC(
        with_sdram=args.with_sdram,
        with_ethernet=args.with_ethernet,
        with_etherbone=args.with_etherbone,
        with_analyzer=args.with_analyzer,
        **soc_kwargs)
    builder_kwargs["csr_csv"] = "csr.csv"
    builder = Builder(soc, **builder_kwargs)
    vns = builder.build(run=False, threads=args.threads, sim_config=sim_config, trace=args.trace)
    if args.with_analyzer:
        soc.analyzer.export_csv(vns, "analyzer.csv")
    builder.build(build=False, threads=args.threads, sim_config=sim_config, trace=args.trace)


if __name__ == "__main__":
    main()
