from migen import *
from migen.sim.generic import run_simulation

from misoc.mem.sdram.code import lasmibus
from misoc.mem.sdram.core.lasmicon.bankmachine import *

from test_common import sdram_phy, sdram_geom, sdram_timing, CommandLogger


def my_generator():
    for x in range(10):
        yield True, x
    for x in range(10):
        yield False, 128*x


class TB(Module):
    def __init__(self):
        self.req = Interface(32, 32, 1,
            sdram_timing.req_queue_size, sdram_phy.read_latency, sdram_phy.write_latency)
        self.submodules.dut = BankMachine(sdram_geom, sdram_timing, 2, 0, self.req)
        self.submodules.logger = CommandLogger(self.dut.cmd, True)
        self.generator = my_generator()
        self.dat_ack_cnt = 0

    def do_simulation(self, selfp):
        if selfp.req.dat_ack:
            self.dat_ack_cnt += 1
        if selfp.req.req_ack:
            try:
                we, adr = next(self.generator)
            except StopIteration:
                selfp.req.stb = 0
                if not selfp.req.lock:
                    print("data ack count: {0}".format(self.dat_ack_cnt))
                    raise StopSimulation
                return
            selfp.req.adr = adr
            selfp.req.we = we
            selfp.req.stb = 1

if __name__ == "__main__":
    run_simulation(TB(), vcd_name="my.vcd")
