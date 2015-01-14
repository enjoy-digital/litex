from lib.sata.common import *
from lib.sata.link import SATALink
from lib.sata.transport import SATATransport
from lib.sata.command import SATACommand

from lib.sata.frontend.crossbar import SATACrossbar

class SATACON(Module):
	def __init__(self, phy):
		###
		# core
		self.link = SATALink(phy)
		self.transport = SATATransport(self.link)
		self.command = SATACommand(self.transport)

		# frontend
		self.crossbar = SATACrossbar(32)
		self.comb += [
			Record.connect(self.crossbar.master.source, self.command.sink),
			Record.connect(self.command.source, self.crossbar.master.sink)
		]
