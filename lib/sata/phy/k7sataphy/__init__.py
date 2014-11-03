from migen.fhdl.std import *

from lib.sata.k7sataphy.std import *
from lib.sata.k7sataphy.gtx import K7SATAPHYGTX
from lib.sata.k7sataphy.crg import K7SATAPHYCRG
from lib.sata.k7sataphy.ctrl import K7SATAPHYHostCtrl, K7SATAPHYDeviceCtrl
from lib.sata.k7sataphy.datapath import K7SATAPHYDatapath

class K7SATAPHY(Module):
	def __init__(self, pads, clk_freq, host=True, default_speed="SATA1"):
	# GTX
		self.submodules.gtx = K7SATAPHYGTX(pads, default_speed)

	# CRG / CTRL
		self.submodules.crg = K7SATAPHYCRG(pads, self.gtx, clk_freq, default_speed)
		if host:
			self.submodules.ctrl = K7SATAPHYHostCtrl(self.gtx, self.crg, clk_freq)
		else:
			self.submodules.ctrl = K7SATAPHYDeviceCtrl(self.gtx, self.crg, clk_freq)

	# DATAPATH
		self.submodules.datapath = K7SATAPHYDatapath(self.gtx, self.ctrl)
		self.sink, self.source = self.datapath.sink, self.datapath.source
