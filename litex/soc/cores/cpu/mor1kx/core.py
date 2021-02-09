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

CPU_VARIANTS = ["standard", "standard+fpu", "linux", "linux+fpu",
                "linux+smp", "linux+smp+fpu"]


class MOR1KX(CPU):
    name                 = "mor1kx"
    human_name           = "MOR1KX"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "big"
    gcc_triple           = "or1k-elf"
    clang_triple         = "or1k-linux"
    linker_output_format = "elf32-or1k"
    nop                  = "l.nop"
    io_regions           = {0x80000000: 0x80000000} # origin, length

    @property
    def mem_map_linux(self):
        # Mainline Linux OpenRISC arch code requires Linux kernel to be loaded at the physical
        # address of 0x0. As we are running Linux from the MAIN_RAM region - move it to satisfy
        # that requirement.
        return {
            "main_ram" : 0x00000000,
            "rom"      : 0x10000000,
            "sram"     : 0x50000000,
            "csr"      : 0xe0000000,
        }

    @property
    def gcc_triple(self):
        return "or1k-elf"

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

    @property
    def clang_flags(self):
        flags =  "-mhard-mul "
        flags += "-mhard-div "
        flags += "-mffl1 "
        flags += "-maddc "
        flags += "-D__mor1kx__ "
        return flags

    @property
    def reserved_interrupts(self):
        return {"nmi": 0}

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.interrupt    = Signal(32)
        self.ibus         = i = wishbone.Interface()
        self.dbus         = d = wishbone.Interface()
        self.periph_buses = [i, d]
        self.memory_buses = []


        if "linux" in variant:
            self.mem_map = self.mem_map_linux

        # # #

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
            p_FEATURE_TIMER             = "NONE",
            p_OPTION_PIC_TRIGGER        = "LEVEL",
            p_FEATURE_SYSCALL           = "NONE",
            p_FEATURE_TRAP              = "NONE",
            p_FEATURE_RANGE             = "NONE",
            p_FEATURE_OVERFLOW          = "NONE",
            p_FEATURE_ADDC              = "ENABLED",
            p_FEATURE_CMOV              = "ENABLED",
            p_FEATURE_FFL1              = "ENABLED",
            p_OPTION_CPU0               = "CAPPUCCINO",
            p_IBUS_WB_TYPE              = "B3_REGISTERED_FEEDBACK",
            p_DBUS_WB_TYPE              = "B3_REGISTERED_FEEDBACK",
        )

        if "smp" in variant:
           cpu_args.update(
               p_OPTION_RF_NUM_SHADOW_GPR = 1,
           )

        if "fpu" in variant:
            cpu_args.update(
                p_FEATURE_FPU = "ENABLED",
            )

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
            # FIXME: Check if these are needed?
            use_defaults = (
                "p_FEATURE_SYSCALL",
                "p_FEATURE_TRAP",
                "p_FEATURE_RANGE",
                "p_FEATURE_OVERFLOW",
            )
            for to_remove in use_defaults:
                del cpu_args[to_remove]

        i_adr_o = Signal(32)
        d_adr_o = Signal(32)
        self.cpu_params = dict(
            **cpu_args,

            i_clk=ClockSignal(),
            i_rst=ResetSignal() | self.reset,

            i_irq_i=self.interrupt,

            o_iwbm_adr_o = i_adr_o,
            o_iwbm_dat_o = i.dat_w,
            o_iwbm_sel_o = i.sel,
            o_iwbm_cyc_o = i.cyc,
            o_iwbm_stb_o = i.stb,
            o_iwbm_we_o  = i.we,
            o_iwbm_cti_o = i.cti,
            o_iwbm_bte_o = i.bte,
            i_iwbm_dat_i = i.dat_r,
            i_iwbm_ack_i = i.ack,
            i_iwbm_err_i = i.err,
            i_iwbm_rty_i = 0,

            o_dwbm_adr_o = d_adr_o,
            o_dwbm_dat_o = d.dat_w,
            o_dwbm_sel_o = d.sel,
            o_dwbm_cyc_o = d.cyc,
            o_dwbm_stb_o = d.stb,
            o_dwbm_we_o  = d.we,
            o_dwbm_cti_o = d.cti,
            o_dwbm_bte_o = d.bte,
            i_dwbm_dat_i = d.dat_r,
            i_dwbm_ack_i = d.ack,
            i_dwbm_err_i = d.err,
            i_dwbm_rty_i = 0,
        )

        self.comb += [
            self.ibus.adr.eq(i_adr_o[2:]),
            self.dbus.adr.eq(d_adr_o[2:])
        ]

        # add verilog sources
        self.add_sources(platform)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
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
