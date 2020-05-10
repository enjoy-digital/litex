# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from litex.build.generic_platform import GenericPlatform
from litex.build.microsemi import common, libero_soc

# MicrosemiPlatform --------------------------------------------------------------------------------

class MicrosemiPlatform(GenericPlatform):
    bitstream_ext = ".bit"

    def __init__(self, *args, toolchain="libero_soc_polarfire", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "libero_soc_polarfire":
            self.toolchain = libero_soc.MicrosemiLiberoSoCPolarfireToolchain()
        else:
            raise ValueError("Unknown toolchain")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict()
        so.update(self.toolchain.special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so,
                                           attr_translate=self.toolchain.attr_translate,
                                           **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if clk is None: return
        clk.attr.add("keep")
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        from_.attr.add("keep")
        to.attr.add("keep")
        self.toolchain.add_false_path_constraint(self, from_, to)
