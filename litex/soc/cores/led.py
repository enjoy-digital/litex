#
# This file is part of LiteX.
#
# Copyright (c) 2020-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Wolfgang Nagele <mail@wnagele.com>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *

from litex.gen import *
from litex.gen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import wishbone

# Led Chaser ---------------------------------------------------------------------------------------

_CHASER_MODE  = 0
_CONTROL_MODE = 1

class LedChaser(LiteXModule):
    def __init__(self, pads, sys_clk_freq, period=1e0, polarity=0):
        self.pads     = pads
        self.polarity = polarity
        self.n        = len(pads)
        self._out     = CSRStorage(len(pads), description="Led Output(s) Control.")

        # # #


        chaser = Signal(self.n)
        mode   = Signal(reset=_CHASER_MODE)
        timer  = WaitTimer(period*sys_clk_freq/(2*self.n))
        leds   = Signal(self.n)
        self.submodules += timer
        self.comb += timer.wait.eq(~timer.done)
        self.sync += If(timer.done, chaser.eq(Cat(~chaser[-1], chaser)))
        self.sync += If(self._out.re, mode.eq(_CONTROL_MODE))
        self.comb += [
            If(mode == _CONTROL_MODE,
                leds.eq(self._out.storage)
            ).Else(
                leds.eq(chaser)
            )
        ]
        self.comb += pads.eq(leds ^ (self.polarity*(2**self.n-1)))

    def add_pwm(self, default_width=512, default_period=1024, with_csr=True):
        from litex.soc.cores.pwm import PWM
        self.pwm = PWM(
            with_csr       = with_csr,
            default_enable = 1,
            default_width  = default_width,
            default_period = default_period
        )
        # Use PWM as Output Enable for pads.
        self.comb += If(~self.pwm.pwm, self.pads.eq(self.polarity*(2**self.n-1)))


# WS2812/NeoPixel ----------------------------------------------------------------------------------

class WS2812(LiteXModule):
    """WS2812/NeoPixel Led Driver.

    Description
    -----------

                ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
                │DI  DO│   │DI  DO│   │DI  DO│   │DI  DO│   │DI  DO│     Next leds
        FPGA ───►      ├───►      ├───►      ├───►      ├───►      ├───►     or
                │ LED0 │   │ LED1 │   │ LED2 │   │ LED3 │   │ LED4 │   end of chain.
                └──────┘   └──────┘   └──────┘   └──────┘   └──────┘
                 24-bit     24-bit     24-bit     24-bit     24-bit

    WS2812/NeoPixel Leds are smart RGB Leds controlled over a simple one wire protocol:
     - Each Led will "digest" a 24-bit control word:  (MSB) G-R-B (LSB).
     - Leds can be chained through DIN->DOUT connection.

     Each control sequence is separated by a reset code: Line low for > 50us (old) or > 280us (new).
     Ones are transmitted as:
                       ┌─────┐
                       │ T0H │           │  T0H = 400ns +-150ns
                       │     │    T0L    │  T0L = 800ns +-150ns
                             └───────────┘
     Zeros are transmitted as:
                       ┌──────────┐
                       │   T1H    │      │  T1H = 850ns +-150ns
                       │          │ T1L  │  T1L = 450ns +-150ns
                                  └──────┘

    Hardware Revisions
    ------------------
    Different revision of WS2812 have been released over the years. Unfortunately not all of them
    have compatible timings, especially on reset that has a minimal width of 50us on older models
    and 280us on newer models. By default, the core will use the timings of the newer models since
    also working on older models. Reset pulse and refresh rate can be improve for older models by
    setting revision to "old".

    Integration
    -----------

     The core handles the WS2812 protocol and exposes the Led chain as an MMAPed peripheral:

                                         32-bit
                                       00_GG_RR_BB
                                      ┌───────────┐
                             Base + 0 │   LED0    │
                                      ├───────────┤
                             Base + 4 │   LED1    │
                                      ├───────────┤
                             Base + 8 │   LED2    │
                                      └───────────┘
                               ...        ...

     It can be simply integrated in a LiteX SoC with:
         self.ws2812 = WS2812(platform.request("x"), nleds=32, sys_clk_freq=sys_clk_freq)
         self.bus.add_slave(name="ws2812", slave=self.ws2812.bus, region=SoCRegion(
             origin = 0x2000_0000,
             size   = 32*4,
         ))

     Each Led can then be directly controlled from the Bus of the SoC.

     Parameters
     ----------
     pad : Signal, in
         FPGA DOut.
     nleds : int, in
         Number of Leds in the chain.
     sys_clk_freq: int, in
         System Clk Frequency.
    """
    def __init__(self, pad, nleds, sys_clk_freq, bus_mastering=False, bus_base=None, revision="new", init=None):
        if bus_mastering:
            self.bus  = bus = wishbone.Interface(data_width=32)
        else:
            # Memory.
            mem = Memory(32, nleds, init=init)
            port = mem.get_port()
            self.specials += mem, port

            # Wishone Memory.
            self.wb_mem = wishbone.SRAM(
                mem_or_size = mem,
                read_only   = False,
                bus         = wishbone.Interface(data_width=32)
            )
            self.bus = self.wb_mem.bus


        # Internal Signals.
        led_count  = Signal(max=nleds)
        led_data   = Signal(24)
        xfer_start = Signal()
        xfer_done  = Signal()
        xfer_data  = Signal(24)

        # Timings
        self.trst = trst = {"old": 50e-6*1.25, "new": 280e-6*1.25}[revision]
        self.t0h  = t0h  = 0.40e-6
        self.t0l  = t0l  = 0.85e-6
        self.t1h  = t1h  = 0.80e-6
        self.t1l  = t1l  = 0.45e-6

        # Timers.
        trst_timer = WaitTimer(trst*sys_clk_freq)
        self.submodules += trst_timer

        t0h_timer = WaitTimer(t0h*sys_clk_freq)
        t0l_timer = WaitTimer(t0l*sys_clk_freq - 1) # Compensate Xfer FSM latency.
        self.submodules += t0h_timer, t0l_timer

        t1h_timer = WaitTimer(t1h*sys_clk_freq)
        t1l_timer = WaitTimer(t1l*sys_clk_freq - 1) # Compensate Xfer FSM latency.
        self.submodules += t1h_timer, t1l_timer

        # Main FSM.
        self.fsm = fsm = FSM(reset_state="RST")
        fsm.act("RST",
            NextValue(led_count, 0),
            trst_timer.wait.eq(xfer_done),
            If(trst_timer.done,
                NextState("LED-READ")
            )
        )
        if bus_mastering:
             fsm.act("LED-READ",
                bus.stb.eq(1),
                bus.cyc.eq(1),
                bus.we.eq(0),
                bus.sel.eq(2**(bus.data_width//8)-1),
                bus.adr.eq(bus_base[2:] + led_count),
                If(bus.ack,
                    NextValue(led_data, bus.dat_r),
                    NextState("LED-SEND")
                )
            )
        else:
            self.comb += port.adr.eq(led_count)
            fsm.act("LED-READ",
                NextState("LED-LATCH")
            )
            fsm.act("LED-LATCH",
                NextValue(led_data, port.dat_r),
                NextState("LED-SEND")
            )

        fsm.act("LED-SEND",
            If(xfer_done,
                xfer_start.eq(1),
                NextState("LED-SHIFT")
            )
        )
        fsm.act("LED-SHIFT",
            If(led_count == (nleds - 1),
                NextState("RST")
            ).Else(
                NextValue(led_count, led_count + 1),
                NextState("LED-READ")
            )
        )

        # XFER FSM.
        xfer_bit = Signal(5)
        xfer_fsm = FSM(reset_state="IDLE")
        self.submodules += xfer_fsm
        xfer_fsm.act("IDLE",
            xfer_done.eq(1),
            If(xfer_start,
                NextValue(xfer_bit, 24-1),
                NextValue(xfer_data, led_data),
                NextState("RUN")
            )
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
                    NextState("IDLE")
                )
            )
        )
