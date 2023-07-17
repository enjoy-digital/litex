#
# This file is part of LiteX.
#
# Copyright (c) 2014-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018-2017 Tim 'mithro' Ansell <me@mith.ro>
# Copyright (c) 2019 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex.gen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard", "linux", "linux+smp"]

# Mor1kx -------------------------------------------------------------------------------------------

class Marocchino(CPU):
    category             = "softcore"
    family               = "or1k"
    name                 = "marocchino"
    human_name           = "Marocchino"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "big"
    gcc_triple           = ("or1k-elf", "or1k-linux")
    clang_triple         = "or1k-linux"
    linker_output_format = "elf32-or1k"
    nop                  = "l.nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # Origin, Length.

    # Memory Mapping for Linux variant.
    @property
    def mem_map_linux(self):
        # Mainline Linux OpenRISC arch code requires Linux kernel to be loaded at the physical
        # address of 0x0. As we are running Linux from the MAIN_RAM region - move it to satisfy
        # that requirement.
        return {
            "main_ram" : 0x0000_0000,
            "rom"      : 0x1000_0000,
            "sram"     : 0x5000_0000,
            "csr"      : 0xe000_0000,
        }

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  "-mhard-mul "
        flags += "-mhard-div "
        flags += "-mcmov "
        flags += "-D__mor1kx__ "

        if "linux" in self.variant:
            flags += "-mror "
            flags += "-msext "

        return flags

    # Clang Flags.
    @property
    def clang_flags(self):
        flags =  "-mhard-mul "
        flags += "-mhard-div "
        flags += "-mffl1 "
        flags += "-maddc "
        flags += "-D__mor1kx__ "
        return flags

    # Reserved Interrupts.
    @property
    def reserved_interrupts(self):
        return {"nmi": 0}

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(32)
        self.ibus         = ibus = wishbone.Interface()
        self.dbus         = dbus = wishbone.Interface()
        self.periph_buses = [ibus, dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []           # Memory buses (Connected directly to LiteDRAM).

        # # #

        # CPU parameters.
        cpu_args = dict(
            p_OPTION_ICACHE_BLOCK_WIDTH = 4,
            p_OPTION_ICACHE_SET_WIDTH   = 8,
            p_OPTION_ICACHE_WAYS        = 1,
            p_OPTION_ICACHE_LIMIT_WIDTH = 31,
            p_OPTION_DCACHE_BLOCK_WIDTH = 4,
            p_OPTION_DCACHE_SET_WIDTH   = 8,
            p_OPTION_DCACHE_WAYS        = 1,
            p_OPTION_DCACHE_LIMIT_WIDTH = 31,
            p_OPTION_PIC_TRIGGER = "LEVEL",
        )

        # SMP parameters.
        if "smp" in variant:
           cpu_args.update(p_OPTION_RF_NUM_SHADOW_GPR=1)

        # Linux parameters
        if "linux" in variant:
            # Linux variant requires specific Memory Mapping.
            self.mem_map = self.mem_map_linux

        self.cpu_params = dict(
            **cpu_args,

            # Clk / Rst.
            i_wb_clk = ClockSignal("sys"),
            i_wb_rst = ResetSignal("sys") | self.reset,
            i_cpu_clk = ClockSignal("sys"),
            i_cpu_rst = ResetSignal("sys") | self.reset,

            # IBus.
            o_iwbm_adr_o = Cat(Signal(2), ibus.adr),
            o_iwbm_stb_o = ibus.stb,
            o_iwbm_cyc_o = ibus.cyc,
            o_iwbm_sel_o = ibus.sel,
            o_iwbm_we_o  = ibus.we,
            o_iwbm_cti_o = ibus.cti,
            o_iwbm_bte_o = ibus.bte,
            o_iwbm_dat_o = ibus.dat_w,
            i_iwbm_err_i = ibus.err,
            i_iwbm_ack_i = ibus.ack,
            i_iwbm_dat_i = ibus.dat_r,
            i_iwbm_rty_i = 0,

            # DBus.
            o_dwbm_adr_o = Cat(Signal(2), dbus.adr),
            o_dwbm_stb_o = dbus.stb,
            o_dwbm_cyc_o = dbus.cyc,
            o_dwbm_sel_o = dbus.sel,
            o_dwbm_we_o  = dbus.we,
            o_dwbm_cti_o = dbus.cti,
            o_dwbm_bte_o = dbus.bte,
            o_dwbm_dat_o = dbus.dat_w,
            i_dwbm_ack_i = dbus.ack,
            i_dwbm_err_i = dbus.err,
            i_dwbm_dat_i = dbus.dat_r,
            i_dwbm_rty_i = 0,

            # IRQ.
            i_irq_i=self.interrupt,
        )

        # Add Verilog sources.
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(p_OPTION_RESET_PC=reset_address)

    @staticmethod
    def add_sources(platform):
        vdir = os.path.join(
            get_data_mod("cpu", "marocchino").data_location,
            "rtl", "verilog")
        platform.add_source_dir(vdir)
        platform.add_verilog_include_path(vdir)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("or1k_marocchino_top", **self.cpu_params)
