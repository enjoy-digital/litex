from migen import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

from misoc.mem.sdram.core import lasmibus
from misoc.mem.sdram.core.lasmicon import *
from misoc.mem.sdram.frontend import wishbone2lasmi

from test_common import sdram_phy, sdram_geom, sdram_timing, DFILogger

l2_size = 8192  # in bytes


def my_generator():
    for x in range(20):
        t = TWrite(x, x)
        yield t
        print(str(t) + " delay=" + str(t.latency))
    for x in range(20):
        t = TRead(x)
        yield t
        print(str(t) + " delay=" + str(t.latency))
    for x in range(20):
        t = TRead(x+l2_size//4)
        yield t
        print(str(t) + " delay=" + str(t.latency))


class TB(Module):
    def __init__(self):
        self.submodules.ctler = LASMIcon(sdram_phy, sdram_geom, sdram_timing)
        self.submodules.xbar = lasmibus.Crossbar([self.ctler.lasmic], self.ctler.nrowbits)
        self.submodules.logger = DFILogger(self.ctler.dfi)
        self.submodules.bridge = wishbone2lasmi.WB2LASMI(l2_size//4, self.xbar.get_master())
        self.submodules.initiator = wishbone.Initiator(my_generator())
        self.submodules.conn = wishbone.InterconnectPointToPoint(self.initiator.bus, self.bridge.wishbone)

if __name__ == "__main__":
    run_simulation(TB(), vcd_name="my.vcd")
