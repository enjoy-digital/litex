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
# - use constraint file when prjtrellis will support it.


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


def yosys_import_sources(platform):
    includes = ""
    reads = []
    for path in platform.verilog_include_paths:
        includes += " -I" + path
    for filename, language, library in platform.sources:
        reads.append("read_{}{} {}".format(
            language, includes, filename))
    return "\n".join(reads)


def generate_prjtrellis_top(top_file, platform, vns):
    # resolve ios directions / types
    ios, _ = platform.resolve_signals(vns)
    ios_direction = {}
    ios_type = {}
    cm = platform.constraint_manager
    for io_name, io_pins, _, _ in ios:
        for cm_sig, cm_pins, _, _ in cm.get_sig_constraints():
            if io_pins == cm_pins:
                ios_direction[io_name] = cm_sig.direction
                ios_type[io_name] = cm_sig.type
        last_io_name = io_name

    # prjtrellis module / ios declaration
    top_contents = []
    top_contents.append("module prjtrellis_{build_name}(")
    ios_declaration = ""
    for io_name, io_pins, io_others, _ in ios:
        for io_other in io_others:
            if isinstance(io_other, IOStandard):
                io_standard = io_other.name
        for i, io_pin in enumerate(io_pins):
            ios_declaration += "(* LOC=\"{}\" *) (* IO_TYPE=\"{}\" *)\n".format(io_pin, io_standard)
            ios_declaration += "\t" + ios_direction[io_name] + " " + io_name + "_io" + (str(i) if len(io_pins) > 1 else "")
            ios_declaration += ",\n" if io_name != last_io_name or (i != len(io_pins) - 1) else ""
    top_contents.append(ios_declaration)
    top_contents.append(");\n")

    # top signals declaration
    signals_declaration = ""
    for io_name, io_pins, _, _ in ios:
        signals_declaration += ios_type[io_name] + " "
        if len(io_pins) > 1:
            signals_declaration += "[{}:0] ".format(len(io_pins) - 1)
        signals_declaration += io_name
        signals_declaration += ";\n"
    top_contents.append(signals_declaration)

    # trellis_ios declaration
    trellis_io_declaration = ""
    for io_name, io_pins, io_others, _ in ios:
        for i, io_pin in enumerate(io_pins):
            io_suffix = "io" + str(i) if len(io_pins) > 1 else "io"
            if ios_direction[io_name] == "input":
                trellis_io_declaration += \
                "TRELLIS_IO #(.DIR(\"INPUT\")) {} (.B({}), .O({}));\n".format(
                    io_name + "_buf" + str(i), io_name + "_" + io_suffix, io_name + "[" + str(i) + "]")
            elif ios_direction[io_name] == "output":
                trellis_io_declaration += \
                "TRELLIS_IO #(.DIR(\"OUTPUT\")) {} (.B({}), .I({}));\n".format(
                    io_name + "_buf" + str(i), io_name + "_" + io_suffix, io_name + "[" + str(i) + "]")
            else:
                pass # handled by Migen's Tristate
    top_contents.append(trellis_io_declaration)

    # top_recopy:
    # - skip module definition.
    # - use ios names for inouts.
    def replace_inouts(l):
        r = l
        for io_name, io_pins, _, _ in ios:
            if ios_direction[io_name] == "inout":
                if len(io_pins) > 1:
                    for i in range(len(io_pins)):
                        r = r.replace(io_name + "[" + str(i) + "]", io_name + "_io" + str(i))
                else:
                    r = r.replace(io_name, io_name + "_io")
        return r

    skip = True
    f = open(top_file, "r")
    for l in f:
        if not skip:
            l = l.replace("\n", "")
            l = l.replace("{", "{{")
            l = l.replace("}", "}}")
            l = replace_inouts(l)
            top_contents.append(l)
        if ");" in l:
            skip = False
    f.close()

    top_contents = "\n".join(top_contents)

    return top_contents


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
            toolchain_path = "/opt/prjtrellis/"
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        # generate verilog
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        top_output = platform.get_verilog(fragment)
        top_file = build_name + ".v"
        top_output.write(top_file)

        # insert constraints and trellis_io to generated verilog
        prjtrellis_top_file = build_name + "_prjtrellis.v"
        prjtrellis_top_contents = generate_prjtrellis_top(top_file, platform, top_output.ns)
        prjtrellis_top_contents = prjtrellis_top_contents.format(build_name=build_name)
        tools.write_to_file(prjtrellis_top_file, prjtrellis_top_contents)
        platform.add_source(prjtrellis_top_file)

        # generate yosys script
        yosys_script_file = build_name + ".ys"
        yosys_script_contents = [
            yosys_import_sources(platform),
            "synth_ecp5 -nomux -json {build_name}.json -top prjtrellis_{build_name}"
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
            "nextpnr-ecp5 --json {build_name}.json --textcfg {build_name}.config --basecfg {basecfg} --{architecture}",
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
