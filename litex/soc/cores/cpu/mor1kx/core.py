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

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["standard", "standard+fpu", "linux", "linux+fpu", "linux+smp", "linux+smp+fpu"]

# Mor1kx -------------------------------------------------------------------------------------------

class MOR1KX(CPU):
    category             = "softcore"
    family               = "or1k"
    name                 = "mor1kx"
    human_name           = "MOR1KX"
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
            p_FEATURE_INSTRUCTIONCACHE  = "ENABLED",
            p_OPTION_ICACHE_BLOCK_WIDTH = 4,
            p_OPTION_ICACHE_SET_WIDTH   = 8,
            p_OPTION_ICACHE_WAYS        = 1,
            p_OPTION_ICACHE_LIMIT_WIDTH = 31,
            p_FEATURE_DATACACHE         = "ENABLED",
            p_OPTION_DCACHE_BLOCK_WIDTH = 4,
            p_OPTION_DCACHE_SET_WIDTH   = 8,
            p_OPTION_DCACHE_WAYS        = 1,
            p_OPTION_DCACHE_LIMIT_WIDTH = 31,
            p_FEATURE_TIMER      = "NONE",
            p_OPTION_PIC_TRIGGER = "LEVEL",
            p_FEATURE_SYSCALL    = "NONE",
            p_FEATURE_TRAP       = "NONE",
            p_FEATURE_RANGE      = "NONE",
            p_FEATURE_OVERFLOW   = "NONE",
            p_FEATURE_ADDC       = "ENABLED",
            p_FEATURE_CMOV       = "ENABLED",
            p_FEATURE_FFL1       = "ENABLED",
            p_OPTION_CPU0        = "CAPPUCCINO",
            p_IBUS_WB_TYPE       = "B3_REGISTERED_FEEDBACK",
            p_DBUS_WB_TYPE       = "B3_REGISTERED_FEEDBACK",
        )

        # SMP parameters.
        if "smp" in variant:
           cpu_args.update(p_OPTION_RF_NUM_SHADOW_GPR=1)

        # FPU parameters.
        if "fpu" in variant:
            cpu_args.update(p_FEATURE_FPU = "ENABLED")

        # Linux parameters
        if "linux" in variant:
            cpu_args.update(
                # Linux needs the memory management units.
                p_FEATURE_IMMU  = "ENABLED",
                p_FEATURE_DMMU  = "ENABLED",
                # FIXME: Currently we need the or1k timer when we should be
                # using the litex timer.
                p_FEATURE_TIMER = "ENABLED",
                p_FEATURE_ROR = "ENABLED",
                p_FEATURE_EXT = "ENABLED",
            )
            # Linux variant requires specific Memory Mapping.
            self.mem_map = self.mem_map_linux
            # FIXME: Check if these are needed?
            use_defaults = (
                "p_FEATURE_SYSCALL",
                "p_FEATURE_TRAP",
                "p_FEATURE_RANGE",
                "p_FEATURE_OVERFLOW",
            )
            for to_remove in use_defaults:
                del cpu_args[to_remove]

        self.cpu_params = dict(
            **cpu_args,

            # Clk / Rst.
            i_clk = ClockSignal("sys"),
            i_rst = ResetSignal("sys") | self.reset,

            # IRQ.
            i_irq_i=self.interrupt,

            # IBus.
            o_iwbm_adr_o = Cat(Signal(2), ibus.adr),
            o_iwbm_dat_o = ibus.dat_w,
            o_iwbm_sel_o = ibus.sel,
            o_iwbm_cyc_o = ibus.cyc,
            o_iwbm_stb_o = ibus.stb,
            o_iwbm_we_o  = ibus.we,
            o_iwbm_cti_o = ibus.cti,
            o_iwbm_bte_o = ibus.bte,
            i_iwbm_dat_i = ibus.dat_r,
            i_iwbm_ack_i = ibus.ack,
            i_iwbm_err_i = ibus.err,
            i_iwbm_rty_i = 0,

            # DBus.
            o_dwbm_adr_o = Cat(Signal(2), dbus.adr),
            o_dwbm_dat_o = dbus.dat_w,
            o_dwbm_sel_o = dbus.sel,
            o_dwbm_cyc_o = dbus.cyc,
            o_dwbm_stb_o = dbus.stb,
            o_dwbm_we_o  = dbus.we,
            o_dwbm_cti_o = dbus.cti,
            o_dwbm_bte_o = dbus.bte,
            i_dwbm_dat_i = dbus.dat_r,
            i_dwbm_ack_i = dbus.ack,
            i_dwbm_err_i = dbus.err,
            i_dwbm_rty_i = 0,
        )

        # Add Verilog sources.
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(p_OPTION_RESET_PC=reset_address)

    @staticmethod
    def add_sources(platform):
        vdir = os.path.join(
            get_data_mod("cpu", "mor1kx").data_location,
            "rtl", "verilog")
        platform.add_source_dir(vdir)
        platform.add_verilog_include_path(vdir)

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("mor1kx", **self.cpu_params)
