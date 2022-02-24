#
# This file is part of LiteX.
#
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 msloniewski <marcin.sloniewski@gmail.com>
# Copyright (c) 2019 vytautasb <v.buitvydas@limemicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import sys
import math
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import Pins, IOStandard, Misc
from litex.build import tools

# IO/Placement Constraints (.qsf) ------------------------------------------------------------------

def _format_constraint(c, signame, fmt_r):
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

def _format_qsf_constraint(signame, pin, others, resname):
    fmt_r = "{}:{}".format(*resname[:2])
    if resname[2] is not None:
        fmt_r += "." + resname[2]
    fmt_c = [_format_constraint(c, signame, fmt_r) for c in ([Pins(pin)] + others)]
    return '\n'.join(fmt_c)

def _is_virtual_pin(pin_name):
    return pin_name in (
        "altera_reserved_tms",
        "altera_reserved_tck",
        "altera_reserved_tdi",
        "altera_reserved_tdo",
    )

def _build_qsf_constraints(named_sc, named_pc):
    qsf = []
    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                if _is_virtual_pin(p):
                    continue
                qsf.append(_format_qsf_constraint("{}[{}]".format(sig, i), p, others, resname))
        else:
            if _is_virtual_pin(pins[0]):
                continue
            qsf.append(_format_qsf_constraint(sig, pins[0], others, resname))
    if named_pc:
        qsf.append("\n\n".join(named_pc))
    return "\n".join(qsf)

# Timing Constraints (.sdc) ------------------------------------------------------------------------

def _build_sdc(clocks, false_paths, vns, named_sc, build_name, additional_sdc_commands):
    sdc = []

    # Clock constraints
    for clk, period in sorted(clocks.items(), key=lambda x: x[0].duid):
        is_port = False
        for sig, pins, others, resname in named_sc:
            if sig == vns.get_name(clk):
                is_port = True
        if is_port:
            tpl = "create_clock -name {clk} -period {period} [get_ports {{{clk}}}]"
            sdc.append(tpl.format(clk=vns.get_name(clk), period=str(period)))
        else:
            tpl = "create_clock -name {clk} -period {period} [get_nets {{{clk}}}]"
            sdc.append(tpl.format(clk=vns.get_name(clk), period=str(period)))

    # False path constraints
    for from_, to in sorted(false_paths, key=lambda x: (x[0].duid, x[1].duid)):
        tpl = "set_false_path -from [get_clocks {{{from_}}}] -to [get_clocks {{{to}}}]"
        sdc.append(tpl.format(from_=vns.get_name(from_), to=vns.get_name(to)))

    # Add additional commands
    sdc += additional_sdc_commands

    # Generate .sdc
    tools.write_to_file("{}.sdc".format(build_name), "\n".join(sdc))

# Project (.qsf) -----------------------------------------------------------------------------------

def _build_qsf(device, ips, sources, vincpaths, named_sc, named_pc, build_name, additional_qsf_commands):
    qsf = []

    # Set device
    qsf.append("set_global_assignment -name DEVICE {}".format(device))

    # Add sources
    for filename, language, library, *copy in sources:
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
                if fpath not in vincpaths:
                    vincpaths.append(fpath)

    # Add ips
    for filename in ips:
        tpl = "set_global_assignment -name QSYS_FILE {filename}"
        qsf.append(tpl.replace(filename=filename.replace("\\", "/")))

    # Add include paths
    for path in vincpaths:
        qsf.append("set_global_assignment -name SEARCH_PATH {}".format(path.replace("\\", "/")))

    # Set top level
    qsf.append("set_global_assignment -name top_level_entity " + build_name)

    # Add io, placement constraints
    qsf.append(_build_qsf_constraints(named_sc, named_pc))

    # Set timing constraints
    qsf.append("set_global_assignment -name SDC_FILE {}.sdc".format(build_name))

    # Add additional commands
    qsf += additional_qsf_commands

    # Generate .qsf
    tools.write_to_file("{}.qsf".format(build_name), "\n".join(qsf))

# Script -------------------------------------------------------------------------------------------

def _build_script(build_name, create_rbf):
    if sys.platform in ["win32", "cygwin"]:
        script_contents = "REM Autogenerated by LiteX / git: " + tools.get_litex_git_revision()
        script_file = "build_" + build_name + ".bat"
    else:
        script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision()
        script_file = "build_" + build_name + ".sh"
    script_contents += """
quartus_map --read_settings_files=on  --write_settings_files=off {build_name} -c {build_name}
quartus_fit --read_settings_files=off --write_settings_files=off {build_name} -c {build_name}
quartus_asm --read_settings_files=off --write_settings_files=off {build_name} -c {build_name}
quartus_sta {build_name} -c {build_name}"""
    if create_rbf:
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

def _run_script(script):
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

# AlteraQuartusToolchain ---------------------------------------------------------------------------

class AlteraQuartusToolchain:
    attr_translate = {}

    def __init__(self):
        self.clocks      = dict()
        self.false_paths = set()
        self.additional_sdc_commands = []
        self.additional_qsf_commands = []

    def build(self, platform, fragment,
        build_dir      = "build",
        build_name     = "top",
        run            = True,
        **kwargs):

        # Create build directory
        cwd = os.getcwd()
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)

        # Finalize design
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        # Generate verilog
        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        named_sc, named_pc = platform.resolve_signals(v_output.ns)
        v_file = build_name + ".v"
        v_output.write(v_file)
        platform.add_source(v_file)

        # Generate design timing constraints file (.sdc)
        _build_sdc(
            clocks                  = self.clocks,
            false_paths             = self.false_paths,
            vns                     = v_output.ns,
            named_sc                = named_sc,
            build_name              = build_name,
            additional_sdc_commands = self.additional_sdc_commands)

        # Generate design project and location constraints file (.qsf)
        _build_qsf(
            device                  = platform.device,
            ips                     = platform.ips,
            sources                 = platform.sources,
            vincpaths               = platform.verilog_include_paths,
            named_sc                = named_sc,
            named_pc                = named_pc,
            build_name              = build_name,
            additional_qsf_commands = self.additional_qsf_commands)

        # Generate build script
        script = _build_script(build_name, platform.create_rbf)

        # Run
        if run:
            _run_script(script)

        os.chdir(cwd)

        return v_output.ns

    def add_period_constraint(self, platform, clk, period):
        clk.attr.add("keep")
        period = math.floor(period*1e3)/1e3 # round to lowest picosecond
        if clk in self.clocks:
            if period != self.clocks[clk]:
                raise ValueError("Clock already constrained to {:.2f}ns, new constraint to {:.2f}ns"
                    .format(self.clocks[clk], period))
        self.clocks[clk] = period

    def add_false_path_constraint(self, platform, from_, to):
        from_.attr.add("keep")
        to.attr.add("keep")
        if (to, from_) not in self.false_paths:
            self.false_paths.add((from_, to))
