from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.test.common import *

class PHYDword:
    def __init__(self, dat=0):
        self.dat = dat
        self.start = 1
        self.done = 0


class PHYSource(Module):
    def __init__(self):
        self.source = Source(phy_description(32))

        # # #

        self.dword = PHYDword()

    def send(self, dword):
        self.dword = dword

    def do_simulation(self, selfp):
        selfp.source.stb = 1
        selfp.source.charisk = 0b0000
        for k, v in primitives.items():
            if v == self.dword.dat:
                selfp.source.charisk = 0b0001
        selfp.source.data = self.dword.dat


class PHYSink(Module):
    def __init__(self):
        self.sink = Sink(phy_description(32))

        # # #

        self.dword = PHYDword()

    def receive(self):
        self.dword.done = 0
        while self.dword.done == 0:
            yield

    def do_simulation(self, selfp):
        self.dword.done = 0
        selfp.sink.ack = 1
        if selfp.sink.stb == 1:
            self.dword.done = 1
            self.dword.dat = selfp.sink.data


class PHYLayer(Module):
    def __init__(self):

        self.submodules.rx = PHYSink()
        self.submodules.tx = PHYSource()

        self.source = self.tx.source
        self.sink = self.rx.sink

    def send(self, dword):
        packet = PHYDword(dword)
        self.tx.send(packet)

    def receive(self):
        yield from self.rx.receive()

    def __repr__(self):
        receiving = "{:08x} ".format(self.rx.dword.dat)
        receiving += decode_primitive(self.rx.dword.dat)
        receiving += " "*(16-len(receiving))

        sending = "{:08x} ".format(self.tx.dword.dat)
        sending += decode_primitive(self.tx.dword.dat)
        sending += " "*(16-len(sending))

        return receiving + sending
