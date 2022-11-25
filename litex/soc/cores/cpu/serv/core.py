#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Greg Davill <greg.davill@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard", "mdu"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                               /------------ Base ISA
    #                               |    /------- Hardware Multiply + Divide
    #                               |    |/----- Atomics
    #                               |    ||/---- Compressed ISA
    #                               |    |||/--- Single-Precision Floating-Point
    #                               |    ||||/-- Double-Precision Floating-Point
    #                               i    macfd
    "standard":         "-march=rv32i2p0      -mabi=ilp32",
    "mdu":              "-march=rv32i2p0_m    -mabi=ilp32",
}

# SERV ---------------------------------------------------------------------------------------------

class SERV(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "serv"
    human_name           = "SERV"
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
        flags += " -D__serv__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.ibus         = ibus = wishbone.Interface()
        self.dbus         = dbus = wishbone.Interface()
        self.periph_buses = [ibus, dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []           # Memory buses (Connected directly to LiteDRAM).

        # # #

        self.cpu_params = dict(
            # Clk / Rst
            i_clk   = ClockSignal(),
            i_i_rst = ResetSignal() | self.reset,

            # Timer IRQ.
            i_i_timer_irq = 0,

            # Ibus.
            o_o_ibus_adr = Cat(Signal(2), ibus.adr),
            o_o_ibus_cyc = ibus.cyc,
            i_i_ibus_rdt = ibus.dat_r,
            i_i_ibus_ack = ibus.ack,

            # Dbus.
            o_o_dbus_adr = Cat(Signal(2), dbus.adr),
            o_o_dbus_dat = dbus.dat_w,
            o_o_dbus_sel = dbus.sel,
            o_o_dbus_we  = dbus.we,
            o_o_dbus_cyc = dbus.cyc,
            i_i_dbus_rdt = dbus.dat_r,
            i_i_dbus_ack = dbus.ack,
        )
        self.comb += [
            ibus.stb.eq(ibus.cyc),
            ibus.sel.eq(0xf),
            dbus.stb.eq(dbus.cyc),
        ]

        # Add MDU.
        if self.variant == "mdu":
            self.add_mdu()

        # Add Verilog sources
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(p_RESET_PC=reset_address)

    def add_mdu(self):
        # Get MDU file.
        mdu_file = "mdu_top.v"
        if not os.path.exists(mdu_file):
            os.system(f"wget https://raw.githubusercontent.com/zeeshanrafique23/mdu/dev/rtl/mdu_top.v")


        # Do MDU instance.
        mdu_rs1   = Signal(32)
        mdu_rs2   = Signal(32)
        mdu_op    = Signal(2)
        mdu_valid = Signal()
        mdu_rd    = Signal(32)
        mdu_ready = Signal()
        self.specials += Instance("mdu_top",
            i_i_clk       = ClockSignal(),
            i_i_rst       = ResetSignal() | self.reset,
            i_i_mdu_rs1   = mdu_rs1,
            i_i_mdu_rs2   = mdu_rs2,
            i_i_mdu_op    = mdu_op,
            i_i_mdu_valid = mdu_valid,
            o_o_mdu_ready = mdu_ready,
            o_o_mdu_rd    = mdu_rd
        )
        self.platform.add_source(mdu_file)

        # Connect MDU to SERV.
        self.cpu_params.update(
            p_MDU          = 1,
            o_o_ext_rs1    = mdu_rs1,
            o_o_ext_rs2    = mdu_rs2,
            o_o_ext_funct3 = mdu_op,
            i_i_ext_rd     = mdu_rd,
            i_i_ext_ready  = mdu_ready,
            o_o_mdu_valid  = mdu_valid
        )

    @staticmethod
    def add_sources(platform):
        vdir = get_data_mod("cpu", "serv").data_location
        platform.add_source_dir(os.path.join(vdir, "rtl"))
        platform.add_verilog_include_path(os.path.join(vdir, "rtl"))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("serv_rf_top", **self.cpu_params)
