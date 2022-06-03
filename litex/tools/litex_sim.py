#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# SPDX-License-Identifier: BSD-2-Clause

import sys
import argparse

from migen import *

from litex.build.generic_platform import *
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.build.sim.verilator import verilator_build_args, verilator_build_argdict

from litex.soc.integration.common import *
from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.integration.soc import *
from litex.soc.cores.bitbang import *
from litex.soc.cores.gpio import GPIOTristate
from litex.soc.cores.cpu import CPUS

from litedram import modules as litedram_modules
from litedram.modules import parse_spd_hexdump
from litedram.phy.model import sdram_module_nphases, get_sdram_phy_settings
from litedram.phy.model import SDRAMPHYModel

from liteeth.phy.gmii import LiteEthPHYGMII
from liteeth.phy.xgmii import LiteEthPHYXGMII
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

# IOs ----------------------------------------------------------------------------------------------

_io = [
    # Clk / Rst.
    ("sys_clk", 0, Pins(1)),
    ("sys_rst", 0, Pins(1)),

    # Serial.
    ("serial", 0,
        Subsignal("source_valid", Pins(1)),
        Subsignal("source_ready", Pins(1)),
        Subsignal("source_data",  Pins(8)),

        Subsignal("sink_valid",   Pins(1)),
        Subsignal("sink_ready",   Pins(1)),
        Subsignal("sink_data",    Pins(8)),
    ),

    # Ethernet (Stream Endpoint).
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

    # Ethernet (XGMII).
    ("xgmii_eth", 0,
        Subsignal("rx_data",      Pins(64)),
        Subsignal("rx_ctl",       Pins(8)),
        Subsignal("tx_data",      Pins(64)),
        Subsignal("tx_ctl",       Pins(8)),
    ),

    # Ethernet (GMII).
    ("gmii_eth", 0,
        Subsignal("rx_data",      Pins(8)),
        Subsignal("rx_dv",        Pins(1)),
        Subsignal("rx_er",        Pins(1)),
        Subsignal("tx_data",      Pins(8)),
        Subsignal("tx_en",        Pins(1)),
        Subsignal("tx_er",        Pins(1)),
    ),

    # I2C.
    ("i2c", 0,
        Subsignal("scl",     Pins(1)),
        Subsignal("sda_out", Pins(1)),
        Subsignal("sda_in",  Pins(1)),
    ),

    # SPI-Flash (X1).
    ("spiflash", 0,
        Subsignal("cs_n", Pins(1)),
        Subsignal("clk",  Pins(1)),
        Subsignal("mosi", Pins(1)),
        Subsignal("miso", Pins(1)),
        Subsignal("wp",   Pins(1)),
        Subsignal("hold", Pins(1)),
    ),

    # SPI-Flash (X4).
    ("spiflash4x", 0,
        Subsignal("cs_n", Pins(1)),
        Subsignal("clk",  Pins(1)),
        Subsignal("dq",   Pins(4)),
    ),

    # Tristate GPIOs (for sim control/status).
    ("gpio", 0,
        Subsignal("oe", Pins(32)),
        Subsignal("o",  Pins(32)),
        Subsignal("i",  Pins(32)),
    )
]

# Platform -----------------------------------------------------------------------------------------

class Platform(SimPlatform):
    def __init__(self):
        SimPlatform.__init__(self, "SIM", _io)

# Simulation SoC -----------------------------------------------------------------------------------

class SimSoC(SoCCore):
    def __init__(self,
        with_sdram            = False,
        with_ethernet         = False,
        ethernet_phy_model    = "sim",
        with_etherbone        = False,
        etherbone_mac_address = 0x10e2d5000001,
        etherbone_ip_address  = "192.168.1.51",
        with_analyzer         = False,
        sdram_module          = "MT48LC16M16",
        sdram_init            = [],
        sdram_data_width      = 32,
        sdram_spd_data        = None,
        sdram_verbosity       = 0,
        with_i2c              = False,
        with_sdcard           = False,
        with_spi_flash        = False,
        spi_flash_init        = [],
        with_gpio             = False,
        sim_debug             = False,
        trace_reset_on        = False,
        **kwargs):
        platform     = Platform()
        sys_clk_freq = int(1e6)

        # CRG --------------------------------------------------------------------------------------
        self.submodules.crg = CRG(platform.request("sys_clk"))

        # SoCCore ----------------------------------------------------------------------------------
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq,
            ident = "LiteX Simulation",
            **kwargs)

        # BIOS Config ------------------------------------------------------------------------------
        # FIXME: Expose?
        #self.add_config("BIOS_NO_PROMPT")
        #self.add_config("BIOS_NO_DELAYS")
        #self.add_config("BIOS_NO_BUILD_TIME")
        #self.add_config("BIOS_NO_CRC")

        # SDRAM ------------------------------------------------------------------------------------
        if not self.integrated_main_ram_size and with_sdram:
            sdram_clk_freq = int(100e6) # FIXME: use 100MHz timings
            if sdram_spd_data is None:
                sdram_module_cls = getattr(litedram_modules, sdram_module)
                sdram_rate       = "1:{}".format(sdram_module_nphases[sdram_module_cls.memtype])
                sdram_module     = sdram_module_cls(sdram_clk_freq, sdram_rate)
            else:
                sdram_module = litedram_modules.SDRAMModule.from_spd_data(sdram_spd_data, sdram_clk_freq)
            self.submodules.sdrphy = SDRAMPHYModel(
                module     = sdram_module,
                data_width = sdram_data_width,
                clk_freq   = sdram_clk_freq,
                verbosity  = sdram_verbosity,
                init       = sdram_init)
            self.add_sdram("sdram",
                phy                     = self.sdrphy,
                module                  = sdram_module,
                l2_cache_size           = kwargs.get("l2_size", 8192),
                l2_cache_min_data_width = kwargs.get("min_l2_data_width", 128),
                l2_cache_reverse        = False
            )
            if sdram_init != []:
                # Skip SDRAM test to avoid corrupting pre-initialized contents.
                self.add_constant("SDRAM_TEST_DISABLE")
            else:
                # Reduce memtest size for simulation speedup
                self.add_constant("MEMTEST_DATA_SIZE", 8*1024)
                self.add_constant("MEMTEST_ADDR_SIZE", 8*1024)

        # Ethernet / Etherbone PHY -----------------------------------------------------------------
        if with_ethernet or with_etherbone:
            if ethernet_phy_model == "sim":
                self.submodules.ethphy = LiteEthPHYModel(self.platform.request("eth", 0))
            elif ethernet_phy_model == "xgmii":
                self.submodules.ethphy = LiteEthPHYXGMII(None, self.platform.request("xgmii_eth", 0), model=True)
            elif ethernet_phy_model == "gmii":
                self.submodules.ethphy = LiteEthPHYGMII(None, self.platform.request("gmii_eth", 0), model=True)
            else:
                raise ValueError("Unknown Ethernet PHY model:", ethernet_phy_model)

        # Ethernet and Etherbone -------------------------------------------------------------------
        if with_ethernet and with_etherbone:
            etherbone_ip_address = convert_ip(etherbone_ip_address)
            # Ethernet MAC
            self.submodules.ethmac = LiteEthMAC(phy=self.ethphy, dw=8,
                interface  = "hybrid",
                endianness = self.cpu.endianness,
                hw_mac     = etherbone_mac_address)

            # SoftCPU
            self.add_memory_region("ethmac", self.mem_map.get("ethmac", None), 0x2000, type="io")
            self.add_wb_slave(self.mem_regions["ethmac"].origin, self.ethmac.bus, 0x2000)
            if self.irq.enabled:
                self.irq.add("ethmac", use_loc_if_exists=True)
            # HW ethernet
            self.submodules.arp  = LiteEthARP(self.ethmac, etherbone_mac_address, etherbone_ip_address, sys_clk_freq, dw=8)
            self.submodules.ip   = LiteEthIP(self.ethmac, etherbone_mac_address, etherbone_ip_address, self.arp.table, dw=8)
            self.submodules.icmp = LiteEthICMP(self.ip, etherbone_ip_address, dw=8)
            self.submodules.udp  = LiteEthUDP(self.ip, etherbone_ip_address, dw=8)
            # Etherbone
            self.submodules.etherbone = LiteEthEtherbone(self.udp, 1234, mode="master")
            self.bus.add_master(master=self.etherbone.wishbone.bus)

        # Ethernet ---------------------------------------------------------------------------------
        elif with_ethernet:
            # Ethernet MAC
            self.submodules.ethmac = ethmac = LiteEthMAC(
                phy        = self.ethphy,
                dw         = 64 if ethernet_phy_model == "xgmii" else 32,
                interface  = "wishbone",
                endianness = self.cpu.endianness)
            ethmac_region_size = (ethmac.rx_slots.constant + ethmac.tx_slots.constant)*ethmac.slot_size.constant
            self.add_memory_region("ethmac", self.mem_map.get("ethmac", None), ethmac_region_size, type="io")
            self.add_wb_slave(self.mem_regions["ethmac"].origin, ethmac.bus, ethmac_region_size)
            if self.irq.enabled:
                self.irq.add("ethmac", use_loc_if_exists=True)

        # Etherbone --------------------------------------------------------------------------------
        elif with_etherbone:
            self.add_etherbone(
                phy         = self.ethphy,
                ip_address  = etherbone_ip_address,
                mac_address = etherbone_mac_address
            )

        # I2C --------------------------------------------------------------------------------------
        if with_i2c:
            pads = platform.request("i2c", 0)
            self.submodules.i2c = I2CMasterSim(pads)

        # SDCard -----------------------------------------------------------------------------------
        if with_sdcard:
            self.add_sdcard("sdcard", use_emulator=True)

        # SPI Flash --------------------------------------------------------------------------------
        if with_spi_flash:
            from litespi.phy.model import LiteSPIPHYModel
            from litespi.modules import S25FL128L
            from litespi.opcodes import SpiNorFlashOpCodes as Codes
            spiflash_module = S25FL128L(Codes.READ_1_1_4)
            if spi_flash_init is None:
                platform.add_sources(os.path.abspath(os.path.dirname(__file__)), "../build/sim/verilog/iddr_verilog.v")
                platform.add_sources(os.path.abspath(os.path.dirname(__file__)), "../build/sim/verilog/oddr_verilog.v")
            self.submodules.spiflash_phy = LiteSPIPHYModel(spiflash_module, init=spi_flash_init)
            self.add_spi_flash(phy=self.spiflash_phy, mode="4x", module=spiflash_module, with_master=True)

        # GPIO --------------------------------------------------------------------------------------
        if with_gpio:
            self.submodules.gpio = GPIOTristate(platform.request("gpio"), with_irq=True)
            self.irq.add("gpio", use_loc_if_exists=True)

        # Simulation debugging ----------------------------------------------------------------------
        if sim_debug:
            platform.add_debug(self, reset=1 if trace_reset_on else 0)
        else:
            self.comb += platform.trace.eq(1)

        # Analyzer ---------------------------------------------------------------------------------
        if with_analyzer:
            analyzer_signals = [
                # IBus (could also just added as self.cpu.ibus)
                self.cpu.ibus.stb,
                self.cpu.ibus.cyc,
                self.cpu.ibus.adr,
                self.cpu.ibus.we,
                self.cpu.ibus.ack,
                self.cpu.ibus.sel,
                self.cpu.ibus.dat_w,
                self.cpu.ibus.dat_r,
                # DBus (could also just added as self.cpu.dbus)
                self.cpu.dbus.stb,
                self.cpu.dbus.cyc,
                self.cpu.dbus.adr,
                self.cpu.dbus.we,
                self.cpu.dbus.ack,
                self.cpu.dbus.sel,
                self.cpu.dbus.dat_w,
                self.cpu.dbus.dat_r,
            ]
            self.submodules.analyzer = LiteScopeAnalyzer(analyzer_signals,
                depth        = 512,
                clock_domain = "sys",
                csr_csv      = "analyzer.csv")

# Build --------------------------------------------------------------------------------------------

def generate_gtkw_savefile(builder, vns, trace_fst):
    from litex.build.sim import gtkwave as gtkw
    dumpfile = os.path.join(builder.gateware_dir, "sim.{}".format("fst" if trace_fst else "vcd"))
    savefile = os.path.join(builder.gateware_dir, "sim.gtkw")
    soc = builder.soc

    with gtkw.GTKWSave(vns, savefile=savefile, dumpfile=dumpfile) as save:
        save.clocks()
        save.fsm_states(soc)
        if "main_ram" in soc.bus.slaves.keys():
            save.add(soc.bus.slaves["main_ram"], mappers=[gtkw.wishbone_sorter(), gtkw.wishbone_colorer()])

        if hasattr(soc, "sdrphy"):
            # all dfi signals
            save.add(soc.sdrphy.dfi, mappers=[gtkw.dfi_sorter(), gtkw.dfi_in_phase_colorer()])

            # each phase in separate group
            with save.gtkw.group("dfi phaseX", closed=True):
                for i, phase in enumerate(soc.sdrphy.dfi.phases):
                    save.add(phase, group_name="dfi p{}".format(i), mappers=[
                        gtkw.dfi_sorter(phases=False),
                        gtkw.dfi_in_phase_colorer(),
                    ])

            # only dfi command/data signals
            def dfi_group(name, suffixes):
                save.add(soc.sdrphy.dfi, group_name=name, mappers=[
                    gtkw.regex_filter(gtkw.suffixes2re(suffixes)),
                    gtkw.dfi_sorter(),
                    gtkw.dfi_per_phase_colorer(),
                ])

            dfi_group("dfi commands", ["cas_n", "ras_n", "we_n"])
            dfi_group("dfi commands", ["wrdata"])
            dfi_group("dfi commands", ["wrdata_mask"])
            dfi_group("dfi commands", ["rddata"])

def sim_args(parser):
    builder_args(parser)
    soc_core_args(parser)
    verilator_build_args(parser)
    parser.add_argument("--rom-init",             default=None,            help="ROM init file (.bin or .json).")
    parser.add_argument("--ram-init",             default=None,            help="RAM init file (.bin or .json).")
    parser.add_argument("--with-sdram",           action="store_true",     help="Enable SDRAM support.")
    parser.add_argument("--sdram-module",         default="MT48LC16M16",   help="Select SDRAM chip.")
    parser.add_argument("--sdram-data-width",     default=32,              help="Set SDRAM chip data width.")
    parser.add_argument("--sdram-init",           default=None,            help="SDRAM init file (.bin or .json).")
    parser.add_argument("--sdram-from-spd-dump",  default=None,            help="Generate SDRAM module based on data from SPD EEPROM dump.")
    parser.add_argument("--sdram-verbosity",      default=0,               help="Set SDRAM checker verbosity.")
    parser.add_argument("--with-ethernet",        action="store_true",     help="Enable Ethernet support.")
    parser.add_argument("--ethernet-phy-model",   default="sim",           help="Ethernet PHY to simulate (sim, xgmii or gmii).")
    parser.add_argument("--with-etherbone",       action="store_true",     help="Enable Etherbone support.")
    parser.add_argument("--local-ip",             default="192.168.1.50",  help="Local IP address of SoC.")
    parser.add_argument("--remote-ip",            default="192.168.1.100", help="Remote IP address of TFTP server.")
    parser.add_argument("--with-analyzer",        action="store_true",     help="Enable Analyzer support.")
    parser.add_argument("--with-i2c",             action="store_true",     help="Enable I2C support.")
    parser.add_argument("--with-sdcard",          action="store_true",     help="Enable SDCard support.")
    parser.add_argument("--with-spi-flash",       action="store_true",     help="Enable SPI Flash (MMAPed).")
    parser.add_argument("--spi_flash-init",       default=None,            help="SPI Flash init file.")
    parser.add_argument("--with-gpio",            action="store_true",     help="Enable Tristate GPIO (32 pins).")
    parser.add_argument("--sim-debug",            action="store_true",     help="Add simulation debugging modules.")
    parser.add_argument("--gtkwave-savefile",     action="store_true",     help="Generate GTKWave savefile.")
    parser.add_argument("--non-interactive",      action="store_true",     help="Run simulation without user input.")

def main():
    from litex.soc.integration.soc import LiteXSoCArgumentParser
    parser = LiteXSoCArgumentParser(description="LiteX SoC Simulation utility")
    sim_args(parser)
    args = parser.parse_args()

    soc_kwargs             = soc_core_argdict(args)
    builder_kwargs         = builder_argdict(args)
    verilator_build_kwargs = verilator_build_argdict(args)

    sys_clk_freq = int(1e6)
    sim_config   = SimConfig()
    sim_config.add_clocker("sys_clk", freq_hz=sys_clk_freq)

    # Configuration --------------------------------------------------------------------------------

    cpu = CPUS.get(soc_kwargs.get("cpu_type", "vexriscv"))

    # UART.
    if soc_kwargs["uart_name"] == "serial":
        soc_kwargs["uart_name"] = "sim"
        sim_config.add_module("serial2console", "serial")

    # ROM.
    if args.rom_init:
        soc_kwargs["integrated_rom_init"] = get_mem_data(args.rom_init, endianness=cpu.endianness)

    # RAM / SDRAM.
    ram_boot_offset  = 0x40000000 # FIXME
    ram_boot_address = None
    soc_kwargs["integrated_main_ram_size"] = args.integrated_main_ram_size
    if args.integrated_main_ram_size:
        if args.ram_init is not None:
            soc_kwargs["integrated_main_ram_init"] = get_mem_data(args.ram_init, endianness=cpu.endianness, offset=ram_boot_offset)
            ram_boot_address                       = get_boot_address(args.ram_init)
    elif args.with_sdram:
        assert args.ram_init is None
        soc_kwargs["sdram_module"]     = args.sdram_module
        soc_kwargs["sdram_data_width"] = int(args.sdram_data_width)
        soc_kwargs["sdram_verbosity"]  = int(args.sdram_verbosity)
        if args.sdram_from_spd_dump:
            soc_kwargs["sdram_spd_data"] = parse_spd_hexdump(args.sdram_from_spd_dump)
        if args.sdram_init is not None:
            soc_kwargs["sdram_init"] = get_mem_data(args.sdram_init, endianness=cpu.endianness, offset=ram_boot_offset)
            ram_boot_address         = get_boot_address(args.sdram_init)

    # Ethernet.
    if args.with_ethernet or args.with_etherbone:
        if args.ethernet_phy_model == "sim":
            sim_config.add_module("ethernet", "eth", args={"interface": "tap0", "ip": args.remote_ip})
        elif args.ethernet_phy_model == "xgmii":
            sim_config.add_module("xgmii_ethernet", "xgmii_eth", args={"interface": "tap0", "ip": args.remote_ip})
        elif args.ethernet_phy_model == "gmii":
            sim_config.add_module("gmii_ethernet", "gmii_eth", args={"interface": "tap0", "ip": args.remote_ip})
        else:
            raise ValueError("Unknown Ethernet PHY model: " + args.ethernet_phy_model)

    # I2C.
    if args.with_i2c:
        sim_config.add_module("spdeeprom", "i2c")

    # SoC ------------------------------------------------------------------------------------------
    soc = SimSoC(
        with_sdram         = args.with_sdram,
        with_ethernet      = args.with_ethernet,
        ethernet_phy_model = args.ethernet_phy_model,
        with_etherbone     = args.with_etherbone,
        with_analyzer      = args.with_analyzer,
        with_i2c           = args.with_i2c,
        with_sdcard        = args.with_sdcard,
        with_spi_flash     = args.with_spi_flash,
        with_gpio          = args.with_gpio,
        sim_debug          = args.sim_debug,
        trace_reset_on     = int(float(args.trace_start)) > 0 or int(float(args.trace_end)) > 0,
        spi_flash_init     = None if args.spi_flash_init is None else get_mem_data(args.spi_flash_init, endianness="big"),
        **soc_kwargs)
    if ram_boot_address is not None:
        if ram_boot_address == 0:
            ram_boot_address = ram_boot_offset
        soc.add_constant("ROM_BOOT_ADDRESS", ram_boot_address)
    if args.with_ethernet:
        for i in range(4):
            soc.add_constant("LOCALIP{}".format(i+1), int(args.local_ip.split(".")[i]))
        for i in range(4):
            soc.add_constant("REMOTEIP{}".format(i+1), int(args.remote_ip.split(".")[i]))

    # Build/Run ------------------------------------------------------------------------------------
    def pre_run_callback(vns):
        if args.trace:
            generate_gtkw_savefile(builder, vns, args.trace_fst)

    builder_kwargs["csr_csv"] = "csr.csv"
    builder = Builder(soc, **builder_kwargs)
    builder.build(
        sim_config       = sim_config,
        interactive      = not args.non_interactive,
        pre_run_callback = pre_run_callback,
        **verilator_build_kwargs,
    )

if __name__ == "__main__":
    main()
