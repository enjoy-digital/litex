from migen.fhdl.structure import *

class M1Reset:
	def __init__(self):
		self.trigger_reset = Signal()
		self.sys_rst = Signal()
		self.ac97_rst_n = Signal()
		self.videoin_rst_n = Signal()
		self.flash_rst_n = Signal()
		self._inst = Instance("m1reset",
			[("sys_rst", self.sys_rst),
			("ac97_rst_n", self.ac97_rst_n),
			("videoin_rst_n", self.videoin_rst_n),
			("flash_rst_n", self.flash_rst_n)],
			[("trigger_reset", self.trigger_reset)],
			clkport="sys_clk")

	def get_fragment(self):
		return Fragment(instances=[self._inst],
			pads={self.ac97_rst_n, self.videoin_rst_n, self.flash_rst_n})
