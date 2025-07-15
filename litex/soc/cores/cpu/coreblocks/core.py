#
# This file is part of LiteX.
#
# Copyright (c) 2023-2025 Piotr Wegrzyn (Coreforge Foundation) <piotro@piotro.eu>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess

from migen import *

from litex import get_data_mod
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32
from litex.soc.interconnect import wishbone

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = {
    "standard": "basic",
    "full":     "full",
}

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    "standard":         "-march=rv32i2p0_m                                    -mabi=ilp32 ",
    "full":             "-march=rv32i2p0_mac_zba_zbb_zbc_zbs                  -mabi=ilp32 ",
}

# Coreblocks ----------------------------------------------------------------------------------------

class Coreblocks(CPU):
    category             = "softcore"
    family               = "riscv"
    name                 = "coreblocks"
    human_name           = "Coreblocks"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "little"
    gcc_triple           = CPU_GCC_TRIPLE_RISCV32
    linker_output_format = "elf32-littleriscv"
    nop                  = "nop"
    io_regions           = {0xe000_0000: 0x2000_0000} # Origin, Length.

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  GCC_FLAGS[self.variant]
        flags += "-D__coreblocks__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.human_name   = f"Coreblocks-{CPU_VARIANTS[variant]}"
        self.reset        = Signal()
        self.interrupt    = Signal(16) # hart-local 16 platform interrupts - ids 16+n

        self.ibus         = ibus = wishbone.Interface()
        self.dbus         = dbus = wishbone.Interface()
        self.periph_buses = [self.ibus, self.dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []                     # Memory buses (Connected directly to LiteDRAM).

        # # #

        self.interrupts_full = Signal(32)
        # Shift interrupts to platform range
        self.comb += self.interrupts_full.eq(self.interrupt << 16)

        self.cpu_params = dict(
            # Clk / Rst.
            i_clk = ClockSignal("sys"),
            i_rst = ResetSignal("sys") | self.reset,

            ## IRQ.
            i_interrupts = self.interrupts_full,

            # Ibus.
            o_wb_instr__stb   = ibus.stb,
            o_wb_instr__cyc   = ibus.cyc,
            o_wb_instr__we    = ibus.we,
            o_wb_instr__adr   = ibus.adr,
            o_wb_instr__dat_w = ibus.dat_w,
            o_wb_instr__sel   = ibus.sel,
            i_wb_instr__ack   = ibus.ack,
            i_wb_instr__err   = ibus.err,
            i_wb_instr__dat_r = ibus.dat_r,

            # Dbus.
            o_wb_data__stb   = dbus.stb,
            o_wb_data__cyc   = dbus.cyc,
            o_wb_data__we    = dbus.we,
            o_wb_data__adr   = dbus.adr,
            o_wb_data__dat_w = dbus.dat_w,
            o_wb_data__sel   = dbus.sel,
            i_wb_data__ack   = dbus.ack,
            i_wb_data__err   = dbus.err,
            i_wb_data__dat_r = dbus.dat_r,
        )

    # Memory Mapping.
    @property
    def mem_map(self):
        # Default Memory Map.
        # In Coreblocks MMIO region is set to 0xe000_0000 - 0xffff_fffff by default configuration.
        # It can be changed with coreblocks `CoreConfiguration` dataclass.
        # Remaps `csr` to that region. Other segements can be arbitraily overwritten.
        return {
            "rom":      0x0000_0000,
            "sram":     0x0100_0000,
            "main_ram": 0x4000_0000,
            "csr":      0xe000_0000,
        }


    def set_reset_address(self, reset_address):
        self.reset_address = reset_address

    @staticmethod
    def elaborate(variant, reset_address, verilog_filename):
        cli_params = []
        cli_params.append("--output={}".format(verilog_filename))
        cli_params.append("--config={}".format(CPU_VARIANTS[variant]))
        cli_params.append("--reset-pc=0x{:x}".format(reset_address))

        data_mod = get_data_mod("cpu", "coreblocks")
        sdir = data_mod.data_location

        env = os.environ.copy()
        env.setdefault("PIPX_STANDALONE_PYTHON_RELEASE", "20250604")

        if data_mod.RUN_NATIVE:
            command = ["python3", os.path.join(sdir, "scripts", "gen_verilog.py")]
        else:
            command = ["pipx", "run", f"--python=3.{data_mod.PYTHON3_VERSION}", "--fetch-missing-python", os.path.join(sdir, "..", "gen_verilog_wrapper.py")]

        command += cli_params

        print(command)
        if subprocess.call(command):
            raise OSError("Unable to elaborate Coreblocks CPU, please check your coreblocks, Amaranth/Yosys, and requirements install")

    def do_finalize(self):
        assert hasattr(self, "reset_address")

        verilog_filename = os.path.join(self.platform.output_dir, "gateware", "core.v")
        self.elaborate(
            variant          = self.variant,
            reset_address    = self.reset_address,
            verilog_filename = verilog_filename)

        self.platform.add_source(verilog_filename)
        self.specials += Instance("top", **self.cpu_params)
