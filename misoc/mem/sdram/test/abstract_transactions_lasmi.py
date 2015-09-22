from migen.fhdl.std import *
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

from misoc.mem.sdram.core import lasmibus


def my_generator(n):
    bank = n % 4
    for x in range(4):
        t = TWrite(4*bank+x, 0x1000*bank + 0x100*x)
        yield t
        print("{0}: Wrote in {1} cycle(s)".format(n, t.latency))

    for x in range(4):
        t = TRead(4*bank+x)
        yield t
        print("{0}: Read {1:x} in {2} cycle(s)".format(n, t.data, t.latency))
        assert(t.data == 0x1000*bank + 0x100*x)


class MyModel(lasmibus.TargetModel):
    def read(self, bank, address):
        r = 0x1000*bank + 0x100*address
        #print("read from bank {0} address {1} -> {2:x}".format(bank, address, r))
        return r

    def write(self, bank, address, data, we):
        print("write to bank {0} address {1:x} data {2:x}".format(bank, address, data))
        assert(data == 0x1000*bank + 0x100*address)


class TB(Module):
    def __init__(self):
        self.submodules.controller = lasmibus.Target(MyModel(), aw=4, dw=32, nbanks=4, req_queue_size=4,
            read_latency=4, write_latency=1)
        self.submodules.xbar = lasmibus.Crossbar([self.controller.bus], 2)
        self.initiators = [lasmibus.Initiator(my_generator(n), self.xbar.get_master()) for n in range(4)]
        self.submodules += self.initiators

if __name__ == "__main__":
    run_simulation(TB())
