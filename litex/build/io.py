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
    def __init__(self, i, o, clk=None):
        Special.__init__(self)
        self.i            = wrap(i)
        self.o            = wrap(o)
        if clk is None:
            clk = ClockSignal()
        self.clk          = wrap(clk)
        self.clk_domain   = None if not hasattr(clk, "cd") else clk.cd
        assert len(self.i) == len(self.o)

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
        _o  = Signal().like(o)
        _oe = Signal().like(oe)
        _i  = Signal().like(i) if i is not None else None
        self.specials   += SDROutput(o, _o, clk)
        if _i is not None:
            self.specials   += SDRInput(_i, i, clk)
        self.submodules += InferedSDRIO(oe, _oe, clk)
        self.specials   += Tristate(io, _o, _oe, _i)

class SDRTristate(Special):
    def __init__(self, io, o, oe, i=None, clk=None):
        Special.__init__(self)
        self.io  = wrap(io)
        self.o   = wrap(o)
        self.oe  = wrap(oe)
        self.i   = wrap(i) if i is not None else None
        self.clk = wrap(clk) if clk is not None else ClockSignal()
        if self.i is not None:
            assert len(self.i) == len(self.o) == len(self.oe)
        else:
            assert len(self.o) == len(self.oe)

    def iter_expressions(self):
        yield self, "io" , SPECIAL_INOUT
        yield self, "o"  , SPECIAL_INPUT
        yield self, "oe" , SPECIAL_INPUT
        if self.i is not None:
            yield self, "i"  , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        return InferedSDRTristate(dr.io, dr.o, dr.oe, dr.i, dr.clk)

# DDR Input/Output ---------------------------------------------------------------------------------

class DDRInput(Special):
    def __init__(self, i, o1, o2, clk=None):
        Special.__init__(self)
        self.i   = wrap(i)
        self.o1  = wrap(o1)
        self.o2  = wrap(o2)
        if clk is None:
            clk = ClockSignal()
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
    def __init__(self, i1, i2, o, clk=None):
        Special.__init__(self)
        self.i1  = wrap(i1)
        self.i2  = wrap(i2)
        self.o   = wrap(o)
        if clk is None:
            clk = ClockSignal()
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
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk, i_async):
        _o  = Signal().like(o1)
        _oe = Signal().like(oe1)
        _i  = Signal().like(_o) if i1 is not None and i2 is not None else None
        self.specials += DDROutput(o1, o2, _o, clk)
        self.specials += DDROutput(oe1, oe2, _oe, clk) if oe2 is not None else SDROutput(oe1, _oe, clk)
        if _i is not None:
            self.specials += DDRInput(_i, i1, i2, clk)
            if i_async is not None:
                self.comb += i_async.eq(_i)
        elif i_async is not None:
            _i = i_async
        self.specials += Tristate(io, _o, _oe, _i)

class DDRTristate(Special):
    def __init__(self, io, o1, o2, oe1, oe2=None, i1=None, i2=None, clk=None, i_async=None):
        Special.__init__(self)
        self.io      = io
        self.o1      = o1
        self.o2      = o2
        self.oe1     = oe1
        self.oe2     = oe2
        self.i1      = i1
        self.i2      = i2
        self.clk     = clk     if     clk is not None else ClockSignal()
        self.i_async = i_async

    def iter_expressions(self):
        attr_context = [
            ("io" ,     SPECIAL_INOUT),
            ("o1" ,     SPECIAL_INPUT),
            ("o2" ,     SPECIAL_INPUT),
            ("oe1",     SPECIAL_INPUT),
            ("oe2",     SPECIAL_INPUT),
            ("i1" ,     SPECIAL_OUTPUT),
            ("i2" ,     SPECIAL_OUTPUT),
            ("clk",     SPECIAL_INPUT),
            ("i_async", SPECIAL_OUTPUT)
        ]
        for attr, target_context in attr_context:
            if getattr(self, attr) is not None:
                yield self, attr, target_context

    @staticmethod
    def lower(dr):
        return InferedDDRTristate(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk, dr.i_async)

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
