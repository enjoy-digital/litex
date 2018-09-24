import os

from migen import *

from litex.soc.interconnect import wishbone


class MOR1KX(Module):
    name = "or1k"
    endianness = "big"
    gcc_triple = "or1k-elf"
    gcc_flags = "-mhard-mul -mhard-div -mror"
    clang_triple = "or1k-linux"
    clang_flags = "-mhard-mul -mhard-div -mror -mffl1 -maddc"
    linker_output_format = "elf32-or1k"

    def __init__(self, platform, reset_pc, variant=None):
        assert variant in (None, "linux"), "Unsupported variant %s" % variant
        self.reset = Signal()
        self.ibus = i = wishbone.Interface()
        self.dbus = d = wishbone.Interface()
        self.interrupt = Signal(32)

        # # #

        cpu_args = dict(
            p_FEATURE_INSTRUCTIONCACHE="ENABLED",
            p_OPTION_ICACHE_BLOCK_WIDTH=4,
            p_OPTION_ICACHE_SET_WIDTH=8,
            p_OPTION_ICACHE_WAYS=1,
            p_OPTION_ICACHE_LIMIT_WIDTH=31,
            p_FEATURE_DATACACHE="ENABLED",
            p_OPTION_DCACHE_BLOCK_WIDTH=4,
            p_OPTION_DCACHE_SET_WIDTH=8,
            p_OPTION_DCACHE_WAYS=1,
            p_OPTION_DCACHE_LIMIT_WIDTH=31,
            p_FEATURE_TIMER="NONE",
            p_OPTION_PIC_TRIGGER="LEVEL",
            p_FEATURE_SYSCALL="NONE",
            p_FEATURE_TRAP="NONE",
            p_FEATURE_RANGE="NONE",
            p_FEATURE_OVERFLOW="NONE",
            p_FEATURE_ADDC="ENABLED",
            p_FEATURE_CMOV="ENABLED",
            p_FEATURE_FFL1="ENABLED",
            p_OPTION_CPU0="CAPPUCCINO",
            p_OPTION_RESET_PC=reset_pc,
            p_IBUS_WB_TYPE="B3_REGISTERED_FEEDBACK",
            p_DBUS_WB_TYPE="B3_REGISTERED_FEEDBACK",
        )

        if variant == None:
            # Use the default configuration
            pass
        elif variant == "linux":
            cpu_args.update(dict(
                # Linux needs the memory management units.
                p_FEATURE_IMMU="ENABLED",
                p_FEATURE_DMMU="ENABLED",
                # FIXME: Currently we need the or1k timer when we should be
                # using the litex timer.
                p_FEATURE_TIMER="ENABLED",
            ))
            # FIXME: Check if these are needed?
            use_defaults = (
                "p_FEATURE_SYSCALL", "p_FEATURE_TRAP", "p_FEATURE_RANGE",
                "p_FEATURE_OVERFLOW",
            )
            for to_remove in use_defaults:
                del cpu_args[to_remove]

        else:
            assert False, "Unsupported variant %s" % variant

        i_adr_o = Signal(32)
        d_adr_o = Signal(32)
        self.specials += Instance("mor1kx",
            **cpu_args,

            i_clk=ClockSignal(),
            i_rst=ResetSignal() | self.reset,

            i_irq_i=self.interrupt,

            o_iwbm_adr_o=i_adr_o,
            o_iwbm_dat_o=i.dat_w,
            o_iwbm_sel_o=i.sel,
            o_iwbm_cyc_o=i.cyc,
            o_iwbm_stb_o=i.stb,
            o_iwbm_we_o=i.we,
            o_iwbm_cti_o=i.cti,
            o_iwbm_bte_o=i.bte,
            i_iwbm_dat_i=i.dat_r,
            i_iwbm_ack_i=i.ack,
            i_iwbm_err_i=i.err,
            i_iwbm_rty_i=0,

            o_dwbm_adr_o=d_adr_o,
            o_dwbm_dat_o=d.dat_w,
            o_dwbm_sel_o=d.sel,
            o_dwbm_cyc_o=d.cyc,
            o_dwbm_stb_o=d.stb,
            o_dwbm_we_o=d.we,
            o_dwbm_cti_o=d.cti,
            o_dwbm_bte_o=d.bte,
            i_dwbm_dat_i=d.dat_r,
            i_dwbm_ack_i=d.ack,
            i_dwbm_err_i=d.err,
            i_dwbm_rty_i=0)

        self.comb += [
            self.ibus.adr.eq(i_adr_o[2:]),
            self.dbus.adr.eq(d_adr_o[2:])
        ]

        # add verilog sources
        self.add_sources(platform)

    @staticmethod
    def add_sources(platform):
        vdir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            "verilog", "rtl", "verilog")
        platform.add_source_dir(vdir)
