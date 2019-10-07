# This file is Copyright (c) 2014-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2014-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2016-2018 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2015 William D. Jones <thor0505@comcast.net>
# License: BSD

import os
import sys
import subprocess
try:
    import colorama
    colorama.init()  # install escape sequence translation on Windows
    _have_colorama = True
except ImportError:
    _have_colorama = False

from migen.fhdl.structure import *
from migen.fhdl.specials import Instance
from migen.fhdl.module import Module
from migen.genlib.cdc import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.io import *

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


def settings(path, ver=None, sub=None):
    if ver is None:
        vers = list(tools.versions(path))
        if not vers:
            raise OSError("no version directory for Xilinx tools found in "
                          + path)
        ver = max(vers)

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

    raise OSError("no Xilinx tools settings file found")


class XilinxMultiRegImpl(MultiRegImpl):
    def __init__(self, *args, **kwargs):
        MultiRegImpl.__init__(self, *args, **kwargs)
        i = self.i
        if not hasattr(i, "attr"):
            i0, i = i, Signal()
            self.comb += i.eq(i0)
        self.regs[0].attr.add("mr_ff")
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
            Instance("FDPE",
                p_INIT=1, i_D=0, i_PRE=async_reset,
                i_CE=1, i_C=cd.clk, o_Q=rst_meta,
                attr={"async_reg", "ars_ff1"}),
            Instance("FDPE", p_INIT=1,
                i_D=rst_meta, i_PRE=async_reset,
                i_CE=1, i_C=cd.clk, o_Q=cd.rst,
                attr={"async_reg", "ars_ff2"})
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


xilinx_special_overrides = {
    MultiReg:               XilinxMultiReg,
    AsyncResetSynchronizer: XilinxAsyncResetSynchronizer,
    DifferentialInput:      XilinxDifferentialInput,
    DifferentialOutput:     XilinxDifferentialOutput
}


class XilinxDDROutputImplS6(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += Instance("ODDR2",
            p_DDR_ALIGNMENT="C0", p_INIT=0, p_SRTYPE="ASYNC",
            i_C0=clk, i_C1=~clk, i_CE=1, i_S=0, i_R=0,
            i_D0=i1, i_D1=i2, o_Q=o,
        )


class XilinxDDROutputS6:
    @staticmethod
    def lower(dr):
        return XilinxDDROutputImplS6(dr.i1, dr.i2, dr.o, dr.clk)


xilinx_s6_special_overrides = {
    DDROutput:              XilinxDDROutputS6
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


class XilinxDDRInputImplS7(Module):
    def __init__(self, i, o1, o2, clk):
        self.specials += Instance("IDDR",
            p_DDR_CLK_EDGE="SAME_EDGE",
            i_C=clk, i_CE=1, i_S=0, i_R=0,
            i_D=i, o_Q1=o1, o_Q2=o2,
        )


class XilinxDDRInputS7:
    @staticmethod
    def lower(dr):
        return XilinxDDRInputImplS7(dr.i, dr.o1, dr.o2, dr.clk)


xilinx_s7_special_overrides = {
    DDROutput:              XilinxDDROutputS7,
    DDRInput:               XilinxDDRInputS7
}


class XilinxDDROutputImplKU(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += Instance("ODDRE1",
            i_C=clk, i_SR=0,
            i_D1=i1, i_D2=i2, o_Q=o,
        )


class XilinxDDROutputKU:
    @staticmethod
    def lower(dr):
        return XilinxDDROutputImplKU(dr.i1, dr.i2, dr.o, dr.clk)


class XilinxDDRInputImplKU(Module):
    def __init__(self, i, o1, o2, clk):
        self.specials += Instance("IDDRE1",
            p_DDR_CLK_EDGE="SAME_EDGE_PIPELINED",
            p_IS_C_INVERTED=0,
            p_IS_CB_INVERTED=1,
            i_D=i,
            o_Q1=o1, o_Q2=o2,
            i_C=clk, i_CB=clk,
            i_R=0
        )


class XilinxDDRInputKU:
    @staticmethod
    def lower(dr):
        return XilinxDDRInputImplKU(dr.i, dr.o1, dr.o2, dr.clk)


xilinx_ku_special_overrides = {
    DDROutput:              XilinxDDROutputKU,
    DDRInput:               XilinxDDRInputKU
}


def _run_yosys(device, sources, vincpaths, build_name):
    ys_contents = ""
    incflags = ""
    for path in vincpaths:
        incflags += " -I" + path
    for filename, language, library in sources:
        assert language != "vhdl"
        ys_contents += "read_{}{} {}\n".format(language, incflags, filename)

    ys_contents += """\
hierarchy -top top

# FIXME: Are these needed?
# proc; memory; opt; fsm; opt

# Map keep to keep=1 for yosys
log
log XX. Converting (* keep = "xxxx" *) attribute for Yosys
log
attrmap -tocase keep -imap keep="true" keep=1 -imap keep="false" keep=0 -remove keep=0
select -list a:keep=1

# Add keep=1 for yosys to objects which have dont_touch="true" attribute.
log
log XX. Converting (* dont_touch = "true" *) attribute for Yosys
log
select -list a:dont_touch=true
setattr -set keep 1 a:dont_touch=true

# Convert (* async_reg = "true" *) to async registers for Yosys.
# (* async_reg = "true", dont_touch = "true" *) reg xilinxmultiregimpl0_regs1 = 1'd0;
log
log XX. Converting (* async_reg = "true" *) attribute to async registers for Yosys
log
select -list a:async_reg=true
setattr -set keep 1 a:async_reg=true

synth_xilinx -top top

write_edif -pvector bra -attrprop {build_name}.edif
""".format(build_name=build_name)

    ys_name = build_name + ".ys"
    tools.write_to_file(ys_name, ys_contents)
    r = subprocess.call(["yosys", ys_name])
    if r != 0:
        raise OSError("Subprocess failed")
