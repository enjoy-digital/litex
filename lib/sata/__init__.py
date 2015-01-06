from lib.sata.common import *
from lib.sata.link import SATALink
from lib.sata.transport import SATATransport
from lib.sata.command import SATACommand

class SATACON(Module):
	def __init__(self, phy):
		###
		self.link = SATALink(phy)
		self.transport = SATATransport(self.link)
		self.command = SATACommand(self.transport)
		self.sink, self.source = self.command.sink, self.command.source

