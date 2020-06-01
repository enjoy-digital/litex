# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
# License: BSD

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform
from litex.build.openocd import OpenOCD
from litex.boards.platforms.arty import _io, _connectors

# Platform -----------------------------------------------------------------------------------------

class Platform(XilinxPlatform):
    default_clk_name   = "clk100"
    default_clk_period = 1e9/100e6

    def __init__(self, variant="a7-35"):
        device = {
            "a7-35":  {"part": "xc7a35tcsg324-1", "symbiflow-device": "xc7a50t_test"},
        }[variant]
        XilinxPlatform.__init__(self, device["part"], _io, _connectors, toolchain="symbiflow")
        self.toolchain.symbiflow_device = device["symbiflow-device"]

    def create_programmer(self):
        bscan_spi = "bscan_spi_xc7a100t.bit" if "xc7a100t" in self.device else "bscan_spi_xc7a35t.bit"
        return OpenOCD("openocd_xc7_ft2232.cfg", bscan_spi)

    def do_finalize(self, fragment):
        # Prevent GenericPlatform from creating period constraint on input clock
        pass

    def add_period_constraint(self, clk, period, phase=0):
        if clk is None: return
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period, phase)
