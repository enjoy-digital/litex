#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.build.generic_platform import Pins

from litex.soc.interconnect import axi
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32, CPU_GCC_TRIPLE_RISCV64
from litex.soc.integration.soc import SoCRegion

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard", "rv32", "rv64"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    "rv32": "-march=rv32i2p0_mac  -mabi=ilp32 ",
    "rv64": "-march=rv64i2p0_mac  -mabi=lp64 -mcmodel=medany ",
}

# Helpers ------------------------------------------------------------------------------------------

def _qemu_bus_interface():
    return axi.AXIInterface(data_width=32, address_width=32)


def _qemu_bus_pad_name(shared_ram=False):
    return "qemu_axi_shared_ram" if shared_ram else "qemu_axi"


def _qemu_region_is_in_io_regions(region_origin, region_size, io_regions):
    for origin, size in io_regions.items():
        if region_origin >= origin and region_origin + region_size <= origin + size:
            return True
    return False

# QEMU ---------------------------------------------------------------------------------------------


class QEMU(CPU):
    category             = "emulator"
    family               = "riscv"
    name                 = "qemu"
    human_name           = "QEMU RISC-V"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"

    def __init__(self, platform, variant="standard"):
        if variant == "standard":
            variant = "rv32"

        self.platform = platform
        self.variant  = variant
        self.xlen     = 64 if variant == "rv64" else 32
        self.reset    = Signal()

        self.bus          = _qemu_bus_interface()
        self.periph_buses = [self.bus]
        self.memory_buses = []

        self.interrupt           = Signal(32)
        self.interrupts          = {}
        self.reserved_interrupts = {"noirq": 0}

        if self.xlen == 64:
            self.data_width           = 64
            self.gcc_triple           = CPU_GCC_TRIPLE_RISCV64
            self.linker_output_format = "elf64-littleriscv"
            self.mem_map = {
                "clint"    : 0x0200_0000,
                "plic"     : 0x0c00_0000,
                "rom"      : 0x1000_0000,
                "sram"     : 0x1100_0000,
                "csr"      : 0x1200_0000,
                "ethmac"   : 0x3000_0000,
                "main_ram" : 0x8000_0000,
            }
            self.io_regions = {0x1200_0000: 0x6e00_0000}
        else:
            self.data_width           = 32
            self.gcc_triple           = CPU_GCC_TRIPLE_RISCV32
            self.linker_output_format = "elf32-littleriscv"
            self.mem_map = {
                "clint"    : 0xf001_0000,
                "plic"     : 0xf0c0_0000,
                "rom"      : 0x0000_0000,
                "sram"     : 0x1000_0000,
                "main_ram" : 0x4000_0000,
                "csr"      : 0xf000_0000,
            }
            self.io_regions = {0x8000_0000: 0x8000_0000}

        self._add_sim_pads(platform, _qemu_bus_pad_name())

    @property
    def gcc_flags(self):
        flags  = "-mno-save-restore "
        flags += GCC_FLAGS[self.variant]
        flags += "-D__qemu__ -D__riscv_plic__ -DUART_POLLING "
        return flags

    def _add_sim_pads(self, platform, name):
        platform.add_extension(self.bus.get_ios(name))
        platform.add_extension([("qemu_irq", 0, Pins(len(self.interrupt)))])
        platform.add_extension([("qemu_reset", 0, Pins(1))])
        self.comb += self.bus.connect_to_pads(platform.request(name), mode="slave")
        self.comb += platform.request("qemu_irq").eq(self.interrupt)
        self.comb += platform.request("qemu_reset").eq(self.reset)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address

    def add_jtag(self, pads):
        pass

    def add_soc_components(self, soc):
        soc.add_config("CPU_COUNT", 1)
        soc.add_config("CPU_ISA",   "rv{}imac".format(self.xlen))
        soc.add_config("CPU_MMU",   {32: "sv32", 64: "sv39"}[self.xlen])

        for name, size in {
            "clint" : 0x1_0000,
            "plic"  : 0x40_0000,
        }.items():
            origin = soc.mem_map.get(name)
            cached = not _qemu_region_is_in_io_regions(
                region_origin = origin,
                region_size   = size,
                io_regions    = self.io_regions,
            )
            soc.bus.add_region(name, SoCRegion(
                origin = origin,
                size   = size,
                cached = cached,
                linker = True,
            ))

# QEMU Shared RAM ----------------------------------------------------------------------------------

class QEMUSharedRAM(LiteXModule):
    def __init__(self, platform, name=None):
        name     = _qemu_bus_pad_name(shared_ram=True) if name is None else name
        self.bus = _qemu_bus_interface()
        self._add_sim_pads(platform, name)

    def _add_sim_pads(self, platform, name):
        platform.add_extension(self.bus.get_ios(name))
        self.comb += self.bus.connect_to_pads(platform.request(name), mode="master")
