#
# This file is part of LiteX.
#
# Copyright (c) 2020-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Wolfgang Nagele <mail@wnagele.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.misc import WaitTimer

from litex.soc.interconnect.csr import *
from litex.soc.interconnect import wishbone

# Led Chaser ---------------------------------------------------------------------------------------

_CHASER_MODE  = 0
_CONTROL_MODE = 1


# Based on: migen.genlib.misc.WaitTimer
class ModifiableWaitTimer(Module):
    def __init__(self, t):
        self.wait = Signal()
        self.done = Signal()
        self.reset = Signal(bits_for(t), reset=t)

        # # #

        count = Signal(bits_for(t), reset=t)
        self.comb += self.done.eq(count == 0)
        self.sync += \
            If(self.wait,
                If(~self.done, count.eq(count - 1))
            ).Else(count.eq(self.reset))


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

    Hardware Revisions
    ------------------
    WS2812 hardware has several different revisions that have been released over the years.
    Unfortunately not all of them are compatible with the timings they require. Especially 
    the reset timing has substantial differences between older and newer models.
    Adjust the hardware_revision to your needs depending on which model you are using.

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
    def __init__(self, pad, nleds, sys_clk_freq, bus_mastering=False, bus_base=None, hardware_revision="old", test_data=None):
        if bus_mastering:
            self.bus  = bus = wishbone.Interface(data_width=32)
        else:
            # Memory.
            mem = Memory(32, nleds, init=test_data)
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
        led_count = Signal(max = nleds + 1)

        # Timings
        self.trst = trst = 285e-6 if hardware_revision == "new" else 55e-6
        self.t0h = t0h = 0.40e-6
        self.t1h = t1h = 0.80e-6
        self.t0l = t0l = 0.85e-6
        self.t1l = t1l = 0.45e-6

        # Timers.
        t0h_timer = ModifiableWaitTimer(int(t0h*sys_clk_freq))
        t0l_timer = ModifiableWaitTimer(int(t0l*sys_clk_freq) - 1) # compensate for data clk in cycle
        self.submodules += t0h_timer, t0l_timer

        t1h_timer = ModifiableWaitTimer(int(t1h*sys_clk_freq))
        t1l_timer = ModifiableWaitTimer(int(t1l*sys_clk_freq) - 1) # compensate for data clk in cycle
        self.submodules += t1h_timer, t1l_timer

        trst_timer = ModifiableWaitTimer(int(trst*sys_clk_freq))
        self.submodules += trst_timer

        # FSM
        self.submodules.fsm = fsm = FSM(reset_state="RST")
        fsm.act("RST",
            trst_timer.wait.eq(1),
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
                    NextValue(bit_count, 24-1),
                    NextValue(led_data, bus.dat_r),
                    NextState("BIT-TEST")
                )
            )
        else:
            self.comb += port.adr.eq(led_count)
            fsm.act("LED-READ",
                NextValue(bit_count, 24-1),
                NextValue(led_count, led_count + 1),
                NextValue(led_data, port.dat_r),
                NextState("BIT-TEST")
            )

        fsm.act("BIT-TEST",
            # by including the cycles spent on checking for conditions
            # data shifting, etc. we make the timing more precise
            If(bit_count == 0,
                # BIT-SHIFT + LED-SHIFT + LED-READ + BIT-TEST
                NextValue(t0l_timer.reset, t0l_timer.reset.reset - 4),
                NextValue(t1l_timer.reset, t1l_timer.reset.reset - 4)
            ).Else(
                # BIT-SHIFT + BIT-TEST
                NextValue(t0l_timer.reset, t0l_timer.reset.reset - 2),
                NextValue(t1l_timer.reset, t1l_timer.reset.reset - 2)
            ),
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
            If(bit_count == 0,
                NextState("LED-SHIFT")
            ).Else(
                NextValue(bit_count, bit_count - 1),
                NextState("BIT-TEST")
            )
        )
        fsm.act("LED-SHIFT",
            If(led_count == nleds,
                NextValue(led_count, 0),
                NextState("RST")
            ).Else(
                NextState("LED-READ")
            )
        )