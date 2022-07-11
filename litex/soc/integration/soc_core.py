#
# This file is part of LiteX.
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 Dolu1990 <charles.papon.90@gmail.com>
# This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
# This file is Copyright (c) 2019 Ilia Sergachev <ilia.sergachev@protonmail.ch>
# This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
# This file is Copyright (c) 2020 Raptor Engineering, LLC <sales@raptorengineering.com>
# This file is Copyright (c) 2015 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2018 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2018 Stafford Horne <shorne@gmail.com>
# This file is Copyright (c) 2018-2017 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2015 whitequark <whitequark@whitequark.org>
# This file is Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

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
    # Default register/interrupt/memory mappings (can be redefined by user)
    csr_map       = {}
    interrupt_map = {}
    mem_map       = {
        "rom":      0x00000000,
        "sram":     0x01000000,
        "main_ram": 0x40000000,
    }

    def __init__(self, platform, clk_freq,
        # Bus parameters
        bus_standard             = "wishbone",
        bus_data_width           = 32,
        bus_address_width        = 32,
        bus_timeout              = 1e6,
        bus_bursting             = False,
        bus_interconnect         = "shared",

        # CPU parameters
        cpu_type                 = "vexriscv",
        cpu_reset_address        = None,
        cpu_variant              = None,
        cpu_cfu                  = None,

        # CFU parameters
        cfu_filename             = None,

        # ROM parameters
        integrated_rom_size      = 0,
        integrated_rom_mode      = "r",
        integrated_rom_init      = [],

        # SRAM parameters
        integrated_sram_size     = 0x2000,
        integrated_sram_init     = [],

        # MAIN_RAM parameters
        integrated_main_ram_size = 0,
        integrated_main_ram_init = [],

        # CSR parameters
        csr_data_width           = 32,
        csr_address_width        = 14,
        csr_paging               = 0x800,
        csr_ordering             = "big",

        # Interrupt parameters
        irq_n_irqs               = 32,

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
        timer_uptime             = False,

        # Controller parameters
        with_ctrl                = True,

        # Others
        **kwargs):

        # New LiteXSoC class ----------------------------------------------------------------------------
        LiteXSoC.__init__(self, platform, clk_freq,
            bus_standard         = bus_standard,
            bus_data_width       = bus_data_width,
            bus_address_width    = bus_address_width,
            bus_timeout          = bus_timeout,
            bus_bursting         = bus_bursting,
            bus_interconnect     = bus_interconnect,
            bus_reserved_regions = {},

            csr_data_width       = csr_data_width,
            csr_address_width    = csr_address_width,
            csr_paging           = csr_paging,
            csr_ordering         = csr_ordering,
            csr_reserved_csrs    = self.csr_map,

            irq_n_irqs           = irq_n_irqs,
            irq_reserved_irqs    = {},
        )

        # Attributes
        self.mem_regions = self.bus.regions
        self.clk_freq    = self.sys_clk_freq
        self.mem_map     = self.mem_map
        self.config      = {}

        # Parameters management --------------------------------------------------------------------

        # CPU.
        cpu_type          = None if cpu_type == "None" else cpu_type
        cpu_reset_address = None if cpu_reset_address == "None" else cpu_reset_address

        self.cpu_type     = cpu_type
        self.cpu_variant  = cpu_variant

        # ROM.
        # Initialize ROM from binary file when provided.
        if isinstance(integrated_rom_init, str):
            integrated_rom_init = get_mem_data(integrated_rom_init, "little") # FIXME: Endianness.
            integrated_rom_size = 4*len(integrated_rom_init)

        # Disable ROM when no CPU/hard-CPU.
        if cpu_type in [None, "zynq7000", "zynqmp", "eos_s3"]:
            integrated_rom_init = []
            integrated_rom_size = 0
        self.integrated_rom_size        = integrated_rom_size
        self.integrated_rom_initialized = integrated_rom_init != []

        # SRAM.
        self.integrated_sram_size = integrated_sram_size

        # MAIN RAM.
        self.integrated_main_ram_size = integrated_main_ram_size

        # CSRs.
        self.csr_data_width = csr_data_width

        # Wishbone Slaves.
        self.wb_slaves = {}

        # Modules instances ------------------------------------------------------------------------

        # Add SoCController
        if with_ctrl:
            self.add_controller("ctrl")

        # Add CPU
        self.add_cpu(
            name          = str(cpu_type),
            variant       = "standard" if cpu_variant is None else cpu_variant,
            reset_address = None if integrated_rom_size else cpu_reset_address,
            cfu           = cpu_cfu)

        # Add User's interrupts
        if self.irq.enabled:
            for name, loc in self.interrupt_map.items():
                self.irq.add(name, loc)

        # Add integrated ROM
        if integrated_rom_size:
            self.add_rom("rom",
                origin   = self.cpu.reset_address,
                size     = integrated_rom_size,
                contents = integrated_rom_init,
                mode     = integrated_rom_mode
            )

        # Add integrated SRAM
        if integrated_sram_size:
            self.add_ram("sram",
                origin = self.mem_map["sram"],
                size   = integrated_sram_size,
            )

        # Add integrated MAIN_RAM (only useful when no external SRAM/SDRAM is available)
        if integrated_main_ram_size:
            self.add_ram("main_ram",
                origin   = self.mem_map["main_ram"],
                size     = integrated_main_ram_size,
                contents = integrated_main_ram_init,
            )

        # Add Identifier
        if ident != "":
            self.add_identifier("identifier", identifier=ident, with_build_time=ident_version)

        # Add UART
        if with_uart:
            self.add_uart(name="uart", uart_name=uart_name, baudrate=uart_baudrate, fifo_depth=uart_fifo_depth)

        # Add Timer
        if with_timer:
            self.add_timer(name="timer0")
            if timer_uptime:
                self.timer0.add_uptime()

    # Methods --------------------------------------------------------------------------------------

    def add_interrupt(self, interrupt_name, interrupt_id=None, use_loc_if_exists=False):
        self.irq.add(interrupt_name, interrupt_id, use_loc_if_exists=use_loc_if_exists)

    def add_csr(self, csr_name, csr_id=None, use_loc_if_exists=False):
        self.csr.add(csr_name, csr_id, use_loc_if_exists=use_loc_if_exists)

    def initialize_rom(self, data):
        self.init_rom(name="rom", contents=data)

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
            if region.linker:
                region.type += "+linker"
        self.csr_regions = self.csr.regions
        for name, value in self.config.items():
            self.add_config(name, value)

# SoCCore arguments --------------------------------------------------------------------------------

def soc_core_args(parser):
    soc_group = parser.add_argument_group(title="SoC options")
    # Bus parameters
    soc_group.add_argument("--bus-standard",      default="wishbone",                help="Select bus standard: {}.".format(", ".join(SoCBusHandler.supported_standard)))
    soc_group.add_argument("--bus-data-width",    default=32,         type=auto_int, help="Bus data-width.")
    soc_group.add_argument("--bus-address-width", default=32,         type=auto_int, help="Bus address-width.")
    soc_group.add_argument("--bus-timeout",       default=int(1e6),   type=float,    help="Bus timeout in cycles.")
    soc_group.add_argument("--bus-bursting",      action="store_true",               help="Enable burst cycles on the bus if supported.")
    soc_group.add_argument("--bus-interconnect",  default="shared",                  help="Select bus interconnect: shared (default) or crossbar.")

    # CPU parameters
    soc_group.add_argument("--cpu-type",          default="vexriscv",               help="Select CPU: {}.".format(", ".join(iter(cpu.CPUS.keys()))))
    soc_group.add_argument("--cpu-variant",       default=None,                     help="CPU variant.")
    soc_group.add_argument("--cpu-reset-address", default=None,      type=auto_int, help="CPU reset address (Boot from Integrated ROM by default).")
    soc_group.add_argument("--cpu-cfu",           default=None,                     help="Optional CPU CFU file/instance to add to the CPU.")

    # Controller parameters
    soc_group.add_argument("--no-ctrl", action="store_true", help="Disable Controller.")

    # ROM parameters
    soc_group.add_argument("--integrated-rom-size", default=0x20000, type=auto_int, help="Size/Enable the integrated (BIOS) ROM (Automatically resized to BIOS size when smaller).")
    soc_group.add_argument("--integrated-rom-init", default=None,    type=str,      help="Integrated ROM binary initialization file (override the BIOS when specified).")

    # SRAM parameters
    soc_group.add_argument("--integrated-sram-size", default=0x2000, type=auto_int, help="Size/Enable the integrated SRAM.")

    # MAIN_RAM parameters
    soc_group.add_argument("--integrated-main-ram-size", default=None, type=auto_int, help="size/enable the integrated main RAM.")

    # CSR parameters
    soc_group.add_argument("--csr-data-width",    default=32  ,  type=auto_int, help="CSR bus data-width (8 or 32).")
    soc_group.add_argument("--csr-address-width", default=14,    type=auto_int, help="CSR bus address-width.")
    soc_group.add_argument("--csr-paging",        default=0x800, type=auto_int, help="CSR bus paging.")
    soc_group.add_argument("--csr-ordering",      default="big",                help="CSR registers ordering (big or little).")

    # Identifier parameters
    soc_group.add_argument("--ident",             default=None,  type=str, help="SoC identifier.")
    soc_group.add_argument("--no-ident-version",  action="store_true",     help="Disable date/time in SoC identifier.")

    # UART parameters
    soc_group.add_argument("--no-uart",         action="store_true",                help="Disable UART.")
    soc_group.add_argument("--uart-name",       default="serial",    type=str,      help="UART type/name.")
    soc_group.add_argument("--uart-baudrate",   default=115200,      type=auto_int, help="UART baudrate.")
    soc_group.add_argument("--uart-fifo-depth", default=16,          type=auto_int, help="UART FIFO depth.")

    # Timer parameters
    soc_group.add_argument("--no-timer",        action="store_true", help="Disable Timer.")
    soc_group.add_argument("--timer-uptime",    action="store_true", help="Add an uptime capability to Timer.")

    # L2 Cache
    soc_group.add_argument("--l2-size", default=8192, type=auto_int, help="L2 cache size.")

def soc_core_argdict(args):
    r = dict()
    # Iterate on all arguments.
    soc_args  = inspect.getfullargspec(SoCCore.__init__).args
    full_args = soc_args + ["l2_size"]
    for a in full_args:
        # Exclude specific arguments.
        if a in ["self", "platform"]:
            continue
        # Handle specific with_xy case (--no_xy is exposed).
        if a in ["with_uart", "with_timer", "with_ctrl"]:
            arg = not getattr(args, a.replace("with", "no"), True)
        # Handle specific ident_version case (--no-ident-version is exposed).
        elif a in ["ident_version"]:
            arg = not getattr(args, "no_ident_version")
        # Regular cases.
        else:
            arg = getattr(args, a, None)
        # Fill Dict.
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
