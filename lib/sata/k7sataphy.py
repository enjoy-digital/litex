from migen.fhdl.std import *
from lib.sata.k7satagtx import SATAGTX

class K7SATAPHY(Module):
	def __init__(self, pads):
		self.sata_gtx = SATAGTX(pads)
