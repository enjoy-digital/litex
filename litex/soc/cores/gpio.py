from migen import *
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect.csr import *


class GPIOIn(Module, AutoCSR):
    def __init__(self, signal):
        self._in = CSRStatus(len(signal))
        self.specials += MultiReg(signal, self._in.status)


class GPIOOut(Module, AutoCSR):
    def __init__(self, signal):
        self._out = CSRStorage(len(signal))
        self.comb += signal.eq(self._out.storage)


class GPIOInOut(Module):
    def __init__(self, in_signal, out_signal):
        self.submodules.gpio_in = GPIOIn(in_signal)
        self.submodules.gpio_out = GPIOOut(out_signal)

    def get_csrs(self):
        return self.gpio_in.get_csrs() + self.gpio_out.get_csrs()


class Blinker(Module):
    def __init__(self, signal, divbits=26):
        counter = Signal(divbits)
        self.comb += signal.eq(counter[divbits-1])
        self.sync += counter.eq(counter + 1)
