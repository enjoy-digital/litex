#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.build.vhd2v_converter import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["minimal", "lite", "standard", "full"]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    #                               /------------ Base ISA
    #                               |    /------- Hardware Multiply + Divide
    #                               |    |/----- Atomics
    #                               |    ||/---- Compressed ISA
    #                               |    |||/--- Single-Precision Floating-Point
    #                               |    ||||/-- Double-Precision Floating-Point
    #                               i    macfd
    "minimal":          "-march=rv32i2p0      -mabi=ilp32",
    "lite":             "-march=rv32i2p0_mc   -mabi=ilp32",
    "standard":         "-march=rv32i2p0_mc   -mabi=ilp32",
    "full":             "-march=rv32i2p0_mc   -mabi=ilp32",
}

# NEORV32 ------------------------------------------------------------------------------------------

class NEORV32(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "neorv32"
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
        flags += " -D__neorv32__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.human_name   = f"NEORV32-{variant}"
        self.reset        = Signal()
        self.ibus         = idbus = wishbone.Interface()
        self.periph_buses = [idbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []      # Memory buses (Connected directly to LiteDRAM).

        # # #

        # CPU LiteX Core Complex Wrapper
        self.specials += Instance("neorv32_litex_core_complex",
            # Clk/Rst.
            i_clk_i  = ClockSignal("sys"),
            i_rstn_i = ~(ResetSignal() | self.reset),

            # JTAG.
            i_jtag_trst_i = 0,
            i_jtag_tck_i  = 0,
            i_jtag_tdi_i  = 0,
            o_jtag_tdo_o  = Open(),
            i_jtag_tms_i  = 0,

            # Interrupt.
            i_mext_irq_i  = 0,

            # I/D Wishbone Bus.
            o_wb_adr_o = Cat(Signal(2), idbus.adr),
            i_wb_dat_i = idbus.dat_r,
            o_wb_dat_o = idbus.dat_w,
            o_wb_we_o  = idbus.we,
            o_wb_sel_o = idbus.sel,
            o_wb_stb_o = idbus.stb,
            o_wb_cyc_o = idbus.cyc,
            i_wb_ack_i = idbus.ack,
            i_wb_err_i = idbus.err,
        )

        self.submodules.vhd2v_converter = VHD2VConverter(platform,
            top_entity    = "neorv32_litex_core_complex",
            build_dir     = os.path.abspath(os.path.dirname(__file__)),
            work_package  = "neorv32",
            force_convert = True,
            params = dict(
                p_CONFIG = {
                    "minimal"  : 0,
                    "lite"     : 1,
                    "standard" : 2,
                    "full"     : 3
                }[variant],
                p_DEBUG = False,
            )
        )

        # Add Verilog sources
        self.add_sources(variant)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        assert reset_address == 0x0000_0000

    def add_sources(self, variant):
        cdir = os.path.abspath(os.path.dirname(__file__))
        # List VHDL sources.
        sources = {
            "core" : [
                # CPU & Processors Packages/Cores.
                "neorv32_package.vhd",
                "neorv32_fifo.vhd",

                # CPU components.
                "neorv32_cpu.vhd",
                    "neorv32_cpu_alu.vhd",
                        "neorv32_cpu_cp_bitmanip.vhd",
                        "neorv32_cpu_cp_cfu.vhd",
                        "neorv32_cpu_cp_fpu.vhd",
                        "neorv32_cpu_cp_muldiv.vhd",
                        "neorv32_cpu_cp_shifter.vhd",
                    "neorv32_cpu_bus.vhd",
                    "neorv32_cpu_control.vhd",
                        "neorv32_cpu_decompressor.vhd",
                    "neorv32_cpu_regfile.vhd",

                # Processor components.
                "neorv32_top.vhd",
                    "neorv32_icache.vhd",
                    "neorv32_busswitch.vhd",
                    "neorv32_bus_keeper.vhd",
                    "neorv32_wishbone.vhd",
                    "neorv32_mtime.vhd",
                    "neorv32_sysinfo.vhd",
                    "neorv32_debug_dm.vhd",
                    "neorv32_debug_dtm.vhd",
            ],

            "core/mem": [
                "neorv32_imem.default.vhd",
                "neorv32_dmem.default.vhd",
            ],

            "system_integration": [
                "neorv32_litex_core_complex.vhd",
            ],
        }

        # Download VHDL sources (if not already present).
        sha1 = "d610a0bd777f55d17dd59f174566aa88e911a1ec"
        for directory, vhds in sources.items():
            for vhd in vhds:
                self.vhd2v_converter.add_source(os.path.join(cdir, vhd))
                if not os.path.exists(os.path.join(cdir, vhd)):
                    os.system(f"wget https://raw.githubusercontent.com/stnolting/neorv32/{sha1}/rtl/{directory}/{vhd} -P {cdir}")

    def do_finalize(self):
        assert hasattr(self, "reset_address")
