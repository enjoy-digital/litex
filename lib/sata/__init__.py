from migen.fhdl.std import *

from lib.sata.common import *
from lib.sata.link import SATALink
from lib.sata.transport import SATATransport
from lib.sata.command import SATACommand

class SATACON(Module):
	def __init__(self, phy, sector_size=512, max_count=16):
		self.submodules.link = SATALink(phy)
		self.submodules.transport = SATATransport(self.link)
		self.submodules.command = SATACommand(self.transport)
		self.sink, self.source = self.command.sink, self.command.source

