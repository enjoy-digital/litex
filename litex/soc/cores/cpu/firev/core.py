#
# This file is part of LiteX.
#
# Copyright (c) 2022 Sylvain Lefebvre <sylvain.lefebvre@inria.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = {
    "standard": "firev",
}

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                       /------------ Base ISA
    #                       |    /------- Hardware Multiply + Divide
    #                       |    |/----- Atomics
    #                       |    ||/---- Compressed ISA
    #                       |    |||/--- Single-Precision Floating-Point
    #                       |    ||||/-- Double-Precision Floating-Point
    #                       i    macfd
    "standard": "-march=rv32i2p0      -mabi=ilp32",
}

# FireV ------------------------------------------------------------------------------------------

class FireV(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "firev"
    human_name           = "firev"
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
        flags =  GCC_FLAGS[self.variant]
        flags += " -D__firev__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.human_name   = f"FireV-{variant.upper()}"
        self.reset        = Signal()
        self.idbus        = idbus = wishbone.Interface()
        self.periph_buses = [idbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []      # Memory buses (Connected directly to LiteDRAM).

        # FireV Mem Bus.
        # ----------------
        mbus = Record([
            ("out_ram_addr",    32),
            ("out_ram_in_valid", 1),
            ("out_ram_wmask",    4),
            ("out_ram_rw",       1),
            ("out_ram_data_in", 32),
            ("in_ram_done",      1),
            ("in_ram_data_out", 32),
            ("in_boot_at",      32),
        ])

        # FireV Instance.
        # -----------------
        self.cpu_params = dict(
            # Clk / Rst.
            i_clock = ClockSignal("sys"),
            i_reset = (ResetSignal("sys") | self.reset),

            # Reset Address.
            i_in_boot_at = Constant(0, 32),

            # I/D Bus.
            o_out_ram_addr     = mbus.out_ram_addr,
            o_out_ram_in_valid = mbus.out_ram_in_valid,
            o_out_ram_wmask    = mbus.out_ram_wmask,
            o_out_ram_data_in  = mbus.out_ram_data_in,
            o_out_ram_rw       = mbus.out_ram_rw,
            i_in_ram_done      = mbus.in_ram_done,
            i_in_ram_data_out  = mbus.in_ram_data_out,
        )

        # Adapt FireV Mem Bus to Wishbone.
        # --------------------------------
        self.fsm = fsm = FSM(reset_state="WAIT")
        fsm.act("WAIT",
            If(mbus.out_ram_in_valid,
                idbus.stb.eq(1),
                idbus.cyc.eq(1),
                NextState("WB-ACCESS")
            )
        )
        fsm.act("WB-ACCESS",
            idbus.stb.eq(1),
            idbus.cyc.eq(1),
            If(idbus.ack,
                NextState("WAIT")
            )
        )
        self.comb += [
            idbus.we.eq(mbus.out_ram_rw),
            idbus.adr.eq(mbus.out_ram_addr[2:]),
            idbus.sel.eq(mbus.out_ram_wmask),
            idbus.dat_w.eq(mbus.out_ram_data_in),


            mbus.in_ram_data_out.eq(idbus.dat_r),
            mbus.in_ram_done.eq(idbus.ack),
        ]

        # Add Verilog sources.
        # --------------------
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(i_in_boot_at=Constant(reset_address, 32))

    @staticmethod
    def add_sources(platform, variant):
        platform.add_verilog_include_path(os.getcwd())
        cpu_file = f"{CPU_VARIANTS[variant]}.v"
        if not os.path.exists(cpu_file):
            os.system(f"wget https://raw.githubusercontent.com/sylefeb/Silice/draft/projects/fire-v/export-verilog/{cpu_file}")
        platform.add_source(cpu_file)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("M_rv32i_cpu", **self.cpu_params)
