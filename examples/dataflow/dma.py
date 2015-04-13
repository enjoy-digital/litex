from random import Random

from migen.fhdl.std import *
from migen.flow.network import *
from migen.flow.transactions import *
from migen.actorlib import dma_wishbone
from migen.actorlib.sim import *
from migen.bus import wishbone
from migen.sim.generic import run_simulation


class MyModel:
    def read(self, address):
        return address + 4


class MyModelWB(MyModel, wishbone.TargetModel):
    def __init__(self):
        self.prng = Random(763627)

    def can_ack(self, bus):
        return self.prng.randrange(0, 2)


def adrgen_gen():
    for i in range(10):
        print("Address:  " + hex(i))
        yield Token("address", {"a": i})


class SimAdrGen(SimActor):
    def __init__(self, nbits):
        self.address = Source([("a", nbits)])
        SimActor.__init__(self, adrgen_gen())


def dumper_gen():
    while True:
        t = Token("data", idle_wait=True)
        yield t
        print("Received: " + hex(t.value["d"]))


class SimDumper(SimActor):
    def __init__(self):
        self.data = Sink([("d", 32)])
        SimActor.__init__(self, dumper_gen())


def trgen_gen():
    for i in range(10):
        a = i
        d = i+10
        print("Address: " + hex(a) + " Data: " + hex(d))
        yield Token("address_data", {"a": a, "d": d})


class SimTrGen(SimActor):
    def __init__(self, a_nbits):
        self.address_data = Source([("a", a_nbits), ("d", 32)])
        SimActor.__init__(self, trgen_gen())


class TBWishbone(Module):
    def __init__(self, master):
        self.submodules.peripheral = wishbone.Target(MyModelWB())
        self.submodules.tap = wishbone.Tap(self.peripheral.bus)
        self.submodules.interconnect = wishbone.InterconnectPointToPoint(master.bus,
          self.peripheral.bus)


class TBWishboneReader(TBWishbone):
    def __init__(self):
        self.adrgen = SimAdrGen(30)
        self.reader = dma_wishbone.Reader()
        self.dumper = SimDumper()
        g = DataFlowGraph()
        g.add_connection(self.adrgen, self.reader)
        g.add_connection(self.reader, self.dumper)
        self.submodules.comp = CompositeActor(g)
        TBWishbone.__init__(self, self.reader)


class TBWishboneWriter(TBWishbone):
    def __init__(self):
        self.trgen = SimTrGen(30)
        self.writer = dma_wishbone.Writer()
        g = DataFlowGraph()
        g.add_connection(self.trgen, self.writer)
        self.submodules.comp = CompositeActor(g)
        TBWishbone.__init__(self, self.writer)


def test_wb_reader():
    print("*** Testing Wishbone reader")
    run_simulation(TBWishboneReader(), 100)


def test_wb_writer():
    print("*** Testing Wishbone writer")
    run_simulation(TBWishboneWriter(), 100)

if __name__ == "__main__":
    test_wb_reader()
    test_wb_writer()
