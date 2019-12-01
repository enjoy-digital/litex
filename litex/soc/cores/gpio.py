# This file is Copyright (c) 2013-2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# License: BSD

from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *

# GPIO Input ----------------------------------------------------------------------------------------

class GPIOIn(Module, AutoCSR):
    def __init__(self, signal):
        self._in = CSRStatus(len(signal))
        self.specials += MultiReg(signal, self._in.status)

# GPIO Output --------------------------------------------------------------------------------------

class GPIOOut(Module, AutoCSR):
    def __init__(self, signal):
        self._out = CSRStorage(len(signal))
        self.comb += signal.eq(self._out.storage)

# GPIO Input/Output --------------------------------------------------------------------------------

class GPIOInOut(Module):
    def __init__(self, in_signal, out_signal):
        self.submodules.gpio_in = GPIOIn(in_signal)
        self.submodules.gpio_out = GPIOOut(out_signal)

    def get_csrs(self):
        return self.gpio_in.get_csrs() + self.gpio_out.get_csrs()

# GPIO Tristate ------------------------------------------------------------------------------------

class GPIOTristate(Module, AutoCSR):
    def __init__(self, pads):
        self._oe  = CSRStorage(len(pads))
        self._in  = CSRStatus(len(pads))
        self._out = CSRStorage(len(pads))

        t = TSTriple(len(pads))
        self.specials += t.get_tristate(pads)
        self.comb += t.oe.eq(self._oe.storage)
        self.comb += t.o.eq(self._out.storage)
        self.specials += MultiReg(t.i, self._in.status)
