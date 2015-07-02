import os
import sys
from distutils.version import StrictVersion

from migen.fhdl.std import *
from migen.fhdl.specials import SynthesisDirective
from migen.genlib.cdc import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.io import *
from mibuild import tools


def settings(path, ver=None, sub=None):
    vers = list(tools.versions(path))
    if ver is None:
        ver = max(vers)
    else:
        ver = StrictVersion(ver)
        assert ver in vers

    full = os.path.join(path, str(ver))
    if sub:
        full = os.path.join(full, sub)

    search = [64, 32]
    if tools.arch_bits() == 32:
        search.reverse()

    if sys.platform == "win32" or sys.platform == "cygwin":
        script_ext = "bat"
    else:
        script_ext = "sh"

    for b in search:
        settings = os.path.join(full, "settings{0}.{1}".format(b, script_ext))
        if os.path.exists(settings):
            return settings

    raise OSError("no settings file found")


class XilinxNoRetimingImpl(Module):
    def __init__(self, reg):
        self.specials += SynthesisDirective("attribute register_balancing of {r} is no", r=reg)


class XilinxNoRetiming:
    @staticmethod
    def lower(dr):
        return XilinxNoRetimingImpl(dr.reg)


class XilinxMultiRegImpl(MultiRegImpl):
    def __init__(self, *args, **kwargs):
        MultiRegImpl.__init__(self, *args, **kwargs)
        self.specials += [SynthesisDirective("attribute shreg_extract of {r} is no", r=r)
            for r in self.regs]


class XilinxMultiReg:
    @staticmethod
    def lower(dr):
        return XilinxMultiRegImpl(dr.i, dr.o, dr.odomain, dr.n)


class XilinxAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("FDPE", p_INIT=1, i_D=0, i_PRE=async_reset,
                i_CE=1, i_C=cd.clk, o_Q=rst1),
            Instance("FDPE", p_INIT=1, i_D=rst1, i_PRE=async_reset,
                i_CE=1, i_C=cd.clk, o_Q=cd.rst)
        ]


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
    NoRetiming:             XilinxNoRetiming,
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
