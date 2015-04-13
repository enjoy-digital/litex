import unittest

from migen.fhdl.std import *
from migen.flow.actor import *
from migen.flow.transactions import *
from migen.flow.network import *
from migen.actorlib.sim import *

from migen.test.support import SimCase, SimBench


def source_gen(sent):
    for i in range(10):
        yield Token("source", {"value": i})
        sent.append(i)


class SimSource(SimActor):
    def __init__(self):
        self.source = Source([("value", 32)])
        self.sent = []
        SimActor.__init__(self, source_gen(self.sent))


def sink_gen(received):
    while True:
        t = Token("sink")
        yield t
        received.append(t.value["value"])


class SimSink(SimActor):
    def __init__(self):
        self.sink = Sink([("value", 32)])
        self.received = []
        SimActor.__init__(self, sink_gen(self.received))


class SourceSinkCase(SimCase, unittest.TestCase):
    class TestBench(SimBench):
        def __init__(self):
            self.source = SimSource()
            self.sink = SimSink()
            g = DataFlowGraph()
            g.add_connection(self.source, self.sink)
            self.submodules.comp = CompositeActor(g)

        def do_simulation(self, selfp):
            if self.source.token_exchanger.done:
                raise StopSimulation

    def test_equal(self):
        self.run_with(lambda tb, tbp: None)
        self.assertEqual(self.tb.source.sent, self.tb.sink.received)


class SourceSinkDirectCase(SimCase, unittest.TestCase):
    class TestBench(SimBench):
        def __init__(self):
            self.source = SimSource()
            self.sink = SimSink()
            self.submodules += self.source, self.sink
            self.comb += self.sink.sink.connect(self.source.source)

        def do_simulation(self, selfp):
            if self.source.token_exchanger.done:
                raise StopSimulation

    def test_equal(self):
        self.run_with(lambda tb, tbp: None)
        self.assertEqual(self.tb.source.sent, self.tb.sink.received)
