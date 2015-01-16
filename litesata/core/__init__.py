from litesata.common import *
from litesata.core.link import LiteSATALink
from litesata.core.transport import LiteSATATransport
from litesata.core.command import LiteSATACommand

class LiteSATACore(Module):
	def __init__(self, phy):
		self.link = LiteSATALink(phy)
		self.transport = LiteSATATransport(self.link)
		self.command = LiteSATACommand(self.transport)
		self.sink, self.source = self.command.sink, self.command.source
