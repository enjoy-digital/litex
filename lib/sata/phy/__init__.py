from lib.sata.common import *
from lib.sata.phy.ctrl import SATAPHYHostCtrl, SATAPHYDeviceCtrl
from lib.sata.phy.datapath import SATAPHYDatapath

class SATAPHY(Module):
	def __init__(self, pads, clk_freq, host=True, device_family="k7", speed="SATA1"):
		self.speed = speed
	# Transceiver / Clocks
		if device_family == "k7":
			from lib.sata.phy.k7.trx import K7SATAPHYTRX
			from lib.sata.phy.k7.crg import K7SATAPHYCRG
			self.trx = K7SATAPHYTRX(pads, speed)
			self.crg = K7SATAPHYCRG(pads, self.trx, clk_freq, speed)
		else:
			raise NotImplementedError(device_family + "device family not implemented")

	# Control
		if host:
			self.ctrl = SATAPHYHostCtrl(self.trx, self.crg, clk_freq)
		else:
			self.ctrl = SATAPHYDeviceCtrl(self.trx, self.crg, clk_freq)

	# Datapath
		self.datapath = SATAPHYDatapath(self.trx, self.ctrl)
		self.sink, self.source = self.datapath.sink, self.datapath.source
