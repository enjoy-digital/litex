from mibuild.generic_platform import GenericPlatform
from mibuild.xilinx import common, vivado, ise


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
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so, **kwargs)

    def get_edif(self, fragment, **kwargs):
        return GenericPlatform.get_edif(self, fragment, "UNISIMS", "Xilinx", self.device, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)
