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

import os
import inspect
from operator import itemgetter

from migen import *

from litex.build.tools import deprecated_warning

from litex.soc.cores import identifier, timer, uart
from litex.soc.cores import cpu
from litex.soc.interconnect.csr import *
from litex.soc.interconnect import wishbone, csr_bus, wishbone2csr
from litex.soc.integration.common import *

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

# SoCController ------------------------------------------------------------------------------------

class SoCController(Module, AutoCSR):
    def __init__(self):
        self._reset      = CSR()
        self._scratch    = CSRStorage(32, reset=0x12345678)
        self._bus_errors = CSRStatus(32)

        # # #

        # reset
        self.reset = Signal()
        self.comb += self.reset.eq(self._reset.re)

        # bus errors
        self.bus_error = Signal()
        bus_errors     = Signal(32)
        self.sync += \
            If(bus_errors != (2**len(bus_errors)-1),
                If(self.bus_error,
                    bus_errors.eq(bus_errors + 1)
                )
            )
        self.comb += self._bus_errors.status.eq(bus_errors)

# SoCCore ------------------------------------------------------------------------------------------

class SoCCore(Module):
    # default register/interrupt/memory mappings (can be redefined by user)
    csr_map       = {}
    interrupt_map = {}
    mem_map       = {
        "rom":      0x00000000,
        "sram":     0x01000000,
        "main_ram": 0x40000000,
        "csr":      0x82000000,
    }
    io_regions   = {}

    def __init__(self, platform, clk_freq,
                # CPU parameters
                cpu_type="vexriscv", cpu_reset_address=0x00000000, cpu_variant=None,
                # ROM parameters
                integrated_rom_size=0, integrated_rom_init=[],
                # SRAM parameters
                integrated_sram_size=4096, integrated_sram_init=[],
                # MAIN_RAM parameters
                integrated_main_ram_size=0, integrated_main_ram_init=[],
                # CSR parameters
                csr_data_width=8, csr_alignment=32, csr_address_width=14,
                # Identifier parameters
                ident="", ident_version=False,
                # UART parameters
                with_uart=True, uart_name="serial", uart_baudrate=115200, uart_stub=False,
                # Timer parameters
                with_timer=True,
                # Controller parameters
                with_ctrl=True,
                # Wishbone parameters
                with_wishbone=True, wishbone_timeout_cycles=1e6,
                **kwargs):
        self.platform = platform
        self.clk_freq = clk_freq

        # SoC's CSR/Mem/Interrupt mapping (default or user defined + dynamically allocateds)
        self.soc_csr_map       = {}
        self.soc_interrupt_map = {}
        self.soc_mem_map       = self.mem_map
        self.soc_io_regions    = self.io_regions

        # SoC's Config/Constants/Regions
        self.config      = {}
        self.constants   = {}
        self.mem_regions = {}
        self.csr_regions = {}

        # Wishbone masters/slaves lists
        self._wb_masters = []
        self._wb_slaves  = []

        # CSR masters list
        self._csr_masters = []

        self.add_retro_compat(kwargs)

        # Parameters managment ---------------------------------------------------------------------
        if cpu_type == "None":
            cpu_type = None

        if not with_wishbone:
            self.soc_mem_map["csr"]  = 0x00000000

        self.cpu_type    = cpu_type
        self.cpu_variant = cpu.check_format_cpu_variant(cpu_variant)

        self.integrated_rom_size        = integrated_rom_size
        self.integrated_rom_initialized = integrated_rom_init != []
        self.integrated_sram_size       = integrated_sram_size
        self.integrated_main_ram_size   = integrated_main_ram_size

        assert csr_data_width in [8, 32, 64]
        assert 2**(csr_address_width + 2) <= 0x1000000
        self.csr_data_width    = csr_data_width
        self.csr_address_width = csr_address_width

        self.with_ctrl = with_ctrl

        self.with_uart     = with_uart
        self.uart_baudrate = uart_baudrate

        self.with_wishbone           = with_wishbone
        self.wishbone_timeout_cycles = wishbone_timeout_cycles

        # Modules instances ------------------------------------------------------------------------

        # Add user's CSRs (needs to be done before the first dynamic allocation)
        for _name, _id in self.csr_map.items():
            self.add_csr(_name, _id)

        # Add SoCController
        if with_ctrl:
            self.submodules.ctrl = SoCController()
            self.add_csr("ctrl", allow_user_defined=True)

        # Add CPU
        self.config["CPU_TYPE"] = str(cpu_type).upper()
        if cpu_type is not None:
            if cpu_variant is not None:
                self.config["CPU_VARIANT"] = str(cpu_variant.split('+')[0]).upper()
            # Check type
            if cpu_type not in cpu.CPUS.keys():
                raise ValueError("Unsupported CPU type: {}".format(cpu_type))
            # Add the CPU
            self.add_cpu(cpu.CPUS[cpu_type](platform, self.cpu_variant))

            # Update Memory Map (if defined by CPU)
            self.soc_mem_map.update(self.cpu.mem_map)

            # Update IO Regions (if defined by CPU)
            self.soc_io_regions.update(self.cpu.io_regions)

            # Set reset address
            self.cpu.set_reset_address(self.soc_mem_map["rom"] if integrated_rom_size else cpu_reset_address)
            self.config["CPU_RESET_ADDR"] = self.cpu.reset_address

            # Add CPU buses as 32-bit Wishbone masters
            for cpu_bus in self.cpu.buses:
                assert cpu_bus.data_width in [32, 64, 128]
                soc_bus = wishbone.Interface(data_width=32)
                self.submodules += wishbone.Converter(cpu_bus, soc_bus)
                self.add_wb_master(soc_bus)

            # Add CPU CSR (dynamic)
            self.add_csr("cpu", allow_user_defined=True)

            # Add CPU interrupts
            for _name, _id in self.cpu.interrupts.items():
                self.add_interrupt(_name, _id)

            # Allow SoCController to reset the CPU
            if with_ctrl:
                self.comb += self.cpu.reset.eq(self.ctrl.reset)
        else:
            self.add_cpu(cpu.CPUNone())
            self.soc_io_regions.update(self.cpu.io_regions)

        # Add user's interrupts (needs to be done after CPU interrupts are allocated)
        for _name, _id in self.interrupt_map.items():
            self.add_interrupt(_name, _id)

        # Add integrated ROM
        if integrated_rom_size:
            self.submodules.rom = wishbone.SRAM(integrated_rom_size, read_only=True, init=integrated_rom_init)
            self.register_rom(self.rom.bus, integrated_rom_size)

        # Add integrated SRAM
        if integrated_sram_size:
            self.submodules.sram = wishbone.SRAM(integrated_sram_size, init=integrated_sram_init)
            self.register_mem("sram", self.soc_mem_map["sram"], self.sram.bus, integrated_sram_size)

        # Add integrated MAIN_RAM (only useful when no external SRAM/SDRAM is available)
        if integrated_main_ram_size:
            self.submodules.main_ram = wishbone.SRAM(integrated_main_ram_size, init=integrated_main_ram_init)
            self.register_mem("main_ram", self.soc_mem_map["main_ram"], self.main_ram.bus, integrated_main_ram_size)

        # Add UART
        if with_uart:
            if uart_stub:
                self.submodules.uart  = uart.UARTStub()
            else:
                if uart_name == "jtag_atlantic":
                    from litex.soc.cores.jtag import JTAGAtlantic
                    self.submodules.uart_phy = JTAGAtlantic()
                elif uart_name == "jtag_uart":
                    from litex.soc.cores.jtag import JTAGPHY
                    self.submodules.uart_phy = JTAGPHY(device=platform.device)
                else:
                    self.submodules.uart_phy = uart.UARTPHY(platform.request(uart_name), clk_freq, uart_baudrate)
                self.submodules.uart = ResetInserter()(uart.UART(self.uart_phy))
            self.add_csr("uart_phy", allow_user_defined=True)
            self.add_csr("uart", allow_user_defined=True)
            self.add_interrupt("uart", allow_user_defined=True)

        # Add Identifier
        if ident:
            if ident_version:
                ident = ident + " " + get_version()
            self.submodules.identifier = identifier.Identifier(ident)
            self.add_csr("identifier_mem", allow_user_defined=True)
        self.config["CLOCK_FREQUENCY"] = int(clk_freq)

        # Add Timer
        if with_timer:
            self.submodules.timer0 = timer.Timer()
            self.add_csr("timer0", allow_user_defined=True)
            self.add_interrupt("timer0", allow_user_defined=True)

        # Add Wishbone to CSR bridge
        csr_alignment = max(csr_alignment, self.cpu.data_width)
        self.config["CSR_DATA_WIDTH"] = csr_data_width
        self.config["CSR_ALIGNMENT"]  = csr_alignment
        self.csr_data_width = csr_data_width
        self.csr_alignment  = csr_alignment
        if with_wishbone:
            self.submodules.wishbone2csr = wishbone2csr.WB2CSR(
                bus_csr=csr_bus.Interface(
                    address_width = csr_address_width,
                    data_width    = csr_data_width))
            self.add_csr_master(self.wishbone2csr.csr)
            self.register_mem("csr", self.soc_mem_map["csr"], self.wishbone2csr.wishbone, 0x1000000)

    # Methods --------------------------------------------------------------------------------------

    def add_cpu(self, cpu):
        if self.finalized:
            raise FinalizeError
        if hasattr(self, "cpu"):
            raise NotImplementedError("More than one CPU is not supported")
        self.submodules.cpu = cpu

    def add_interrupt(self, interrupt_name, interrupt_id=None, allow_user_defined=False):
        # Check that interrupt_name is not already used
        if interrupt_name in self.soc_interrupt_map.keys():
            if allow_user_defined:
                return
            else:
                raise ValueError("Interrupt conflict, {} name already used".format(interrupt_name))

        # Check that interrupt_id is in range
        if interrupt_id is not None and interrupt_id >= 32:
            raise ValueError("{} Interrupt ID out of range ({}, max=31)".format(
                interrupt_name, interrupt_id))

        # Interrupt_id not provided: allocate interrupt to the first available id
        if interrupt_id is None:
            for n in range(32):
                if n not in self.soc_interrupt_map.values():
                    self.soc_interrupt_map.update({interrupt_name: n})
                    return
            raise ValueError("No more space to allocate {} interrupt".format(interrupt_name))
        # Interrupt_id provided: check that interrupt_id is not already used and add interrupt
        else:
            for _name, _id in self.soc_interrupt_map.items():
                if interrupt_id == _id:
                    raise ValueError("Interrupt conflict, {} already used by {} interrupt".format(
                        interrupt_id, _name))
            self.soc_interrupt_map.update({interrupt_name: interrupt_id})

    def add_csr(self, csr_name, csr_id=None, allow_user_defined=False):
        # Check that csr_name is not already used
        if csr_name in self.soc_csr_map.keys():
            if allow_user_defined:
                return
            else:
                raise ValueError("CSR conflict, {} name already used".format(csr_name))

        # Check that csr_id is in range
        if csr_id is not None and csr_id >= 2**self.csr_address_width:
            raise ValueError("{} CSR ID out of range ({}, max=31)".format(
                csr_name, csr_id))

        # csr_id not provided: allocate csr to the first available id
        if csr_id is None:
            for n in range(2**self.csr_address_width):
                if n not in self.soc_csr_map.values():
                    self.soc_csr_map.update({csr_name: n})
                    return
            raise ValueError("No more space to allocate {} csr".format(csr_name))
        # csr_id provided: check that csr_id is not already used and add csr
        else:
            for _name, _id in self.soc_csr_map.items():
                if csr_id == _id:
                    raise ValueError("CSR conflict, {} already used by {} csr".format(
                        csr_id, _name))
            self.soc_csr_map.update({csr_name: csr_id})

    def initialize_rom(self, data):
        self.rom.mem.init = data

    def add_wb_master(self, wbm):
        if self.finalized:
            raise FinalizeError
        self._wb_masters.append(wbm)

    def add_wb_slave(self, address_or_address_decoder, interface, size=None):
        if self.finalized:
            raise FinalizeError
        if size is not None:
            address_decoder = mem_decoder(address_or_address_decoder, size)
        else:
            address_decoder = address_or_address_decoder
        self._wb_slaves.append((address_decoder, interface))

    def add_csr_master(self, csrm):
        # CSR masters are not arbitrated, use this with precaution.
        if self.finalized:
            raise FinalizeError
        self._csr_masters.append(csrm)

    def check_io_region(self, name, origin, length):
        for region_origin, region_length in self.soc_io_regions.items():
            if (origin >= region_origin) & ((origin + length) < (region_origin + region_length)):
                return
        msg = "{} region (0x{:08x}-0x{:08x}) is not located in an IO region.\n".format(
            name, origin, origin + length - 1)
        msg += "Available IO regions: "
        if not bool(self.soc_io_regions):
            msg += "None\n"
        else:
            msg += "\n"
            for region_origin, region_length in self.soc_io_regions.items():
                msg += "- 0x{:08x}-0x{:08x}\n".format(region_origin, region_origin + region_length - 1)
        raise ValueError(msg)

    def add_memory_region(self, name, origin, length, io_region=False):
        if io_region:
            self.check_io_region(name, origin, length)
        def in_this_region(addr):
            return addr >= origin and addr < origin + length
        for n, r in self.mem_regions.items():
            r.length = 2**log2_int(r.length, False)
            if n == name or in_this_region(r.origin) or in_this_region(r.origin + r.length - 1):
                raise ValueError("Memory region conflict between {} and {}".format(n, name))
        self.mem_regions[name] = SoCMemRegion(origin, length)

    def register_mem(self, name, address, interface, size=0x10000000):
        self.add_wb_slave(address, interface, size)
        self.add_memory_region(name, address, size)

    def register_rom(self, interface, rom_size=0xa000):
        self.add_wb_slave(self.soc_mem_map["rom"], interface, rom_size)
        self.add_memory_region("rom", self.cpu.reset_address, rom_size)

    def check_csr_range(self, name, addr):
        if addr >= 1<<(self.csr_address_width+2):
            raise ValueError("{} CSR out of range, increase csr_address_width".format(name))

    def check_csr_region(self, name, origin):
        for n, r in self.csr_regions.items():
            if n == name or r.origin == origin:
                raise ValueError("CSR region conflict between {} and {}".format(n, name))

    def add_csr_region(self, name, origin, busword, obj):
        self.check_io_region(name, origin, 0x800)
        self.check_csr_region(name, origin)
        self.csr_regions[name] = SoCCSRRegion(origin, busword, obj)

    def add_constant(self, name, value=None):
        if name in self.constants.keys():
            raise ValueError("Constant {} already declared.".format(name))
        self.constants[name] = SoCConstant(value)

    def get_csr_dev_address(self, name, memory):
        if memory is not None:
            name = name + "_" + memory.name_override
        try:
            return self.soc_csr_map[name]
        except KeyError as e:
            msg = "Undefined \"{}\" CSR.\n".format(name)
            msg += "Avalaible CSRs in {} ({}):\n".format(
                self.__class__.__name__, inspect.getfile(self.__class__))
            for k in sorted(self.soc_csr_map.keys()):
                msg += "- {}\n".format(k)
            raise RuntimeError(msg)
        except ValueError:
            return None

    def build(self, *args, **kwargs):
        return self.platform.build(self, *args, **kwargs)

    # Finalization ---------------------------------------------------------------------------------

    def do_finalize(self):
        # Verify CPU has required memories
        if self.cpu_type is not None:
            for name in "rom", "sram":
                if name not in self.mem_regions.keys():
                    raise FinalizeError("CPU needs \"{}\" to be registered with SoC.register_mem()".format(name))

        # Add the Wishbone Masters/Slaves interconnect
        if len(self._wb_masters):
            self.submodules.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
                self._wb_slaves, register=True, timeout_cycles=self.wishbone_timeout_cycles)
            if self.with_ctrl and (self.wishbone_timeout_cycles is not None):
                self.comb += self.ctrl.bus_error.eq(self.wishbonecon.timeout.error)

        # Collect and create CSRs
        self.submodules.csrbankarray = csr_bus.CSRBankArray(self,
            self.get_csr_dev_address,
            data_width    = self.csr_data_width,
            address_width = self.csr_address_width,
            alignment     = self.csr_alignment
        )

        # Add CSRs interconnect
        if len(self._csr_masters) != 0:
            self.submodules.csrcon = csr_bus.InterconnectShared(
                self._csr_masters, self.csrbankarray.get_buses())

        # Check and add CSRs regions
        for name, csrs, mapaddr, rmap in self.csrbankarray.banks:
            self.check_csr_range(name, 0x800*mapaddr)
            self.add_csr_region(name, (self.soc_mem_map["csr"] + 0x800*mapaddr),
                self.csr_data_width, csrs)

        # Check and add Memory regions
        for name, memory, mapaddr, mmap in self.csrbankarray.srams:
            self.check_csr_range(name, 0x800*mapaddr)
            self.add_csr_region(name + "_" + memory.name_override,
                (self.soc_mem_map["csr"] + 0x800*mapaddr),
                self.csr_data_width, memory)

        # Add CSRs / Config items to constants
        for name, constant in self.csrbankarray.constants:
            self.add_constant(name.upper() + "_" + constant.name.upper(),
                              constant.value.value)
        for name, value in sorted(self.config.items(), key=itemgetter(0)):
            self.add_constant("CONFIG_" + name.upper(), value)
            if isinstance(value, str):
                self.add_constant("CONFIG_" + name.upper() + "_" + value)

        # Connect interrupts
        if hasattr(self, "cpu"):
            if hasattr(self.cpu, "interrupt"):
                for _name, _id in sorted(self.soc_interrupt_map.items()):
                    if _name in self.cpu.interrupts.keys():
                        continue
                    if hasattr(self, _name):
                        module = getattr(self, _name)
                        assert hasattr(module, 'ev'), "Submodule %s does not have EventManager (xx.ev) module" % _name
                        self.comb += self.cpu.interrupt[_id].eq(module.ev.irq)
                    self.constants[_name.upper() + "_INTERRUPT"] = _id


    # API retro-compatibility layer ----------------------------------------------------------------
    # Allow user to build the design the old API for ~3 months after the API change is introduced.
    # Adds warning and artificical delay to encourage user to update.

    def add_retro_compat(self, kwargs):
        # 2019-10-09 : deprecate shadow_base, introduce io_regions
        if "shadow_base" in kwargs.keys():
            deprecated_warning(": shadow_base replaced by IO regions.")
        self.retro_compat_shadow_base = kwargs.get("shadow_base", 0x80000000)
        self.config["SHADOW_BASE"] = self.retro_compat_shadow_base

    def __getattr__(self, name):
        # 2019-10-09: deprecate shadow_base, introduce io_regions
        if name == "shadow_base":
            deprecated_warning(": shadow_base replaced by IO regions.")
            return self.retro_compat_shadow_base
        else:
            return Module.__getattr__(self, name)

# SoCCore arguments --------------------------------------------------------------------------------

def soc_core_args(parser):
    parser.add_argument("--cpu-type", default=None,
                        help="select CPU: {}".format(", ".join(iter(cpu.CPUS.keys()))))
    parser.add_argument("--cpu-variant", default=None,
                        help="select CPU variant")
    parser.add_argument("--integrated-rom-size", default=None, type=int,
                        help="size/enable the integrated (BIOS) ROM")
    parser.add_argument("--integrated-main-ram-size", default=None, type=int,
                        help="size/enable the integrated main RAM")
    parser.add_argument("--uart-stub", default=False, type=bool,
                        help="enable uart stub")


def soc_core_argdict(args):
    r = dict()
    for a in inspect.getargspec(SoCCore.__init__).args:
        if a not in ["self", "platform"]:
            arg = getattr(args, a, None)
            if arg is not None:
                r[a] = arg
    return r

# SoCMini ---------------------------------------------------------------------------------------

class SoCMini(SoCCore):
     def __init__(self, *args, **kwargs):
        if "cpu_type" not in kwargs.keys():
            kwargs["cpu_type"] = None
        if "integrated_sram_size" not in kwargs.keys():
            kwargs["integrated_sram_size"] = 0
        if "with_uart" not in kwargs.keys():
            kwargs["with_uart"] = False
        if "with_timer" not in kwargs.keys():
            kwargs["with_timer"] = False

        SoCCore.__init__(self, *args, **kwargs)

# SoCMini arguments -----------------------------------------------------------------------------

soc_mini_args = soc_core_args
soc_mini_argdict = soc_core_argdict
