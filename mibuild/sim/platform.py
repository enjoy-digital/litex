from mibuild.generic_platform import GenericPlatform
from mibuild.sim import common, verilator


class SimPlatform(GenericPlatform):
    def __init__(self, *args, toolchain="verilator", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "verilator":
            self.toolchain = verilator.SimVerilatorToolchain()
        else:
            raise ValueError("Unknown toolchain")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.sim_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

