from migen.fhdl.structure import *
from migen.fhdl.module import Module
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

mm = MultiMod()
print(verilog.convert(mm, {mm.foo.cd_sys.clk, mm.bar.cd_sys.clk}))
