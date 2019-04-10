# This file is Copyright (c) 2013 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import os
import subprocess

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import Pins, IOStandard, Misc
from litex.build import tools


def _format_constraint(c, signame, fmt_r):
    if isinstance(c, Pins):
        return "set_location_assignment -comment \"{name}\" " \
            "-to {signame} Pin_{pin}".format(
                signame=signame,
                name=fmt_r,
                pin=c.identifiers[0])
    elif isinstance(c, IOStandard):
        return "set_instance_assignment -name io_standard " \
            "-comment \"{name}\" \"{std}\" -to {signame}".format(
                signame=signame,
                name=fmt_r,
                std=c.name)
    elif isinstance(c, Misc):
        if not isinstance(c.misc, str) and len(c.misc) == 2:
            return "set_instance_assignment -comment \"{name}\" " \
                "-name {misc[0]} \"{misc[1]}\" -to {signame}".format(
                    signame=signame,
                    name=fmt_r,
                    misc=c.misc)
        else:
            return "set_instance_assignment -comment \"{name}\" " \
                "-name {misc} " \
                "-to {signame}".format(
                    signame=signame,
                    name=fmt_r,
                    misc=c.misc)


def _format_qsf(signame, pin, others, resname):
    fmt_r = "{}:{}".format(*resname[:2])
    if resname[2] is not None:
        fmt_r += "." + resname[2]

    fmt_c = [_format_constraint(c, signame, fmt_r) for c in
             ([Pins(pin)] + others)]

    return '\n'.join(fmt_c)


def _build_qsf(named_sc, named_pc, build_name):
    lines = []
    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                lines.append(
                    _format_qsf("{}[{}]".format(sig, i), p, others, resname))
        else:
            lines.append(_format_qsf(sig, pins[0], others, resname))

    if named_pc:
        lines.append("")
        lines.append("\n\n".join(named_pc))

    # Set top level name to "build_name" in .qsf file instead always use "top" name
    lines.append("set_global_assignment -name top_level_entity " + build_name)
    return "\n".join(lines)


def _build_files(device, sources, vincpaths, named_sc, named_pc, build_name):
    lines = []
    for filename, language, library in sources:
        # Enforce use of SystemVerilog
        # (Quartus does not support global parameters in Verilog)
        if language == "verilog":
            language = "systemverilog"
        lines.append(
            "set_global_assignment -name {lang}_FILE {path} "
            "-library {lib}".format(
                lang=language.upper(),
                path=filename.replace("\\", "/"),
                lib=library))

    for path in vincpaths:
        lines.append("set_global_assignment -name SEARCH_PATH {}".format(
            path.replace("\\", "/")))

    lines.append(_build_qsf(named_sc, named_pc, build_name))
    lines.append("set_global_assignment -name DEVICE {}".format(device))
    tools.write_to_file("{}.qsf".format(build_name), "\n".join(lines))


def _run_quartus(build_name, quartus_path):
    build_script_contents = """# Autogenerated by Migen

set -e

quartus_map --read_settings_files=on --write_settings_files=off {build_name} -c {build_name}
quartus_fit --read_settings_files=off --write_settings_files=off {build_name} -c {build_name}
quartus_asm --read_settings_files=off --write_settings_files=off {build_name} -c {build_name}
quartus_sta {build_name} -c {build_name}
if [ -f "{build_name}.sof" ]
then
    quartus_cpf -c {build_name}.sof {build_name}.rbf
fi

""".format(build_name=build_name)  # noqa
    build_script_file = "build_" + build_name + ".sh"
    tools.write_to_file(build_script_file,
                        build_script_contents,
                        force_unix=True)

    if subprocess.call(["bash", build_script_file]):
        raise OSError("Subprocess failed")


class AlteraQuartusToolchain:
    def build(self, platform, fragment, build_dir="build", build_name="top",
              toolchain_path=None, run=True, **kwargs):
        if toolchain_path is None:
            toolchain_path="/opt/Altera"
        cwd = os.getcwd()
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)

        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        named_sc, named_pc = platform.resolve_signals(v_output.ns)
        v_file = build_name + ".v"
        v_output.write(v_file)
        sources = platform.sources | {(v_file, "verilog", "work")}
        _build_files(platform.device,
                     sources,
                     platform.verilog_include_paths,
                     named_sc,
                     named_pc,
                     build_name)
        if run:
            _run_quartus(build_name, toolchain_path)

        os.chdir(cwd)

        return v_output.ns

    def add_period_constraint(self, platform, clk, period):
        # TODO: handle differential clk
        platform.add_platform_command(
            "set_global_assignment -name duty_cycle 50 -section_id {clk}",
            clk=clk)
        platform.add_platform_command(
            "set_global_assignment -name fmax_requirement \"{freq} MHz\" "
            "-section_id {clk}".format(freq=(1. / period) * 1000,
                                       clk="{clk}"),
            clk=clk)
