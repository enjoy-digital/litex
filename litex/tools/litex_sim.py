#!/usr/bin/env python3

# This file is Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
# This file is Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# License: BSD

import argparse

from migen import *

from litex.build.generic_platform import *
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig

from litex.soc.integration.common import *
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *
from litex.soc.integration.soc import *

from litedram import modules as litedram_modules
from litedram.common import *
from litedram.phy.model import SDRAMPHYModel

from liteeth.phy.model import LiteEthPHYModel
from liteeth.mac import LiteEthMAC
from liteeth.core.arp import LiteEthARP
from liteeth.core.ip import LiteEthIP
from liteeth.core.udp import LiteEthUDP
from liteeth.core.icmp import LiteEthICMP
from liteeth.core import LiteEthUDPIPCore
from liteeth.frontend.etherbone import LiteEthEtherbone
from liteeth.common import *

from litescope import LiteScopeAnalyzer

from litedram.modulemodel import SDRAMModuleModel
from litedram.phy.genericddr3phy import GenericDDR3PHY
from litedram.core import ControllerSettings
from litedram.modules import MT41K64M16

class DebugHelper(Module, AutoCSR):
    def __init__(self):
        self.tag = CSRStorage(128, atomic_write=True)
        self.arg = CSRStorage(32, atomic_write=True, reset=0xFFFFFFFF)
        self.finish = CSR()
        self.sync += If(self.finish.re, Finish())

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("sys_clk", 0, Pins(1)),
    ("dram_clk", 0,
        Subsignal("full_clk",   Pins(1)),
        Subsignal("half_a_clk", Pins(1)),
        Subsignal("half_b_clk", Pins(1)),
    ),
    ("sys_rst", 0, Pins(1)),
    ("serial", 0,
        Subsignal("source_valid", Pins(1)),
        Subsignal("source_ready", Pins(1)),
        Subsignal("source_data",  Pins(8)),

        Subsignal("sink_valid",   Pins(1)),
        Subsignal("sink_ready",   Pins(1)),
        Subsignal("sink_data",    Pins(8)),
    ),
    ("eth_clocks", 0,
        Subsignal("tx", Pins(1)),
        Subsignal("rx", Pins(1)),
    ),
    ("eth", 0,
        Subsignal("source_valid", Pins(1)),
        Subsignal("source_ready", Pins(1)),
        Subsignal("source_data",  Pins(8)),

        Subsignal("sink_valid",   Pins(1)),
        Subsignal("sink_ready",   Pins(1)),
        Subsignal("sink_data",    Pins(8)),
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(SimPlatform):
    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

# DFI PHY model settings ---------------------------------------------------------------------------

sdram_module_nphases = {
    "SDR":   1,
    "DDR":   2,
    "LPDDR": 2,
    "DDR2":  2,
    "DDR3":  4,
    "DDR4":  4,
}

def get_sdram_phy_settings(memtype, data_width, clk_freq):
    nphases = sdram_module_nphases[memtype]

    if memtype == "SDR":
        # Settings from gensdrphy
        rdphase       = 0
        wrphase       = 0
        rdcmdphase    = 0
        wrcmdphase    = 0
        cl            = 2
        cwl           = None
        read_latency  = 4
        write_latency = 0
    elif memtype in ["DDR", "LPDDR"]:
        # Settings from s6ddrphy
        rdphase       = 0
        wrphase       = 1
        rdcmdphase    = 1
        wrcmdphase    = 0
        cl            = 3
        cwl           = None
        read_latency  = 5
        write_latency = 0
    elif memtype in ["DDR2", "DDR3"]:
        # Settings from s7ddrphy
        tck                 = 2/(2*nphases*clk_freq)
        cmd_latency         = 0
        cl, cwl             = get_cl_cw(memtype, tck)
        cl_sys_latency      = get_sys_latency(nphases, cl)
        cwl                 = cwl + cmd_latency
        cwl_sys_latency     = get_sys_latency(nphases, cwl)
        rdcmdphase, rdphase = get_sys_phases(nphases, cl_sys_latency, cl)
        wrcmdphase, wrphase = get_sys_phases(nphases, cwl_sys_latency, cwl)
        read_latency        = 2 + cl_sys_latency + 2 + 3
        write_latency       = cwl_sys_latency
    elif memtype == "DDR4":
        # Settings from usddrphy
        tck                 = 2/(2*nphases*clk_freq)
        cmd_latency         = 0
        cl, cwl             = get_cl_cw(memtype, tck)
        cl_sys_latency      = get_sys_latency(nphases, cl)
        cwl                 = cwl + cmd_latency
        cwl_sys_latency     = get_sys_latency(nphases, cwl)
        rdcmdphase, rdphase = get_sys_phases(nphases, cl_sys_latency, cl)
        wrcmdphase, wrphase = get_sys_phases(nphases, cwl_sys_latency, cwl)
        read_latency        = 2 + cl_sys_latency + 1 + 3
        write_latency       = cwl_sys_latency

    sdram_phy_settings = {
        "nphases":       nphases,
        "rdphase":       rdphase,
        "wrphase":       wrphase,
        "rdcmdphase":    rdcmdphase,
        "wrcmdphase":    wrcmdphase,
        "cl":            cl,
        "cwl":           cwl,
        "read_latency":  read_latency,
        "write_latency": write_latency,
    }

    return PhySettings(
        phytype      = "SDRAMPHYModel",
        memtype      = memtype,
        databits     = data_width,
        dfi_databits = data_width if memtype == "SDR" else 2*data_width,
        **sdram_phy_settings,
    )

class SimCRG(CRG):
    def __init__(self, platform):
        clk = platform.request("sys_clk") 
        dram_clk = platform.request("dram_clk")

        super().__init__(clk=clk, rst=0)

        self.sdram_half_a = dram_clk.half_a_clk
        self.sdram_half_b = dram_clk.half_b_clk

        self.clock_domains.cd_sdram_half = ClockDomain()
        self.comb += self.cd_sdram_half.clk.eq(self.sdram_half_a)

        self.clock_domains.cd_sdram_full = ClockDomain()
        self.comb += self.cd_sdram_full.clk.eq(dram_clk.full_clk)

        self.clock_domains.cd_sdram_full_wr = ClockDomain()
        self.clock_domains.cd_sdram_full_rd = ClockDomain()
        self.clk4x_wr_strb = Signal()
        self.clk4x_rd_strb = Signal()

        pll_lckd = Signal()

        # sdram_full
        self.specials += Instance("BUFPLL", name="sdram_full_bufpll",
                                  p_DIVIDE=4,
                                  i_PLLIN=self.cd_sdram_full.clk, i_GCLK=self.cd_sys.clk,
                                  i_LOCKED=pll_lckd,
                                  o_IOCLK=self.cd_sdram_full_wr.clk,
                                  o_SERDESSTROBE=self.clk4x_wr_strb)
        self.comb += [
            self.cd_sdram_full_rd.clk.eq(self.cd_sdram_full_wr.clk),
            self.clk4x_rd_strb.eq(self.clk4x_wr_strb)
        ]

# Simulation SoC -----------------------------------------------------------------------------------

class SimSoC(SoCSDRAM):
    mem_map = {
        "ethmac": 0xb0000000,
    }
    mem_map.update(SoCSDRAM.mem_map)

    def __init__(self,
        with_sdram            = False,
        with_ethernet         = False,
        with_etherbone        = False,
        etherbone_mac_address = 0x10e2d5000001,
        etherbone_ip_address  = "192.168.1.51",
        with_analyzer         = False,
        sdram_module          = "MT41K64M16",
        sdram_init            = [],
        sdram_data_width      = 32,
        sdram_spd_data        = None,
        sdram_verbosity       = 0,
        **kwargs):
        platform     = Platform()
        sys_clk_freq = int(200e6)

        # SoCSDRAM ---------------------------------------------------------------------------------
        SoCSDRAM.__init__(self, platform, clk_freq=sys_clk_freq,
            ident               = "LiteX Simulation", ident_version=True,
            l2_reverse          = False,
            **kwargs)
        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = SimCRG(platform)

        # SDRAM ------------------------------------------------------------------------------------

        self.submodules.sdram_module_model = SDRAMModuleModel(platform)
        if with_sdram:
            self.comb += self.sdram_module_model.clk_p.eq(self.crg.sdram_half_b)
            self.comb += self.sdram_module_model.clk_n.eq(~self.crg.sdram_half_b)

            sdram_clk_freq   = int(400e6)
            sdram_module = MT41K64M16(sdram_clk_freq, "1:2")

            self.submodules.ddrphy = GenericDDR3PHY(
                self.sdram_module_model,
                "DDR3",
                rd_bitslip=0,
                wr_bitslip=4,
                platform=platform)
            controller_settings = ControllerSettings(with_bandwidth=True)
            self.register_sdram(self.ddrphy,
                                sdram_module.geom_settings,
                                sdram_module.timing_settings,
                                controller_settings=controller_settings)

            self.comb += [
                self.ddrphy.clk4x_wr_strb.eq(self.crg.clk4x_wr_strb),
                self.ddrphy.clk4x_rd_strb.eq(self.crg.clk4x_rd_strb),
            ]

            # Reduce memtest size for simulation speedup
            self.add_constant("MEMTEST_BUS_SIZE",  128)
            self.add_constant("MEMTEST_DATA_SIZE", 128)
            self.add_constant("MEMTEST_ADDR_SIZE", 128)

        #assert not (with_ethernet and with_etherbone)

        if with_ethernet and with_etherbone:
            dw = 8
            etherbone_ip_address = convert_ip(etherbone_ip_address)
            # Ethernet PHY
            self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
            self.add_csr("ethphy")
            # Ethernet MAC
            self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=dw,
                interface  = "hybrid",
                endianness = self.cpu.endianness,
                hw_mac     = etherbone_mac_address)

            # SoftCPU
            self.add_memory_region("ethmac", self.mem_map["ethmac"], 0x2000, type="io")
            self.add_wb_slave(self.mem_regions["ethmac"].origin, self.ethmac.bus, 0x2000)
            self.add_csr("ethmac")
            self.add_interrupt("ethmac")
            # HW ethernet
            self.submodules.arp = LiteEthARP(self.ethmac, etherbone_mac_address, etherbone_ip_address, sys_clk_freq, dw=dw)
            self.submodules.ip = LiteEthIP(self.ethmac, etherbone_mac_address, etherbone_ip_address, self.arp.table, dw=dw)
            self.submodules.icmp = LiteEthICMP(self.ip, etherbone_ip_address, dw=dw)
            self.submodules.udp = LiteEthUDP(self.ip, etherbone_ip_address, dw=dw)
            # Etherbone
            self.submodules.etherbone = LiteEthEtherbone(self.udp, 1234, mode="master")
            self.add_wb_master(self.etherbone.wishbone.bus)

        # Ethernet ---------------------------------------------------------------------------------
        elif with_ethernet:
            # Ethernet PHY
            self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
            self.add_csr("ethphy")
            # Ethernet MAC
            ethmac = LiteEthMAC(phy=self.ethphy, dw=32,
                interface  = "wishbone",
                endianness = self.cpu.endianness)
            if with_etherbone:
                ethmac = ClockDomainsRenamer({"eth_tx": "ethphy_eth_tx", "eth_rx":  "ethphy_eth_rx"})(ethmac)
            self.submodules.ethmac = ethmac
            self.add_memory_region("ethmac", self.mem_map["ethmac"], 0x2000, type="io")
            self.add_wb_slave(self.mem_regions["ethmac"].origin, self.ethmac.bus, 0x2000)
            self.add_csr("ethmac")
            self.add_interrupt("ethmac")

        # Etherbone --------------------------------------------------------------------------------
        elif with_etherbone:
            # Ethernet PHY
            self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0)) # FIXME
            self.add_csr("ethphy")
            # Ethernet Core
            ethcore = LiteEthUDPIPCore(self.ethphy,
                mac_address = etherbone_mac_address,
                ip_address  = etherbone_ip_address,
                clk_freq    = sys_clk_freq)
            self.submodules.ethcore = ethcore
            # Etherbone
            self.submodules.etherbone = LiteEthEtherbone(self.ethcore.udp, 1234, mode="master")
            self.add_wb_master(self.etherbone.wishbone.bus)

        # Analyzer ---------------------------------------------------------------------------------
        if with_analyzer:
            analyzer_signals = [
                self.cpu.ibus.stb,
                self.cpu.ibus.cyc,
                self.cpu.ibus.adr,
                self.cpu.ibus.we,
                self.cpu.ibus.ack,
                self.cpu.ibus.sel,
                self.cpu.ibus.dat_w,
                self.cpu.ibus.dat_r,
            ]
            self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
                depth        = 512,
                clock_domain = "sys",
                csr_csv      = "analyzer.csv")
            self.add_csr("analyzer")
        
        self.submodules.debug_helper = DebugHelper()
        self.add_csr("debug_helper")

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generic LiteX SoC Simulation")
    builder_args(parser)
    soc_sdram_args(parser)
    parser.add_argument("--threads",              default=1,               help="Set number of threads (default=1)")
    parser.add_argument("--rom-init",             default=None,            help="rom_init file")
    parser.add_argument("--ram-init",             default=None,            help="ram_init file")
    parser.add_argument("--with-sdram",           action="store_true",     help="Enable SDRAM support")
    parser.add_argument("--sdram-module",         default="MT41K64M16",    help="Select SDRAM chip")
    parser.add_argument("--sdram-data-width",     default=32,              help="Set SDRAM chip data width")
    parser.add_argument("--sdram-init",           default=None,            help="SDRAM init file")
    parser.add_argument("--sdram-from-spd-data",  default=None,            help="Generate SDRAM module based on SPD data from file")
    parser.add_argument("--sdram-verbosity",      default=0,               help="Set SDRAM checker verbosity")
    parser.add_argument("--with-ethernet",        action="store_true",     help="Enable Ethernet support")
    parser.add_argument("--with-etherbone",       action="store_true",     help="Enable Etherbone support")
    parser.add_argument("--local-ip",             default="192.168.1.50",  help="Local IP address of SoC (default=192.168.1.50)")
    parser.add_argument("--remote-ip",            default="192.168.1.100", help="Remote IP address of TFTP server (default=192.168.1.100)")
    parser.add_argument("--with-analyzer",        action="store_true",     help="Enable Analyzer support")
    parser.add_argument("--trace",                action="store_true",     help="Enable Tracing")
    parser.add_argument("--trace-fst",            action="store_true",     help="Enable FST tracing (default=VCD)")
    parser.add_argument("--trace-start",          default=0,               help="Cycle to start tracing")
    parser.add_argument("--trace-end",            default=-1,              help="Cycle to end tracing")
    parser.add_argument("--opt-level",            default="O3",            help="Compilation optimization level")
    args = parser.parse_args()

    soc_kwargs     = soc_sdram_argdict(args)
    builder_kwargs = builder_argdict(args)

    sim_config = SimConfig(default_clk="sys_clk")
    sim_config.add_module("serial2console", "serial")

    # Configuration --------------------------------------------------------------------------------

    cpu_endianness = "little"
    if "cpu_type" in soc_kwargs:
        if soc_kwargs["cpu_type"] in ["mor1kx", "lm32"]:
            cpu_endianness = "big"
    soc_kwargs["uart_name"] = "sim"
    if args.rom_init:
        soc_kwargs["integrated_rom_init"] = get_mem_data(args.rom_init, cpu_endianness)
    if not args.with_sdram:
        soc_kwargs["integrated_main_ram_size"] = 0x10000000 # 256 MB
        if args.ram_init is not None:
            soc_kwargs["integrated_main_ram_init"] = get_mem_data(args.ram_init, cpu_endianness)
    else:
        assert args.ram_init is None
        soc_kwargs["integrated_main_ram_size"] = 0x0
        soc_kwargs["sdram_module"]             = args.sdram_module
        soc_kwargs["sdram_data_width"]         = int(args.sdram_data_width)
        soc_kwargs["sdram_verbosity"]          = int(args.sdram_verbosity)
        if args.sdram_from_spd_data:
            with open(args.sdram_from_spd_data, "rb") as f:
                soc_kwargs["sdram_spd_data"] = [int(b) for b in f.read()]

    if args.with_ethernet or args.with_etherbone:
        sim_config.add_module("ethernet", "eth", args={"interface": "tap0", "ip": args.remote_ip})

    # SoC ------------------------------------------------------------------------------------------
    soc = SimSoC(
        with_sdram     = args.with_sdram,
        with_ethernet  = args.with_ethernet,
        with_etherbone = args.with_etherbone,
        with_analyzer  = args.with_analyzer,
        sdram_init     = [] if args.sdram_init is None else get_mem_data(args.sdram_init, cpu_endianness),
        **soc_kwargs)
    if args.ram_init is not None:
        soc.add_constant("ROM_BOOT_ADDRESS", 0x40000000)
    if args.with_ethernet:
        for i in range(4):
            soc.add_constant("LOCALIP{}".format(i+1), int(args.local_ip.split(".")[i]))
        for i in range(4):
            soc.add_constant("REMOTEIP{}".format(i+1), int(args.remote_ip.split(".")[i]))

    # Build/Run ------------------------------------------------------------------------------------
    builder_kwargs["csr_csv"] = "csr.csv"
    builder = Builder(soc, **builder_kwargs)
    vns = builder.build(run=False, threads=args.threads, sim_config=sim_config,
        opt_level   = args.opt_level,
        trace       = args.trace,
        trace_fst   = args.trace_fst,
        trace_start = int(args.trace_start),
        trace_end   = int(args.trace_end))
    if args.with_analyzer:
        soc.analyzer.export_csv(vns, "analyzer.csv")
    builder.build(build=False, threads=args.threads, sim_config=sim_config,
        opt_level   = args.opt_level,
        trace       = args.trace,
        trace_fst   = args.trace,
        trace_start = int(args.trace_start),
        trace_end   = int(args.trace_end)
    )

if __name__ == "__main__":
    main()
