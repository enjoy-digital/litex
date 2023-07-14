#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import MultiReg

from litex.gen import *

from litex.soc.interconnect import wishbone


class EMIF(LiteXModule):
    """External Memory Interface core

    Provides a simple EMIF to Wishbone Master bridge.
    """
    def __init__(self, pads):
        self.bus = bus = wishbone.Interface()

        # # #

        # Resynchronization ------------------------------------------------------------------------
        cs_n   = Signal(reset=1)
        oe_n   = Signal(reset=1)
        we_n   = Signal(reset=1)
        ba     = Signal(2)
        addr   = Signal(22)
        dqm_n  = Signal(2)
        data   = self.add_tristate(pads.data) if not hasattr(pads.data, "oe") else pads.data
        data_i = Signal(16)
        self.specials += [
            MultiReg(pads.cs_n, cs_n),
            MultiReg(pads.oe_n, oe_n),
            MultiReg(pads.we_n, we_n),
            MultiReg(pads.ba,   ba),
            MultiReg(pads.addr, addr),
            MultiReg(data.i,    data_i),
        ]

        # EMIF <--> Wishbone -----------------------------------------------------------------------
        access = Signal()
        we_n_d = Signal()
        oe_n_d = Signal()
        self.sync += [
            we_n_d.eq(we_n),
            oe_n_d.eq(oe_n),
            If(~we_n & we_n_d,
                access.eq(1)
            ).Elif(~oe_n & oe_n_d,
                access.eq(1)
            ).Elif(bus.ack,
                access.eq(0)
            )
        ]
        self.comb += [
            bus.stb.eq(~cs_n  & access),
            bus.cyc.eq(~cs_n  & access),
            bus.we.eq(~we_n),
            bus.adr.eq(addr),
            data.oe.eq(~oe_n),
            If(ba[1],
                bus.dat_w[:16].eq(data_i),
                bus.sel[:2].eq(~dqm_n)
            ).Else(
                bus.dat_w[16:].eq(data_i),
                bus.sel[2:].eq(~dqm_n)
            )
        ]
        self.sync += [
            If(bus.ack,
                If(ba[1],
                    data.o.eq(bus.dat_r[:16])
                ).Else(
                    data.o.eq(bus.dat_r[16:])
                )
            )
        ]

    def add_tristate(self, pad):
        t = TSTriple(len(pad))
        self.specials += t.get_tristate(pad)
        return t


class EMIF16To32Adapter(LiteXModule):
    def __init__(self, emif):
        self.bus = bus = wishbone.Interface()

        # # #

        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(emif.bus.stb & emif.bus.cyc,
                If(emif.bus.we,
                    NextState("WRITE0")
                ).Else(
                    NextState("READ")
                )
            )
        )
        emif_bus_dat_w = Signal(32)
        fsm.act("WRITE0",
            emif.bus.ack.eq(1),
            If(emif.bus.sel[0],
                NextValue(emif_bus_dat_w[8*0:8*1], emif.bus.dat_w[8*0:8*1])
            ),
            If(emif.bus.sel[1],
                NextValue(emif_bus_dat_w[8*1:8*2], emif.bus.dat_w[8*1:8*2])
            ),
            If(emif.bus.sel[2],
                NextValue(emif_bus_dat_w[8*2:8*3], emif.bus.dat_w[8*2:8*3])
            ),
            If(emif.bus.sel[3],
                NextValue(emif_bus_dat_w[8*3:8*4], emif.bus.dat_w[8*3:8*4])
            ),
            NextState("WRITE1"),
        )
        fsm.act("WRITE1",
            bus.stb.eq(emif.bus.stb & emif.bus.cyc),
            bus.we.eq(1),
            bus.cyc.eq(emif.bus.stb & emif.bus.cyc),
            bus.adr.eq(emif.bus.adr),
            bus.sel.eq(0b1111),
            bus.dat_w.eq(emif_bus_dat_w),
            If(emif.bus.sel[0],
                bus.dat_w[8*0:8*1].eq(emif.bus.dat_w[8*0:8*1])
            ),
            If(emif.bus.sel[1],
                bus.dat_w[8*1:8*2].eq(emif.bus.dat_w[8*1:8*2])
            ),
            If(emif.bus.sel[2],
                bus.dat_w[8*2:8*3].eq(emif.bus.dat_w[8*2:8*3])
            ),
            If(emif.bus.sel[3],
                bus.dat_w[8*3:8*4].eq(emif.bus.dat_w[8*3:8*4])
            ),
            If(bus.stb & bus.ack,
                emif.bus.ack.eq(1),
                NextState("IDLE")
            )
        )
        fsm.act("READ",
            bus.stb.eq(1),
            bus.we.eq(0),
            bus.cyc.eq(1),
            bus.adr.eq(emif.bus.adr),
            If(bus.ack,
                emif.bus.ack.eq(1),
                emif.bus.dat_r.eq(bus.dat_r),
                NextState("IDLE")
            )
        )
