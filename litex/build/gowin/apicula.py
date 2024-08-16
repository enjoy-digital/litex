#
# This file is part of LiteX.
#
# Copyright (c) 2024 Mai Lapyst
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.gowin.gowin import _build_cst
from litex.build.yosys_nextpnr_toolchain import YosysNextPNRToolchain

class GowinApiculaToolchain(YosysNextPNRToolchain):
    family     = "gowin"
    synth_fmt  = "json"
    pnr_fmt    = "report"
    packer_cmd = "gowin_pack"

    def __init__(self):
        super().__init__()
        self.options = {}
        self.additional_cst_commands = []

    def build_io_constraints(self):
        _build_cst(self.named_sc, self.named_pc, self.additional_cst_commands, self._build_name)
        return (self._build_name + ".cst", "CST")

    def finalize(self):
        pnr_opts = "--write {top}_routed.json --top {top} --device {device}" + \
            " --vopt family={devicename} --vopt cst={top}.cst"
        self._pnr_opts += pnr_opts.format(
            top        = self._build_name,
            device     = self.platform.device,
            devicename = self.platform.devicename
        )

        self._packer_opts += "-d {devicename} -o {top}.fs {top}_routed.json".format(
            devicename = self.platform.devicename,
            top        = self._build_name
        )

        # use_mspi_as_gpio and friends
        for option, value in self.options.items():
            if option.startswith("use_") and value:
                self._packer_opts += " --" + option[4:]

        YosysNextPNRToolchain.finalize(self)

        # family is gowin but NextPNRWrapper needs to call 'nextpnr-himbaechel' not 'nextpnr-gowin'
        self._nextpnr.name = "nextpnr-himbaechel"

    def build(self, platform, fragment, **kwargs):
        self.platform = platform

        return YosysNextPNRToolchain.build(self, platform, fragment, **kwargs)
