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
import struct
import inspect
import json
import math
import datetime
import time
from operator import itemgetter

from migen import *

from litex.build.tools import deprecated_warning

from litex.soc.cores import identifier, timer, uart
from litex.soc.cores import cpu
from litex.soc.interconnect.csr import *
from litex.soc.interconnect import wishbone, csr_bus, wishbone2csr


__all__ = [
    "mem_decoder",
    "get_mem_data",
    "csr_map_update",
    "SoCCore",
    "soc_core_args",
    "soc_core_argdict",
    "SoCMini",
    "soc_mini_args",
    "soc_mini_argdict",
]

# Helpers ------------------------------------------------------------------------------------------

def version(with_time=True):
    if with_time:
        return datetime.datetime.fromtimestamp(
                time.time()).strftime("%Y-%m-%d %H:%M:%S")
    else:
        return datetime.datetime.fromtimestamp(
                time.time()).strftime("%Y-%m-%d")

def get_mem_data(filename_or_regions, endianness="big", mem_size=None):
    # create memory regions
    if isinstance(filename_or_regions, dict):
        regions = filename_or_regions
    else:
        filename = filename_or_regions
        _, ext = os.path.splitext(filename)
        if ext == ".json":
            f = open(filename, "r")
            regions = json.load(f)
            f.close()
        else:
            regions = {filename: "0x00000000"}

    # determine data_size
    data_size = 0
    for filename, base in regions.items():
        data_size = max(int(base, 16) + os.path.getsize(filename), data_size)
    assert data_size > 0
    if mem_size is not None:
        assert data_size < mem_size, (
            "file is too big: {}/{} bytes".format(
             data_size, mem_size))

    # fill data
    data = [0]*math.ceil(data_size/4)
    for filename, base in regions.items():
        with open(filename, "rb") as f:
            i = 0
            while True:
                w = f.read(4)
                if not w:
                    break
                if len(w) != 4:
                    for _ in range(len(w), 4):
                        w += b'\x00'
                if endianness == "little":
                    data[int(base, 16)//4 + i] = struct.unpack("<I", w)[0]
                else:
                    data[int(base, 16)//4 + i] = struct.unpack(">I", w)[0]
                i += 1
    return data

def mem_decoder(address, size=0x10000000):
    address &= ~0x80000000
    size = 2**log2_int(size, False)
    assert (address & (size - 1)) == 0
    address >>= 2 # bytes to words aligned
    size    >>= 2 # bytes to words aligned
    return lambda a: (a[log2_int(size):-1] == (address >> log2_int(size)))

def csr_map_update(csr_map, csr_peripherals):
    csr_map.update(dict((n, v)
        for v, n in enumerate(csr_peripherals, start=max(csr_map.values()) + 1)))

# SoCController ------------------------------------------------------------------------------------

class SoCController(Module, AutoCSR):
    def __init__(self):
        self._reset = CSR()
        self._scratch = CSRStorage(32, reset=0x12345678)
        self._bus_errors = CSRStatus(32)

        # # #

        # reset
        self.reset = Signal()
        self.comb += self.reset.eq(self._reset.re)

        # bus errors
        self.bus_error = Signal()
        bus_errors = Signal(32)
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
        "rom":      0x00000000,  # (default shadow @0x80000000)
        "sram":     0x01000000,  # (default shadow @0x81000000)
        "csr":      0x02000000,  # (default shadow @0x82000000)
        "main_ram": 0x40000000,  # (default shadow @0xc0000000)
    }
    def __init__(self, platform, clk_freq,
                # CPU parameters
                cpu_type="vexriscv", cpu_reset_address=0x00000000, cpu_variant=None,
                # MEM MAP parameters
                shadow_base=0x80000000,
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
                wishbone_timeout_cycles=1e6):
        self.platform = platform
        self.clk_freq = clk_freq

        # config dictionary (store all SoC's parameters to be exported to software)
        self.config = dict()

        # SoC's register/interrupt/memory mappings (default or user defined + dynamically allocateds)
        self.soc_csr_map = {}
        self.soc_interrupt_map = {}
        self.soc_mem_map = self.mem_map

        # Regions / Constants lists
        self._memory_regions = []  # (name, origin, length)
        self._linker_regions = []  # (name, origin, length)
        self._csr_regions = []     # (name, origin, busword, csr_list/Memory)
        self._constants = []       # (name, value)

        # Wishbone masters/slaves lists
        self._wb_masters = []
        self._wb_slaves = []

        # CSR masters list
        self._csr_masters = []

        # Parameters managment ---------------------------------------------------------------------

        # NOTE: RocketChip reserves the first 256Mbytes for internal use,
        #       so we must change default mem_map;
        #       Also, CSRs *must* be 64-bit aligned.
        if cpu_type == "rocket":
            self.soc_mem_map["rom"]  = 0x10000000
            self.soc_mem_map["sram"] = 0x11000000
            self.soc_mem_map["csr"]  = 0x12000000
            csr_alignment = 64

        if cpu_type == "None":
            cpu_type = None
        self.cpu_type = cpu_type

        self.cpu_variant = cpu.check_format_cpu_variant(cpu_variant)

        if integrated_rom_size:
            cpu_reset_address = self.soc_mem_map["rom"]
        self.cpu_reset_address = cpu_reset_address
        self.config["CPU_RESET_ADDR"] = self.cpu_reset_address

        self.shadow_base = shadow_base

        self.integrated_rom_size = integrated_rom_size
        self.integrated_rom_initialized = integrated_rom_init != []
        self.integrated_sram_size = integrated_sram_size
        self.integrated_main_ram_size = integrated_main_ram_size

        assert csr_data_width in [8, 32, 64]
        assert csr_alignment in [32, 64]
        self.csr_data_width = csr_data_width
        self.csr_alignment = csr_alignment
        self.csr_address_width = csr_address_width

        self.with_ctrl = with_ctrl

        self.with_uart = with_uart
        self.uart_baudrate = uart_baudrate

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
            # CPU selection / instance
            if cpu_type == "lm32":
                self.add_cpu(cpu.lm32.LM32(platform, self.cpu_reset_address, self.cpu_variant))
            elif cpu_type == "mor1kx" or cpu_type == "or1k":
                if cpu_type == "or1k":
                    deprecated_warning("SoCCore's \"cpu-type\" to \"mor1kx\"")
                self.add_cpu(cpu.mor1kx.MOR1KX(platform, self.cpu_reset_address, self.cpu_variant))
            elif cpu_type == "picorv32":
                self.add_cpu(cpu.picorv32.PicoRV32(platform, self.cpu_reset_address, self.cpu_variant))
            elif cpu_type == "vexriscv":
                self.add_cpu(cpu.vexriscv.VexRiscv(platform, self.cpu_reset_address, self.cpu_variant))
            elif cpu_type == "minerva":
                self.add_cpu(cpu.minerva.Minerva(platform, self.cpu_reset_address, self.cpu_variant))
            elif cpu_type == "rocket":
                self.add_cpu(cpu.rocket.RocketRV64(platform, self.cpu_reset_address, self.cpu_variant))
            else:
                raise ValueError("Unsupported CPU type: {}".format(cpu_type))

            # Add Instruction/Data buses as Wisbone masters
            self.add_wb_master(self.cpu.ibus)
            self.add_wb_master(self.cpu.dbus)

            # Add CPU CSR (dynamic)
            self.add_csr("cpu", allow_user_defined=True)

            # Add CPU reserved interrupts
            for _name, _id in self.cpu.reserved_interrupts.items():
                self.add_interrupt(_name, _id)

            # Allow SoCController to reset the CPU
            if with_ctrl:
                self.comb += self.cpu.reset.eq(self.ctrl.reset)

        # Add user's interrupts (needs to be done after CPU reserved interrupts are allocated)
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

        # Add Wishbone to CSR bridge
        self.submodules.wishbone2csr = wishbone2csr.WB2CSR(
            bus_csr=csr_bus.Interface(csr_data_width, csr_address_width))
        self.add_csr_master(self.wishbone2csr.csr)
        self.config["CSR_DATA_WIDTH"] = csr_data_width
        self.config["CSR_ALIGNMENT"] = csr_alignment
        assert 2**(csr_address_width + 2) <= 0x1000000
        self.register_mem("csr", self.soc_mem_map["csr"], self.wishbone2csr.wishbone, 0x1000000)

        # Add UART
        if with_uart:
            if uart_stub:
                self.submodules.uart  = uart.UARTStub()
            else:
                self.submodules.uart_phy = uart.RS232PHY(platform.request(uart_name), clk_freq, uart_baudrate)
                self.submodules.uart = ResetInserter()(uart.UART(self.uart_phy))
            self.add_csr("uart_phy", allow_user_defined=True)
            self.add_csr("uart", allow_user_defined=True)
            self.add_interrupt("uart", allow_user_defined=True)

        # Add Identifier
        if ident:
            if ident_version:
                ident = ident + " " + version()
            self.submodules.identifier = identifier.Identifier(ident)
            self.add_csr("identifier_mem", allow_user_defined=True)
        self.config["CLOCK_FREQUENCY"] = int(clk_freq)

        # Add Timer
        if with_timer:
            self.submodules.timer0 = timer.Timer()
            self.add_csr("timer0", allow_user_defined=True)
            self.add_interrupt("timer0", allow_user_defined=True)

    # Methods --------------------------------------------------------------------------------------

    def add_cpu(self, cpu):
        if self.finalized:
            raise FinalizeError
        if hasattr(self, "cpu"):
            raise NotImplementedError("More than one CPU is not supported")
        self.submodules.cpu = cpu

    def add_cpu_or_bridge(self, cpu_or_bridge):
        deprecated_warning("SoCCore's \"add_cpu_or_bridge\" call to \"add_cpu\"")
        self.add_cpu(cpu_or_bridge)
        self.cpu_or_bridge = self.cpu

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

    def add_linker_region(self, name, origin, length):
        self._linker_regions.append((name, origin, length))

    def add_memory_region(self, name, origin, length):
        def in_this_region(addr):
            return addr >= origin and addr < origin + length
        for n, o, l in self._memory_regions:
            l = 2**log2_int(l, False)
            if n == name or in_this_region(o) or in_this_region(o+l-1):
                raise ValueError("Memory region conflict between {} and {}".format(n, name))

        self._memory_regions.append((name, origin, length))

    def register_mem(self, name, address, interface, size=0x10000000):
        self.add_wb_slave(address, interface, size)
        self.add_memory_region(name, address, size)

    def register_rom(self, interface, rom_size=0xa000):
        self.add_wb_slave(self.soc_mem_map["rom"], interface, rom_size)
        self.add_memory_region("rom", self.cpu_reset_address, rom_size)

    def get_memory_regions(self):
        return self._memory_regions

    def get_linker_regions(self):
        return self._linker_regions

    def check_csr_range(self, name, addr):
        if addr >= 1<<(self.csr_address_width+2):
            raise ValueError("{} CSR out of range, increase csr_address_width".format(name))

    def check_csr_region(self, name, origin):
        for n, o, l, obj in self._csr_regions:
            if n == name or o == origin:
                raise ValueError("CSR region conflict between {} and {}".format(n, name))

    def add_csr_region(self, name, origin, busword, obj):
        self.check_csr_region(name, origin)
        self._csr_regions.append((name, origin, busword, obj))

    def get_csr_regions(self):
        return self._csr_regions

    def add_constant(self, name, value=None):
        self._constants.append((name, value))

    def get_constants(self):
        r = []
        for _name, _id in sorted(self.soc_interrupt_map.items()):
            r.append((_name.upper() + "_INTERRUPT", _id))
        r += self._constants
        return r

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
        registered_mems = {regions[0] for regions in self._memory_regions + self._linker_regions}
        if self.cpu_type is not None:
            for mem in "rom", "sram":
                if mem not in registered_mems:
                    raise FinalizeError("CPU needs a {} to be defined as memory or linker region".format(mem))

        # Add the Wishbone Masters/Slaves interconnect
        if len(self._wb_masters):
            self.submodules.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
                self._wb_slaves, register=True, timeout_cycles=self.wishbone_timeout_cycles)
            if self.with_ctrl and (self.wishbone_timeout_cycles is not None):
                self.comb += self.ctrl.bus_error.eq(self.wishbonecon.timeout.error)

        # Collect and create CSRs
        self.submodules.csrbankarray = csr_bus.CSRBankArray(self,
            self.get_csr_dev_address,
            data_width=self.csr_data_width,
            address_width=self.csr_address_width,
            alignment=self.csr_alignment)

        # Add CSRs interconnect
        self.submodules.csrcon = csr_bus.InterconnectShared(
                self._csr_masters, self.csrbankarray.get_buses())

        # Check and add CSRs regions
        for name, csrs, mapaddr, rmap in self.csrbankarray.banks:
            self.check_csr_range(name, 0x800*mapaddr)
            self.add_csr_region(name, (self.soc_mem_map["csr"] + 0x800*mapaddr) | self.shadow_base,
                self.csr_data_width, csrs)

        # Check and add Memory regions
        for name, memory, mapaddr, mmap in self.csrbankarray.srams:
            self.check_csr_range(name, 0x800*mapaddr)
            self.add_csr_region(name + "_" + memory.name_override,
                (self.soc_mem_map["csr"] + 0x800*mapaddr) | self.shadow_base,
                self.csr_data_width, memory)

        # Add CSRs / Config items to constants
        for name, constant in self.csrbankarray.constants:
            self._constants.append(((name + "_" + constant.name).upper(), constant.value.value))
        for name, value in sorted(self.config.items(), key=itemgetter(0)):
            self._constants.append(("CONFIG_" + name.upper(), value))
            if isinstance(value, str):
                self._constants.append(("CONFIG_" + name.upper() + "_" + value, 1))

        # Connect interrupts
        if hasattr(self, "cpu"):
            if hasattr(self.cpu, "interrupt"):
                for _name, _id in sorted(self.soc_interrupt_map.items()):
                    if _name in self.cpu.reserved_interrupts.keys():
                        continue
                    if hasattr(self, _name):
                        module = getattr(self, _name)
                        assert hasattr(module, 'ev'), "Submodule %s does not have EventManager (xx.ev) module" % _name
                        self.comb += self.cpu.interrupt[_id].eq(module.ev.irq)


# SoCCore arguments --------------------------------------------------------------------------------

def soc_core_args(parser):
    parser.add_argument("--cpu-type", default=None,
                        help="select CPU: lm32, or1k, picorv32, vexriscv, minerva, rocket")
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
    for a in [
        "cpu_type",
        "cpu_variant",
        "integrated_rom_size",
        "integrated_main_ram_size",
        "uart_stub"]:
        arg = getattr(args, a)
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
