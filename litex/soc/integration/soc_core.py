# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 Dolu1990 <charles.papon.90@gmail.com>
# This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
# This file is Copyright (c) 2019 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
# This file is Copyright (c) 2015 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2018 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2018 Stafford Horne <shorne@gmail.com>
# This file is Copyright (c) 2018-2017 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2015 whitequark <whitequark@whitequark.org>
# This file is Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# License: BSD

####################################################################################################
#       DISCLAIMER: Provides retro-compatibility layer for existing SoCCore based designs.
#     Most of the SoC code has been refactored/improved and is now located in integration/soc.py
####################################################################################################

import os
import inspect

from migen import *

from litex.soc.cores import cpu
from litex.soc.interconnect import wishbone
from litex.soc.integration.common import *
from litex.soc.integration.soc import *

__all__ = [
    "mem_decoder",
    "get_mem_data",
    "SoCCore",
    "soc_core_args",
    "soc_core_argdict",
    "SoCMini",
    "soc_mini_args",
    "soc_mini_argdict",
]

# Helpers ------------------------------------------------------------------------------------------

def mem_decoder(address, size=0x10000000):
    size = 2**log2_int(size, False)
    assert (address & (size - 1)) == 0
    address >>= 2 # bytes to words aligned
    size    >>= 2 # bytes to words aligned
    return lambda a: (a[log2_int(size):] == (address >> log2_int(size)))

# SoCCore ------------------------------------------------------------------------------------------

class SoCCore(LiteXSoC):
    # default register/interrupt/memory mappings (can be redefined by user)
    csr_map       = {}
    interrupt_map = {}
    mem_map       = {
        "rom":      0x00000000,
        "sram":     0x01000000,
        "main_ram": 0x40000000,
        "csr":      0x82000000,
    }

    def __init__(self, platform, clk_freq,
        # CPU parameters
        cpu_type                 = "vexriscv",
        cpu_reset_address        = None,
        cpu_variant              = None,
        # ROM parameters
        integrated_rom_size      = 0,
        integrated_rom_init      = [],
        # SRAM parameters
        integrated_sram_size     = 0x1000,
        integrated_sram_init     = [],
        # MAIN_RAM parameters
        integrated_main_ram_size = 0,
        integrated_main_ram_init = [],
        # CSR parameters
        csr_data_width           = 8,
        csr_alignment            = 32,
        csr_address_width        = 14,
        csr_paging               = 0x800,
        # Identifier parameters
        ident                    = "",
        ident_version            = False,
        # UART parameters
        with_uart                = True,
        uart_name                = "serial",
        uart_baudrate            = 115200,
        uart_fifo_depth          = 16,
        # Timer parameters
        with_timer               = True,
        # Controller parameters
        with_ctrl                = True,
        # Wishbone parameters
        with_wishbone            = True,
        wishbone_timeout_cycles  = 1e6,
        # Others
        **kwargs):

        # New LiteXSoC class ----------------------------------------------------------------------------
        LiteXSoC.__init__(self, platform, clk_freq,
            bus_standard         = "wishbone",
            bus_data_width       = 32,
            bus_address_width    = 32,
            bus_timeout          = wishbone_timeout_cycles,
            bus_reserved_regions = {},

            csr_data_width       = csr_data_width,
            csr_address_width    = csr_address_width,
            csr_alignment        = csr_alignment,
            csr_paging           = csr_paging,
            csr_reserved_csrs    = self.csr_map,

            irq_n_irqs           = 32,
            irq_reserved_irqs    = {},
        )

        # Attributes
        self.mem_regions = self.bus.regions
        self.clk_freq    = self.sys_clk_freq
        self.mem_map     = self.mem_map
        self.config      = {}

        # Parameters management --------------------------------------------------------------------
        cpu_type          = None if cpu_type == "None" else cpu_type
        cpu_reset_address = None if cpu_reset_address == "None" else cpu_reset_address
        cpu_variant = cpu.check_format_cpu_variant(cpu_variant)

        if not with_wishbone:
            self.mem_map["csr"]  = 0x00000000

        self.cpu_type                   = cpu_type
        self.cpu_variant                = cpu_variant

        self.integrated_rom_size        = integrated_rom_size
        self.integrated_rom_initialized = integrated_rom_init != []
        self.integrated_sram_size       = integrated_sram_size
        self.integrated_main_ram_size   = integrated_main_ram_size

        self.csr_data_width             = csr_data_width

        self.with_wishbone              = with_wishbone
        self.wishbone_timeout_cycles    = wishbone_timeout_cycles

        self.wb_slaves = {}

        # Modules instances ------------------------------------------------------------------------

        # Add SoCController
        if with_ctrl:
            self.add_controller("ctrl")

        # Add CPU
        self.add_cpu(
            name          = str(cpu_type),
            variant       = "standard" if cpu_variant is None else cpu_variant,
            reset_address = None if integrated_rom_size else cpu_reset_address)

        # Add User's interrupts
        for name, loc in self.interrupt_map.items():
            self.irq.add(name, loc)

        # Add integrated ROM
        if integrated_rom_size:
            self.add_rom("rom", self.cpu.reset_address, integrated_rom_size, integrated_rom_init)

        # Add integrated SRAM
        if integrated_sram_size:
            self.add_ram("sram", self.mem_map["sram"], integrated_sram_size)

        # Add integrated MAIN_RAM (only useful when no external SRAM/SDRAM is available)
        if integrated_main_ram_size:
            self.add_ram("main_ram", self.mem_map["main_ram"], integrated_main_ram_size, integrated_main_ram_init)

        # Add Identifier
        if ident != "":
            self.add_identifier("identifier", identifier=ident, with_build_time=ident_version)

        # Add UART
        if with_uart:
            self.add_uart(name=uart_name, baudrate=uart_baudrate, fifo_depth=uart_fifo_depth)

        # Add Timer
        if with_timer:
            self.add_timer(name="timer0")

        # Add Wishbone to CSR bridge
        if with_wishbone:
            self.add_csr_bridge(self.mem_map["csr"])

    # Methods --------------------------------------------------------------------------------------

    def add_interrupt(self, interrupt_name, interrupt_id=None, use_loc_if_exists=False):
        self.irq.add(interrupt_name, interrupt_id, use_loc_if_exists=use_loc_if_exists)

    def add_csr(self, csr_name, csr_id=None, use_loc_if_exists=False):
        self.csr.add(csr_name, csr_id, use_loc_if_exists=use_loc_if_exists)

    def initialize_rom(self, data):
        self.rom.mem.init = data

    def add_wb_master(self, wbm):
        self.bus.add_master(master=wbm)

    def add_wb_slave(self, address, interface, size=None):
        wb_name = None
        for name, region in self.bus.regions.items():
            if address == region.origin:
                wb_name = name
                break
        if wb_name is None:
            self.wb_slaves[address] = interface
        else:
            self.bus.add_slave(name=wb_name, slave=interface)

    def add_memory_region(self, name, origin, length, type="cached"):
        self.bus.add_region(name, SoCRegion(origin=origin, size=length,
            cached="cached" in type,
            linker="linker" in type))

    def register_mem(self, name, address, interface, size=0x10000000):
        self.bus.add_slave(name, interface, SoCRegion(origin=address, size=size))

    def register_rom(self, interface, rom_size=0xa000):
        self.bus.add_slave("rom", interface, SoCRegion(origin=self.cpu.reset_address, size=rom_size))

    def add_csr_region(self, name, origin, busword, obj):
        self.csr_regions[name] = SoCCSRRegion(origin, busword, obj)

    # Finalization ---------------------------------------------------------------------------------

    def do_finalize(self):
        # Retro-compatibility
        for address, interface in self.wb_slaves.items():
            wb_name = None
            for name, region in self.bus.regions.items():
                if address == region.origin:
                    wb_name = name
                    break
            self.bus.add_slave(name=wb_name, slave=interface)

        SoC.do_finalize(self)
        # Retro-compatibility
        for region in self.bus.regions.values():
            region.length = region.size
            region.type   = "cached" if region.cached else "io"
        self.csr_regions = self.csr.regions
        for name, value in self.config.items():
            self.add_config(name, value)

# SoCCore arguments --------------------------------------------------------------------------------

def soc_core_args(parser):
    # CPU parameters
    parser.add_argument("--cpu-type", default=None,
                        help="select CPU: {}, (default=vexriscv)".format(", ".join(iter(cpu.CPUS.keys()))))
    parser.add_argument("--cpu-variant", default=None,
                        help="select CPU variant, (default=standard)")
    parser.add_argument("--cpu-reset-address", default=None, type=auto_int,
                        help="CPU reset address (default=None (Integrated ROM)")
    # ROM parameters
    parser.add_argument("--integrated-rom-size", default=0x8000, type=auto_int,
                        help="size/enable the integrated (BIOS) ROM (default=32KB)")
    parser.add_argument("--integrated-rom-file", default=None, type=str,
                        help="integrated (BIOS) ROM binary file")
    # SRAM parameters
    parser.add_argument("--integrated-sram-size", default=0x1000, type=auto_int,
                        help="size/enable the integrated SRAM (default=4KB)")
    # MAIN_RAM parameters
    parser.add_argument("--integrated-main-ram-size", default=None, type=auto_int,
                        help="size/enable the integrated main RAM")
    # CSR parameters
    parser.add_argument("--csr-data-width", default=None, type=auto_int,
                        help="CSR bus data-width (8 or 32, default=8)")
    parser.add_argument("--csr-address-width", default=14, type=auto_int,
                        help="CSR bus address-width")
    parser.add_argument("--csr-paging", default=0x800, type=auto_int,
                        help="CSR bus paging")
    # Identifier parameters
    parser.add_argument("--ident", default=None, type=str,
                        help="SoC identifier (default=\"\"")
    parser.add_argument("--ident-version", default=None, type=bool,
                        help="add date/time to SoC identifier (default=False)")
    # UART parameters
    parser.add_argument("--no-uart", action="store_true",
                        help="Disable UART (default=False)")
    parser.add_argument("--uart-name", default="serial", type=str,
                        help="UART type/name (default=serial)")
    parser.add_argument("--uart-baudrate", default=None, type=auto_int,
                        help="UART baudrate (default=115200)")
    parser.add_argument("--uart-fifo-depth", default=16, type=auto_int,
                        help="UART FIFO depth (default=16)")
    # Timer parameters
    parser.add_argument("--no-timer", action="store_true",
                        help="Disable Timer (default=False)")
    # Controller parameters
    parser.add_argument("--no-ctrl", action="store_true",
                        help="Disable Controller (default=False)")

def soc_core_argdict(args):
    r = dict()
    rom_file = getattr(args, "integrated_rom_file", None)
    if rom_file is not None:
        args.integrated_rom_init = get_mem_data(rom_file, "little") # FIXME: endianness
        args.integrated_rom_size = len(args.integrated_rom_init)*4
    for a in inspect.getargspec(SoCCore.__init__).args:
        if a not in ["self", "platform"]:
            if a in ["with_uart", "with_timer", "with_ctrl"]:
                arg = not getattr(args, a.replace("with", "no"), True)
            else:
                arg = getattr(args, a, None)
            if arg is not None:
                r[a] = arg
    return r

# SoCMini ---------------------------------------------------------------------------------------

class SoCMini(SoCCore):
     def __init__(self, *args, **kwargs):
        if "cpu_type" not in kwargs.keys():
            kwargs["cpu_type"] = "None"
        if "integrated_sram_size" not in kwargs.keys():
            kwargs["integrated_sram_size"] = 0
        if "with_uart" not in kwargs.keys():
            kwargs["with_uart"] = False
        if "with_timer" not in kwargs.keys():
            kwargs["with_timer"] = False

        SoCCore.__init__(self, *args, **kwargs)

# SoCMini arguments -----------------------------------------------------------------------------

soc_mini_args    = soc_core_args
soc_mini_argdict = soc_core_argdict
