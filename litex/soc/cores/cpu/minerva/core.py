import os

from migen import *

from litex.soc.interconnect import wishbone


class Minerva(Module):
    name = "minerva"
    endianness = "little"
    gcc_triple = ("riscv64-unknown-elf", "riscv32-unknown-elf")
    gcc_flags = "-D__minerva__ -march=rv32i -mabi=ilp32"
    linker_output_format = "elf32-littleriscv"

    def __init__(self, platform, cpu_reset_address, variant=None):
        assert variant is None, "Unsupported variant %s" % variant
        self.reset = Signal()
        self.ibus = wishbone.Interface()
        self.dbus = wishbone.Interface()
        self.interrupt = Signal(32)

        ###

        try: # FIXME: workaround until Minerva code is released
            from minerva.core import Minerva as MinervaCPU
            self.submodules.cpu = MinervaCPU(reset_address=cpu_reset_address)
            self.comb += [
                self.cpu.reset.eq(self.reset),
                self.cpu.external_interrupt.eq(self.interrupt),
                self.cpu.ibus.connect(self.ibus),
                self.cpu.dbus.connect(self.dbus)
            ]
        except:
            pass

