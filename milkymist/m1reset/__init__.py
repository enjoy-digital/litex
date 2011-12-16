from functools import partial

from migen.fhdl.structure import *

class Inst:
	def __init__(self):
		d = partial(declare_signal, self)
		d("trigger_reset")
		d("sys_rst")
		d("ac97_rst_n")
		d("videoin_rst_n")
		d("flash_rst_n")
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
