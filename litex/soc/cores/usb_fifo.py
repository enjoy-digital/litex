#
# This file is part of LiteX.
#
# Copyright (c) 2015-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *
from migen.fhdl.specials import Tristate
from migen.genlib.cdc import MultiReg

from litex.soc.interconnect import stream

from litex.build.io import SDRTristate

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
    # FIXME: Check/Improve sampling timings.
    def __init__(self, pads, clk_freq,
        fifo_depth = 64,
        read_time  = 128,
        write_time = 128):
        self.dw     = dw = len(pads.data)
        self.pads   = pads
        self.sink   = stream.Endpoint(phy_description(dw))
        self.source = stream.Endpoint(phy_description(dw))

        # # #

        # Pads Reset.
        # -----------
        pads.oe_n.reset = 1
        pads.rd_n.reset = 1
        pads.wr_n.reset = 1

        # Read CDC/FIFO (FTDI --> SoC).
        # -----------------------------
        self.submodules.read_cdc  = stream.ClockDomainCrossing(phy_description(dw),
            cd_from         = "usb",
            cd_to           = "sys",
            with_common_rst = True
        )
        self.submodules.read_fifo = stream.SyncFIFO(phy_description(dw), fifo_depth)
        self.comb += self.read_cdc.source.connect(self.read_fifo.sink)
        self.comb += self.read_fifo.source.connect(self.source)
        read_fifo_almost_full = (self.read_fifo.level > (fifo_depth - 4))
        read_fifo_almost_full_usb = Signal()
        self.specials += MultiReg(read_fifo_almost_full, read_fifo_almost_full_usb)

        # Write FIFO/CDC (SoC --> FTDI).
        # ------------------------------
        self.submodules.write_fifo = stream.SyncFIFO(phy_description(dw), fifo_depth)
        self.submodules.write_cdc  = stream.ClockDomainCrossing(phy_description(dw),
            cd_from         = "sys",
            cd_to           = "usb",
            with_common_rst = True
        )
        self.comb += self.sink.connect(self.write_fifo.sink)
        self.comb += self.write_fifo.source.connect(self.write_cdc.sink)

        # Read / Write Anti-Starvation.
        # -----------------------------
        read_time_en,  max_read_time  = anti_starvation(self, read_time)
        write_time_en, max_write_time = anti_starvation(self, write_time)

        # Read / Write Detection.
        # -----------------------
        self.wants_write = wants_write = Signal()
        self.wants_read  = wants_read  = Signal()
        self.comb += [
            wants_write.eq(~pads.txe_n & self.write_cdc.source.valid),
            wants_read.eq( ~pads.rxf_n & (self.read_cdc.sink.ready & ~read_fifo_almost_full_usb)),
        ]

        # Data Bus Tristate.
        # ------------------
        self.data_w  = data_w  = Signal(dw)
        self.data_r  = data_r  = Signal(dw)
        self.data_oe = data_oe = Signal()
        for i in range(dw):
            self.specials += SDRTristate(
                io  = pads.data[i],
                o   = data_w[i],
                oe  = data_oe,
                i   = data_r[i],
                clk = ClockSignal("usb")
            )
        if hasattr(pads, "be"):
            for i in range(dw//8):
                self.specials += SDRTristate(
                    io  = pads.be[i],
                    o   = Signal(reset=0b1),
                    oe  = data_oe,
                    i   = Signal(),
                    clk = ClockSignal("usb")
                )

        # Read / Write FSM.
        # -----------------
        fsm = FSM(reset_state="READ")
        fsm = ClockDomainsRenamer("usb")(fsm)
        self.submodules.fsm = fsm
        fsm.act("READ",
            # Arbitration.
            read_time_en.eq(1),
            If(wants_write,
                If(~wants_read | max_read_time,
                    NextState("READ-TO-WRITE")
                )
            ),
            # Control/Data-Path.
            data_oe.eq(0),
            NextValue(pads.oe_n, ~wants_read),
            NextValue(pads.rd_n, pads.oe_n | ~wants_read),
            NextValue(pads.wr_n, 1),
        )
        self.comb += self.read_cdc.sink.data.eq(data_r)
        self.sync.usb += self.read_cdc.sink.valid.eq(~pads.rd_n & ~pads.rxf_n)

        fsm.act("READ-TO-WRITE",
            NextState("WRITE")
        )
        fsm.act("WRITE",
            # Arbitration.
            write_time_en.eq(1),
            If(wants_read,
                If(~wants_write | max_write_time,
                    NextState("WRITE-TO-READ")
                )
            ),
            # Control/Data-Path.
            data_oe.eq(1),
            NextValue(pads.oe_n, 1),
            NextValue(pads.rd_n, 1),
            NextValue(pads.wr_n, ~wants_write),
            #data_w.eq(write_fifo.source.data),
            NextValue(data_w, self.write_cdc.source.data), # FIXME: Add 1 cycle delay.
            self.write_cdc.source.ready.eq(wants_write),
        )
        fsm.act("WRITE-TO-READ",
            NextState("READ")
        )

    def get_litescope_probes(self):
        return  [
            # Physical.
            self.pads.oe_n,
            self.pads.rd_n,
            self.pads.wr_n,
            self.pads.txe_n,
            self.pads.rxf_n,
            self.data_w,
            self.data_r,
            self.data_oe,

            # Core.
            self.wants_write,
            self.wants_read,
            self.fsm,

            # FIFOs.
            self.write_fifo.source,
            self.read_cdc.sink,
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
