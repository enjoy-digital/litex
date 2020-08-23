#
# This file is part of LiteX.
#
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *
from migen.fhdl.specials import Tristate
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect import stream

# Layout/Helpers -----------------------------------------------------------------------------------

def phy_description(dw):
    payload_layout = [("data", dw)]
    return stream.EndpointDescription(payload_layout)


def anti_starvation(module, timeout):
        en = Signal()
        max_time = Signal()
        if timeout:
            t = timeout - 1
            time = Signal(max=t+1)
            module.comb += max_time.eq(time == 0)
            module.sync += If(~en,
                    time.eq(t)
                ).Elif(~max_time,
                    time.eq(time - 1)
                )
        else:
            module.comb += max_time.eq(0)
        return en, max_time

# FT245 Synchronous FIFO Mode ----------------------------------------------------------------------

class FT245PHYSynchronous(Module):
    def __init__(self, pads, clk_freq,
                 fifo_depth = 8,
                 read_time  = 128,
                 write_time = 128):
        dw = len(pads.data)

        # read fifo (FTDI --> SoC)
        read_fifo   = stream.AsyncFIFO(phy_description(dw), fifo_depth)
        read_fifo   = ClockDomainsRenamer({"write": "usb", "read": "sys"})(read_fifo)
        read_buffer = stream.SyncFIFO(phy_description(dw), 4)
        read_buffer = ClockDomainsRenamer("usb")(read_buffer)
        self.comb += read_buffer.source.connect(read_fifo.sink)
        self.submodules += read_fifo, read_buffer

        # write fifo (SoC --> FTDI)
        write_fifo = stream.AsyncFIFO(phy_description(dw), fifo_depth)
        write_fifo = ClockDomainsRenamer({"write": "sys", "read": "usb"})(write_fifo)
        self.submodules += write_fifo

        # sink / source interfaces
        self.sink   = write_fifo.sink
        self.source = read_fifo.source

        # read / write arbitration
        wants_write = Signal()
        wants_read  = Signal()

        txe_n = Signal()
        rxf_n = Signal()

        self.comb += [
            txe_n.eq(pads.txe_n),
            rxf_n.eq(pads.rxf_n),
            wants_write.eq(~txe_n & write_fifo.source.valid),
            wants_read.eq(~rxf_n & read_fifo.sink.ready),
        ]

        read_time_en,  max_read_time  = anti_starvation(self, read_time)
        write_time_en, max_write_time = anti_starvation(self, write_time)

        data_w_accepted = Signal(reset=1)

        fsm = FSM(reset_state="READ")
        self.submodules += ClockDomainsRenamer("usb")(fsm)

        fsm.act("READ",
            read_time_en.eq(1),
            If(wants_write,
                If(~wants_read | max_read_time,
                    NextState("RTW")
                )
            )
        )
        fsm.act("RTW",
            NextState("WRITE")
        )
        fsm.act("WRITE",
            write_time_en.eq(1),
            If(wants_read,
                If(~wants_write | max_write_time,
                    NextState("WTR")
                )
            ),
            write_fifo.source.ready.eq(wants_write & data_w_accepted)
        )
        fsm.act("WTR",
            NextState("READ")
        )

        # databus tristate
        data_w  = Signal(dw)
        data_r  = Signal(dw)
        data_oe = Signal()
        self.specials += Tristate(pads.data, data_w, data_oe, data_r)

        # read / write actions
        pads.oe_n.reset = 1
        pads.rd_n.reset = 1
        pads.wr_n.reset = 1

        self.sync.usb += [
            If(fsm.ongoing("READ"),
                data_oe.eq(0),

                pads.oe_n.eq(0),
                pads.rd_n.eq(~wants_read),
                pads.wr_n.eq(1)
            ).Elif(fsm.ongoing("WRITE"),
                data_oe.eq(1),

                pads.oe_n.eq(1),
                pads.rd_n.eq(1),
                pads.wr_n.eq(~wants_write),

                data_w_accepted.eq(~txe_n)
            ).Else(
                data_oe.eq(1),

                pads.oe_n.eq(~fsm.ongoing("WTR")),
                pads.rd_n.eq(1),
                pads.wr_n.eq(1)
            ),
            read_buffer.sink.valid.eq(~pads.rd_n & ~rxf_n),
            read_buffer.sink.data.eq(data_r),
            If(~txe_n & data_w_accepted,
                data_w.eq(write_fifo.source.data)
            )
        ]

# FT245 Asynchronous FIFO Mode ---------------------------------------------------------------------

class FT245PHYAsynchronous(Module):
    def __init__(self, pads, clk_freq,
                 fifo_depth = 8,
                 read_time  = 128,
                 write_time = 128):
        dw = len(pads.data)
        self.clk_freq = clk_freq

        # timings
        tRD          = self.ns(30) # RD# active pulse width (t4)
        tRDDataSetup = self.ns(14) # RD# to DATA (t3)
        tWRDataSetup = self.ns(5)  # DATA to WR# active setup time (t8)
        tWR          = self.ns(30) # WR# active pulse width (t10)
        tMultiReg    = 2

        # read fifo (FTDI --> SoC)
        read_fifo = stream.SyncFIFO(phy_description(dw), fifo_depth)

        # write fifo (SoC --> FTDI)
        write_fifo = stream.SyncFIFO(phy_description(dw), fifo_depth)

        self.submodules += read_fifo, write_fifo

        # sink / source interfaces
        self.sink   = write_fifo.sink
        self.source = read_fifo.source

        # read / write arbitration
        wants_write = Signal()
        wants_read  = Signal()

        txe_n = Signal()
        rxf_n = Signal()

        self.specials += [
            MultiReg(pads.txe_n, txe_n),
            MultiReg(pads.rxf_n, rxf_n)
        ]

        self.comb += [
            wants_write.eq(~txe_n & write_fifo.source.valid),
            wants_read.eq(~rxf_n & read_fifo.sink.ready),
        ]

        read_time_en,  max_read_time  = anti_starvation(self, read_time)
        write_time_en, max_write_time = anti_starvation(self, write_time)

        fsm = FSM(reset_state="READ")
        self.submodules += fsm

        read_done = Signal()
        write_done = Signal()
        commuting = Signal()

        fsm.act("READ",
            read_time_en.eq(1),
            If(wants_write & read_done,
                If(~wants_read | max_read_time,
                    commuting.eq(1),
                    NextState("RTW")
                )
            )
        )
        fsm.act("RTW",
            NextState("WRITE")
        )
        fsm.act("WRITE",
            write_time_en.eq(1),
            If(wants_read & write_done,
                If(~wants_write | max_write_time,
                    commuting.eq(1),
                    NextState("WTR")
                )
            )
        )
        fsm.act("WTR",
            NextState("READ")
        )

        # databus tristate
        data_w       = Signal(dw)
        data_r_async = Signal(dw)
        data_r       = Signal(dw)
        data_oe      = Signal()
        self.specials += [
            Tristate(pads.data, data_w, data_oe, data_r_async),
            MultiReg(data_r_async, data_r)
        ]

        # read actions
        pads.rd_n.reset = 1

        read_fsm = FSM(reset_state="IDLE")
        self.submodules += read_fsm
        read_counter = Signal(8)
        read_fsm.act("IDLE",
            read_done.eq(1),
            NextValue(read_counter, 0),
            If(fsm.ongoing("READ") & wants_read,
                If(~commuting,
                    NextState("PULSE_RD_N")
                )
            )
        )
        read_fsm.act("PULSE_RD_N",
            pads.rd_n.eq(0),
            NextValue(read_counter, read_counter + 1),
            If(read_counter == max(tRD-1, tRDDataSetup + tMultiReg -1),
                NextState("ACQUIRE_DATA")
            )
        )
        read_fsm.act("ACQUIRE_DATA",
            read_fifo.sink.valid.eq(1),
            read_fifo.sink.data.eq(data_r),
            NextState("WAIT_RXF_N")
        )
        read_fsm.act("WAIT_RXF_N",
            If(rxf_n,
                NextState("IDLE")
            )
        )

        # write actions
        pads.wr_n.reset = 1

        write_fsm = FSM(reset_state="IDLE")
        self.submodules += write_fsm
        write_counter = Signal(8)
        write_fsm.act("IDLE",
            write_done.eq(1),
            NextValue(write_counter, 0),
            If(fsm.ongoing("WRITE") & wants_write,
                If(~commuting,
                    NextState("SET_DATA")
                )
            )
        )
        write_fsm.act("SET_DATA",
            data_oe.eq(1),
            data_w.eq(write_fifo.source.data),
            NextValue(write_counter, write_counter + 1),
            If(write_counter == (tWRDataSetup-1),
                NextValue(write_counter, 0),
                NextState("PULSE_WR_N")
            )
        )
        write_fsm.act("PULSE_WR_N",
            data_oe.eq(1),
            data_w.eq(write_fifo.source.data),
            pads.wr_n.eq(0),
            NextValue(write_counter, write_counter + 1),
            If(write_counter == (tWR-1),
                NextState("WAIT_TXE_N")
            )
        )
        write_fsm.act("WAIT_TXE_N",
            If(txe_n,
                write_fifo.source.ready.eq(1),
                NextState("IDLE")
            )
        )

    def ns(self, t, margin=True):
        clk_period_ns = 1e9/self.clk_freq
        if margin:
            t += clk_period_ns/2
        return math.ceil(t/clk_period_ns)

# FT245 FIFO Mode PHY (Automatic Asynchronous/Synchronous selection) -------------------------------

def FT245PHY(pads, *args, **kwargs):
    # autodetect PHY
    if hasattr(pads, "clkout"):
        return FT245PHYSynchronous(pads, *args, **kwargs)
    else:
        return FT245PHYAsynchronous(pads, *args, **kwargs)
