# This file is Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2017-2019 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2019 Mateusz Holenko <mholenko@antmicro.com>
# License: BSD

import os

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.cores.cpu import CPU

CPU_VARIANTS = ["minimal", "lite", "standard"]


class LM32(CPU):
    name                 = "lm32"
    data_width           = 32
    endianness           = "big"
    gcc_triple           = "lm32-elf"
    linker_output_format = "elf32-lm32"
    io_regions           = {0x80000000: 0x80000000} # origin, length

    @property
    def gcc_flags(self):
        flags =  "-mbarrel-shift-enabled "
        flags += "-mmultiply-enabled "
        flags += "-mdivide-enabled "
        flags += "-msign-extend-enabled "
        flags += "-D__lm32__ "
        return flags

    def __init__(self, platform, variant="standard"):
        assert variant in CPU_VARIANTS, "Unsupported variant %s" % variant
        self.platform  = platform
        self.variant   = variant
        self.reset     = Signal()
        self.ibus      = i = wishbone.Interface()
        self.dbus      = d = wishbone.Interface()
        self.interrupt = Signal(32)
        self.buses     = [i, d]

        # # #

        i_adr_o = Signal(32)
        d_adr_o = Signal(32)
        self.cpu_params = dict(
            i_clk_i=ClockSignal(),
            i_rst_i=ResetSignal() | self.reset,

            i_interrupt=self.interrupt,

            o_I_ADR_O = i_adr_o,
            o_I_DAT_O = i.dat_w,
            o_I_SEL_O = i.sel,
            o_I_CYC_O = i.cyc,
            o_I_STB_O = i.stb,
            o_I_WE_O  = i.we,
            o_I_CTI_O = i.cti,
            o_I_BTE_O = i.bte,
            i_I_DAT_I = i.dat_r,
            i_I_ACK_I = i.ack,
            i_I_ERR_I = i.err,
            i_I_RTY_I = 0,

            o_D_ADR_O = d_adr_o,
            o_D_DAT_O = d.dat_w,
            o_D_SEL_O = d.sel,
            o_D_CYC_O = d.cyc,
            o_D_STB_O = d.stb,
            o_D_WE_O  = d.we,
            o_D_CTI_O = d.cti,
            o_D_BTE_O = d.bte,
            i_D_DAT_I = d.dat_r,
            i_D_ACK_I = d.ack,
            i_D_ERR_I = d.err,
            i_D_RTY_I = 0,
        )

        self.comb += [
            self.ibus.adr.eq(i_adr_o[2:]),
            self.dbus.adr.eq(d_adr_o[2:])
        ]

        # add verilog sources
        self.add_sources(platform, variant)

    def set_reset_address(self, reset_address):
        assert not hasattr(self, "reset_address")
        self.reset_address = reset_address
        self.cpu_params.update(
            p_eba_reset=Instance.PreformattedParam("32'h{:08x}".format(reset_address))
        )

    @staticmethod
    def add_sources(platform, variant):
        vdir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "verilog")
        platform.add_sources(os.path.join(vdir, "submodule", "rtl"),
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
        platform.add_verilog_include_path(os.path.join(vdir, "submodule", "rtl"))
        if variant == "minimal":
            platform.add_verilog_include_path(os.path.join(vdir, "config_minimal"))
        elif variant == "lite":
            platform.add_verilog_include_path(os.path.join(vdir, "config_lite"))
        elif variant == "standard":
            platform.add_verilog_include_path(os.path.join(vdir, "config"))
        else:
            raise TypeError("Unknown variant {}".format(variant))

    def do_finalize(self):
        assert hasattr(self, "reset_address")
        self.specials += Instance("lm32_cpu", **self.cpu_params)
