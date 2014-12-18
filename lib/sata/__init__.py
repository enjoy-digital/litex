from lib.sata.common import *
from lib.sata.link import SATALink
from lib.sata.transport import SATATransport
from lib.sata.command import SATACommand

class SATACON(Module):
	def __init__(self, phy, sector_size=512, max_count=8):
		self.submodules.link = SATALink(phy)
		self.submodules.transport = SATATransport(self.link)
		self.submodules.command = SATACommand(self.transport, sector_size=sector_size, max_count=max_count)
		self.sink, self.source = self.command.sink, self.command.source

