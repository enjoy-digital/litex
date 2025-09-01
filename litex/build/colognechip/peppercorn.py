#
# This file is part of LiteX.
#
# Copyright (c) 2025 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build.colognechip.colognechip import _build_ccf
from litex.build import tools
from litex.build.yosys_nextpnr_toolchain import YosysNextPNRToolchain

# PeppercornToolchain ------------------------------------------------------------------------------

class PeppercornToolchain(YosysNextPNRToolchain):
    family     = "gatemate"
    synth_fmt  = "json"
    pnr_fmt    = "txt"
    packer_cmd = "gmpack"

    def __init__(self):
        super().__init__()
        self._synth_opts = "-luttree -nomx8"

    # Timing Constraints (.sdc) --------------------------------------------------------------------

    def build_timing_constraints(self, vns):
        max_freq = 0
        sdc      = []

        # Clock constraints
        for clk, [period, name] in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            # Search for the highest frequency.
            freq = int(1e3 / period)
            if freq > max_freq:
                max_freq = freq

            is_port = False
            for sig, pins, others, resname in self.named_sc:
                if sig == vns.get_name(clk):
                    is_port = True
            clk_sig = self._vns.get_name(clk)
            if name is None:
                name = clk_sig
            if is_port:
                tpl = "create_clock -name {name} -period {period} [get_ports {{{clk}}}]"
                sdc.append(tpl.format(name=name, clk=clk_sig, period=str(period)))
            else:
                tpl = "create_clock -name {name} -period {period} [get_nets {{{clk}}}]"
                sdc.append(tpl.format(name=name, clk=clk_sig, period=str(period)))

        # False path constraints
        for from_, to in sorted(self.false_paths, key=lambda x: (x[0].duid, x[1].duid)):
            tpl = "set_false_path -from [get_clocks {{{from_}}}] -to [get_clocks {{{to}}}]"
            sdc.append(tpl.format(from_=vns.get_name(from_), to=vns.get_name(to)))

        # Generate .sdc
        tools.write_to_file("{}.sdc".format(self._build_name), "\n".join(sdc))

        # FIXME: NextPNRWrapper is constructed at finalize level, too early
        # to update self._pnr_opts. The solution is to update _nextpnr instance.
        self._nextpnr._pnr_opts += f" --freq {max_freq}"

    # IO Constraints (.ccf) ------------------------------------------------------------------------

    def build_io_constraints(self):
        ccf = _build_ccf(self.named_sc, self.named_pc)
        tools.write_to_file(f"{self._build_name}.ccf", "\n".join(ccf))
        return (f"{self._build_name}.ccf", "CCF")

    def finalize(self):
        pnr_opts = "--device {device}" + \
            " --vopt ccf={top}.ccf --router router2"
        #pnr_opts += " --sdc {top}.sdc"
        self._pnr_opts += pnr_opts.format(
            device     = self.platform.device,
            top        = self._build_name,
        )

        self._packer_opts += "{top}.txt {top}.bit".format(
            top = self._build_name
        )

        YosysNextPNRToolchain.finalize(self)

    def build(self, platform, fragment, **kwargs):
        self.platform = platform
        # CologneChip does not have distributed RAM
        self._yosys_cmds = [
            "hierarchy -top {build_name}",
            "setattr -unset ram_style a:ram_style=distributed",
        ]

        return YosysNextPNRToolchain.build(self, platform, fragment, **kwargs)

def peppercorn_args(parser):
    pass

def peppercorn_argdict(args):
    return {}
