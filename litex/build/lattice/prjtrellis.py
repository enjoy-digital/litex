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
# - add inout support to iowrapper.
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


def yosys_import_sources(platform):
    includes = ""
    reads = []
    for path in platform.verilog_include_paths:
        includes += " -I" + path
    for filename, language, library in platform.sources:
        reads.append("read_{}{} {}".format(
            language, includes, filename))
    return "\n".join(reads)


def generate_prjtrellis_iowrapper(platform, vns):
    ios, _ = platform.resolve_signals(vns)
    ios_direction = {}
    # resolve ios directions
    cm = platform.constraint_manager
    for io_name, io_pins, _, _ in ios:
        for cm_sig, cm_pins, _, _ in cm.get_sig_constraints():
            if io_pins == cm_pins:
                ios_direction[io_name] = cm_sig.direction
        last_io_name = io_name

    iowrapper_contents = []
    iowrapper_contents.append("module {build_name}_iowrapper(")

    # ios declaration
    ios_declaration = ""
    for io_name, io_pins, io_others, _ in ios:
        for io_other in io_others:
            if isinstance(io_other, IOStandard):
                io_standard = io_other.name
        for i, io_pin in enumerate(io_pins):
            ios_declaration += "(* LOC=\"{}\" *) (* IO_TYPE=\"{}\" *)\n".format(io_pin, io_standard)
            ios_declaration += "\t" + ios_direction[io_name] + " " + io_name + "_io" + (str(i) if len(io_pins) > 1 else "")
            ios_declaration += ",\n" if io_name != last_io_name or (i != len(io_pins) - 1) else ""
    iowrapper_contents.append(ios_declaration)
    iowrapper_contents.append(");\n")

    # wires declaration
    wires_declaration = ""
    for io_name, io_pins, _, _ in ios:
        wires_declaration += "wire "
        if len(io_pins) > 1:
            wires_declaration += "[{}:0] ".format(len(io_pins) - 1)
        wires_declaration += io_name
        wires_declaration += ";\n"
    iowrapper_contents.append(wires_declaration)

    # trellis_io declaration
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
    iowrapper_contents.append(trellis_io_declaration)

    # top declaration
    top_declaration = "{build_name} _{build_name}(\n"
    for io_name, io_pins, _, _ in ios:
        if ios_direction[io_name] == "inout":
            if len(io_pins) > 1:
                io_concat_name = "{{"
                io_concat_name += ",".join([io_name + "_io" + str(i) for i in range(len(io_pins))])
                io_concat_name += "}}"
                top_declaration += "\t." + io_name + "(" + io_concat_name + ")"
            else:
                top_declaration += "\t." + io_name + "(" + io_name + "_io)"
        else:
            top_declaration += "\t." + io_name + "(" + io_name + ")"
        top_declaration += ",\n" if io_name != last_io_name else "\n"
    top_declaration += ");\n"
    iowrapper_contents.append(top_declaration)

    iowrapper_contents.append("endmodule")

    iowrapper_contents = "\n".join(iowrapper_contents)

    return iowrapper_contents


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

        v_output = platform.get_verilog(fragment)
        v_file = build_name + ".v"
        v_output.write(v_file)
        platform.add_source(v_file)

        # generate iowrapper (with constraints and trellis_ios)
        # FIXME: remove when prjtrellis will support constraint files
        iowrapper_file = build_name + "_iowrapper.v"
        iowrapper_contents = generate_prjtrellis_iowrapper(platform, v_output.ns)
        iowrapper_contents = iowrapper_contents.format(build_name=build_name)
        tools.write_to_file(iowrapper_file, iowrapper_contents)
        platform.add_source(iowrapper_file)

        # generate yosys script
        yosys_script_file = build_name + ".ys"
        yosys_script_contents = [
            yosys_import_sources(platform),
            "synth_ecp5 -nomux -json {build_name}.json -top {build_name}_iowrapper"
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

        return v_output.ns

    def add_period_constraint(self, platform, clk, period):
        print("TODO: add_period_constraint")
