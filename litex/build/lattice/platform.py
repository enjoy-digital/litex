from litex.build.generic_platform import GenericPlatform
from litex.build.lattice import common, diamond, icestorm, prjtrellis


class LatticePlatform(GenericPlatform):
    bitstream_ext = ".bit"

    def __init__(self, *args, toolchain="diamond", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "diamond":
            self.toolchain = diamond.LatticeDiamondToolchain()
        elif toolchain == "prjtrellis":
            self.toolchain = prjtrellis.LatticePrjTrellisToolchain()
        elif toolchain == "icestorm":
            self.bitstream_ext = ".bin"
            self.toolchain = icestorm.LatticeIceStormToolchain()
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
