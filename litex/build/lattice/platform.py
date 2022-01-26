#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017 William D. Jones <thor0505@comcast.net>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import GenericPlatform
from litex.build.lattice import common, diamond, icestorm, trellis, radiant, oxide

# LatticePlatform ----------------------------------------------------------------------------------

class LatticePlatform(GenericPlatform):
    bitstream_ext = ".bit"

    def __init__(self, *args, toolchain="diamond", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "diamond":
            self.toolchain = diamond.LatticeDiamondToolchain()
        elif toolchain == "trellis":
            self.toolchain = trellis.LatticeTrellisToolchain()
        elif toolchain == "icestorm":
            self.bitstream_ext = ".bin"
            self.toolchain = icestorm.LatticeIceStormToolchain()
        elif toolchain == "radiant":
            self.toolchain = radiant.LatticeRadiantToolchain()
        elif toolchain == "oxide":
            self.toolchain = oxide.LatticeOxideToolchain()
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict()  # No common overrides between ECP5 and iCE40.
        so.update(self.toolchain.special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs)


    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if clk is None: return
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        self.toolchain.add_false_path_constraint(self, from_, to)
