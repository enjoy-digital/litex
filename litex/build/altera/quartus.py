#
# This file is part of LiteX.
#
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 msloniewski <marcin.sloniewski@gmail.com>
# Copyright (c) 2019 vytautasb <v.buitvydas@limemicro.com>
# Copyright (c) 2022 Gwenhael Goavec-Merou <gwenhael.goavec-merou@trabucayre.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import sys
import math
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import Pins, IOStandard, Misc
from litex.build.generic_toolchain import GenericToolchain
from litex.build import tools

# AlteraQuartusToolchain ---------------------------------------------------------------------------

class AlteraQuartusToolchain(GenericToolchain):
    attr_translate = {
        "keep": ("keep", 1),
    }

    def __init__(self):
        super().__init__()
        self.additional_sdc_commands = []
        self.additional_qsf_commands = []
        self.cst                     = []

    # IO/Placement Constraints (.qsf) --------------------------------------------------------------

    def _format_constraint(self, c, signame, fmt_r):
        # IO location constraints
        if isinstance(c, Pins):
            tpl = "set_location_assignment -comment \"{name}\" -to {signame} Pin_{pin}"
            return tpl.format(signame=signame, name=fmt_r, pin=c.identifiers[0])

        # IO standard constraints
        elif isinstance(c, IOStandard):
            tpl = "set_instance_assignment -name io_standard -comment \"{name}\" \"{std}\" -to {signame}"
            return tpl.format(signame=signame, name=fmt_r, std=c.name)

        # Others constraints
        elif isinstance(c, Misc):
            if not isinstance(c.misc, str) and len(c.misc) == 2:
                tpl = "set_instance_assignment -comment \"{name}\" -name {misc[0]} \"{misc[1]}\" -to {signame}"
                return tpl.format(signame=signame, name=fmt_r, misc=c.misc)
            else:
                tpl = "set_instance_assignment -comment \"{name}\"  -name {misc} -to {signame}"
                return tpl.format(signame=signame, name=fmt_r, misc=c.misc)

    def _format_qsf_constraint(self, signame, pin, others, resname):
        fmt_r = "{}:{}".format(*resname[:2])
        if resname[2] is not None:
            fmt_r += "." + resname[2]
        fmt_c = [self._format_constraint(c, signame, fmt_r) for c in ([Pins(pin)] + others)]
        return '\n'.join(fmt_c)

    def _is_virtual_pin(self, pin_name):
        return pin_name in (
            "altera_reserved_tms",
            "altera_reserved_tck",
            "altera_reserved_tdi",
            "altera_reserved_tdo",
        )

    def build_io_constraints(self):
        for sig, pins, others, resname in self.named_sc:
            if len(pins) > 1:
                for i, p in enumerate(pins):
                    if self._is_virtual_pin(p):
                        continue
                    self.cst.append(self._format_qsf_constraint("{}[{}]".format(sig, i), p, others, resname))
            else:
                if self._is_virtual_pin(pins[0]):
                    continue
                self.cst.append(self._format_qsf_constraint(sig, pins[0], others, resname))
        if self.named_pc:
            self.cst.append("\n\n".join(self.named_pc))

    # Timing Constraints (.sdc) --------------------------------------------------------------------

    def build_timing_constraints(self, vns):
        sdc = []

        # Clock constraints
        for clk, period in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            is_port = False
            for sig, pins, others, resname in self.named_sc:
                if sig == vns.get_name(clk):
                    is_port = True
            if is_port:
                tpl = "create_clock -name {clk} -period {period} [get_ports {{{clk}}}]"
                sdc.append(tpl.format(clk=vns.get_name(clk), period=str(period)))
            else:
                tpl = "create_clock -name {clk} -period {period} [get_nets {{{clk}}}]"
                sdc.append(tpl.format(clk=vns.get_name(clk), period=str(period)))

        # Enable automatical constraint generation for PLLs
        sdc.append("derive_pll_clocks -use_net_name")

        # False path constraints
        for from_, to in sorted(self.false_paths, key=lambda x: (x[0].duid, x[1].duid)):
            tpl = "set_false_path -from [get_clocks {{{from_}}}] -to [get_clocks {{{to}}}]"
            sdc.append(tpl.format(from_=vns.get_name(from_), to=vns.get_name(to)))

        # Add additional commands
        sdc += self.additional_sdc_commands

        # Generate .sdc
        tools.write_to_file("{}.sdc".format(self._build_name), "\n".join(sdc))

    # Project (.qsf) -------------------------------------------------------------------------------

    def build_project(self):
        qsf = []

        # Set device
        qsf.append("set_global_assignment -name DEVICE {}".format(self.platform.device))

        # Add sources
        for filename, language, library, *copy in self.platform.sources:
            if language == "verilog": language = "systemverilog" # Enforce use of SystemVerilog
            tpl = "set_global_assignment -name {lang}_FILE {path} -library {lib}"
            # Do not add None type files
            if language is not None:
                qsf.append(tpl.format(lang=language.upper(), path=filename.replace("\\", "/"), lib=library))
            # Check if the file is a header. Those should not be explicitly added to qsf,
            # but rather included in include search_path
            else:
                if filename.endswith(".svh") or filename.endswith(".vh"):
                    fpath = os.path.dirname(filename)
                    if fpath not in platform.verilog_include_paths:
                        platform.verilog_include_paths.append(fpath)

        # Add IPs
        for filename in self.platform.ips:
            qsf.append("set_global_assignment -name QSYS_FILE " + filename.replace("\\", "/"))

        # Add include paths
        for path in self.platform.verilog_include_paths:
            qsf.append("set_global_assignment -name SEARCH_PATH {}".format(path.replace("\\", "/")))

        # Set top level
        qsf.append("set_global_assignment -name top_level_entity " + self._build_name)

        # Add io, placement constraints
        qsf.append("\n".join(self.cst))

        # Set timing constraints
        qsf.append("set_global_assignment -name SDC_FILE {}.sdc".format(self._build_name))

        # Add additional commands
        qsf += self.additional_qsf_commands

        # Generate .qsf
        tools.write_to_file("{}.qsf".format(self._build_name), "\n".join(qsf))

    # Script ---------------------------------------------------------------------------------------

    def build_script(self):
        build_name = self._build_name

        if sys.platform in ["win32", "cygwin"]:
            script_file = "build_" + build_name + ".bat"
            script_contents = "REM Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n"
        else:
            script_file = "build_" + build_name + ".sh"
            script_contents = "#!/usr/bin/env bash\n"
            script_contents += "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n"
            script_contents += "set -e -u -x -o pipefail\n"
        script_contents += """
quartus_map --read_settings_files=on  --write_settings_files=off {build_name} -c {build_name}
quartus_fit --read_settings_files=off --write_settings_files=off {build_name} -c {build_name}
quartus_asm --read_settings_files=off --write_settings_files=off {build_name} -c {build_name}
quartus_sta {build_name} -c {build_name}"""
        if self.platform.create_rbf:
            if sys.platform in ["win32", "cygwin"]:
              script_contents += """
if exist "{build_name}.sof" (
    quartus_cpf -c {build_name}.sof {build_name}.rbf
)
"""
            else:
              script_contents += """
if [ -f "{build_name}.sof" ]
then
    quartus_cpf -c {build_name}.sof {build_name}.rbf
fi
"""
        script_contents = script_contents.format(build_name=build_name)
        tools.write_to_file(script_file, script_contents, force_unix=True)

        return script_file

    def run_script(self, script):
        if sys.platform in ["win32", "cygwin"]:
            shell = ["cmd", "/c"]
        else:
            shell = ["bash"]

        if which("quartus_map") is None:
            msg = "Unable to find Quartus toolchain, please:\n"
            msg += "- Add Quartus toolchain to your $PATH."
            raise OSError(msg)

        if subprocess.call(shell + [script]) != 0:
            raise OSError("Error occured during Quartus's script execution.")
