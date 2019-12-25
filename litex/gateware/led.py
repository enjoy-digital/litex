from migen import *

from litex.soc.interconnect.csr import *
from litex.soc.cores import gpio

from litex.gateware.pwm import PWM


class ClassicLed(gpio.GPIOOut):
    def __init__(self, pads):
        gpio.GPIOOut.__init__(self, pads)


class RGBLed(Module, AutoCSR):
    def __init__(self, pads):
        nleds = len(pads.r)

        # # #

        for n in range(nleds):
            for c in "rgb":
                setattr(self.submodules, c+str(n), PWM(getattr(pads, c)[n]))
