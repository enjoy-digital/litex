from migen.build.generic_platform import GenericPlatform
from migen.build.altera import common, quartus


class AlteraPlatform(GenericPlatform):
    bitstream_ext = ".sof"

    def __init__(self, *args, toolchain="quartus", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "quartus":
            self.toolchain = quartus.AlteraQuartusToolchain()
        else:
            raise ValueError("Unknown toolchain")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.altera_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so,
                                           **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)
