from litex.build.generic_platform import GenericPlatform
from litex.build.xilinx import common, vivado, ise


class XilinxPlatform(GenericPlatform):
    bitstream_ext = ".bit"

    def __init__(self, *args, toolchain="ise", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "ise":
            self.toolchain = ise.XilinxISEToolchain()
        elif toolchain == "vivado":
            self.toolchain = vivado.XilinxVivadoToolchain()
        else:
            raise ValueError("Unknown toolchain")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.xilinx_special_overrides)
        if self.device[:3] == "xc7":
            so.update(common.xilinx_s7_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)
