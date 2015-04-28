from collections import OrderedDict

from misoclib.com.liteeth.common import *

class LiteEthCrossbar(Module):
    def __init__(self, master_port, dispatch_param):
        self.users = OrderedDict()
        self.master = master_port(8)
        self.dispatch_param = dispatch_param

    # overload this in derived classes
    def get_port(self, *args, **kwargs):
        pass

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
