from migen import *
from migen.genlib.fsm import FSM, NextState

from misoc.interconnect import wishbone


class NorFlash16(Module):
    def __init__(self, pads, rd_timing, wr_timing):
        self.bus = wishbone.Interface()

        ###

        data = TSTriple(16)
        lsb = Signal()

        self.specials += data.get_tristate(pads.d)
        self.comb += [
            data.oe.eq(pads.oe_n),
            pads.ce_n.eq(0)
        ]

        load_lo = Signal()
        load_hi = Signal()
        store = Signal()

        pads.oe_n.reset, pads.we_n.reset = 1, 1
        self.sync += [
            pads.oe_n.eq(1),
            pads.we_n.eq(1),

            # Register data/address to avoid off-chip glitches
            If(self.bus.cyc & self.bus.stb,
                pads.adr.eq(Cat(lsb, self.bus.adr)),
                If(self.bus.we,
                    # Only 16-bit writes are supported. Assume sel=0011 or 1100.
                    If(self.bus.sel[0],
                        data.o.eq(self.bus.dat_w[:16])
                    ).Else(
                        data.o.eq(self.bus.dat_w[16:])
                    )
                ).Else(
                    pads.oe_n.eq(0)
                )
            ),

            If(load_lo, self.bus.dat_r[:16].eq(data.i)),
            If(load_hi, self.bus.dat_r[16:].eq(data.i)),
            If(store, pads.we_n.eq(0))
        ]

        # Typical timing of the flash chips:
        #  - 110ns address to output
        #  - 50ns write pulse width
        counter = Signal(max=max(rd_timing, wr_timing)+1)
        counter_en = Signal()
        counter_wr_mode = Signal()
        counter_done = Signal()
        self.comb += counter_done.eq(counter == Mux(counter_wr_mode, wr_timing, rd_timing))
        self.sync += If(counter_en & ~counter_done,
                counter.eq(counter + 1)
            ).Else(
                counter.eq(0)
            )

        fsm = FSM()
        self.submodules += fsm

        fsm.act("IDLE",
            If(self.bus.cyc & self.bus.stb,
                If(self.bus.we,
                    NextState("WR")
                ).Else(
                    NextState("RD_HI")
                )
            )
        )
        fsm.act("RD_HI",
            lsb.eq(0),
            counter_en.eq(1),
            If(counter_done,
                load_hi.eq(1),
                NextState("RD_LO")
            )
        )
        fsm.act("RD_LO",
            lsb.eq(1),
            counter_en.eq(1),
            If(counter_done,
                load_lo.eq(1),
                NextState("ACK")
            )
        )
        fsm.act("WR",
            # supported cases: sel=0011 [lsb=1] and sel=1100 [lsb=0]
            lsb.eq(self.bus.sel[0]),
            counter_wr_mode.eq(1),
            counter_en.eq(1),
            store.eq(1),
            If(counter_done, NextState("ACK"))
        )
        fsm.act("ACK",
            self.bus.ack.eq(1),
            NextState("IDLE")
        )
