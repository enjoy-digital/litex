import os

from litex.gen import *

from litex.soc.interconnect import wishbone


class LM32(Module):
    def __init__(self, platform, eba_reset):
        self.ibus = i = wishbone.Interface()
        self.dbus = d = wishbone.Interface()
        self.interrupt = Signal(32)

        # # #

        i_adr_o = Signal(32)
        d_adr_o = Signal(32)
        self.specials += Instance("lm32_cpu",
            p_eba_reset=Instance.PreformattedParam("32'h{:08x}".format(eba_reset)),

            i_clk_i=ClockSignal(),
            i_rst_i=ResetSignal(),

            i_interrupt=self.interrupt,

            o_I_ADR_O=i_adr_o,
            o_I_DAT_O=i.dat_w,
            o_I_SEL_O=i.sel,
            o_I_CYC_O=i.cyc,
            o_I_STB_O=i.stb,
            o_I_WE_O=i.we,
            o_I_CTI_O=i.cti,
            o_I_BTE_O=i.bte,
            i_I_DAT_I=i.dat_r,
            i_I_ACK_I=i.ack,
            i_I_ERR_I=i.err,
            i_I_RTY_I=0,

            o_D_ADR_O=d_adr_o,
            o_D_DAT_O=d.dat_w,
            o_D_SEL_O=d.sel,
            o_D_CYC_O=d.cyc,
            o_D_STB_O=d.stb,
            o_D_WE_O=d.we,
            o_D_CTI_O=d.cti,
            o_D_BTE_O=d.bte,
            i_D_DAT_I=d.dat_r,
            i_D_ACK_I=d.ack,
            i_D_ERR_I=d.err,
            i_D_RTY_I=0)

        self.comb += [
            self.ibus.adr.eq(i_adr_o[2:]),
            self.dbus.adr.eq(d_adr_o[2:])
        ]

        # add verilog sources
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
        platform.add_verilog_include_path(vdir)
