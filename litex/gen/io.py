# This file is Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.fhdl.specials import Special

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
        raise NotImplementedError("Attempted to use a differential input, but platform does not support them")


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
        raise NotImplementedError("Attempted to use a differential output, but platform does not support them")


# SDR Input/Output ---------------------------------------------------------------------------------

class InferedSDRIO(Module):
    def __init__(self, i, o, clk, clk_domain):
        if clk_domain is None:
            raise NotImplementedError("Attempted to use an InferedSDRIO but no clk_domain specified.")
        sync = getattr(self.sync, clk_domain)
        sync += o.eq(i)


class SDRIO(Special):
    def __init__(self, i, o, clk=ClockSignal()):
        assert len(i) == len(o)
        Special.__init__(self)
        print(o)
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
