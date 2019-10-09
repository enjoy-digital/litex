#!/usr/bin/env python3

# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# License: BSD

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

from litedram.common import PhySettings
from litedram.modules import MT48LC16M16
from litedram.phy.model import SDRAMPHYModel

from liteeth.common import convert_ip
from liteeth.phy.model import LiteEthPHYModel
from liteeth.mac import LiteEthMAC
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone

from litescope import LiteScopeAnalyzer


class SimPins(Pins):
    def __init__(self, n=1):
        Pins.__init__(self, "s "*n)


_io = [
    ("sys_clk", 0, SimPins(1)),
    ("sys_rst", 0, SimPins(1)),
    ("serial", 0,
        Subsignal("source_valid", SimPins()),
        Subsignal("source_ready", SimPins()),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins()),
        Subsignal("sink_ready", SimPins()),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("eth_clocks", 0,
        Subsignal("none", SimPins()),
    ),
    ("eth", 0,
        Subsignal("source_valid", SimPins()),
        Subsignal("source_ready", SimPins()),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins()),
        Subsignal("sink_ready", SimPins()),
        Subsignal("sink_data", SimPins(8)),
    ),
    ("eth_clocks", 1,
        Subsignal("none", SimPins()),
    ),
    ("eth", 1,
        Subsignal("source_valid", SimPins()),
        Subsignal("source_ready", SimPins()),
        Subsignal("source_data", SimPins(8)),

        Subsignal("sink_valid", SimPins()),
        Subsignal("sink_ready", SimPins()),
        Subsignal("sink_data", SimPins(8)),
    ),
]


class Platform(SimPlatform):
    default_clk_name = "sys_clk"
    default_clk_period = 1000 # ~ 1MHz

    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

    def do_finalize(self, fragment):
        pass


class SimSoC(SoCSDRAM):
    mem_map = {
        "ethmac": 0xb0000000,
    }
    mem_map.update(SoCSDRAM.mem_map)

    def __init__(self,
        with_sdram=False,
        with_ethernet=False,
        with_etherbone=False, etherbone_mac_address=0x10e2d5000000, etherbone_ip_address="192.168.1.50",
        with_analyzer=False,
        **kwargs):
        platform = Platform()
        sys_clk_freq = int(1e6)
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
            integrated_rom_size=0x8000,
            ident="LiteX Simulation", ident_version=True,
            with_uart=False,
            **kwargs)
        # crg
        self.submodules.crg = CRG(platform.request("sys_clk"))

        # serial
        self.submodules.uart_phy = uart.RS232PHYModel(platform.request("serial"))
        self.submodules.uart = uart.UART(self.uart_phy)
        self.add_csr("uart")
        self.add_interrupt("uart")

        # sdram
        if with_sdram:
            sdram_module =  MT48LC16M16(100e6, "1:1") # use 100MHz timings
            phy_settings = PhySettings(
                memtype="SDR",
                databits=32,
                dfi_databits=16,
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
                sdram_module.timing_settings)
            # reduce memtest size for simulation speedup
            self.add_constant("MEMTEST_DATA_SIZE", 8*1024)
            self.add_constant("MEMTEST_ADDR_SIZE", 8*1024)

        assert not (with_ethernet and with_etherbone) # FIXME: fix simulator with 2 ethernet interfaces

        # ethernet
        if with_ethernet:
            # eth phy
            self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
            self.add_csr("ethphy")
            # eth mac
            ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
                interface="wishbone", endianness=self.cpu.endianness)
            if with_etherbone:
                ethmac = ClockDomainsRenamer({"eth_tx": "ethphy_eth_tx", "eth_rx":  "ethphy_eth_rx"})(ethmac)
            self.submodules.ethmac = ethmac
            self.add_wb_slave(self.mem_map["ethmac"], self.ethmac.bus, 0x2000)
            self.add_memory_region("ethmac", self.mem_map["ethmac"], 0x2000, io_region=True)
            self.add_csr("ethmac")
            self.add_interrupt("ethmac")

        # etherbone
        if with_etherbone:
            # eth phy
            self.submodules.etherbonephy = LiteEthPHYModel(self.platform.request("eth", 0)) # FIXME
            self.add_csr("etherbonephy")
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
            self.add_csr("analyzer")


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
    parser.add_argument("--trace-start", default=0,
                        help="cycle to start VCD tracing")
    parser.add_argument("--trace-end", default=-1,
                        help="cycle to end VCD tracing")
    parser.add_argument("--opt-level", default="O3",
                        help="compilation optimization level")
    args = parser.parse_args()

    soc_kwargs = soc_sdram_argdict(args)
    builder_kwargs = builder_argdict(args)

    sim_config = SimConfig(default_clk="sys_clk")
    sim_config.add_module("serial2console", "serial")

    cpu_endianness = "little"
    if "cpu_type" in soc_kwargs:
        if soc_kwargs["cpu_type"] in ["mor1kx", "lm32"]:
            cpu_endianness = "big"

    if args.rom_init:
        soc_kwargs["integrated_rom_init"] = get_mem_data(args.rom_init, cpu_endianness)
    if not args.with_sdram:
        soc_kwargs["integrated_main_ram_size"] = 0x10000000 # 256 MB
        if args.ram_init is not None:
            soc_kwargs["integrated_main_ram_init"] = get_mem_data(args.ram_init, cpu_endianness)
    else:
        assert args.ram_init is None
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
    if args.ram_init is not None:
        soc.add_constant("ROM_BOOT_ADDRESS", 0x40000000)
    builder_kwargs["csr_csv"] = "csr.csv"
    builder = Builder(soc, **builder_kwargs)
    vns = builder.build(run=False, threads=args.threads, sim_config=sim_config,
        opt_level=args.opt_level,
        trace=args.trace, trace_start=int(args.trace_start), trace_end=int(args.trace_end))
    if args.with_analyzer:
        soc.analyzer.export_csv(vns, "analyzer.csv")
    builder.build(build=False, threads=args.threads, sim_config=sim_config,
        opt_level=args.opt_level,
        trace=args.trace, trace_start=int(args.trace_start), trace_end=int(args.trace_end))


if __name__ == "__main__":
    main()
