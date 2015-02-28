from litesata.common import *
from litesata.core.link import LiteSATALink
from litesata.core.transport import LiteSATATransport
from litesata.core.command import LiteSATACommand

class LiteSATACore(Module):
	def __init__(self, phy, buffer_depth):
		self.submodules.link = LiteSATALink(phy, buffer_depth)
		self.submodules.transport = LiteSATATransport(self.link)
		self.submodules.command = LiteSATACommand(self.transport)
		self.sink, self.source = self.command.sink, self.command.source
