from misoclib.mem.litesata.common import *

class LiteSATAMasterPort:
    def __init__(self, dw):
        self.source = Source(command_tx_description(dw))
        self.sink = Sink(command_rx_description(dw))

    def connect(self, slave):
        return [
            Record.connect(self.source, slave.sink),
            Record.connect(slave.source, self.sink)
        ]

class LiteSATASlavePort:
    def __init__(self, dw):
        self.sink = Sink(command_tx_description(dw))
        self.source = Source(command_rx_description(dw))

    def connect(self, master):
        return [
            Record.connect(self.sink, master.source),
            Record.connect(master.sink, self.source)
        ]

class LiteSATAUserPort(LiteSATASlavePort):
    def __init__(self, dw):
        LiteSATASlavePort.__init__(self, dw)
