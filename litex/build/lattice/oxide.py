#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019-2020 David Shah <dave@ds0.me>
# Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import sys
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.lattice import common
from litex.build.lattice.radiant import _format_constraint, _format_ldc, _build_pdc
from litex.build.yosys_nextpnr_toolchain import YosysNextPNRToolchain, yosys_nextpnr_args, yosys_nextpnr_argdict

import math


# LatticeOxideToolchain ----------------------------------------------------------------------------

class LatticeOxideToolchain(YosysNextPNRToolchain):
    attr_translate = {
        "keep": ("keep", "true"),
        "syn_useioff": ("syn_useioff", 1),
    }

    special_overrides = common.lattice_NX_special_overrides_for_oxide

    family     = "nexus"
    synth_fmt  = "json"
    constr_fmt = "pdc"
    pnr_fmt    = "fasm"
    packer_cmd = "prjoxide"

    def __init__(self):
        super().__init__()
        self._synth_opts = "-flatten "

    def build(self, platform, fragment, es_device = False, **kwargs):

        self._pnr_opts += " --device {device}{ES} ".format(
            device = platform.device,
            ES     = "ES" if es_device else ""
        )

        return YosysNextPNRToolchain.build(self, platform, fragment, **kwargs)

    def finalize(self):
        self._packer_opts += f" pack {self._build_name}.fasm {self._build_name}.bit"
        YosysNextPNRToolchain.finalize(self)

    # Constraints (.ldc) ---------------------------------------------------------------------------

    def build_io_constraints(self):
        _build_pdc(self.named_sc, self.named_pc, self.clocks, self._vns, self._build_name)
        return (self._build_name + ".pdc", "PDC")

def oxide_args(parser):
    toolchain_group = parser.add_argument_group(title="Oxide toolchain options")
    yosys_nextpnr_args(toolchain_group)
    toolchain_group.add_argument("--nexus-es-device", action="store_true", help="Use Nexus-ES1 part.")

def oxide_argdict(args):
    return {
        **yosys_nextpnr_argdict(args),
        "es_device":    args.nexus_es_device,
    }
