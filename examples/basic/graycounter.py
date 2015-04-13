from random import Random

from migen.fhdl.std import *
from migen.genlib.cdc import GrayCounter
from migen.sim.generic import run_simulation

class TB(Module):
    def __init__(self, width=3):
        self.width = width
        self.submodules.gc = GrayCounter(self.width)
        self.prng = Random(7345)

    def do_simulation(self, selfp):
        print("{0:0{1}b} CE={2} bin={3}".format(selfp.gc.q,
            self.width, selfp.gc.ce, selfp.gc.q_binary))
        selfp.gc.ce = self.prng.getrandbits(1)

if __name__ == "__main__":
    run_simulation(TB(), ncycles=35)
