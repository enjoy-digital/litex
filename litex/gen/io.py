# This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.fhdl.specials import Special


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


class SDRInput(SDRIO): pass


class SDROutput(SDRIO): pass
