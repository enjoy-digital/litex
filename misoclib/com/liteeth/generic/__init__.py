from migen.fhdl.decorators import ModuleTransformer
from misoclib.com.liteeth.common import *


# Generic classes
class Port:
    def connect(self, port):
        r = [
            Record.connect(self.source, port.sink),
            Record.connect(port.source, self.sink)
        ]
        return r
