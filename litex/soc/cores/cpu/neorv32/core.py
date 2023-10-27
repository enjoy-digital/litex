#
# This file is part of LiteX.
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
#               2023 Protech Engineering <m.marzaro@protechgoup.it>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex.build.vhd2v_converter import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = [
    "minimal",
    "minimal+debug",
    "lite",
    "lite+debug",
    "standard",
    "standard+debug",
    "full",
    "full+debug",
]

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
    "minimal+debug":    "-march=rv32i2p0      -mabi=ilp32",
    "lite":             "-march=rv32i2p0_mc   -mabi=ilp32",
    "lite+debug":       "-march=rv32i2p0_mc   -mabi=ilp32",
    "standard":         "-march=rv32i2p0_mc   -mabi=ilp32",
    "standard+debug":   "-march=rv32i2p0_mc   -mabi=ilp32",
    "full":             "-march=rv32i2p0_mc   -mabi=ilp32",
    "full+debug":       "-march=rv32i2p0_mc   -mabi=ilp32",
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
    io_regions           = {0xF000_0000: 0x0FFF_BFFF} # Origin, Length.

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
        self.ibus         = idbus = wishbone.Interface(data_width=32, address_width=32, addressing="byte")
        self.periph_buses = [idbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []      # Memory buses (Connected directly to LiteDRAM).

        # # #

        # CPU Instance.
        self.cpu_params = dict(
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
            o_wb_adr_o = idbus.adr,
            i_wb_dat_i = idbus.dat_r,
            o_wb_dat_o = idbus.dat_w,
            o_wb_we_o  = idbus.we,
            o_wb_sel_o = idbus.sel,
            o_wb_stb_o = idbus.stb,
            o_wb_cyc_o = idbus.cyc,
            i_wb_ack_i = idbus.ack,
            i_wb_err_i = idbus.err,
        )

        if "debug" in variant:
            self.add_debug()

        self.vhd2v_converter = VHD2VConverter(self.platform,
            top_entity    = "neorv32_litex_core_complex",
            build_dir     = os.path.abspath(os.path.dirname(__file__)),
            work_package  = "neorv32",
            force_convert = True,
            params = dict(
                p_CONFIG = {
                    "minimal"        : 0,
                    "minimal+debug"  : 0,
                    "lite"           : 1,
                    "lite+debug"     : 1,
                    "standard"       : 2,
                    "standard+debug" : 2,
                    "full"           : 3,
                    "full+debug"     : 3
                }[self.variant],
                p_DEBUG = "debug" in self.variant,
            )
        )

        self.add_sources()

    # Memory Mapping.
    @property
    def mem_map(self):
        return {
            "rom"       : 0x0000_0000,
            "sram"      : 0x0100_0000,
            "main_ram"  : 0x4000_0000,
            "csr"       : 0xF000_0000,
        }

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        assert reset_address == 0x0000_0000

    def add_debug(self):
        self.i_jtag_trst = Signal()
        self.i_jtag_tck = Signal()
        self.i_jtag_tdi = Signal()
        self.o_jtag_tdo = Signal()
        self.i_jtag_tms = Signal()

        self.cpu_params.update(
            i_jtag_trst_i = self.i_jtag_trst,
            i_jtag_tck_i  = self.i_jtag_tck,
            i_jtag_tdi_i  = self.i_jtag_tdi,
            o_jtag_tdo_o  = self.o_jtag_tdo,
            i_jtag_tms_i  = self.i_jtag_tms,
        )

    def add_sources(self):
        cdir = os.path.abspath(os.path.dirname(__file__))
        # List VHDL sources.
        sources = {
            "core" : [
                "neorv32_application_image.vhd",
                "neorv32_bootloader_image.vhd",
                "neorv32_boot_rom.vhd",
                "neorv32_cfs.vhd",
                "neorv32_cpu_alu.vhd",
                "neorv32_cpu_control.vhd",
                "neorv32_cpu_cp_bitmanip.vhd",
                "neorv32_cpu_cp_cfu.vhd",
                "neorv32_cpu_cp_fpu.vhd",
                "neorv32_cpu_cp_muldiv.vhd",
                "neorv32_cpu_cp_shifter.vhd",
                "neorv32_cpu_decompressor.vhd",
                "neorv32_cpu_lsu.vhd",
                "neorv32_cpu_pmp.vhd",
                "neorv32_cpu_regfile.vhd",
                "neorv32_cpu.vhd",
                "neorv32_crc.vhd",
                "neorv32_dcache.vhd",
                "neorv32_debug_dm.vhd",
                "neorv32_debug_dtm.vhd",
                "neorv32_dma.vhd",
                "neorv32_dmem.entity.vhd",
                "neorv32_fifo.vhd",
                "neorv32_gpio.vhd",
                "neorv32_gptmr.vhd",
                "neorv32_icache.vhd",
                "neorv32_imem.entity.vhd",
                "neorv32_intercon.vhd",
                "neorv32_mtime.vhd",
                "neorv32_neoled.vhd",
                "neorv32_onewire.vhd",
                "neorv32_package.vhd",
                "neorv32_pwm.vhd",
                "neorv32_sdi.vhd",
                "neorv32_slink.vhd",
                "neorv32_spi.vhd",
                "neorv32_sysinfo.vhd",
                "neorv32_top.vhd",
                "neorv32_trng.vhd",
                "neorv32_twi.vhd",
                "neorv32_uart.vhd",
                "neorv32_wdt.vhd",
                "neorv32_wishbone.vhd",
                "neorv32_xip.vhd",
                "neorv32_xirq.vhd",
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
        # Version 1.8.9
        sha1 = "fdb00a5d24e256ac9a9cb29410f2653c95068c91"
        for directory, vhds in sources.items():
            for vhd in vhds:
                self.vhd2v_converter.add_source(os.path.join(cdir, vhd))
                if not os.path.exists(os.path.join(cdir, vhd)):
                    os.system(f"wget https://raw.githubusercontent.com/stnolting/neorv32/{sha1}/rtl/{directory}/{vhd} -P {cdir}")

    def do_finalize(self):
        assert hasattr(self, "reset_address")

        # CPU LiteX Core Complex Wrapper
        self.specials += Instance("neorv32_litex_core_complex", **self.cpu_params)
