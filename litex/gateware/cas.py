"""
Module which allows control via buttons and switches and status reporting via
LEDs.
"""

from litex.build.generic_platform import ConstraintError

from litex.soc.interconnect.csr import AutoCSR
from litex.soc.interconnect.csr_eventmanager import *
from migen.genlib.misc import WaitTimer

from litex.soc.cores.gpio import GPIOIn, GPIOOut
from litex.gateware.led import RGBLed

class ControlAndStatus(Module, AutoCSR):
    def __init__(self, platform, clk_freq):

        # Work out how many LEDs this board has
        user_leds = []
        while True:
            try:
                user_leds.append(platform.request("user_led", len(user_leds)))
            except ConstraintError:
                break

        rgb_leds = []
        while True:
            try:
                rgb_leds.append(platform.request("rgb_led", len(rgb_leds)))
            except ConstraintError:
                break
        for rgb in rgb_leds:
            # TODO: Common anode only for now. Support common cathode.
            r_n = Signal()
            g_n = Signal()
            b_n = Signal()

            self.comb += [
                rgb.r.eq(~r_n),
                rgb.g.eq(~g_n),
                rgb.b.eq(~b_n),
            ]

            user_leds.extend([r_n, g_n, b_n])

        if user_leds:
            leds = Signal(len(user_leds))
            self.submodules.leds = GPIOOut(leds)
            for i in range(0, len(user_leds)):
                self.comb += [
                    user_leds[i].eq(leds[i]),
                ]
        self._leds_count = CSRConstant(len(user_leds))

        # Work out how many switches this board has
        user_sws = []
        while True:
            try:
                user_sws.append(platform.request("user_sw", len(user_sws)))
            except ConstraintError:
                break

        if user_sws:
            switches = Signal(len(user_sws))
            self.submodules.switches = GPIOIn(switches)
            for i in range(0, len(user_sws)):
                self.comb += [
                    switches[i].eq(~user_sws[i]),
                ]
        self._switches_count = CSRConstant(len(user_sws))

        # Work out how many push buttons this board has
        user_btns = []
        while True:
            try:
                user_btns.append(platform.request("user_btn", len(user_btns)))
            except ConstraintError:
                break

        if user_btns:
            self.submodules.buttons_ev = EventManager()

            _10ms = int(clk_freq*(10e-3))

            for i in range(0, len(user_btns)):
                btn_ev = EventSourceProcess()
                btn_timer = WaitTimer(_10ms)

                setattr(self.buttons_ev, "btn_ev{}".format(i), btn_ev)

                self.comb += [
                    btn_timer.wait.eq(user_btns[i]),
                    btn_ev.trigger.eq(~btn_timer.done),
                ]

                self.submodules += [btn_timer]

            self.buttons_ev.finalize()
        self._buttons_count = CSRConstant(len(user_btns))
