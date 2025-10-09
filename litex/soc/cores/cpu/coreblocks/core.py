#
# This file is part of LiteX.
#
# Copyright (c) 2023-2025 Piotr Wegrzyn (Coreforge Foundation) <piotro@piotro.eu>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess

from migen import *

from litex import get_data_mod
from litex.build.xilinx.vivado import XilinxVivadoToolchain
from litex.soc.cores.cpu import CPU, CPU_GCC_TRIPLE_RISCV32
from litex.soc.integration.soc import SoCRegion
from litex.soc.interconnect import wishbone

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = {
    "standard":     "basic",
    "small_linux":  "small_linux",
    "full":         "full",
}

LINUX_CAPABLE_VARIANTS = [
    "small_linux",
    "full",
]

# GCC Flags ----------------------------------------------------------------------------------------

GCC_FLAGS = {
    "standard":         "-march=rv32i2p0_m                                    -mabi=ilp32 ",
    "small_linux":      "-march=rv32i2p0_ma                                   -mabi=ilp32 ",
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

    # Memory Mapping constraints.
    @property
    def mem_map(self):
        # In Coreblocks MMIO region is set to 0xe000_0000 - 0xffff_fffff by default configuration.
        # It can be changed with coreblocks `CoreConfiguration` dataclass.
        # Maps `csr` to that region, with offset left at start for automatic I/O space allocations.
        # Other segments can be arbitrarily chosen.
        mem_map = {
            "csr":          0xe800_0000, # fixed address required by LiteX
        }

        if self.variant in LINUX_CAPABLE_VARIANTS:
            mem_map |= {
                "clint":    0xe100_0000, # fixed in CoreSoCks
            }

        return mem_map

    def add_soc_components(self, soc):
        if "clint" in soc.mem_map:
            soc.bus.add_region("clint", SoCRegion(origin=soc.mem_map.get("clint"), size=0xC_0000, cached=False, linker=False))

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address

    @staticmethod
    def elaborate(platform, variant, reset_address, verilog_filename):
        cli_params = []
        cli_params.append("--output={}".format(verilog_filename))
        cli_params.append("--config={}".format(CPU_VARIANTS[variant]))
        cli_params.append("--reset-pc=0x{:x}".format(reset_address))

        if variant in LINUX_CAPABLE_VARIANTS:
            # Adds CoreSoCks wrapper around the core that adds extra peripherals (like CLINT) for full OS support
            cli_params.append("--with-socks")

        if isinstance(platform.toolchain, XilinxVivadoToolchain):
            cli_params.append("--enable-vivado-hacks")

        data_mod = get_data_mod("cpu", "coreblocks")
        sdir = data_mod.data_location

        command = (["python3", os.path.join(sdir, "scripts", "gen_verilog.py")] if data_mod.RUN_NATIVE else
            ["pipx", "run", f"--python=3.{data_mod.PYTHON3_VERSION}", "--fetch-missing-python", os.path.join(sdir, "..", "gen_verilog_wrapper.py")])

        command += cli_params

        print(command)
        if subprocess.call(command):
            raise OSError("Unable to elaborate Coreblocks CPU, please check your coreblocks, Amaranth/Yosys, and requirements install")

    def do_finalize(self):
        assert hasattr(self, "reset_address")

        verilog_filename = os.path.join(self.platform.output_dir, "gateware", "core.v")
        self.elaborate(
            platform         = self.platform,
            variant          = self.variant,
            reset_address    = self.reset_address,
            verilog_filename = verilog_filename)

        self.platform.add_source(verilog_filename)
        self.specials += Instance("top", **self.cpu_params)
