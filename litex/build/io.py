#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Special, Tristate

# Differential Input/Output ------------------------------------------------------------------------

class DifferentialInput(Special):
    def __init__(self, i_p, i_n, o):
        Special.__init__(self)
        self.i_p = wrap(i_p)
        self.i_n = wrap(i_n)
        self.o   = wrap(o)

    def iter_expressions(self):
        yield self, "i_p", SPECIAL_INPUT
        yield self, "i_n", SPECIAL_INPUT
        yield self, "o"  , SPECIAL_OUTPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a Differential Input, but platform does not support them")


class DifferentialOutput(Special):
    def __init__(self, i, o_p, o_n):
        Special.__init__(self)
        self.i   = wrap(i)
        self.o_p = wrap(o_p)
        self.o_n = wrap(o_n)

    def iter_expressions(self):
        yield self, "i"  , SPECIAL_INPUT
        yield self, "o_p", SPECIAL_OUTPUT
        yield self, "o_n", SPECIAL_OUTPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a Differential Output, but platform does not support them")

# Clk Input/Output ---------------------------------------------------------------------------------

class ClkInput(Special):
    def __init__(self, i, o):
        Special.__init__(self)
        self.i = wrap(i)
        self.o = o if isinstance(o, str) else wrap(o)

    def iter_expressions(self):
        yield self, "i", SPECIAL_INPUT
        yield self, "o", SPECIAL_OUTPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a Clk Input, but platform does not support them")


class ClkOutput(Special):
    def __init__(self, i, o):
        Special.__init__(self)
        self.i = i if isinstance(i, str) else wrap(i)
        self.o = wrap(o)

    def iter_expressions(self):
        yield self, "i", SPECIAL_INPUT
        yield self, "o", SPECIAL_OUTPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a Clk Output, but platform does not support them")

# SDR Input/Output ---------------------------------------------------------------------------------

class InferedSDRIO(Module):
    def __init__(self, i, o, clk):
        self.clock_domains.cd_sdrio = ClockDomain(reset_less=True)
        self.comb += self.cd_sdrio.clk.eq(clk)
        self.sync.sdrio += o.eq(i)

class SDRIO(Special):
    def __init__(self, i, o, clk=ClockSignal()):
        assert len(i) == len(o) == 1
        Special.__init__(self)
        self.i            = wrap(i)
        self.o            = wrap(o)
        self.clk          = wrap(clk)
        self.clk_domain   = None if not hasattr(clk, "cd") else clk.cd

    def iter_expressions(self):
        yield self, "i"  , SPECIAL_INPUT
        yield self, "o"  , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        return InferedSDRIO(dr.i, dr.o, dr.clk)


class SDRInput(SDRIO):  pass
class SDROutput(SDRIO): pass

# SDR Tristate -------------------------------------------------------------------------------------

class InferedSDRTristate(Module):
    def __init__(self, io, o, oe, i, clk):
        _o  = Signal()
        _oe = Signal()
        _i  = Signal()
        self.specials   += SDROutput(o, _o, clk)
        self.specials   += SDRInput(_i, i, clk)
        self.submodules += InferedSDRIO(oe, _oe, clk)
        self.specials   += Tristate(io, _o, _oe, _i)

class SDRTristate(Special):
    def __init__(self, io, o, oe, i, clk=ClockSignal()):
        assert len(i) == len(o) == len(oe)
        Special.__init__(self)
        self.io  = wrap(io)
        self.o   = wrap(o)
        self.oe  = wrap(oe)
        self.i   = wrap(i)
        self.clk = wrap(clk)

    def iter_expressions(self):
        yield self, "io" , SPECIAL_INOUT
        yield self, "o"  , SPECIAL_INPUT
        yield self, "oe" , SPECIAL_INPUT
        yield self, "i"  , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        return InferedSDRTristate(dr.io, dr.o, dr.oe, dr.i, dr.clk)

# DDR Input/Output ---------------------------------------------------------------------------------

class DDRInput(Special):
    def __init__(self, i, o1, o2, clk=ClockSignal()):
        Special.__init__(self)
        self.i   = wrap(i)
        self.o1  = wrap(o1)
        self.o2  = wrap(o2)
        self.clk = clk if isinstance(clk, str) else wrap(clk)

    def iter_expressions(self):
        yield self, "i"  , SPECIAL_INPUT
        yield self, "o1" , SPECIAL_OUTPUT
        yield self, "o2" , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a DDR input, but platform does not support them")


class DDROutput(Special):
    def __init__(self, i1, i2, o, clk=ClockSignal()):
        Special.__init__(self)
        self.i1  = wrap(i1)
        self.i2  = wrap(i2)
        self.o   = wrap(o)
        self.clk = clk if isinstance(clk, str) else wrap(clk)

    def iter_expressions(self):
        yield self, "i1" , SPECIAL_INPUT
        yield self, "i2" , SPECIAL_INPUT
        yield self, "o"  , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a DDR output, but platform does not support them")

# DDR Tristate -------------------------------------------------------------------------------------

class InferedDDRTristate(Module):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk):
        _o  = Signal()
        _oe = Signal()
        _i  = Signal()
        self.specials += DDROutput(o1, o2, _o, clk)
        self.specials += DDROutput(oe1, oe2, _oe, clk)
        self.specials += DDRInput(_i, i1, i2, clk)
        self.specials += Tristate(io, _o, _oe, _i)

class DDRTristate(Special):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk=ClockSignal()):
        Special.__init__(self)
        self.io  = io
        self.o1  = o1
        self.o2  = o2
        self.oe1 = oe1
        self.oe2 = oe2
        self.i1  = i1
        self.i2  = i2
        self.clk = clk

    def iter_expressions(self):
        yield self, "io" , SPECIAL_INOUT
        yield self, "o1" , SPECIAL_INPUT
        yield self, "o2" , SPECIAL_INPUT
        yield self, "oe1", SPECIAL_INPUT
        yield self, "oe2", SPECIAL_INPUT
        yield self, "i1" , SPECIAL_OUTPUT
        yield self, "i2" , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        return InferedDDRTristate(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk)

# QDR Input/Output ---------------------------------------------------------------------------------

class QDRInput(Special):
    def __init__(self, i, o1, o2, o3, o4, clk=ClockSignal(), fastclk=None):
        Special.__init__(self)
        self.i   = wrap(i)
        self.o1  = wrap(o1)
        self.o2  = wrap(o2)
        self.o3  = wrap(o3)
        self.o4  = wrap(o4)
        self.clk = clk if isinstance(clk, str) else wrap(clk)
        self.fastclk = fastclk if isinstance(fastclk, str) else wrap(fastclk)

    def iter_expressions(self):
        yield self, "i"  , SPECIAL_INPUT
        yield self, "o1" , SPECIAL_OUTPUT
        yield self, "o2" , SPECIAL_OUTPUT
        yield self, "o3" , SPECIAL_OUTPUT
        yield self, "o4" , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT
        yield self, "fastclk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a QDR input, but platform does not support them")


class QDROutput(Special):
    def __init__(self, i1, i2, i3, i4, o, clk=ClockSignal(), fastclk=None):
        Special.__init__(self)
        self.i1  = wrap(i1)
        self.i2  = wrap(i2)
        self.i3  = wrap(i3)
        self.i4  = wrap(i4)
        self.o   = wrap(o)
        self.clk = clk if isinstance(clk, str) else wrap(clk)
        self.fastclk = fastclk if isinstance(fastclk, str) else wrap(fastclk)

    def iter_expressions(self):
        yield self, "i1" , SPECIAL_INPUT
        yield self, "i2" , SPECIAL_INPUT
        yield self, "i3" , SPECIAL_INPUT
        yield self, "i4" , SPECIAL_INPUT
        yield self, "o"  , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT
        yield self, "fastclk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a QDR output, but platform does not support them")

# QDR Tristate -------------------------------------------------------------------------------------

class InferedQDRTristate(Module):
    def __init__(self, io, o1, o2, o3, o4, oe1, oe2, oe3, oe4, i1, i2, i3, i4, clk, fastclk_in, fastclk_out):
        _o  = Signal()
        _oe = Signal()
        _i  = Signal()
        self.specials += QDROutput(o1, o2, o3, o4, _o, clk, fastclk_out)
        self.specials += QDROutput(oe1, oe2, oe3, oe4, _oe, clk, fastclk_out) if (oe2 is not None) or (oe3 is not None) or (oe3 is not None) else SDROutput(oe1, _oe, clk)
        self.specials += QDRInput(_i, i1, i2, i3, i4, clk, fastclk_in)
        self.specials += Tristate(io, _o, _oe, _i)

class QDRTristate(Special):
    def __init__(self, io, o1, o2, o3, o4,
                 oe1, oe2=None, oe3=None, oe4=None,
                 i1=Signal(), i2=Signal(), i3=Signal(), i4=Signal(),
                 clk=ClockSignal(), fastclk=None, fastclk_in=None, fastclk_out=None):
        Special.__init__(self)
        self.io  = io
        self.o1  = o1
        self.o2  = o2
        self.o3  = o3
        self.o4  = o4
        self.oe1 = oe1
        self.oe2 = oe2
        self.oe3 = oe3
        self.oe4 = oe4
        self.i1  = i1
        self.i2  = i2
        self.i3  = i3
        self.i4  = i4
        self.clk = clk
        self.fastclk_in = fastclk_in if fastclk_in is not None else fastclk
        self.fastclk_out = fastclk_out if fastclk_out is not None else fastclk

    def iter_expressions(self):
        yield self, "io" , SPECIAL_INOUT
        yield self, "o1" , SPECIAL_INPUT
        yield self, "o2" , SPECIAL_INPUT
        yield self, "o3" , SPECIAL_INPUT
        yield self, "o4" , SPECIAL_INPUT
        yield self, "oe1", SPECIAL_INPUT
        yield self, "oe2", SPECIAL_INPUT
        yield self, "oe3", SPECIAL_INPUT
        yield self, "oe4", SPECIAL_INPUT
        yield self, "i1" , SPECIAL_OUTPUT
        yield self, "i2" , SPECIAL_OUTPUT
        yield self, "i3" , SPECIAL_OUTPUT
        yield self, "i4" , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT
        yield self, "fastclk_in", SPECIAL_INPUT
        yield self, "fastclk_out", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        return InferedDDRTristate(dr.io, dr.o1, dr.o2, dr.o3, dr.o4, 
                                  dr.oe1, dr.oe2, dr.oe3, dr.oe4,
                                  dr.i1, dr.i2, dr.i3, dr.i4, 
                                  dr.clk, dr.fastclk_in, dr.fastclk_out)

# Clock Reset Generator ----------------------------------------------------------------------------

class CRG(Module):
    def __init__(self, clk, rst=0):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_por = ClockDomain(reset_less=True)

        if hasattr(clk, "p"):
            clk_se = Signal()
            self.specials += DifferentialInput(clk.p, clk.n, clk_se)
            clk = clk_se

        # Power on Reset (vendor agnostic)
        int_rst = Signal(reset=1)
        self.sync.por += int_rst.eq(rst)
        self.comb += [
            self.cd_sys.clk.eq(clk),
            self.cd_por.clk.eq(clk),
            self.cd_sys.rst.eq(int_rst)
        ]
