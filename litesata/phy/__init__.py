from litesata.common import *
from litesata.phy.ctrl import *
from litesata.phy.datapath import *

class LiteSATAPHY(Module):
	def __init__(self, device, pads, revision, clk_freq):
		self.revision = revision
		# Transceiver / Clocks
		if device[:3] == "xc7": # Kintex 7
			from litesata.phy.k7.trx import K7LiteSATAPHYTRX
			from litesata.phy.k7.crg import K7LiteSATAPHYCRG
			self.trx = K7LiteSATAPHYTRX(pads, revision)
			self.crg = K7LiteSATAPHYCRG(pads, self.trx, revision, clk_freq)
		else:
			msg = "Device" + device + "not (yet) supported."
			raise NotImplementedError(msg)

		# Control
		self.ctrl = LiteSATAPHYCtrl(self.trx, self.crg, clk_freq)

		# Datapath
		self.datapath = LiteSATAPHYDatapath(self.trx, self.ctrl)
		self.sink, self.source = self.datapath.sink, self.datapath.source
