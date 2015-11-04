from migen import *
from migen.sim.generic import run_simulation

from misoc.mem.sdram.core import lasmibus
from misoc.mem.sdram.core.lasmicon import *

from test_common import sdram_phy, sdram_geom, sdram_timing, DFILogger


def my_generator_r(n):
    for x in range(10):
        t = TRead(128*n + 48*n*x)
        yield t
    print("{0:3}: reads done".format(n))


def my_generator_w(n):
    for x in range(10):
        t = TWrite(128*n + 48*n*x, x)
        yield t
    print("{0:3}: writes done".format(n))


def my_generator(n):
    if n % 2:
        return my_generator_w(n // 2)
    else:
        return my_generator_r(n // 2)


class TB(Module):
    def __init__(self):
        self.submodules.dut = LASMIcon(sdram_phy, sdram_geom, sdram_timing)
        self.submodules.xbar = lasmibus.Crossbar([self.dut.lasmic], self.dut.nrowbits)
        self.submodules.logger = DFILogger(self.dut.dfi)

        masters = [self.xbar.get_master() for i in range(6)]
        self.initiators = [Initiator(my_generator(n), master)
            for n, master in enumerate(masters)]
        self.submodules += self.initiators

if __name__ == "__main__":
    run_simulation(TB(), vcd_name="my.vcd")
