import os
import sys
try:
    import colorama
    # install escape sequence translation on Windows
    if os.getenv("COLORAMA", "") == "force":
        colorama.init(strip=False)
    else:
        colorama.init()
    _have_colorama = True
except ImportError:
    _have_colorama = False

from litex.gen.fhdl.structure import *
from litex.gen.fhdl.specials import Instance
from litex.gen.fhdl.module import Module
from litex.gen.genlib.cdc import *
from litex.gen.genlib.resetsync import AsyncResetSynchronizer
from litex.gen.genlib.io import *

from litex.build import tools


colors = []
if _have_colorama:
    colors += [
        ("^ERROR:.*$", colorama.Fore.RED + colorama.Style.BRIGHT +
         r"\g<0>" + colorama.Style.RESET_ALL),
        ("^CRITICAL WARNING:.*$", colorama.Fore.RED +
         r"\g<0>" + colorama.Style.RESET_ALL),
        ("^WARNING:.*$", colorama.Fore.YELLOW +
         r"\g<0>" + colorama.Style.RESET_ALL),
        ("^INFO:.*$", colorama.Fore.GREEN +
         r"\g<0>" + colorama.Style.RESET_ALL),
    ]


def settings(path, name=None, ver=None, first=None):
    if first == "version":
        if not ver:
            vers = tools.versions(path)
            ver = max(vers)

        full = os.path.join(path, str(ver), name)

    elif first == "name":
        path = os.path.join(path, name)

        if not ver:
            vers = tools.versions(path)
            ver = max(vers)

        full = os.path.join(path, str(ver))

    if not vers:
        raise OSError(
            "no version directory for Xilinx tools found in {}".format(
                path))

    search = [64, 32]
    if tools.arch_bits() == 32:
        search = [32]

    if sys.platform == "win32" or sys.platform == "cygwin":
        script_ext = "bat"
    else:
        script_ext = "sh"

    searched_in = []
    for b in search:
        settings = os.path.join(full, "settings{0}.{1}".format(b, script_ext))
        if os.path.exists(settings):
            return settings
        searched_in.append(settings)

    raise OSError(
        "no Xilinx tools settings file found.\n"
        "Looked in:\n"
        "   " +
        "\n   ".join(searched_in))


class XilinxMultiRegImpl(MultiRegImpl):
    def __init__(self, *args, **kwargs):
        MultiRegImpl.__init__(self, *args, **kwargs)
        for r in self.regs:
            r.attr.add("async_reg")
            r.attr.add("no_shreg_extract")


class XilinxMultiReg:
    @staticmethod
    def lower(dr):
        return XilinxMultiRegImpl(dr.i, dr.o, dr.odomain, dr.n)


class XilinxAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        if not hasattr(async_reset, "attr"):
            i, async_reset = async_reset, Signal()
            self.comb += async_reset.eq(i)
        rst_meta = Signal()
        self.specials += [
            Instance("FDPE", p_INIT=1, i_D=0, i_PRE=async_reset,
                i_CE=1, i_C=cd.clk, o_Q=rst_meta,
                attr={"async_reg", "ars_ff"}),
            Instance("FDPE", p_INIT=1, i_D=rst_meta, i_PRE=async_reset,
                i_CE=1, i_C=cd.clk, o_Q=cd.rst,
                attr={"async_reg", "ars_ff"})
        ]
        async_reset.attr.add("ars_false_path")


class XilinxAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return XilinxAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)


class XilinxDifferentialInputImpl(Module):
    def __init__(self, i_p, i_n, o):
        self.specials += Instance("IBUFDS", i_I=i_p, i_IB=i_n, o_O=o)


class XilinxDifferentialInput:
    @staticmethod
    def lower(dr):
        return XilinxDifferentialInputImpl(dr.i_p, dr.i_n, dr.o)


class XilinxDifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += Instance("OBUFDS", i_I=i, o_O=o_p, o_OB=o_n)


class XilinxDifferentialOutput:
    @staticmethod
    def lower(dr):
        return XilinxDifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)


class XilinxDDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += Instance("ODDR2",
                p_DDR_ALIGNMENT="NONE", p_INIT=0, p_SRTYPE="SYNC",
                i_C0=clk, i_C1=~clk, i_CE=1, i_S=0, i_R=0,
                i_D0=i1, i_D1=i2, o_Q=o,
        )


class XilinxDDROutput:
    @staticmethod
    def lower(dr):
        return XilinxDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)


xilinx_special_overrides = {
    MultiReg:               XilinxMultiReg,
    AsyncResetSynchronizer: XilinxAsyncResetSynchronizer,
    DifferentialInput:      XilinxDifferentialInput,
    DifferentialOutput:     XilinxDifferentialOutput,
    DDROutput:              XilinxDDROutput
}


class XilinxDDROutputImplS7(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += Instance("ODDR",
                p_DDR_CLK_EDGE="SAME_EDGE",
                i_C=clk, i_CE=1, i_S=0, i_R=0,
                i_D1=i1, i_D2=i2, o_Q=o,
        )


class XilinxDDROutputS7:
    @staticmethod
    def lower(dr):
        return XilinxDDROutputImplS7(dr.i1, dr.i2, dr.o, dr.clk)


xilinx_s7_special_overrides = {
    DDROutput:              XilinxDDROutputS7
}
