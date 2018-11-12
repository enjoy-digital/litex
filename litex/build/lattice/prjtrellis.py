# This file is Copyright (c) 2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import os
import subprocess

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.lattice import common

# TODO:
# - add timing constraint support.
# - check/document attr_translate.

nextpnr_ecp5_architectures = {
    "lfe5u-25f": "25k",
    "lfe5u-45f": "45k",
    "lfe5u-85f": "85k",
    "lfe5um-25f": "um-25k",
    "lfe5um-45f": "um-45k",
    "lfe5um-85f": "um-85k",
    "lfe5um5g-25f": "um5g-25k",
    "lfe5um5g-45f": "um5g-45k",
    "lfe5um5g-85f": "um5g-85k",
}


def _format_constraint(c):
    if isinstance(c, Pins):
        return ("LOCATE COMP ", " SITE " + "\"" + c.identifiers[0] + "\"")
    elif isinstance(c, IOStandard):
        return ("IOBUF PORT ", " IO_TYPE=" + c.name)
    elif isinstance(c, Misc):
        return ("IOBUF PORT ", " " + c.misc)


def _format_lpf(signame, pin, others, resname):
    fmt_c = [_format_constraint(c) for c in ([Pins(pin)] + others)]
    r = ""
    for pre, suf in fmt_c:
        r += pre + "\"" + signame + "\"" + suf + ";\n"
    return r


def _build_lpf(named_sc, named_pc):
    r = "BLOCK RESETPATHS;\n"
    r += "BLOCK ASYNCPATHS;\n"
    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                r += _format_lpf(sig + "[" + str(i) + "]", p, others, resname)
        else:
            r += _format_lpf(sig, pins[0], others, resname)
    if named_pc:
        r += "\n" + "\n\n".join(named_pc)
    return r


def yosys_import_sources(platform):
    includes = ""
    reads = []
    for path in platform.verilog_include_paths:
        includes += " -I" + path
    for filename, language, library in platform.sources:
        reads.append("read_{}{} {}".format(
            language, includes, filename))
    return "\n".join(reads)


class LatticePrjTrellisToolchain:
    attr_translate = {
        # FIXME: document
        "keep": ("keep", "true"),
        "no_retiming": None,
        "async_reg": None,
        "mr_ff": None,
        "mr_false_path": None,
        "ars_ff1": None,
        "ars_ff2": None,
        "ars_false_path": None,
        "no_shreg_extract": None
    }

    special_overrides = common.lattice_ecpx_prjtrellis_special_overrides

    def build(self, platform, fragment, build_dir="build", build_name="top",
              toolchain_path=None, run=True):
        if toolchain_path is None:
            toolchain_path = "/usr/share/trellis/"
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # generate verilog
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        top_output = platform.get_verilog(fragment, name=build_name)
        named_sc, named_pc = platform.resolve_signals(top_output.ns)
        top_file = build_name + ".v"
        top_output.write(top_file)
        platform.add_source(top_file)

        # generate constraints
        tools.write_to_file(build_name + ".lpf", _build_lpf(named_sc, named_pc))

        # generate yosys script
        yosys_script_file = build_name + ".ys"
        yosys_script_contents = [
            yosys_import_sources(platform),
            "synth_ecp5 -nomux -json {build_name}.json -top {build_name}"
        ]
        yosys_script_contents = "\n".join(yosys_script_contents)
        yosys_script_contents = yosys_script_contents.format(build_name=build_name)
        tools.write_to_file(yosys_script_file, yosys_script_contents)

        # transform platform.device to nextpnr's architecture / basecfg
        (family, size, package) = platform.device.split("-")
        architecture = nextpnr_ecp5_architectures[(family + "-" + size).lower()]
        basecfg = "empty_" + (family + "-" + size).lower() + ".config"
        basecfg = os.path.join(toolchain_path, "misc", "basecfgs", basecfg)

        # generate build script
        build_script_file = "build_" + build_name + ".sh"
        build_script_contents = [
            "yosys -q -l {build_name}.rpt {build_name}.ys",
            "nextpnr-ecp5 --json {build_name}.json --lpf {build_name}.lpf --textcfg {build_name}.config --basecfg {basecfg} --{architecture}",
            "ecppack {build_name}.config {build_name}.bit"

        ]
        build_script_contents = "\n".join(build_script_contents)
        build_script_contents = build_script_contents.format(
            build_name=build_name,
            architecture=architecture,
            basecfg=basecfg)
        tools.write_to_file(build_script_file, build_script_contents)

        # run scripts
        if run:
            if subprocess.call(["bash", build_script_file]) != 0:
                raise OSError("Subprocess failed")

        os.chdir(cwd)

        return top_output.ns

    def add_period_constraint(self, platform, clk, period):
        print("TODO: add_period_constraint")
