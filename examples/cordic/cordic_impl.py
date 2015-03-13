import copy
import json

from migen.fhdl.std import *
from migen.genlib.cordic import Cordic
from mibuild.tools import mkdir_noerror
from mibuild.generic_platform import *
from mibuild.crg import SimpleCRG
from mibuild.xilinx import XilinxPlatform

class CordicImpl(Module):
	def __init__(self, name, **kwargs):
		self.name = name
		mkdir_noerror("build")
		json.dump(kwargs, open("build/{}.json".format(name), "w"))
		self.platform = platform = Platform()
		self.submodules.cordic = Cordic(**kwargs)
		width = flen(self.cordic.xi)
		self.comb += self.cordic.xi.eq(
				int((1<<width - 1)/self.cordic.gain*.98))
		self.comb += self.cordic.yi.eq(0)
		zi = self.cordic.zi
		self.sync += zi.eq(zi + 1)
		do = platform.request("do")
		self.sync += do.eq(Cat(self.cordic.xo, self.cordic.yo))

	def build(self):
		self.platform.build(self, build_name=self.name)

class Platform(XilinxPlatform):
	_io = [
		("clk", 0, Pins("AB13")),
		("rst", 0, Pins("V5")),
		("do", 0,
			Pins("Y2 W3 W1 P8 P7 P6 P5 T4 T3",
				"U4 V3 N6 N7 M7 M8 R4 P4 M6 L6 P3 N4",
				"M5 V2 V1 U3 U1 T2 T1 R3 R1 P2 P1"),
		),
	]
	def __init__(self):
		XilinxPlatform.__init__(self, "xc6slx45-fgg484-2", self._io,
			lambda p: SimpleCRG(p, "clk", "rst"))

if __name__ == "__main__":
	default = dict(width=16, guard=0, eval_mode="pipelined",
			func_mode="circular", cordic_mode="rotate")
	variations = dict(
			eval_mode=["combinatorial", "pipelined", "iterative"],
			width=[4, 8, 12, 14, 16, 20, 24, 32],
			stages=[10, 12, 14, 16, 20, 24, 32],
			guard=[0, 1, 2, 3, 4],
			)
	CordicImpl("cordic_test", eval_mode="combinatorial").build()

	name = "cordic_baseline"
	CordicImpl(name, **default).build()

	for k, v in sorted(variations.items()):
		for vi in v:
			name = "cordic_{}_{}".format(k, vi)
			kw = copy.copy(default)
			kw[k] = vi
			CordicImpl(name, **kw).build()
