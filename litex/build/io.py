# This file is Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# License: BSD

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
        yield self, "o", SPECIAL_OUTPUT

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
        yield self, "i", SPECIAL_INPUT
        yield self, "o_p", SPECIAL_OUTPUT
        yield self, "o_n", SPECIAL_OUTPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a Differential Output, but platform does not support them")

# SDR Input/Output ---------------------------------------------------------------------------------

class InferedSDRIO(Module):
    def __init__(self, i, o, clk, clk_domain):
        if clk_domain is None:
            raise NotImplementedError("Attempted to use an InferedSDRIO but no clk_domain specified.")
        sync = getattr(self.sync, clk_domain)
        sync += o.eq(i)


class SDRIO(Special):
    def __init__(self, i, o, clk=ClockSignal()):
        assert len(i) == len(o) == 1
        Special.__init__(self)
        self.i            = wrap(i)
        self.o            = wrap(o)
        self.clk          = wrap(clk)
        self.clk_domain   = None if not hasattr(clk, "cd") else clk.cd

    def iter_expressions(self):
        yield self, "i",   SPECIAL_INPUT
        yield self, "o",   SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        return InferedSDRIO(dr.i, dr.o, dr.clk, dr.clk_domain)


class SDRInput(SDRIO):  pass
class SDROutput(SDRIO): pass

# SDR Tristate -------------------------------------------------------------------------------------

class InferedSDRTristate(Module):
    def __init__(self, io, o, oe, i, clk, clk_domain):
        if clk_domain is None:
            raise NotImplementedError("Attempted to use an SDRTristate but no clk_domain specified.")
        _o  = Signal()
        _oe = Signal()
        _i  = Signal()
        self.specials += SDROutput(o, _o)
        self.specials += SDRInput(_i, i)
        self.submodules += InferedSDRIO(oe, _oe, clk, clk_domain)
        self.specials += Tristate(io, _o, _oe, _i)

class SDRTristate(Special):
    def __init__(self, io, o, oe, i, clk=ClockSignal()):
        assert len(i) == len(o) == len(oe)
        Special.__init__(self)
        self.io           = wrap(io)
        self.o            = wrap(o)
        self.oe           = wrap(oe)
        self.i            = wrap(i)
        self.clk          = wrap(clk)
        self.clk_domain   = None if not hasattr(clk, "cd") else clk.cd

    def iter_expressions(self):
        yield self, "io",  SPECIAL_INOUT
        yield self, "o",   SPECIAL_INPUT
        yield self, "oe",  SPECIAL_INPUT
        yield self, "i",   SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        return InferedSDRTristate(dr.io, dr.o, dr.oe, dr.i, dr.clk, dr.clk_domain)

# DDR Input/Output ---------------------------------------------------------------------------------

class DDRInput(Special):
    def __init__(self, i, o1, o2, clk=ClockSignal()):
        Special.__init__(self)
        self.i   = wrap(i)
        self.o1  = wrap(o1)
        self.o2  = wrap(o2)
        self.clk = wrap(clk)

    def iter_expressions(self):
        yield self, "i", SPECIAL_INPUT
        yield self, "o1", SPECIAL_OUTPUT
        yield self, "o2", SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a DDR input, but platform does not support them")


class DDROutput(Special):
    def __init__(self, i1, i2, o, clk=ClockSignal()):
        Special.__init__(self)
        self.i1  = i1
        self.i2  = i2
        self.o   = o
        self.clk = clk

    def iter_expressions(self):
        yield self, "i1", SPECIAL_INPUT
        yield self, "i2", SPECIAL_INPUT
        yield self, "o", SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a DDR output, but platform does not support them")

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
