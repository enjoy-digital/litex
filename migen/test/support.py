from migen.fhdl.std import *
from migen.sim.generic import run_simulation
from migen.fhdl import verilog


class SimBench(Module):
    callback = None
    def do_simulation(self, selfp):
        if self.callback is not None:
            return self.callback(self, selfp)


class SimCase:
    TestBench = SimBench

    def setUp(self, *args, **kwargs):
        self.tb = self.TestBench(*args, **kwargs)

    def test_to_verilog(self):
        verilog.convert(self.tb)

    def run_with(self, cb, ncycles=None):
        self.tb.callback = cb
        run_simulation(self.tb, ncycles=ncycles)
