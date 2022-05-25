#
# This file is part of LiteX.
#
# Copyright (c) 2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = {
    "standard":    "femtorv32_quark",
    "quark":       "femtorv32_quark",       # Quark:       Most elementary version of FemtoRV32.
    "tachyon":     "femtorv32_tachyon",     # Tachyon:     Like Quark but supporting higher freq.
    "electron":    "femtorv32_electron",    # Electron:    Adds M support.
    "intermissum": "femtorv32_intermissum", # Intermissum: Adds Interrupt + CSR.
    "gracilis":    "femtorv32_gracilis",    # Gracilis:    Adds C support.
    "petitbateau": "femtorv32_petitbateau", # PetitBateau: Adds F support.
}

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                               /-------- Base ISA
    #                               |/------- Hardware Multiply + Divide
    #                               ||/----- Atomics
    #                               |||/---- Compressed ISA
    #                               ||||/--- Single-Precision Floating-Point
    #                               |||||/-- Double-Precision Floating-Point
    #                               imacfd
    "standard":         "-march=rv32i     -mabi=ilp32",
    "quark":            "-march=rv32i     -mabi=ilp32",
    "tachyon":          "-march=rv32i     -mabi=ilp32",
    "electron":         "-march=rv32im    -mabi=ilp32",
    "intermissum":      "-march=rv32im    -mabi=ilp32",
    "gracilis":         "-march=rv32imc   -mabi=ilp32",
    "petitbateau":      "-march=rv32imfc  -mabi=ilp32f",
}

# FemtoRV ------------------------------------------------------------------------------------------

class FemtoRV(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "femtorv"
    human_name           = "FemtoRV"
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
        flags += " -D__femtorv__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.human_name   = f"FemtoRV-{variant.upper()}"
        self.reset        = Signal()
        self.idbus        = idbus = wishbone.Interface()
        self.periph_buses = [idbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []      # Memory buses (Connected directly to LiteDRAM).

        # # #

        # FemtoRV Mem Bus.
        # ----------------
        mbus = Record([
            ("addr",  32),
            ("wdata", 32),
            ("wmask",  4),
            ("rdata", 32),
            ("rstrb",  1),
            ("rbusy",  1),
            ("wbusy",  1),
        ])

        # FemtoRV Instance.
        # -----------------
        self.cpu_params = dict(
            # Parameters.
            p_ADDR_WIDTH = 32,
            p_RESET_ADDR = Constant(0, 32),

            # Clk / Rst.
            i_clk   = ClockSignal("sys"),
            i_reset = ~(ResetSignal("sys") | self.reset), # Active Low.

            # I/D Bus.
            o_mem_addr  = mbus.addr,
            o_mem_wdata = mbus.wdata,
            o_mem_wmask = mbus.wmask,
            i_mem_rdata = mbus.rdata,
            o_mem_rstrb = mbus.rstrb,
            i_mem_rbusy = mbus.rbusy,
            i_mem_wbusy = mbus.wbusy,
        )

        # Adapt FemtoRV Mem Bus to Wishbone.
        # ----------------------------------
        latch = Signal()
        write = mbus.wmask != 0
        read  = mbus.rstrb

        self.submodules.fsm = fsm = FSM(reset_state="WAIT")
        fsm.act("WAIT",
            # Latch Address + Bytes to Words conversion.
            NextValue(idbus.adr, mbus.addr[2:]),

            # Latch Wdata/WMask.
            NextValue(idbus.dat_w, mbus.wdata),
            NextValue(idbus.sel,   mbus.wmask),

            # If Read or Write, jump to access.
            If(read | write,
                NextValue(idbus.we, write),
                NextState("WB-ACCESS")
            )
        )
        fsm.act("WB-ACCESS",
            idbus.stb.eq(1),
            idbus.cyc.eq(1),
            mbus.wbusy.eq(1),
            mbus.rbusy.eq(1),
            If(idbus.ack,
                mbus.wbusy.eq(0),
                mbus.rbusy.eq(0),
                latch.eq(1),
                NextState("WAIT")
            )
        )

        # Latch RData on Wishbone ack.
        mbus_rdata = Signal(32)
        self.sync += If(latch, mbus_rdata.eq(idbus.dat_r))
        self.comb += mbus.rdata.eq(mbus_rdata)             # Latched value.
        self.comb += If(latch, mbus.rdata.eq(idbus.dat_r)) # Immediate value.

        # Add Verilog sources.
        # --------------------
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(p_RESET_ADDR=Constant(reset_address, 32))

    @staticmethod
    def add_sources(platform, variant):
        platform.add_verilog_include_path(os.getcwd())
        cpu_files = [f"{CPU_VARIANTS[variant]}.v"]
        if variant == "petitbateau":
            cpu_files.append("petitbateau.v")
        for cpu_file in cpu_files:
            if not os.path.exists(cpu_file):
                os.system(f"wget https://raw.githubusercontent.com/BrunoLevy/learn-fpga/master/FemtoRV/RTL/PROCESSOR/{cpu_file}")
            platform.add_source(cpu_file)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("FemtoRV32", **self.cpu_params)
