from litesata.common import *
from litesata.phy import *
from litesata.core import *
from litesata.frontend import *

from migen.bank.description import *

class LiteSATA(Module, AutoCSR):
	def __init__(self, phy,
			with_crossbar=False,
			with_bist=False, with_bist_csr=False):
		# phy
		self.phy = phy

		# core
		self.core = LiteSATACore(self.phy)

		# frontend
		if with_crossbar:
			self.crossbar = LiteSATACrossbar(self.core)
		if with_bist:
			self.bist = LiteSATABIST(self.crossbar, with_bist_csr)

