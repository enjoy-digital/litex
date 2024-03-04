#
# This file is part of LiteX.
#
# Copyright (c) 2024 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Github project: https://github.com/meiniKi/FazyRV

import os

from migen import *

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = {
    "standard": "fazyrv",
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
    "standard": "-march=rv32i2p0   -mabi=ilp32",
}

# FazyRV ------------------------------------------------------------------------------------------

class FazyRV(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "fazyrv"
    human_name           = "fazyrv"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # Default parameters.
    chunksize = 8
    conf      = "MIN"
    rftype    = "BRAM_DP_BP"

    # Command line configuration arguments.
    @staticmethod
    def args_fill(parser):
        cpu_group = parser.add_argument_group(title="CPU options.")
        cpu_group.add_argument("--cpu-chunksize", default=8,            help="Size of the chunks, i.e., the data path.", type=int,  choices=[1, 2, 4, 8])
        cpu_group.add_argument("--cpu-conf",      default="MIN",        help="Configuration of the processor.",          type=str,  choices=["MIN", "INT", "CSR"])
        cpu_group.add_argument("--cpu-rftype",    default="BRAM_DP_BP", help="Implementation of the register file.",     type=str,  choices=["LOGIC", "BRAM", "BRAM_BP", "BRAM_DP", "BRAM_DP_BP"])

    @staticmethod
    def args_read(args):
        if(args.cpu_chunksize): FazyRV.chunksize = args.cpu_chunksize
        if(args.cpu_conf)     : FazyRV.conf      = args.cpu_conf
        if(args.cpu_rftype)   : FazyRV.rftype    = args.cpu_rftype

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  GCC_FLAGS[self.variant]
        flags += " -D__fazyrv__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.human_name   = f"FazyRV-{variant.upper()}"
        self.reset        = Signal()
        self.ibus         = ibus = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        self.dbus         = dbus = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        self.periph_buses = [ibus, dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []           # Memory buses (Connected directly to LiteDRAM).

        # FazyRV Instance.
        # -----------------
        self.cpu_params = dict(
            # Parameters.
            p_CHUNKSIZE = FazyRV.chunksize,
            p_CONF      = FazyRV.conf,
            p_MTVAL     = 0,
            p_BOOTADR   = 0,
            p_RFTYPE    = FazyRV.rftype,
            p_MEMDLY1   = 0,

            # Clk / Rst.
            i_clk_i  =  ClockSignal("sys"),
            i_rst_in =  ~(ResetSignal("sys") | self.reset),

            # IRQ / Trap.
            i_tirq_i = 0,
            o_trap_o = Open(),

            # I Bus.
            o_wb_imem_stb_o = ibus.stb,
            o_wb_imem_cyc_o = ibus.cyc,
            o_wb_imem_adr_o = ibus.adr,
            i_wb_imem_dat_i = ibus.dat_r,
            i_wb_imem_ack_i = ibus.ack,

            # D Bus.
            o_wb_dmem_cyc_o = dbus.cyc,
            o_wb_dmem_stb_o = dbus.stb,
            o_wb_dmem_we_o  = dbus.we,
            i_wb_dmem_ack_i = dbus.ack,
            o_wb_dmem_be_o  = dbus.sel,
            i_wb_dmem_dat_i = dbus.dat_r,
            o_wb_dmem_adr_o = dbus.adr,
            o_wb_dmem_dat_o = dbus.dat_w,
        )

        # Add Verilog sources.
        # --------------------
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(p_BOOTADR=Constant(reset_address, 32))

    @staticmethod
    def add_sources(platform, variant):
        if not os.path.exists("FazyRV"):
            os.system(f"git clone https://github.com/meiniKi/FazyRV")
        vdir = "FazyRV/rtl"
        platform.add_verilog_include_path(vdir)
        platform.add_source_dir(vdir)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("fazyrv_top", **self.cpu_params)
