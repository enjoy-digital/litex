from collections import OrderedDict

from misoclib.com.liteusb.common import *

class LiteUSBCrossbar(Module):
    def __init__(self):
        self.users = OrderedDict()
        self.master = LiteUSBMasterPort(8)
        self.dispatch_param = "dst"

    def get_port(self, dst):
        port = LiteUSBUserPort(8, dst)
        if dst in self.users.keys():
            raise ValueError("Destination {0:#x} already assigned".format(dst))
        self.users[dst] = port
        return port

    def do_finalize(self):
        # TX arbitrate
        sinks = [port.sink for port in self.users.values()]
        self.submodules.arbiter = Arbiter(sinks, self.master.source)

        # RX dispatch
        sources = [port.source for port in self.users.values()]
        self.submodules.dispatcher = Dispatcher(self.master.sink,
                                                sources,
                                                one_hot=True)
        cases = {}
        cases["default"] = self.dispatcher.sel.eq(0)
        for i, (k, v) in enumerate(self.users.items()):
            cases[k] = self.dispatcher.sel.eq(2**i)
        self.comb += \
            Case(getattr(self.master.sink, self.dispatch_param), cases)
