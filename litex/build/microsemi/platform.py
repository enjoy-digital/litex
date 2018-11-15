from litex.build.generic_platform import GenericPlatform
from litex.build.microsemi import common, libero_soc


class MicrosemiPlatform(GenericPlatform):
    bitstream_ext = ".bit"

    def __init__(self, *args, toolchain="libero_soc_polarfire", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "libero_soc_polarfire":
            self.toolchain = libero_soc.MicrosemiLiberoSoCPolarfireToolchain()
        else:
            raise ValueError("Unknown toolchain")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict()  # No common overrides between ECP and ice40.
        so.update(self.toolchain.special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so,
                                           attr_translate=self.toolchain.attr_translate,
                                           **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)
