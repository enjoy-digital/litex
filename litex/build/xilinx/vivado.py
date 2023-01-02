#
# This file is part of LiteX.
#
# Copyright (c) 2014-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import sys
import math
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build import tools
from litex.build.xilinx import common
from litex.build.generic_toolchain import GenericToolchain

# Constraints (.xdc) -------------------------------------------------------------------------------

def _xdc_separator(msg):
    r =  "#"*80 + "\n"
    r += "# " + msg + "\n"
    r += "#"*80 + "\n"
    return r

def _format_xdc_constraint(c):
    if isinstance(c, Pins):
        return "set_property LOC " + c.identifiers[0]
    elif isinstance(c, IOStandard):
        return "set_property IOSTANDARD " + c.name
    elif isinstance(c, Drive):
        return "set_property DRIVE " + str(c.strength)
    elif isinstance(c, Misc):
        return "set_property " + c.misc.replace("=", " ")
    elif isinstance(c, Inverted):
        return None
    else:
        raise ValueError(f"unknown constraint {c}")


def _format_xdc(signame, resname, *constraints):
    fmt_c = [_format_xdc_constraint(c) for c in constraints]
    fmt_r = resname[0] + ":" + str(resname[1])
    if resname[2] is not None:
        fmt_r += "." + resname[2]
    r = f"# {fmt_r}\n"
    for c in fmt_c:
        if c is not None:
            r += c + " [get_ports {" + signame + "}]\n"
    r += "\n"
    return r


def _build_xdc(named_sc, named_pc):
    r = _xdc_separator("IO constraints")
    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                r += _format_xdc(sig + "[" + str(i) + "]", resname, Pins(p), *others)
        elif pins:
            r += _format_xdc(sig, resname, Pins(pins[0]), *others)
        else:
            r += _format_xdc(sig, resname, *others)
    if named_pc:
        r += _xdc_separator("Design constraints")
        r += "\n" + "\n\n".join(named_pc)
    return r

# XilinxVivadoToolchain ----------------------------------------------------------------------------

class XilinxVivadoCommands(list):
    def add(self, command, **signals):
        self.append((command, signals))

    def resolve(self, vns):
        named_commands = []
        for command in self:
            if isinstance(command, str):
                named_commands.append(command)
            else:
                template, args = command
                name_dict = dict((k, vns.get_name(sig)) for k, sig in args.items())
                named_commands.append(template.format(**name_dict))
        return named_commands


class XilinxVivadoToolchain(GenericToolchain):
    attr_translate = {
        "keep":            ("dont_touch", "true"),
        "no_retiming":     ("dont_touch", "true"),
        "async_reg":       ("async_reg",  "true"),
        "mr_ff":           ("mr_ff",      "true"), # user-defined attribute
        "ars_ff1":         ("ars_ff1",    "true"), # user-defined attribute
        "ars_ff2":         ("ars_ff2",    "true"), # user-defined attribute
        "no_shreg_extract": None
    }

    def __init__(self):
        super().__init__()
        self.bitstream_commands         = []
        self.additional_commands        = []
        self.pre_synthesis_commands     = XilinxVivadoCommands()
        self.pre_placement_commands     = XilinxVivadoCommands()
        self.pre_routing_commands       = XilinxVivadoCommands()
        self.incremental_implementation = False
        self._synth_mode                = "vivado"
        self._enable_xpm                = False

    def finalize(self):
        # Convert clocks and false path to platform commands
        self._build_clock_constraints()
        self._build_false_path_constraints()

    def build(self, platform, fragment,
        synth_mode                           = "vivado",
        enable_xpm                           = False,
        vivado_synth_directive               = "default",
        opt_directive                        = "default",
        vivado_place_directive               = "default",
        vivado_post_place_phys_opt_directive = None,
        vivado_route_directive               = "default",
        vivado_post_route_phys_opt_directive = "default",
        vivado_max_threads                   = None,
        **kwargs):

        self._synth_mode = synth_mode
        self._enable_xpm = enable_xpm

        self.vivado_synth_directive               = vivado_synth_directive
        self.opt_directive                        = opt_directive
        self.vivado_place_directive               = vivado_place_directive
        self.vivado_post_place_phys_opt_directive = vivado_post_place_phys_opt_directive
        self.vivado_route_directive               = vivado_route_directive
        self.vivado_post_route_phys_opt_directive = vivado_post_route_phys_opt_directive
        self.vivado_max_threads                   = vivado_max_threads

        return GenericToolchain.build(self, platform, fragment, **kwargs)

    # Constraints (.xdc) ---------------------------------------------------------------------------

    def _format_xdc_constraint(self, c):
        if isinstance(c, Pins):
            return "set_property LOC " + c.identifiers[0]
        elif isinstance(c, IOStandard):
            return "set_property IOSTANDARD " + c.name
        elif isinstance(c, Drive):
            return "set_property DRIVE " + str(c.strength)
        elif isinstance(c, Misc):
            return "set_property " + c.misc.replace("=", " ")
        elif isinstance(c, Inverted):
            return None
        else:
            raise ValueError(f"unknown constraint {c}")

    def build_io_constraints(self):
        r = _build_xdc(self.named_sc, self.named_pc)
        tools.write_to_file(self._build_name + ".xdc", r)
        return (self._build_name + ".xdc", "XDC")

    # Timing Constraints (in xdc file) -------------------------------------------------------------

    def _build_clock_constraints(self):
        self.platform.add_platform_command(_xdc_separator("Clock constraints"))
        def get_clk_type(clk):
            return {
                False :  "nets",
                True  : "ports",
            }[hasattr(clk, "port")]
        for clk, period in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            self.platform.add_platform_command(
                "create_clock -name {clk} -period " + str(period) +
                " [get_" + get_clk_type(clk) + " {clk}]", clk=clk)
        for _from, _to in sorted(self.false_paths, key=lambda x: (x[0].duid, x[1].duid)):
            self.platform.add_platform_command(
                "set_clock_groups "
                "-group [get_clocks -include_generated_clocks -of [get_" + get_clk_type(_from) + " {_from}]] "
                "-group [get_clocks -include_generated_clocks -of [get_" + get_clk_type(_to)   + " {_to}]] "
                "-asynchronous",
                _from=_from, _to=_to)
        # Make sure add_*_constraint cannot be used again
        self.clocks.clear()
        self.false_paths.clear()

    def _build_false_path_constraints(self):
        self.platform.add_platform_command(_xdc_separator("False path constraints"))
        # The asynchronous input to a MultiReg is a false path
        self.platform.add_platform_command(
            "set_false_path -quiet "
            "-through [get_nets -hierarchical -filter {{mr_ff == TRUE}}]"
        )
        # The asychronous reset input to the AsyncResetSynchronizer is a false path
        self.platform.add_platform_command(
            "set_false_path -quiet "
            "-to [get_pins -filter {{REF_PIN_NAME == PRE}} "
                "-of_objects [get_cells -hierarchical -filter {{ars_ff1 == TRUE || ars_ff2 == TRUE}}]]"
        )
        # clock_period-2ns to resolve metastability on the wire between the AsyncResetSynchronizer FFs
        self.platform.add_platform_command(
            "set_max_delay 2 -quiet "
            "-from [get_pins -filter {{REF_PIN_NAME == C}} "
                "-of_objects [get_cells -hierarchical -filter {{ars_ff1 == TRUE}}]] "
            "-to [get_pins -filter {{REF_PIN_NAME == D}} "
                "-of_objects [get_cells -hierarchical -filter {{ars_ff2 == TRUE}}]]"
        )

    def build_timing_constraints(self, vns):
        # FIXME: -> self ?
        self._vns = vns

    # Project (.tcl) -------------------------------------------------------------------------------

    def build_project(self):
        assert self._synth_mode in ["vivado", "yosys"]
        tcl = []

        # Create project
        tcl.append("\n# Create Project\n")
        tcl.append(f"create_project -force -name {self._build_name} -part {self.platform.device}")
        tcl.append("set_msg_config -id {Common 17-55} -new_severity {Warning}")

        if self.vivado_max_threads:
            tcl.append(f"set_param general.maxThreads {self.vivado_max_threads}")

        # Enable Xilinx Parameterized Macros
        if self._enable_xpm:
            tcl.append("\n# Enable Xilinx Parameterized Macros\n")
            tcl.append("set_property XPM_LIBRARIES {XPM_CDC XPM_MEMORY} [current_project]")

        # Add sources (when Vivado used for synthesis)
        if self._synth_mode == "vivado":
            tcl.append("\n# Add Sources\n")
            # "-include_dirs {}" crashes Vivado 2016.4
            for filename, language, library, *copy in self.platform.sources:
                filename_tcl = "{" + filename + "}"
                if (language == "systemverilog"):
                    tcl.append(f"read_verilog -v {filename_tcl}")
                    tcl.append(f"set_property file_type SystemVerilog [get_files {filename_tcl}]")
                elif (language == "verilog"):
                    tcl.append(f"read_verilog {filename_tcl}")
                elif (language == "vhdl"):
                    tcl.append(f"read_vhdl -vhdl2008 {filename_tcl}")
                    tcl.append(f"set_property library {library} [get_files {filename_tcl}]")
                else:
                    tcl.append("add_files " + filename_tcl)

        # Add EDIFs
        tcl.append("\n# Add EDIFs\n")
        for filename in self.platform.edifs:
            filename_tcl = "{" + filename + "}"
            tcl.append(f"read_edif {filename_tcl}")

        # Add IPs
        tcl.append("\n# Add IPs\n")
        for filename, disable_constraints in self.platform.ips.items():
            if filename.endswith("tcl"):
                tcl += open(filename, "r").read().splitlines()
            else:
                filename_tcl = "{" + filename + "}"
                ip = os.path.splitext(os.path.basename(filename))[0]
                tcl.append(f"read_ip {filename_tcl}")
                tcl.append(f"upgrade_ip [get_ips {ip}]")
                tcl.append(f"generate_target all [get_ips {ip}]")
                tcl.append(f"synth_ip [get_ips {ip}] -force")
                tcl.append(f"get_files -all -of_objects [get_files {filename_tcl}]")
                if disable_constraints:
                    tcl.append(f"set_property is_enabled false [get_files -of_objects [get_files {filename_tcl}] -filter {{FILE_TYPE== XDC}}]")

        # Add constraints
        tcl.append("\n# Add constraints\n")
        tcl.append(f"read_xdc {self._build_name}.xdc")
        tcl.append(f"set_property PROCESSING_ORDER EARLY [get_files {self._build_name}.xdc]")

        # Add pre-synthesis commands
        tcl.append("\n# Add pre-synthesis commands\n")
        tcl.extend(c.format(build_name=self._build_name) for c in self.pre_synthesis_commands.resolve(self._vns))

        # Synthesis
        if self._synth_mode == "vivado":
            tcl.append("\n# Synthesis\n")
            synth_cmd = f"synth_design -directive {self.vivado_synth_directive} -top {self._build_name} -part {self.platform.device}"
            if self.platform.verilog_include_paths:
                synth_cmd += f" -include_dirs {{{' '.join(self.platform.verilog_include_paths)}}}"
            tcl.append(synth_cmd)
        elif self._synth_mode == "yosys":
            tcl.append("\n# Read Yosys EDIF\n")
            tcl.append(f"read_edif {self._build_name}.edif")
            tcl.append(f"link_design -top {self._build_name} -part {self.platform.device}")
        else:
            raise OSError(f"Unknown synthesis mode! {self._synth_mode}")
        tcl.append("\n# Synthesis report\n")
        tcl.append(f"report_timing_summary -file {self._build_name}_timing_synth.rpt")
        tcl.append(f"report_utilization -hierarchical -file {self._build_name}_utilization_hierarchical_synth.rpt")
        tcl.append(f"report_utilization -file {self._build_name}_utilization_synth.rpt")

        # Optimize
        tcl.append("\n# Optimize design\n")
        tcl.append(f"opt_design -directive {self.opt_directive}")

        # Incremental implementation
        if self.incremental_implementation:
            tcl.append("\n# Read design checkpoint\n")
            tcl.append(f"read_checkpoint -incremental {self._build_name}_route.dcp")

        # Add pre-placement commands
        tcl.append("\n# Add pre-placement commands\n")
        tcl.extend(c.format(build_name=self._build_name) for c in self.pre_placement_commands.resolve(self._vns))

        # Placement
        tcl.append("\n# Placement\n")
        tcl.append(f"place_design -directive {self.vivado_place_directive}")
        if self.vivado_post_place_phys_opt_directive:
            tcl.append(f"phys_opt_design -directive {self.vivado_post_place_phys_opt_directive}")
        tcl.append("\n# Placement report\n")
        tcl.append(f"report_utilization -hierarchical -file {self._build_name}_utilization_hierarchical_place.rpt")
        tcl.append(f"report_utilization -file {self._build_name}_utilization_place.rpt")
        tcl.append(f"report_io -file {self._build_name}_io.rpt")
        tcl.append(f"report_control_sets -verbose -file {self._build_name}_control_sets.rpt")
        tcl.append(f"report_clock_utilization -file {self._build_name}_clock_utilization.rpt")

        # Add pre-routing commands
        tcl.append("\n# Add pre-routing commands\n")
        tcl.extend(c.format(build_name=self._build_name) for c in self.pre_routing_commands.resolve(self._vns))

        # Routing
        tcl.append("\n# Routing\n")
        tcl.append(f"route_design -directive {self.vivado_route_directive}")
        tcl.append(f"phys_opt_design -directive {self.vivado_post_route_phys_opt_directive}")
        tcl.append(f"write_checkpoint -force {self._build_name}_route.dcp")
        tcl.append("\n# Routing report\n")
        tcl.append("report_timing_summary -no_header -no_detailed_paths")
        tcl.append(f"report_route_status -file {self._build_name}_route_status.rpt")
        tcl.append(f"report_drc -file {self._build_name}_drc.rpt")
        tcl.append(f"report_timing_summary -datasheet -max_paths 10 -file {self._build_name}_timing.rpt")
        tcl.append(f"report_power -file {self._build_name}_power.rpt")

        # Bitstream generation
        for bitstream_command in self.bitstream_commands:
            tcl.append(bitstream_command.format(build_name=self._build_name))
        tcl.append("\n# Bitstream generation\n")
        tcl.append(f"write_bitstream -force {self._build_name}.bit ")

        # Additional commands
        for additional_command in self.additional_commands:
            tcl.append(additional_command.format(build_name=self._build_name))

        # Quit
        tcl.append("\n# End\n")
        tcl.append("quit")
        tools.write_to_file(self._build_name + ".tcl", "\n".join(tcl))

    # Script ---------------------------------------------------------------------------------------

    def build_script(self):
        if sys.platform in ["win32", "cygwin"]:
            script_contents = "REM Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\n"
            script_ext = "bat"
        else:
            script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision() + "\nset -e\n"
            if os.getenv("LITEX_ENV_VIVADO", False):
                script_contents += "source " + os.path.join(os.getenv("LITEX_ENV_VIVADO"), "settings64.sh\n")
            script_ext = "sh"

        if self._synth_mode == "yosys":
            script_contents += common._build_yosys_project(platform=self.platform, build_name=self._build_name)

        script_contents += "vivado -mode batch -source " + self._build_name + ".tcl\n"
        script_file     = "build_" + self._build_name + "." + script_ext
        tools.write_to_file(script_file, script_contents)
        return script_file

    def run_script(self, script):
        if sys.platform in ["win32", "cygwin"]:
            shell = ["cmd", "/c"]
        else:
            shell = ["bash"]

        if which("vivado") is None and os.getenv("LITEX_ENV_VIVADO", False) == False:
            msg = "Unable to find or source Vivado toolchain, please either:\n"
            msg += "- Source Vivado's settings manually.\n"
            msg += "- Or set LITEX_ENV_VIVADO environment variant to Vivado's settings path.\n"
            msg += "- Or add Vivado toolchain to your $PATH."
            raise OSError(msg)

        if tools.subprocess_call_filtered(shell + [script], common.colors) != 0:
            raise OSError("Error occured during Vivado's script execution.")


def vivado_build_args(parser):
    toolchain_group = parser.add_argument_group(title="Vivado toolchain options")
    toolchain_group.add_argument("--synth-mode",                           default="vivado",  help="Synthesis mode (vivado or yosys).")
    toolchain_group.add_argument("--vivado-synth-directive",               default="default", help="Specify synthesis directive.")
    toolchain_group.add_argument("--vivado-opt-directive",                 default="default", help="Specify opt directive.")
    toolchain_group.add_argument("--vivado-place-directive",               default="default", help="Specify place directive.")
    toolchain_group.add_argument("--vivado-post-place-phys-opt-directive", default=None,      help="Specify phys opt directive.")
    toolchain_group.add_argument("--vivado-route-directive",               default="default", help="Specify route directive.")
    toolchain_group.add_argument("--vivado-post-route-phys-opt-directive", default="default", help="Specify phys opt directive.")
    toolchain_group.add_argument("--vivado-max-threads",                   default=None,      help="Limit the max threads vivado is allowed to use.")

def vivado_build_argdict(args):
    return {
        "synth_mode"                           : args.synth_mode,
        "vivado_synth_directive"               : args.vivado_synth_directive,
        "opt_directive"                        : args.vivado_opt_directive,
        "vivado_place_directive"               : args.vivado_place_directive,
        "vivado_post_place_phys_opt_directive" : args.vivado_post_place_phys_opt_directive,
        "vivado_route_directive"               : args.vivado_route_directive,
        "vivado_post_route_phys_opt_directive" : args.vivado_post_route_phys_opt_directive,
        "vivado_max_threads"                   : args.vivado_max_threads
    }
