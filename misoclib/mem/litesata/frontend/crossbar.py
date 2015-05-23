from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.frontend.common import *
from misoclib.mem.litesata.frontend.arbiter import LiteSATAArbiter


class LiteSATACrossbar(Module):
    def __init__(self, controller):
        self.dw = flen(controller.sink.data)
        self.users = []
        self.master = LiteSATAMasterPort(self.dw)
        self.comb += [
            self.master.source.connect(controller.sink),
            controller.source.connect(self.master.sink)
        ]

    def get_port(self):
        port = LiteSATAUserPort(self.dw)
        self.users += [port]
        return port

    def get_ports(self, n):
        ports = []
        for i in range(n):
            ports.append(self.get_port())
        return ports

    def do_finalize(self):
        arbiter = LiteSATAArbiter(self.users, self.master)
        self.submodules += arbiter
