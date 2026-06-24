#
# This file is part of LiteX.
#
# Copyright (c) 2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = {
    "standard": "kianv",
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
    "standard": "-march=rv32i2p0_ma   -mabi=ilp32",
}

# KianV ------------------------------------------------------------------------------------------

class KianV(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "kianv"
    human_name           = "kianv"
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
        flags += " -D__kianv__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.human_name   = f"KianV-{variant.upper()}"
        self.reset        = Signal()
        self.idbus        = idbus = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        self.periph_buses = [idbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []      # Memory buses (Connected directly to LiteDRAM).

        # KianV Mem Bus.
        # ----------------
        mbus = Record([
            ("valid",  1),
            ("ready",  1),
            ("wstrb",  4),
            ("addr",  32),
            ("wdata", 32),
            ("rdata", 32),
        ])

        # KianV Instance.
        # -----------------
        self.cpu_params = dict(
            # Clk / Rst.
            i_clk    =  ClockSignal("sys"),
            i_resetn = ~(ResetSignal("sys") | self.reset),

            # Parameters.
            p_RESET_ADDR = 0,
            p_STACKADDR  = 0,
            p_RV32E      = 0,

            # Control/Status.
            o_PC           = Open(),
            i_access_fault = 0,
            i_IRQ3         = 0,
            i_IRQ7         = 0,

            # I/D Bus.
            o_mem_valid = mbus.valid,
            i_mem_ready = mbus.ready,
            o_mem_wstrb = mbus.wstrb,
            o_mem_addr  = mbus.addr,
            o_mem_wdata = mbus.wdata,
            i_mem_rdata = mbus.rdata,
        )

        # Adapt KianV Mem Bus to Wishbone.
        # --------------------------------
        self.comb += [
            idbus.stb.eq(mbus.valid),
            idbus.cyc.eq(mbus.valid),
            mbus.ready.eq(idbus.ack),
            idbus.we.eq(mbus.wstrb != 0),
            idbus.adr.eq(mbus.addr),
            idbus.sel.eq(mbus.wstrb),
            idbus.dat_w.eq(mbus.wdata),
            mbus.rdata.eq(idbus.dat_r),
        ]

        # Add Verilog sources.
        # --------------------
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(p_RESET_ADDR=Constant(reset_address, 32))

    @staticmethod
    def add_sources(platform, variant):
        if not os.path.exists("KianRiscv"):
            os.system(f"git clone https://github.com/splinedrive/kianRiscV")
        vdir = "kianRiscV/linux_socs/kianv_harris_mcycle_edition/kianv_harris_edition"
        platform.add_verilog_include_path(vdir)
        platform.add_source_dir(vdir)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("kianv_harris_mc_edition", **self.cpu_params)
