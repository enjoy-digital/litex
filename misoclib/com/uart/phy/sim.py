import os, pty, time

from migen.fhdl.std import *
from migen.flow.actor import Sink, Source

class UARTPHYSim(Module):
    def __init__(self, pads, *args, **kwargs):
        self.sink = Sink([("data", 8)])
        self.source = Source([("data", 8)])

        self.comb += [
            pads.source_stb.eq(self.sink.stb),
            pads.source_data.eq(self.sink.data),
            self.sink.ack.eq(pads.source_ack),

            self.source.stb.eq(pads.sink_stb),
            self.source.data.eq(pads.sink_data),
            pads.sink_ack.eq(self.source.ack)
        ]

        m, s = pty.openpty()
        name = os.ttyname(s)
        print("UART tty: "+name)
        time.sleep(0.5) # pause for user
        f = open("/tmp/simserial", "w")
        f.write(os.ttyname(s))
        f.close()

    def do_exit(self, *args, **kwargs):
        os.remove("/tmp/simserial")
