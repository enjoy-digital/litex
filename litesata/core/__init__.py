from litesata.common import *
from litesata.core.link import LiteSATALink
from litesata.core.transport import LiteSATATransport
from litesata.core.command import LiteSATACommand

class LiteSATACore(Module):
	def __init__(self, phy, buffer_depth):
		self.link = LiteSATALink(phy, buffer_depth)
		self.transport = LiteSATATransport(self.link)
		self.command = LiteSATACommand(self.transport)
		self.sink, self.source = self.command.sink, self.command.source
