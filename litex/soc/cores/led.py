#
# This file is part of LiteX.
#
# Copyright (c) 2020-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import math

from migen import *
from migen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import wishbone

# Led Chaser ---------------------------------------------------------------------------------------

_CHASER_MODE  = 0
_CONTROL_MODE = 1

class LedChaser(Module, AutoCSR):
    def __init__(self, pads, sys_clk_freq, period=1e0):
        self.pads = pads
        self._out = CSRStorage(len(pads), description="Led Output(s) Control.")

        # # #

        n      = len(pads)
        chaser = Signal(n)
        mode   = Signal(reset=_CHASER_MODE)
        timer  = WaitTimer(int(period*sys_clk_freq/(2*n)))
        self.submodules += timer
        self.comb += timer.wait.eq(~timer.done)
        self.sync += If(timer.done, chaser.eq(Cat(~chaser[-1], chaser)))
        self.sync += If(self._out.re, mode.eq(_CONTROL_MODE))
        self.comb += [
            If(mode == _CONTROL_MODE,
                pads.eq(self._out.storage)
            ).Else(
                pads.eq(chaser)
            )
        ]

    def add_pwm(self, default_width=512, default_period=1024, with_csr=True):
        from litex.soc.cores.pwm import PWM
        self.submodules.pwm = PWM(
            with_csr       = with_csr,
            default_enable = 1,
            default_width  = default_width,
            default_period = default_period
        )
        # Use PWM as Output Enable for pads.
        self.comb += If(~self.pwm.pwm, self.pads.eq(0))


# WS2812/NeoPixel ----------------------------------------------------------------------------------

class WS2812(Module):
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

     Each control sequence is separated by a reset code: Line low for > 50us.
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
         self.submodules.ws2812 = WS2812(platform.request("x"), nleds=32, sys_clk_freq=sys_clk_freq)
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
    def __init__(self, pad, nleds, sys_clk_freq):
        # Memory.
        mem = Memory(32, nleds)
        port = mem.get_port()
        self.specials += mem, port

        # Wishone Memory.
        self.submodules.wb_mem = wishbone.SRAM(
            mem_or_size = mem,
            read_only   = False,
            bus         = wishbone.Interface(data_width=32)
        )
        self.bus = self.wb_mem.bus

        # Internal Signals.
        led_data  = Signal(24)
        bit_count = Signal(8)
        led_count = Signal(int(math.log2(nleds)))

        # Timings.
        trst = 75e-6
        t0h  = 0.40e-6
        t0l  = 0.85e-6
        t1h  = 0.80e-6
        t1l  = 0.45e-6

        # Timers.
        t0h_timer = WaitTimer(int(t0h*sys_clk_freq))
        t0l_timer = WaitTimer(int(t0l*sys_clk_freq))
        self.submodules += t0h_timer, t0l_timer

        t1h_timer = WaitTimer(int(t1h*sys_clk_freq))
        t1l_timer = WaitTimer(int(t1l*sys_clk_freq))
        self.submodules += t1h_timer, t1l_timer

        trst_timer = WaitTimer(int(trst*sys_clk_freq))
        self.submodules += trst_timer

        # FSM
        self.submodules.fsm = fsm = FSM(reset_state="RST")
        fsm.act("RST",
            trst_timer.wait.eq(1),
            If(trst_timer.done,
                NextValue(led_count, 0),
                NextState("LED-SHIFT")
            )
        )
        self.comb += port.adr.eq(led_count)
        fsm.act("LED-SHIFT",
            NextValue(bit_count, 24-1),
            NextValue(led_data,  port.dat_r),
            NextValue(led_count, led_count + 1),
            If(led_count == (nleds-1),
                NextState("RST")
            ).Else(
                NextState("BIT-TEST")
            )
        )
        fsm.act("BIT-TEST",
            If(led_data[-1] == 0,
                NextState("ZERO-SEND"),
            ),
            If(led_data[-1] == 1,
                NextState("ONE-SEND"),
            ),
        )
        fsm.act("ZERO-SEND",
            t0h_timer.wait.eq(1),
            t0l_timer.wait.eq(t0h_timer.done),
            pad.eq(~t0h_timer.done),
            If(t0l_timer.done,
                NextState("BIT-SHIFT")
            )
        )
        fsm.act("ONE-SEND",
            t1h_timer.wait.eq(1),
            t1l_timer.wait.eq(t1h_timer.done),
            pad.eq(~t1h_timer.done),
            If(t1l_timer.done,
                NextState("BIT-SHIFT")
            )
        )
        fsm.act("BIT-SHIFT",
            NextValue(led_data, Cat(Signal(), led_data)),
            NextValue(bit_count, bit_count - 1),
            If(bit_count == 0,
                NextState("LED-SHIFT")
            ).Else(
                NextState("BIT-TEST")
            )
        )
