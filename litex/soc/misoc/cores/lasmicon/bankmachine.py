from migen import *
from migen.genlib.roundrobin import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib.fifo import SyncFIFO

from misoc.cores.lasmicon.multiplexer import *


class _AddressSlicer:
    def __init__(self, colbits, address_align):
        self.colbits = colbits
        self.address_align = address_align

    def row(self, address):
        split = self.colbits - self.address_align
        if isinstance(address, int):
            return address >> split
        else:
            return address[split:]

    def col(self, address):
        split = self.colbits - self.address_align
        if isinstance(address, int):
            return (address & (2**split - 1)) << self.address_align
        else:
            return Cat(Replicate(0, self.address_align), address[:split])


class BankMachine(Module):
    def __init__(self, geom_settings, timing_settings, controller_settings, address_align, bankn, req):
        self.refresh_req = Signal()
        self.refresh_gnt = Signal()
        self.cmd = CommandRequestRW(geom_settings.addressbits, geom_settings.bankbits)

        ###

        # Request FIFO
        layout = [("we", 1), ("adr", len(req.adr))]
        req_in = Record(layout)
        reqf = Record(layout)
        self.submodules.req_fifo = SyncFIFO(layout_len(layout),
                                            controller_settings.req_queue_size)
        self.comb += [
            self.req_fifo.din.eq(req_in.raw_bits()),
            reqf.raw_bits().eq(self.req_fifo.dout)
        ]
        self.comb += [
            req_in.we.eq(req.we),
            req_in.adr.eq(req.adr),
            self.req_fifo.we.eq(req.stb),
            req.req_ack.eq(self.req_fifo.writable),

            self.req_fifo.re.eq(req.dat_w_ack | req.dat_r_ack),
            req.lock.eq(self.req_fifo.readable)
        ]

        slicer = _AddressSlicer(geom_settings.colbits, address_align)

        # Row tracking
        has_openrow = Signal()
        openrow = Signal(geom_settings.rowbits)
        hit = Signal()
        self.comb += hit.eq(openrow == slicer.row(reqf.adr))
        track_open = Signal()
        track_close = Signal()
        self.sync += [
            If(track_open,
                has_openrow.eq(1),
                openrow.eq(slicer.row(reqf.adr))
            ),
            If(track_close,
                has_openrow.eq(0)
            )
        ]

        # Address generation
        s_row_adr = Signal()
        self.comb += [
            self.cmd.ba.eq(bankn),
            If(s_row_adr,
                self.cmd.a.eq(slicer.row(reqf.adr))
            ).Else(
                self.cmd.a.eq(slicer.col(reqf.adr))
            )
        ]

        # Respect write-to-precharge specification
        precharge_ok = Signal()
        t_unsafe_precharge = 2 + timing_settings.tWR - 1
        unsafe_precharge_count = Signal(max=t_unsafe_precharge+1)
        self.comb += precharge_ok.eq(unsafe_precharge_count == 0)
        self.sync += [
            If(self.cmd.stb & self.cmd.ack & self.cmd.is_write,
                unsafe_precharge_count.eq(t_unsafe_precharge)
            ).Elif(~precharge_ok,
                unsafe_precharge_count.eq(unsafe_precharge_count-1)
            )
        ]

        # Control and command generation FSM
        fsm = FSM()
        self.submodules += fsm
        fsm.act("REGULAR",
            If(self.refresh_req,
                NextState("REFRESH")
            ).Elif(self.req_fifo.readable,
                If(has_openrow,
                    If(hit,
                        # NB: write-to-read specification is enforced by multiplexer
                        self.cmd.stb.eq(1),
                        req.dat_w_ack.eq(self.cmd.ack & reqf.we),
                        req.dat_r_ack.eq(self.cmd.ack & ~reqf.we),
                        self.cmd.is_read.eq(~reqf.we),
                        self.cmd.is_write.eq(reqf.we),
                        self.cmd.cas_n.eq(0),
                        self.cmd.we_n.eq(~reqf.we)
                    ).Else(
                        NextState("PRECHARGE")
                    )
                ).Else(
                    NextState("ACTIVATE")
                )
            )
        )
        fsm.act("PRECHARGE",
            # Notes:
            # 1. we are presenting the column address, A10 is always low
            # 2. since we always go to the ACTIVATE state, we do not need
            # to assert track_close.
            If(precharge_ok,
                self.cmd.stb.eq(1),
                If(self.cmd.ack, NextState("TRP")),
                self.cmd.ras_n.eq(0),
                self.cmd.we_n.eq(0),
                self.cmd.is_cmd.eq(1)
            )
        )
        fsm.act("ACTIVATE",
            s_row_adr.eq(1),
            track_open.eq(1),
            self.cmd.stb.eq(1),
            self.cmd.is_cmd.eq(1),
            If(self.cmd.ack, NextState("TRCD")),
            self.cmd.ras_n.eq(0)
        )
        fsm.act("REFRESH",
            self.refresh_gnt.eq(precharge_ok),
            track_close.eq(1),
            self.cmd.is_cmd.eq(1),
            If(~self.refresh_req, NextState("REGULAR"))
        )
        fsm.delayed_enter("TRP", "ACTIVATE", timing_settings.tRP-1)
        fsm.delayed_enter("TRCD", "REGULAR", timing_settings.tRCD-1)
