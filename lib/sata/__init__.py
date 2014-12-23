from lib.sata.common import *
from lib.sata.link import SATALink
from lib.sata.transport import SATATransport
from lib.sata.command import SATACommand

class SATACON(Module):
	def __init__(self, phy, sector_size=512, max_count=16):
		self.sector_size = sector_size
		self.max_count = max_count

		###

		self.link = SATALink(phy)
		self.transport = SATATransport(self.link)
		self.command = SATACommand(self.transport, sector_size, max_count)
		self.sink, self.source = self.command.sink, self.command.source

