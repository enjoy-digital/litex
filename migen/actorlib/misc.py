from migen.fhdl.std import *
from migen.genlib.record import *
from migen.genlib.fsm import *
from migen.flow.actor import *
from migen.flow.plumbing import Buffer


# Generates integers from start to maximum-1
class IntSequence(Module):
    def __init__(self, nbits, offsetbits=0, step=1):
        parameters_layout = [("maximum", nbits)]
        if offsetbits:
            parameters_layout.append(("offset", offsetbits))

        self.parameters = Sink(parameters_layout)
        self.source = Source([("value", max(nbits, offsetbits))])
        self.busy = Signal()

        ###

        load = Signal()
        ce = Signal()
        last = Signal()

        maximum = Signal(nbits)
        if offsetbits:
            offset = Signal(offsetbits)
        counter = Signal(nbits)

        if step > 1:
            self.comb += last.eq(counter + step >= maximum)
        else:
            self.comb += last.eq(counter + 1 == maximum)
        self.sync += [
            If(load,
                counter.eq(0),
                maximum.eq(self.parameters.maximum),
                offset.eq(self.parameters.offset) if offsetbits else None
            ).Elif(ce,
                If(last,
                    counter.eq(0)
                ).Else(
                    counter.eq(counter + step)
                )
            )
        ]
        if offsetbits:
            self.comb += self.source.value.eq(counter + offset)
        else:
            self.comb += self.source.value.eq(counter)

        fsm = FSM()
        self.submodules += fsm
        fsm.act("IDLE",
            load.eq(1),
            self.parameters.ack.eq(1),
            If(self.parameters.stb, NextState("ACTIVE"))
        )
        fsm.act("ACTIVE",
            self.busy.eq(1),
            self.source.stb.eq(1),
            If(self.source.ack,
                ce.eq(1),
                If(last, NextState("IDLE"))
            )
        )

# Add buffers on Endpoints (can be used to improve timings)
class BufferizeEndpoints(ModuleTransformer):
    def __init__(self, *names):
        self.names = names

    def transform_instance(self, submodule):
        endpoints = get_endpoints(submodule)
        sinks = {}
        sources = {}
        for name, endpoint in endpoints.items():
            if not self.names or name in self.names:
                if isinstance(endpoint, Sink):
                    sinks.update({name: endpoint})
                elif isinstance(endpoint, Source):
                    sources.update({name: endpoint})

        # add buffer on sinks
        for name, sink in sinks.items():
            buf = Buffer(sink.description)
            submodule.submodules += buf
            setattr(submodule, name, buf.d)
            submodule.comb += Record.connect(buf.q, sink)

        # add buffer on sources
        for name, source in sources.items():
            buf = Buffer(source.description)
            submodule.submodules += buf
            submodule.comb += Record.connect(source, buf.d)
            setattr(submodule, name, buf.q)
