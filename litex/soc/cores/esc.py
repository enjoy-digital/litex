#
# This file is part of LiteX.
#
# Copyright (c) 2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *

from litex.gen import LiteXModule
from litex.gen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import wishbone

# ESCDShot Timings ---------------------------------------------------------------------------------

class DShotTimings:
    def compute(self):
        self.t1l  = (self.period - self.t1h)
        self.t0l  = (self.period - self.t0h)
        self.tgap = 16*self.period # FIXME: Refine.

class D150Timings(DShotTimings):
    t1h    = 5.00e6
    t0h    = 2.50e6
    period = 6.67e6

class D300Timings(DShotTimings):
    t1h    = 2.50e6
    t0h    = 1.25e6
    period = 3.33e6

class D600Timings(DShotTimings):
    t1h    = 1.250e6
    t0h    = 0.625e6
    period = 1.670e6

# ESCDShot Core ------------------------------------------------------------------------------------

class ESCDShot(LiteXModule):
    """ESC DShot Driver.

    Description
    -----------

        DShot is a digital protocol for FC (Flight Controller) to ESC (Electronic Speed Controler)
        communication.

        It consists of 16 bit words send continously:
        - 11 bit throttle:
                  0 : Disarmed command.
               1-47 : Special commands.
            48-2047 : Trotthe value (0-2000).
        -  1 bit telemetry request:
             0 : No telemetry.
             1 : Telemetry sent back on separate channel.
        -  4 bit CRC to validate/check throttle + telemetry request values.

        Zeroes are transmitted as:
                       ┌─────┐
                       │ T0H │           │
                       │     │           │
                             └───────────┘
        Ones are transmitted as:
                       ┌──────────┐
                       │   T1H    │      │
                       │          │      │
                                  └──────┘
        With:
        D150 (150Kbit/s) : T1H:    5us / T0H:   2.5us / Bit Duration: 6.67us.
        D300 (300Kbit/s) : T1H:  2.5us / T0H:  1.25us / Bit Duration: 3.33us.
        D600 (600Kbit/s) : T1h: 1.25us / T0H: 0.625us / Bit Duration: 1.67us.

        The checksum is calculated over the throttle value and the telemetry bit with the following
        formula: crc = (value ^ (value >> 4) ^ (value >> 8)) & 0x0f

        With current implementation, user or software directly write the raw transmitted value on the
        CSR register, so formating and CRC has to be pre-computed by the user or software.

        Example over LiteX-Server/Bridge:

        # Integration in SoC:
        # -------------------

        esc_pad = Signal() # Or platform.request("X") with X = esc pin name.

        from litex.soc.cores.esc import ESCDShot
        self.submodules.esc0 = ESCDShot(esc_pad, sys_clk_freq, protocol="DSHOT150")

        # Test script:
        # ------------

        from litex import RemoteClient

        bus = RemoteClient()
        bus.open()

        class ESC:
            def __init__(self, bus, n, sys_clk_freq):
                self.value = getattr(bus.regs, f"esc{n}_value")
                self.set(0)

            def set(self, value):
                value = max(value,   0)
                value = min(value,  99)
                if value == 0:
                    throttle  = 0
                else:
                    throttle  = value*20 + 48
                telemetry = 0
                data = (throttle << 1) | telemetry
                crc  = (data ^ (data >> 4) ^ (data >> 8)) & 0x0f
                print(f"0b{(data << 4 | crc):016b}")
                self.value.write(data << 4 | crc)



        esc = ESC(bus, n=0, int(100e6))
        esc.set(50) # 0-99.

        bus.close()
    """
    def __init__(self, pad, sys_clk_freq, protocol="D150"):
        self.value = CSRStorage(16)

        # # #

        # Internal Signals.
        xfer_start = Signal()
        xfer_done  = Signal()
        xfer_data  = Signal(16)

        # Timings.
        timings = {
            "D150": D150Timings(),
            "D300": D300Timings(),
            "D600": D600Timings(),
        }[protocol]
        timings.compute()

        # Timers.
        t0h_timer = WaitTimer(timings.t0h*sys_clk_freq)
        t0l_timer = WaitTimer(timings.t0l*sys_clk_freq - 1) # Compensate Xfer FSM latency.
        self.submodules += t0h_timer, t0l_timer

        t1h_timer = WaitTimer(timings.t1h*sys_clk_freq)
        t1l_timer = WaitTimer(timings.t1l*sys_clk_freq - 1) # Compensate Xfer FSM latency.
        self.submodules += t1h_timer, t1l_timer

        tgap_timer = WaitTimer(timings.tgap*sys_clk_freq)
        self.submodules += tgap_timer

        # XFER FSM.
        xfer_bit = Signal(4)
        xfer_fsm = FSM(reset_state="IDLE")
        self.submodules += xfer_fsm
        xfer_fsm.act("IDLE",
            NextValue(xfer_bit, 16 - 1),
            NextValue(xfer_data, self.value.storage),
            NextState("RUN")
        )
        xfer_fsm.act("RUN",
            # Send a one.
            If(xfer_data[-1],
                t1h_timer.wait.eq(1),
                t1l_timer.wait.eq(t1h_timer.done),
                pad.eq(~t1h_timer.done),
            # Send a zero.
            ).Else(
                t0h_timer.wait.eq(1),
                t0l_timer.wait.eq(t0h_timer.done),
                pad.eq(~t0h_timer.done),
            ),

            # When bit has been sent:
            If(t0l_timer.done | t1l_timer.done,
                # Clear wait on timers.
                t0h_timer.wait.eq(0),
                t0l_timer.wait.eq(0),
                t1h_timer.wait.eq(0),
                t1l_timer.wait.eq(0),
                # Shift xfer_data.
                NextValue(xfer_data, Cat(Signal(), xfer_data)),
                # Decrement xfer_bit.
                NextValue(xfer_bit, xfer_bit - 1),
                # When xfer_bit reaches 0.
                If(xfer_bit == 0,
                    NextState("GAP")
                )
            )
        )
        xfer_fsm.act("GAP",
            tgap_timer.wait.eq(1),
            If(tgap_timer.done,
                NextState("IDLE")
            )
        )
