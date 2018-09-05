import os

from migen import *

from litex.soc.interconnect import wishbone

from minerva.core import Minerva as MinervaCPU


class Minerva(Module):
    def __init__(self, platform, cpu_reset_address, variant=None):
        assert variant is None, "Unsupported variant %s" % variant
        self.reset = Signal()
        self.ibus = wishbone.Interface()
        self.dbus = wishbone.Interface()
        self.interrupt = Signal(32)

        ###

        self.submodules.cpu = MinervaCPU(reset_address=cpu_reset_address)
        self.comb += [
            self.cpu.reset.eq(self.reset),
            self.cpu.external_interrupt.eq(self.interrupt),
            self.cpu.ibus.connect(self.ibus),
            self.cpu.dbus.connect(self.dbus)
        ]
