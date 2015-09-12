from migen import *
from migen.fhdl import verilog
from migen.genlib.divider import Divider


class CDM(Module):
    def __init__(self):
        self.submodules.divider = Divider(5)
        self.clock_domains.cd_sys = ClockDomain(reset_less=True)


class MultiMod(Module):
    def __init__(self):
        self.submodules.foo = CDM()
        self.submodules.bar = CDM()

if __name__ == "__main__":
    mm = MultiMod()
    print(verilog.convert(mm, {mm.foo.cd_sys.clk, mm.bar.cd_sys.clk}))
