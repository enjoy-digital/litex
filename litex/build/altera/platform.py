#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 msloniewski <marcin.sloniewski@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import GenericPlatform
from litex.build.altera import common, quartus

# AlteraPlatform -----------------------------------------------------------------------------------

class AlteraPlatform(GenericPlatform):
    bitstream_ext = ".sof"
    create_rbf    = True

    def __init__(self, *args, toolchain="quartus", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        self.ips = set()
        if toolchain == "quartus":
            self.toolchain = quartus.AlteraQuartusToolchain()
        else:
            raise ValueError("Unknown toolchain")

    def add_ip(self, filename):
        self.ips.add((os.path.abspath(filename)))

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.altera_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so, **kwargs)

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
