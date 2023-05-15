#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018-2019 David Shah <dave@ds0.me>
# Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import sys
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.lattice import common
from litex.build.yosys_nextpnr_toolchain import YosysNextPNRToolchain, yosys_nextpnr_args, yosys_nextpnr_argdict

# LatticeTrellisToolchain --------------------------------------------------------------------------

class LatticeTrellisToolchain(YosysNextPNRToolchain):
    attr_translate = {
        "keep": ("keep", "true"),
    }

    family     = "ecp5"
    synth_fmt  = "json"
    constr_fmt = "lpf"
    pnr_fmt    = "config"
    packer_cmd = "ecppack"

    special_overrides = common.lattice_ecp5_trellis_special_overrides

    def __init__(self):
        super().__init__()

    def build(self, platform, fragment,
        bootaddr       = 0,
        spimode        = None,
        freq           = None,
        compress       = True,
        **kwargs):

        # Validate options
        ecp5_mclk_freqs = [
            2.4,
            4.8,
            9.7,
            19.4,
            38.8,
            62.0,
        ]
        if freq is not None:
            assert freq in ecp5_mclk_freqs, "Invalid MCLK frequency. Valid frequencies: " + str(ecp5_mclk_freqs)

        # prepare ecppack opts
        self._packer_opts += " --bootaddr {bootaddr} {spimode} {freq} {compress} ".format(
            bootaddr = bootaddr,
            spimode  = "" if spimode is None else f"--spimode {spimode}",
            freq     = "" if freq is None else "--freq {}".format(freq),
            compress = "" if not compress else "--compress"
        )

        return YosysNextPNRToolchain.build(self, platform, fragment, **kwargs)

    def finalize(self):
        # Translate device to Nextpnr architecture/package
        (family, size, self._speed_grade, self._package) = self.nextpnr_ecp5_parse_device(self.platform.device)
        self._architecture = self.nextpnr_ecp5_architectures[(family + "-" + size)]

        self._packer_opts += " {build_name}.config --svf {build_name}.svf --bit {build_name}.bit".format(
                build_name = self._build_name,
        )
        return YosysNextPNRToolchain.finalize(self)

    # IO Constraints (.lpf) ------------------------------------------------------------------------

    @classmethod
    def _format_constraint(cls, c):
        if isinstance(c, Pins):
            return ("LOCATE COMP ", " SITE " + "\"" + c.identifiers[0] + "\"")
        elif isinstance(c, IOStandard):
            return ("IOBUF PORT ", " IO_TYPE=" + c.name)
        elif isinstance(c, Misc):
            return ("IOBUF PORT ", " " + c.misc)

    def _format_lpf(self, signame, pin, others, resname):
        fmt_c = [self._format_constraint(c) for c in ([Pins(pin)] + others)]
        lpf = []
        for pre, suf in fmt_c:
            lpf.append(pre + "\"" + signame + "\"" + suf + ";")
        return "\n".join(lpf)

    def build_io_constraints(self):
        lpf = []
        lpf.append("BLOCK RESETPATHS;")
        lpf.append("BLOCK ASYNCPATHS;")
        for sig, pins, others, resname in self.named_sc:
            if len(pins) > 1:
                for i, p in enumerate(pins):
                    lpf.append(self._format_lpf(sig + "[" + str(i) + "]", p, others, resname))
            else:
                lpf.append(self._format_lpf(sig, pins[0], others, resname))
        if self.named_pc:
            lpf.append("\n\n".join(self.named_pc))
        tools.write_to_file(self._build_name + ".lpf", "\n".join(lpf))

    # NextPnr Helpers/Templates --------------------------------------------------------------------

    def nextpnr_ecp5_parse_device(self, device):
        device      = device.lower()
        family      = device.split("-")[0]
        size        = device.split("-")[1]
        speed_grade = device.split("-")[2][0]
        if speed_grade not in ["6", "7", "8"]:
           raise ValueError("Invalid speed grade {}".format(speed_grade))
        package     = device.split("-")[2][1:]
        if "256" in package:
            package = "CABGA256"
        elif "285" in package:
            package = "CSFBGA285"
        elif "381" in package:
            package = "CABGA381"
        elif "554" in package:
            package = "CABGA554"
        elif "756" in package:
            package = "CABGA756"
        else:
           raise ValueError("Invalid package {}".format(package))
        return (family, size, speed_grade, package)

    nextpnr_ecp5_architectures = {
        "lfe5u-12f"   : "12k",
        "lfe5u-25f"   : "25k",
        "lfe5u-45f"   : "45k",
        "lfe5u-85f"   : "85k",
        "lfe5um-25f"  : "um-25k",
        "lfe5um-45f"  : "um-45k",
        "lfe5um-85f"  : "um-85k",
        "lfe5um5g-25f": "um5g-25k",
        "lfe5um5g-45f": "um5g-45k",
        "lfe5um5g-85f": "um5g-85k",
    }

    def add_period_constraint(self, platform, clk, period):
        platform.add_platform_command("""FREQUENCY PORT "{clk}" {freq} MHz;""".format(
            freq=str(float(1/period)*1000), clk="{clk}"), clk=clk)

def trellis_args(parser):
    toolchain_group = parser.add_argument_group(title="Trellis toolchain options")
    yosys_nextpnr_args(toolchain_group)
    toolchain_group.add_argument("--ecppack-bootaddr",     default=0,           help="Set boot address for next image.")
    toolchain_group.add_argument("--ecppack-spimode",      default=None,        help="Set slave SPI programming mode.")
    toolchain_group.add_argument("--ecppack-freq",         default=None,        help="Set SPI MCLK frequency.")
    toolchain_group.add_argument("--ecppack-compress",     action="store_true", help="Use Bitstream compression.")

def trellis_argdict(args):
    return {
        **yosys_nextpnr_argdict(args),
        "bootaddr":     args.ecppack_bootaddr,
        "spimode":      args.ecppack_spimode,
        "freq":         float(args.ecppack_freq) if args.ecppack_freq is not None else None,
        "compress":     args.ecppack_compress,
    }
