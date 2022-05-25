#
# This file is part of LiteX.
#
# Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017-2019 Tim 'mithro' Ansell <me@mith.ro>
# Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2019 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *

from litex import get_data_mod
from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU

# Variants -----------------------------------------------------------------------------------------

CPU_VARIANTS = ["minimal", "lite", "standard"]

# LM32 ---------------------------------------------------------------------------------------------

class LM32(CPU):
    category             = "softcore"
    family               = "lm32"
    name                 = "lm32"
    human_name           = "LM32"
    variants             = CPU_VARIANTS
    data_width           = 32
    endianness           = "big"
    gcc_triple           = "lm32-elf"
    linker_output_format = "elf32-lm32"
    nop                  = "nop"
    io_regions           = {0x8000_0000: 0x8000_0000} # origin, length

    # GCC Flags.
    @property
    def gcc_flags(self):
        flags =  "-mbarrel-shift-enabled "
        flags += "-mmultiply-enabled "
        flags += "-mdivide-enabled "
        flags += "-msign-extend-enabled "
        flags += "-D__lm32__ "
        return flags

    def __init__(self, platform, variant="standard"):
        self.platform     = platform
        self.variant      = variant
        self.reset        = Signal()
        self.ibus         = ibus = wishbone.Interface()
        self.dbus         = dbus = wishbone.Interface()
        self.interrupt    = Signal(32)
        self.periph_buses = [ibus, dbus] # Peripheral buses (Connected to main SoC's bus).
        self.memory_buses = []           # Memory buses (Connected directly to LiteDRAM).

        # # #

        self.cpu_params = dict(
            # Clk / Rst.
            i_clk_i = ClockSignal(),
            i_rst_i = ResetSignal() | self.reset,

            # IRQ.
            i_interrupt=self.interrupt,

            # IBus.
            o_I_ADR_O = Cat(Signal(2), ibus.adr),
            o_I_DAT_O = ibus.dat_w,
            o_I_SEL_O = ibus.sel,
            o_I_CYC_O = ibus.cyc,
            o_I_STB_O = ibus.stb,
            o_I_WE_O  = ibus.we,
            o_I_CTI_O = ibus.cti,
            o_I_BTE_O = ibus.bte,
            i_I_DAT_I = ibus.dat_r,
            i_I_ACK_I = ibus.ack,
            i_I_ERR_I = ibus.err,
            i_I_RTY_I = 0,

            # DBus.
            o_D_ADR_O = Cat(Signal(2), dbus.adr),
            o_D_DAT_O = dbus.dat_w,
            o_D_SEL_O = dbus.sel,
            o_D_CYC_O = dbus.cyc,
            o_D_STB_O = dbus.stb,
            o_D_WE_O  = dbus.we,
            o_D_CTI_O = dbus.cti,
            o_D_BTE_O = dbus.bte,
            i_D_DAT_I = dbus.dat_r,
            i_D_ACK_I = dbus.ack,
            i_D_ERR_I = dbus.err,
            i_D_RTY_I = 0,
        )

        # Add Verilog sources.
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        self.reset_address = reset_address
        self.cpu_params.update(
            p_eba_reset=Instance.PreformattedParam("32'h{:08x}".format(reset_address))
        )

    @staticmethod
    def add_sources(platform, variant):
        vdir = get_data_mod("cpu", "lm32").data_location
        platform.add_sources(os.path.join(vdir, "rtl"),
            "lm32_cpu.v",
            "lm32_instruction_unit.v",
            "lm32_decoder.v",
            "lm32_load_store_unit.v",
            "lm32_adder.v",
            "lm32_addsub.v",
            "lm32_logic_op.v",
            "lm32_shifter.v",
            "lm32_multiplier.v",
            "lm32_mc_arithmetic.v",
            "lm32_interrupt.v",
            "lm32_ram.v",
            "lm32_dp_ram.v",
            "lm32_icache.v",
            "lm32_dcache.v",
            "lm32_debug.v",
            "lm32_itlb.v",
            "lm32_dtlb.v")
        platform.add_verilog_include_path(os.path.join(vdir, "rtl"))
        cdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "verilog")
        if variant == "minimal":
            platform.add_verilog_include_path(os.path.join(cdir, "config_minimal"))
        elif variant == "lite":
            platform.add_verilog_include_path(os.path.join(cdir, "config_lite"))
        elif variant == "standard":
            platform.add_verilog_include_path(os.path.join(cdir, "config"))
        else:
            raise TypeError("Unknown variant {}".format(variant))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("lm32_cpu", **self.cpu_params)
