from migen import *
from migen.bus.transactions import TRead, TWrite
from migen.bus import wishbone
from migen.sim.generic import Simulator
from migen.sim import icarus
from mibuild.platforms import papilio_pro as board
from misoc import sdram
from misoc.mem.sdram.core.minicon import Minicon
from misoc.mem.sdram.phy import gensdrphy
from itertools import chain
from os.path import isfile
import sys

clk_freq = 80000000

from math import ceil


def ns(t, margin=True):
    clk_period_ns = 1000000000/clk_freq
    if margin:
        t += clk_period_ns/2
    return ceil(t/clk_period_ns)


class MiniconTB(Module):
    def __init__(self, sdrphy, dfi, sdram_geom, sdram_timing, pads, sdram_clk):

        self.clk_freq = 80000000
        phy_settings = sdrphy.settings
        rdphase = phy_settings.rdphase
        self.submodules.slave = Minicon(phy_settings, sdram_geom, sdram_timing)

        self.submodules.tap = wishbone.Tap(self.slave.bus)
        self.submodules.dc = dc = wishbone.DownConverter(32, phy_settings.nphases*len(dfi.phases[rdphase].rddata))
        self.submodules.master = wishbone.Initiator(self.genxfers(), bus=dc.wishbone_i)
        self.submodules.intercon = wishbone.InterconnectPointToPoint(dc.wishbone_o, self.slave.bus)

        self.submodules.sdrphy = self.sdrphy = sdrphy
        self.dfi = dfi
        self.pads = pads

        self.specials += Instance("mt48lc4m16a2",
                                  io_Dq=pads.dq,
                                  i_Addr=pads.a,
                                  i_Ba=pads.ba,
                                  i_Clk=ClockSignal(),
                                  i_Cke=pads.cke,
                                  i_Cs_n=pads.cs_n,
                                  i_Ras_n=pads.ras_n,
                                  i_Cas_n=pads.cas_n,
                                  i_We_n=pads.we_n,
                                  i_Dqm=pads.dm
        )

    def genxfers(self):
        cycle = 0
        for a in chain(range(4), range(256, 260), range(1024, 1028)):
            t = TRead(a)
            yield t
            print("read {} in {} cycles".format(t.data, t.latency))
        for a in chain(range(4), range(256, 260), range(1024, 1028), range(4096, 4100)):
            t = TWrite(a, 0xaa55aa55+cycle)
            cycle += 1
            yield t
            print("read {} in {} cycles".format(t.data, t.latency))
        for a in chain(range(4), range(256, 260), range(1024, 1028), range(4096, 4100)):
            t = TRead(a)
            yield t
            print("read {} in {} cycles".format(t.data, t.latency))

    def gen_simulation(self, selfp):
        dfi = selfp.dfi
        phy = self.sdrphy
        rdphase = phy.settings.rdphase
        cycle = 0

        while True:
            yield


class MyTopLevel:
    def __init__(self, vcd_name=None, vcd_level=1,
      top_name="top", dut_type="dut", dut_name="dut",
      cd_name="sys", clk_period=10):
        self.vcd_name = vcd_name
        self.vcd_level = vcd_level
        self.top_name = top_name
        self.dut_type = dut_type
        self.dut_name = dut_name

        self._cd_name = cd_name
        self._clk_period = clk_period

        cd = ClockDomain(self._cd_name)
        cd_ps = ClockDomain("sys_ps")
        self.clock_domains = [cd, cd_ps]
        self.ios = {cd.clk, cd.rst, cd_ps.clk}

    def get(self, sockaddr):
        template1 = """`timescale 1ns / 1ps

module {top_name}();

reg {clk_name};
reg {rst_name};
reg sys_ps_clk;

initial begin
    {rst_name} <= 1'b1;
    @(posedge {clk_name});
    {rst_name} <= 1'b0;
end

always begin
    {clk_name} <= 1'b0;
    #{hclk_period};
    {clk_name} <= 1'b1;
    #{hclk_period};
end

always @(posedge {clk_name} or negedge {clk_name})
    sys_ps_clk <= #({hclk_period}*2-3) {clk_name};

{dut_type} {dut_name}(
    .{rst_name}({rst_name}),
    .{clk_name}({clk_name}),
    .sys_ps_clk(sys_ps_clk)
);

initial $migensim_connect("{sockaddr}");
always @(posedge {clk_name}) $migensim_tick;
"""
        template2 = """
initial begin
    $dumpfile("{vcd_name}");
    $dumpvars({vcd_level}, {dut_name});
end
"""
        r = template1.format(top_name=self.top_name,
            dut_type=self.dut_type,
            dut_name=self.dut_name,
            clk_name=self._cd_name + "_clk",
            rst_name=self._cd_name + "_rst",
            hclk_period=str(self._clk_period/2),
            sockaddr=sockaddr)
        if self.vcd_name is not None:
            r += template2.format(vcd_name=self.vcd_name,
                vcd_level=str(self.vcd_level),
                dut_name=self.dut_name)
        r += "\nendmodule"
        return r


if __name__ == "__main__":

    plat = board.Platform()

    sdram_geom = sdram.GeomSettings(
        bankbits=2,
        rowbits=12,
        colbits=8
    )

    sdram_timing = sdram.TimingSettings(
        tRP=ns(15),
        tRCD=ns(15),
        tWR=ns(14),
        tWTR=2,
        tREFI=ns(64*1000*1000/4096, False),
        tRFC=ns(66),
        req_queue_size=8,
        read_time=32,
        write_time=16
    )

    sdram_pads = plat.request("sdram")
    sdram_clk = plat.request("sdram_clock")

    sdrphy = gensdrphy.GENSDRPHY(sdram_pads)

# This sets CL to 2 during LMR done on 1st cycle
    sdram_pads.a.reset = 1<<5

    s = MiniconTB(sdrphy, sdrphy.dfi, sdram_geom, sdram_timing, pads=sdram_pads, sdram_clk=sdram_clk)

    extra_files = ["sdram_model/mt48lc4m16a2.v"]

    if not isfile(extra_files[0]):
        print("ERROR: You need to download Micron Verilog simulation model for MT48LC4M16A2 and put it in sdram_model/mt48lc4m16a2.v")
        print("File can be downloaded from this URL: http://www.micron.com/-/media/documents/products/sim%20model/dram/dram/4054mt48lc4m16a2.zip")
        sys.exit(1)

    with Simulator(s, MyTopLevel("top.vcd", clk_period=int(1/0.08)), icarus.Runner(extra_files=extra_files, keep_files=True)) as sim:
        sim.run(5000)
