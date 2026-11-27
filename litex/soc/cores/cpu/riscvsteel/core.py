#
# This file is part of LiteX.
#
# 
# SPDX-License-Identifier: BSD-2-Clause

import os
import re

from migen import *

from litex.gen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                       /------------ Base ISA
    #                       |    /------- Hardware Multiply + Divide
    #                       |    |/----- Atomics
    #                       |    ||/---- Compressed ISA
    #                       |    |||/--- Single-Precision Floating-Point
    #                       |    ||||/-- Double-Precision Floating-Point
    #                       i    macfd
    "standard": "-march=rv32izicsr   -mabi=ilp32 ",
}

# Helpers ------------------------------------------------------------------------------------------

def add_sources(platform):
    vloc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "standard", "rvsteel_core.v")
    platform.add_source(vloc)

# Wishbone <> Steel ----------------------------------------------------------------------------------

steel_layout = [
    ("rw_address", 32),
    ("read_data", 32),
    ("read_request", 1),
    ("read_response", 1),
    ("write_data", 32),
    ("write_strobe", 4),
    ("write_request", 1),
    ("write_response", 1),
]

class SteelCore2Wishbone(LiteXModule):
    def __init__(self, steel_idbus, idbus):
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")

        fsm.act("IDLE",
            If(steel_idbus.read_request,
                NextValue(idbus.adr, steel_idbus.rw_address),
                NextValue(idbus.stb, 1),
                NextValue(idbus.cyc, 1),
                NextValue(idbus.sel, 0b1111),
                NextValue(idbus.we, 0),
                NextState("READ")
            ).Elif(steel_idbus.write_request,
                NextValue(idbus.adr, steel_idbus.rw_address),
                NextValue(idbus.dat_w, steel_idbus.write_data),
                NextValue(idbus.stb, 1),
                NextValue(idbus.cyc, 1),
                NextValue(idbus.sel, steel_idbus.write_strobe),
                NextValue(idbus.we, 1),
                NextState("WRITE")
            ),
        )

        fsm.act("READ",
            If(idbus.ack,
                steel_idbus.read_data.eq(idbus.dat_r),
                steel_idbus.read_response.eq(1),
                NextValue(idbus.stb, 0),  # Deassert stb after ack
                NextValue(idbus.cyc, 0),  # Deassert cyc after ack
                NextValue(idbus.sel, 0),  # Deassert sel after ack
                NextState("IDLE")
            )
        )

        fsm.act("WRITE",
            If(idbus.ack,
                steel_idbus.write_response.eq(1),
                NextValue(idbus.stb, 0),  # Deassert stb after ack
                NextValue(idbus.cyc, 0),  # Deassert cyc after ack
                NextValue(idbus.sel, 0),  # Deassert sel after ack
                NextState("IDLE")
            )
        )

# riscvsteel -----------------------------------------------------------------------------------------

class riscvsteel(CPU):
    family               = "riscv"
    category             = "softcore"
    name                 = "riscvsteel"
    human_name           = "riscv-steel"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags = GCC_FLAGS[self.variant]
        flags += "-D__riscvsteel__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform          = platform
        self.variant           = variant
        self.reset             = Signal()
        self.idbus             = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        
        self.periph_buses      = [self.idbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses      = []      # Memory buses (Connected directly to LiteDRAM).
        self.interrupt         = Signal(16)

        self.steel_idbus = Record(steel_layout)

        # Steel <> Wishbone.
        self.idbus_conv = SteelCore2Wishbone(self.steel_idbus, self.idbus)

        self.cpu_params = dict(
            # Global signals
            i_clock                     = ClockSignal("sys"),
            i_reset                     = ResetSignal("sys") | self.reset, # FIXME: self.reset does not clear interrupt signals so reboot isn't fully functional 
            i_halt                      = 0,

            # IO interface
            o_rw_address                = self.steel_idbus.rw_address,
            i_read_data                 = self.steel_idbus.read_data,
            o_read_request              = self.steel_idbus.read_request,
            i_read_response             = self.steel_idbus.read_response,
            o_write_data                = self.steel_idbus.write_data,
            o_write_strobe              = self.steel_idbus.write_strobe,
            o_write_request             = self.steel_idbus.write_request,
            i_write_response            = self.steel_idbus.write_response,

            i_irq_external              = 0,
            o_irq_external_response     = Open(),
            i_irq_timer                 = 0,
            o_irq_timer_response        = Open(),
            i_irq_software              = 0,
            o_irq_software_response     = Open(),
            i_irq_fast                  = self.interrupt,
            o_irq_fast_response         = Open(16),

            i_real_time_clock           = 0
        )

        add_sources(platform)

    def set_reset_address(self, reset_address):
        assert hasattr(self, "reset_address") == False
        self.reset_address = reset_address
        self.cpu_params.update(p_BOOT_ADDRESS=reset_address)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("rvsteel_core", **self.cpu_params)
