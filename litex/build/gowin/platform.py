#
# This file is part of LiteX.
#
# Copyright (c) 2020 Pepijn de Vos <pepijndevos@gmail.com>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import GenericPlatform
from litex.build.gowin import common, gowin

# GowinPlatform -----------------------------------------------------------------------------------

class GowinPlatform(GenericPlatform):
    bitstream_ext = ".fs"

    def __init__(self, device, *args, toolchain="gowin", devicename=None, **kwargs):
        GenericPlatform.__init__(self, device, *args, **kwargs)
        if not devicename:
            idx = device.find('-')
            likely_name = f"{device[:idx]}-{device[idx+3]}"
            raise ValueError(f"devicename not provided, maybe {likely_name}?")
        self.devicename = devicename
        if toolchain == "gowin":
            self.toolchain = gowin.GowinToolchain()
        elif toolchain == "apicula":
            raise ValueError("Apicula toolchain needs more work")
        else:
            raise ValueError(f"Unknown toolchain {toolchain}")

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.gowin_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args,
            special_overrides = so,
            attr_translate    = self.toolchain.attr_translate,
            **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if clk is None: return
        self.toolchain.add_period_constraint(self, clk, period)
