from migen.fhdl.std import *
from migen.genlib.record import *
from migen.sim.generic import run_simulation

from misoclib.com.spi import SPIMaster


class SPISlave(Module):
    def __init__(self, pads, width):
        self.pads = pads
        self.width = width

        ###

        self.mosi = 0
        self.miso = 0

        self.last_cs_n = 1
        self.last_clk = 0


    def get_mosi(self):
        return self.mosi

    def set_miso(self, value):
        self.miso = value

    def do_simulation(self, selfp):
        # detect edges
        cs_n_rising = 0
        cs_n_falling = 0
        clk_rising = 0
        clk_falling = 0
        if selfp.pads.cs_n and not self.last_cs_n:
            cs_n_rising = 1
        if not selfp.pads.cs_n and self.last_cs_n:
            cs_n_falling = 1
        if selfp.pads.clk and not self.last_clk:
            clk_rising = 1
        if not selfp.pads.clk and self.last_clk:
            clk_falling = 1

        # input mosi
        if clk_falling and not selfp.pads.cs_n:
            self.mosi = self.mosi << 1
            self.mosi |= selfp.pads.mosi

        # output miso
        if (clk_rising and not selfp.pads.cs_n):
            selfp.pads.miso = (self.miso >> (self.width-1)) & 0x1
            self.miso = self.miso << 1

        # save signal states
        self.last_cs_n = selfp.pads.cs_n
        self.last_clk = selfp.pads.clk


def spi_access(selfp, length, mosi):
    selfp.spi_master._mosi.storage = mosi
    yield
    selfp.spi_master._ctrl.r = (length << 8) | 1
    selfp.spi_master._ctrl.re = 1
    yield
    selfp.spi_master._ctrl.r = 0
    selfp.spi_master._ctrl.re = 0
    yield
    while not (selfp.spi_master._status.status & 0x1):
        yield


class TB(Module):
    def __init__(self):
        pads = Record([("cs_n", 1), ("clk", 1), ("mosi", 1), ("miso", 1)])
        self.submodules.spi_master = SPIMaster(pads, 24, 4)
        self.submodules.spi_slave = SPISlave(pads, 24)

    def gen_simulation(self, selfp):
        for i in range(16):
            yield
        self.spi_slave.set_miso(0x123457)
        yield from spi_access(selfp, 8, 0x123457)
        print("{:08x}".format(self.spi_slave.get_mosi()))
        print("{:08x}".format(selfp.spi_master._miso.status))

if __name__ == "__main__":
    run_simulation(TB(), ncycles=1000, vcd_name="my.vcd", keep_files=True)
