from migen.fhdl import verilog
from migen.fhdl.std import *
from migen.genlib.mhamgen import HammingGenerator, HammingChecker


# Instantiates Hamming code generator and checker modules back
# to back.  Also creates an intermediate bus between generator
# and checker and injects a single-bit error on the bus, to
# demonstrate the correction.
class gen_check(Module):
    def __init__(self, width=8):
        # Save module parameters and instantiate generator and checker
        self.width = width
        hg = HammingGenerator(self.width)
        hc = HammingChecker(self.width, correct=True)
        self.submodules += hg
        self.submodules += hc

        # Create the intermediate bus and inject a single-bit error on
        # the bus.  Position of the error bit is controllable by the
        # error_bit input.
        data = Signal(width)
        error_bit = Signal(bits_for(width))
        self.comb += data.eq(hg.data_in ^ (1 << error_bit))
        self.comb += hc.code_in.eq(hg.code_out)
        self.comb += hc.data_in.eq(data)

        # Call out I/O necessary for testing the generator/checker
        self.io = set()
        self.io.add(hg.data_in)
        self.io.add(hc.enable)
        self.io.add(error_bit)
        self.io.add(hc.code_out)
        self.io.add(hc.data_out)

gc = gen_check()
print(verilog.convert(gc, gc.io, name="gen_check"))
