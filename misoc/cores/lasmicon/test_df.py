from migen import *
from migen.sim.generic import run_simulation

from misoc.mem.sdram.core import lasmibus
from misoc.mem.sdram.core.lasmicon import *
from misoc.mem.sdram.frontend import dma_lasmi

from test_common import sdram_phy, sdram_geom, sdram_timing, DFILogger


class TB(Module):
    def __init__(self):
        self.submodules.ctler = LASMIcon(sdram_phy, sdram_geom, sdram_timing)
        self.submodules.xbar = lasmibus.Crossbar([self.ctler.lasmic], self.ctler.nrowbits)
        self.submodules.logger = DFILogger(self.ctler.dfi)
        self.submodules.writer = dma_lasmi.Writer(self.xbar.get_master())

        self.comb += self.writer.address_data.stb.eq(1)
        pl = self.writer.address_data.payload
        pl.a.reset = 255
        pl.d.reset = pl.a.reset*2
        self.sync += If(self.writer.address_data.ack,
            pl.a.eq(pl.a + 1),
            pl.d.eq(pl.d + 2)
        )
        self.open_row = None

    def do_simulation(self, selfp):
        dfip = selfp.ctler.dfi
        for p in dfip.phases:
            if p.ras_n and not p.cas_n and not p.we_n:  # write
                d = dfip.phases[0].wrdata | (dfip.phases[1].wrdata << 64)
                print(d)
                if d != p.address//2 + p.bank*512 + self.open_row*2048:
                    print("**** ERROR ****")
            elif not p.ras_n and p.cas_n and p.we_n:  # activate
                self.open_row = p.address

if __name__ == "__main__":
    run_simulation(TB(), ncycles=3500, vcd_name="my.vcd")
