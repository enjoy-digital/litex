#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *
from migen.fhdl.specials import Tristate

from litex.gen import *
from litex.gen.genlib.misc import WaitTimer

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import CSRField, CSRStatus

# APS256XXN-OBx9, Rev. 1.2: https://www.apmemory.com/tw/downloadFiles/0325021716tb786912
# APS512XXN-OBx9, Rev. 1.0: https://www.apmemory.com/en/downloadFiles/1025112710dj710649

# AP Memory PHY ------------------------------------------------------------------------------------

class APMemoryPHY(LiteXModule):
    """Low-speed x16 OPI/HPI PHY for AP Memory's standard-temperature OB9 devices.

    CLK runs at sys/8. Data changes two sys cycles before/after each CLK edge. Read data is
    sampled one sys cycle after the first DQS synchronizer stage; each byte lane follows its own
    DQS. This requires a 50..100MHz system clock and bounded FPGA I/O delays: 5ns for inputs,
    CLK and CE#, and 8ns for DQ/DM outputs (including tristate enables). Board signal skew must
    stay below 1ns. The platform must constrain these paths. At the end of a transaction, CE#
    and the output enables are released one sys cycle after the final falling CLK edge.
    It does not use the devices' maximum clock rate or support the 1us extended-temperature tCEM.
    """
    def __init__(self, pads, sys_clk_freq):
        if not 50e6 <= sys_clk_freq <= 100e6:
            raise ValueError("APMemoryPHY requires a 50..100MHz system clock.")

        self.start   = Signal()
        self.cmd     = Signal(8)
        self.address = Signal(32)
        self.dat_w   = Signal(32)
        self.sel     = Signal(4)
        self.done    = Signal()
        self.error   = Signal()
        self.dat_r   = Signal(32)

        # # #

        # Pads -------------------------------------------------------------------------------------
        # Pads can also be simulation records with o/oe/i fields.
        dq_o   = Signal(16)
        dq_oe  = Signal(2)
        dq_i   = Signal(16)
        dqs_o  = Signal(2)
        dqs_oe = Signal()
        dqs_i  = Signal(2)
        if hasattr(pads.dq, "o"):
            self.comb += [
                pads.dq.o.eq(dq_o),
                pads.dq.oe.eq(dq_oe),
                dq_i.eq(pads.dq.i),
            ]
            self.comb += [
                pads.dqs.o.eq(dqs_o),
                pads.dqs.oe.eq(dqs_oe),
                dqs_i.eq(pads.dqs.i),
            ]
        else:
            for lane in range(2):
                self.specials += Tristate(pads.dq[8*lane:8*(lane + 1)],
                    o  = dq_o[8*lane:8*(lane + 1)],
                    oe = dq_oe[lane],
                    i  = dq_i[8*lane:8*(lane + 1)],
                )
            self.specials += Tristate(pads.dqs,
                o  = dqs_o,
                oe = dqs_oe,
                i  = dqs_i,
            )

        # Read Sampling ----------------------------------------------------------------------------
        # DQ is stable when a synchronized DQS transition qualifies its later sample.
        dq_sample  = Signal(16)
        dqs_meta   = Signal(2)
        dqs_sample = Signal(2)
        dqs_last   = Signal(2)
        # Keep the sampling stages explicit: their input paths need a maximum delay constraint,
        # whereas MultiReg would mark them as false paths in the platform toolchain.
        for signal in [dq_sample, dqs_meta, dqs_sample]:
            signal.attr.update({"async_reg", "no_shreg_extract", "no_retiming"})
        self.sync += [
            dq_sample.eq(dq_i),
            dqs_meta.eq(dqs_i),
            dqs_sample.eq(dqs_meta),
            dqs_last.eq(dqs_sample),
        ]

        cmd      = Signal(8)
        address  = Signal(32)
        dat_w    = Signal(32)
        sel      = Signal(4)
        phase    = Signal(2)
        edge     = Signal(7)
        active   = Signal()
        timeout  = Signal(max=math.ceil(3e-6*sys_clk_freq) + 1)
        armed    = Signal(2)
        counts   = [Signal(2) for _ in range(2)]
        received = Signal()
        self.comb += received.eq((counts[0] == 2) & ((cmd == 0x40) | (counts[1] == 2)))

        for lane, count in enumerate(counts):
            self.sync += If(~active,
                armed[lane].eq(0),
                count.eq(0),
            ).Elif(~cmd[7] & (edge >= 6),
                If(~dqs_sample[lane],
                    armed[lane].eq(1),
                ),
                If(armed[lane] & (count < 2) & (dqs_sample[lane] != dqs_last[lane]),
                    # The first beat is a rising edge, the second a falling edge.
                    If(dqs_sample[lane] == (count == 0),
                        Case(count, {
                            n: self.dat_r[16*n + 8*lane:16*n + 8*(lane + 1)].eq(
                                dq_sample[8*lane:8*(lane + 1)])
                            for n in range(2)
                        }),
                        count.eq(count + 1),
                    )
                )
            )

        # Write Data -------------------------------------------------------------------------------
        # Command and address always use DQ[7:0], including after enabling x16 mode.
        tx_data = Signal(16)
        tx_oe   = Signal(2)
        tx_mask = Signal(2)
        tx_dm   = Signal()
        self.comb += [
            If(edge < 6,
                tx_oe.eq(1),
                Case(edge, {
                    0: tx_data.eq(cmd),
                    1: tx_data.eq(cmd),
                    2: tx_data.eq(address[24:32]),
                    3: tx_data.eq(address[16:24]),
                    4: tx_data.eq(address[8:16]),
                    5: tx_data.eq(address[0:8]),
                }),
            ).Elif(cmd == 0xc0,
                # Register writes have one cycle of latency (counting from A1).
                tx_oe.eq(1),
                tx_data.eq(dat_w[:8]),
                tx_dm.eq(1),
            ).Elif((cmd == 0xa0) & (edge >= 14),
                # Reset MR4 selects write latency 5. Each bus word is two x16 beats.
                tx_oe.eq(3),
                tx_dm.eq(1),
                If(edge[0],
                    tx_data.eq(dat_w[16:32]),
                    tx_mask.eq(~sel[2:4]),
                ).Else(
                    tx_data.eq(dat_w[0:16]),
                    tx_mask.eq(~sel[0:2]),
                )
            )
        ]

        # Transfer FSM -----------------------------------------------------------------------------
        self.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(self.start,
                NextValue(cmd,        self.cmd),
                NextValue(address,    self.address),
                NextValue(dat_w,      self.dat_w),
                NextValue(sel,        self.sel),
                NextValue(self.error, 0),
                NextValue(pads.cs_n,  0),
                NextValue(phase,      0),
                NextValue(edge,       0),
                NextValue(timeout,    0),
                NextState("TRANSFER"),
            )
        )
        fsm.act("TRANSFER",
            active.eq(1),
            NextValue(phase, phase + 1),
            If(timeout != math.ceil(3e-6*sys_clk_freq),
                NextValue(timeout, timeout + 1),
            ),
            If(phase == 0,
                NextValue(dq_o,   tx_data),
                NextValue(dq_oe,  tx_oe),
                NextValue(dqs_o,  tx_mask),
                NextValue(dqs_oe, tx_dm),
            ),
            If(phase == 2,
                NextValue(pads.clk, ~pads.clk),
            ),
            If(phase == 3,
                NextValue(edge, edge + 1),
                # Finish on a falling edge and leave CLK low between transactions.
                If(edge[0] & (
                    ((cmd == 0xff) & (edge == 7)) |
                    ((cmd == 0xc0) & (edge == 7)) |
                    ((cmd == 0xa0) & (edge == 15)) |
                    (~cmd[7] & received) |
                    (timeout == math.ceil(3e-6*sys_clk_freq))),
                    NextValue(self.error, ~cmd[7] & ~received),
                    NextValue(pads.cs_n, 1),
                    NextValue(dq_oe,  0),
                    NextValue(dqs_oe, 0),
                    NextValue(phase,  0),
                    NextState("RECOVER"),
                )
            )
        )
        fsm.act("RECOVER",
            NextValue(phase, phase + 1),
            If(phase == 3,
                self.done.eq(1),
                NextState("IDLE"),
            )
        )
        pads.cs_n.reset = 1
# AP Memory Controller -----------------------------------------------------------------------------

class APMemory(LiteXModule):
    """32-bit Wishbone controller for APS256XXN/APS512XXN-OB9 PSRAM in x16 mode.

    Initialization uses Global Reset, enables x16 through MR8, and checks MR8/vendor/density.
    The default read/write latency codes are retained. Reads follow DQS (variable latency).
    Each access transfers one 32-bit word, with per-byte write masks and a bounded CE# low time.
    """
    def __init__(self, pads, sys_clk_freq, size=32*1024*1024, with_csr=True):
        if size not in [32*1024*1024, 64*1024*1024]:
            raise ValueError("APMemory supports 32MiB APS256XXN and 64MiB APS512XXN devices.")
        self.bus = bus = wishbone.Interface(data_width=32, address_width=32, addressing="word")

        self.ready      = Signal()
        self.init_error = Signal()
        self.timeout    = Signal()
        self.id         = Signal(16)

        # # #

        # PHY / Timers -----------------------------------------------------------------------------
        self.phy     = phy     = APMemoryPHY(pads, sys_clk_freq)
        self.powerup = powerup = WaitTimer(math.ceil(150e-6*sys_clk_freq))
        self.reset   = reset   = WaitTimer(math.ceil(2e-6*sys_clk_freq))

        self.sync += If(phy.done & phy.error,
            self.timeout.eq(1),
        )
        self.comb += bus.dat_r.eq(phy.dat_r)

        # Bus Access -------------------------------------------------------------------------------
        # x16 addresses have a ten-bit word column. Wire CA10 is unused, not a row bit.
        # APS512 needs 15 row bits per its geometry/PASR tables; Rev. 1.0's CA table omits RA14.
        word_address = bus.adr[:log2_int(size//4)]
        address      = Signal(32)
        dat_w        = Signal(32)
        sel          = Signal(4)
        write        = Signal()
        aborted      = Signal()
        failed       = Signal()

        # Initialization / Access FSM ---------------------------------------------------------------
        self.fsm = fsm = FSM(reset_state="POWERUP")
        fsm.act("POWERUP",
            powerup.wait.eq(1),
            If(powerup.done,
                NextState("RESET"),
            ),
        )
        fsm.act("RESET",
            phy.start.eq(1),
            phy.cmd.eq(0xff),
            NextState("RESET-WAIT"),
        )
        fsm.act("RESET-WAIT",
            If(phy.done,
                NextState("RESET-RECOVER"),
            ),
        )
        fsm.act("RESET-RECOVER",
            reset.wait.eq(1),
            If(reset.done,
                NextState("X16"),
            ),
        )
        fsm.act("X16",
            phy.start.eq(1),
            phy.cmd.eq(0xc0),
            phy.address.eq(8),
            phy.dat_w.eq(0x40),
            NextState("X16-WAIT"),
        )
        fsm.act("X16-WAIT",
            If(phy.done,
                NextState("VERIFY"),
            ),
        )
        fsm.act("VERIFY",
            phy.start.eq(1),
            phy.cmd.eq(0x40),
            phy.address.eq(8),
            NextState("VERIFY-WAIT"),
        )
        fsm.act("VERIFY-WAIT",
            If(phy.done,
                If(phy.error | (phy.dat_r[:8] != 0x40),
                    NextState("FAILED"),
                ).Else(
                    NextState("IDENTIFY"),
                )
            )
        )
        fsm.act("IDENTIFY",
            phy.start.eq(1),
            phy.cmd.eq(0x40),
            phy.address.eq(1),
            NextState("IDENTIFY-WAIT"),
        )
        fsm.act("IDENTIFY-WAIT",
            If(phy.done,
                NextValue(self.id, Cat(phy.dat_r[:8], phy.dat_r[16:24])),
                If(phy.error | (phy.dat_r[:5] != 0x0d) |
                    (phy.dat_r[16:19] != (7 if size == 32*1024*1024 else 6)),
                    NextState("FAILED"),
                ).Else(
                    NextValue(self.ready, 1),
                    NextState("IDLE"),
                )
            )
        )
        fsm.act("FAILED",
            self.init_error.eq(1),
            bus.err.eq(bus.cyc & bus.stb),
        )
        fsm.act("IDLE",
            If(bus.cyc & bus.stb,
                NextValue(address, Cat(C(0, 1), word_address[:9], C(0, 1), word_address[9:])),
                NextValue(dat_w,   bus.dat_w),
                NextValue(sel,     bus.sel),
                NextValue(write,   bus.we),
                NextValue(aborted, 0),
                NextState("ACCESS"),
            )
        )
        fsm.act("ACCESS",
            phy.start.eq(1),
            phy.cmd.eq(Mux(write, 0xa0, 0x20)),
            phy.address.eq(address),
            phy.dat_w.eq(dat_w),
            phy.sel.eq(sel),
            If(~bus.cyc,
                NextValue(aborted, 1),
            ),
            NextState("ACCESS-WAIT"),
        )
        fsm.act("ACCESS-WAIT",
            If(~bus.cyc,
                NextValue(aborted, 1),
            ),
            If(phy.done,
                NextValue(failed, phy.error),
                NextState("RESPONSE"),
            )
        )
        fsm.act("RESPONSE",
            bus.ack.eq(bus.cyc & bus.stb & ~aborted & ~failed),
            bus.err.eq(bus.cyc & bus.stb & ~aborted &  failed),
            NextState("IDLE"),
        )

        # CSRs -------------------------------------------------------------------------------------
        if with_csr:
            self.status = CSRStatus(fields=[
                CSRField("ready",      description="Initialization completed and device ID matched."),
                CSRField("init_error", description="Initialization failed; reset the core to retry."),
                CSRField("timeout",    description="A read timed out. Cleared by core reset."),
            ])
            self.identification = CSRStatus(16, description="MR1 in bits 7:0, MR2 in bits 15:8.")
            self.comb += [
                self.status.fields.ready.eq(self.ready),
                self.status.fields.init_error.eq(self.init_error),
                self.status.fields.timeout.eq(self.timeout),
                self.identification.status.eq(self.id),
            ]
