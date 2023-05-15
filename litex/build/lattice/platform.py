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
    _bitstream_ext = ".bit"

    _supported_toolchains = {
        "ice40" : ["icestorm"],
        "ecp5"  : ["trellis", "diamond"],
        "nexus" : ["radiant", "oxide"],
    }

    def __init__(self, *args, toolchain="diamond", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        if toolchain == "diamond":
            self.toolchain = diamond.LatticeDiamondToolchain()
        elif toolchain == "trellis":
            self.toolchain = trellis.LatticeTrellisToolchain()
        elif toolchain == "icestorm":
            self._bitstream_ext = ".bin"
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

    @classmethod
    def fill_args(cls, toolchain, parser):
        """
        pass parser to the specific toolchain to
        fill this with toolchain args

        Parameters
        ==========
        toolchain: str
            toolchain name
        parser: argparse.ArgumentParser
            parser to be filled
        """
        if toolchain == "radiant":
            radiant.radiant_build_args(parser)
        elif toolchain == "oxide":
            oxide.oxide_args(parser)
        elif toolchain == "trellis":
            trellis.trellis_args(parser)
        elif toolchain == "icestorm":
            icestorm.icestorm_args(parser)
        # nothing for diamond

    @classmethod
    def get_argdict(cls, toolchain, args):
        """
        return a dict of args

        Parameters
        ==========
        toolchain: str
            toolchain name

        Return
        ======
        a dict of key/value for each args or an empty dict
        """
        if toolchain == "radiant":
            return radiant.radiant_build_argdict(args)
        elif toolchain == "oxide":
            return oxide.oxide_argdict(args)
        elif toolchain == "trellis":
            return trellis.trellis_argdict(args)
        elif toolchain == "icestorm":
            return icestorm.icestorm_argdict(args)
        else:
            return {}
        # nothing for diamond

# LatticeiCE40Platform -----------------------------------------------------------------------------

class LatticeiCE40Platform(LatticePlatform):
    device_family = "ice40"

# LatticeECP5Platform ------------------------------------------------------------------------------

class LatticeECP5Platform(LatticePlatform):
    device_family = "ecp5"

# LatticeNexusPlatform -----------------------------------------------------------------------------

class LatticeNexusPlatform(LatticePlatform):
    device_family = "nexus"
