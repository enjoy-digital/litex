from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.core.link import LiteSATALink
from misoclib.mem.litesata.core.transport import LiteSATATransport
from misoclib.mem.litesata.core.command import LiteSATACommand

class LiteSATACore(Module):
    def __init__(self, phy, buffer_depth):
        self.submodules.link = LiteSATALink(phy, buffer_depth)
        self.submodules.transport = LiteSATATransport(self.link)
        self.submodules.command = LiteSATACommand(self.transport)
        self.sink, self.source = self.command.sink, self.command.source
