#
# This file is part of LiteX.
#
# Copyright (c) 2023 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabubucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import GenericPlatform
from litex.build.colognechip import common, colognechip, peppercorn

# CologneChipPlatform ------------------------------------------------------------------------------

class CologneChipPlatform(GenericPlatform):
    _bitstream_ext = "_00.cfg.bit"
    _jtag_support  = False

    _supported_toolchains = ["colognechip", "peppercorn"]

    def __init__(self, device, *args, toolchain="colognechip", devicename=None, **kwargs):
        GenericPlatform.__init__(self, device, *args, **kwargs)

        if toolchain == "colognechip":
            self.toolchain = colognechip.CologneChipToolchain()
        elif toolchain == "peppercorn":
            self._bitstream_ext = ".bit"
            self.toolchain = peppercorn.PeppercornToolchain()
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.colognechip_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs
        )

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if clk is None: return
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
        if toolchain == "colognechip":
            colognechip.colognechip_args(parser)
        else:
            peppercorn.peppercorn_args(parser)

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
        if toolchain == "colognechip":
            return colognechip.colognechip_argdict(args)
        else:
            return peppercorn.peppercorn_argdict(args)
