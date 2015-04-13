from migen.fhdl.std import *
from migen.flow.actor import *
from migen.genlib.fifo import SyncFIFO


class Reader(Module):
    def __init__(self, lasmim, fifo_depth=None):
        self.address = Sink([("a", lasmim.aw)])
        self.data = Source([("d", lasmim.dw)])
        self.busy = Signal()

        ###

        if fifo_depth is None:
            fifo_depth = lasmim.req_queue_size + lasmim.read_latency + 2

        # request issuance
        request_enable = Signal()
        request_issued = Signal()

        self.comb += [
            lasmim.we.eq(0),
            lasmim.stb.eq(self.address.stb & request_enable),
            lasmim.adr.eq(self.address.a),
            self.address.ack.eq(lasmim.req_ack & request_enable),
            request_issued.eq(lasmim.stb & lasmim.req_ack)
        ]

        # FIFO reservation level counter
        # incremented when data is planned to be queued
        # decremented when data is dequeued
        data_dequeued = Signal()
        rsv_level = Signal(max=fifo_depth+1)
        self.sync += [
            If(request_issued,
                If(~data_dequeued, rsv_level.eq(rsv_level + 1))
            ).Elif(data_dequeued,
                rsv_level.eq(rsv_level - 1)
            )
        ]
        self.comb += [
            self.busy.eq(rsv_level != 0),
            request_enable.eq(rsv_level != fifo_depth)
        ]

        # FIFO
        fifo = SyncFIFO(lasmim.dw, fifo_depth)
        self.submodules += fifo

        self.comb += [
            fifo.din.eq(lasmim.dat_r),
            fifo.we.eq(lasmim.dat_r_ack),

            self.data.stb.eq(fifo.readable),
            fifo.re.eq(self.data.ack),
            self.data.d.eq(fifo.dout),
            data_dequeued.eq(self.data.stb & self.data.ack)
        ]


class Writer(Module):
    def __init__(self, lasmim, fifo_depth=None):
        self.address_data = Sink([("a", lasmim.aw), ("d", lasmim.dw)])
        self.busy = Signal()

        ###

        if fifo_depth is None:
            fifo_depth = lasmim.req_queue_size + lasmim.write_latency + 2

        fifo = SyncFIFO(lasmim.dw, fifo_depth)
        self.submodules += fifo

        self.comb += [
            lasmim.we.eq(1),
            lasmim.stb.eq(fifo.writable & self.address_data.stb),
            lasmim.adr.eq(self.address_data.a),
            self.address_data.ack.eq(fifo.writable & lasmim.req_ack),
            fifo.we.eq(self.address_data.stb & lasmim.req_ack),
            fifo.din.eq(self.address_data.d)
        ]

        self.comb += [
            If(lasmim.dat_w_ack,
                fifo.re.eq(1),
                lasmim.dat_we.eq(2**(lasmim.dw//8)-1),
                lasmim.dat_w.eq(fifo.dout)
            ),
            self.busy.eq(fifo.readable)
        ]
