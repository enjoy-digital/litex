# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import os

from litex.build.generic_platform import GenericPlatform
from litex.build.xilinx import common, vivado, ise

# XilinxPlatform -----------------------------------------------------------------------------------

class XilinxPlatform(GenericPlatform):
    bitstream_ext = ".bit"

    def __init__(self, *args, toolchain="ise", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        self.edifs = set()
        self.ips   = set()
        if toolchain == "ise":
            self.toolchain = ise.XilinxISEToolchain()
        elif toolchain == "vivado":
            self.toolchain = vivado.XilinxVivadoToolchain()
        else:
            raise ValueError("Unknown toolchain")

    def add_edif(self, filename):
        self.edifs.add((os.path.abspath(filename)))

    def add_ip(self, filename):
        self.ips.add((os.path.abspath(filename)))

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.xilinx_special_overrides)
        if self.device[:3] == "xc6":
            so.update(common.xilinx_s6_special_overrides)
        if self.device[:3] == "xc7":
            so.update(common.xilinx_s7_special_overrides)
        if self.device[:4] == "xcku":
            so.update(common.xilinx_us_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so,
            attr_translate=self.toolchain.attr_translate, **kwargs)

    def get_edif(self, fragment, **kwargs):
        return GenericPlatform.get_edif(self, fragment, "UNISIMS", "Xilinx", self.device, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        self.toolchain.add_false_path_constraint(self, from_, to)
