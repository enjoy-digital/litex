#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2015-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import pathlib
import math
import sys
import site
import inspect
import datetime
import subprocess
import shutil
import glob

from xml.dom import expatbuilder
import xml.etree.ElementTree as et

from migen.fhdl.structure import _Fragment
from migen.fhdl.tools import *
from migen.fhdl.simplify import FullMemoryWE

from litex.build import tools
from litex.build.generic_platform import *
from litex.build.generic_platform import Pins, IOStandard, Misc
from litex.build.generic_toolchain import GenericToolchain

from litex.build.efinix import common
from litex.build.efinix import InterfaceWriter
from litex.build.efinix import IPMWriter

def _add_custom_params(parent, params):
    for key, value in params.items():
        if isinstance(value, bool):
            value_type = "e_bool"
            value = "on" if value else "off"
        elif isinstance(value, list):
            value_type = value[1]
            value = value[0]
        else:
            value_type = "e_string"
        et.SubElement(parent, "efx:param", {
            "name" : key,
            "value": str(value),
            "value_type": value_type,
        })


# Efinity Toolchain --------------------------------------------------------------------------------

class EfinityToolchain(GenericToolchain):
    attr_translate = {}

    def __init__(self, efinity_path):
        super().__init__()
        self.options                   = {}
        self.efinity_path              = efinity_path
        os.environ["EFXPT_HOME"]       = self.efinity_path + "/pt"
        self.ifacewriter               = InterfaceWriter(efinity_path)
        self.ipmwriter                 = IPMWriter(efinity_path)
        self.excluded_ios              = []
        self.additional_sdc_commands   = []
        self.additional_iface_commands = []

    def finalize(self):
        self.ifacewriter.set_build_params(self.platform, self._build_name)
        # Add Include Paths.
        if self.platform.verilog_include_paths:
            self.options["includ_path"] = "{" + ";".join(self.platform.verilog_include_paths) + "}"

    def build(self, platform, fragment,
        efx_map_params           = None,
        efx_pnr_params           = None,
        efx_pgm_params           = None,
        efx_security_params      = None,
        efx_debugger_params      = None,
        **kwargs):

        self._efx_map_params           = efx_map_params if efx_map_params is not None else {}
        self._efx_pnr_params           = efx_pnr_params if efx_pnr_params is not None else {}
        self._efx_pgm_params           = efx_pgm_params if efx_pgm_params is not None else {}
        self._efx_security_params      = efx_security_params if efx_security_params is not None else {}
        self._efx_debugger_params      = efx_debugger_params if efx_debugger_params is not None else {}

        if platform.family != "Trion":
            self._efx_map_params.pop("mult_input_regs_packing", None)
            self._efx_map_params.pop("mult_output_regs_packing", None)

        # Apply FullMemoryWE on Design (Efiniy does not infer memories correctly otherwise).
        FullMemoryWE()(fragment)

        return GenericToolchain.build(self, platform, fragment, **kwargs)

    # Timing Constraints (.sdc) --------------------------------------------------------------------

    def build_timing_constraints(self, vns):
        sdc = []

        # Clock constraints
        for clk, [period, name] in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            is_port = False
            for sig, pins, others, resname in self.named_sc:
                if sig == self._vns.get_name(clk):
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
            sdc.append(tpl.format(from_=self._vns.get_name(from_), to=self._vns.get_name(to)))
            tpl = "set_false_path -from [get_clocks {{{to}}}] -to [get_clocks {{{from_}}}]"
            sdc.append(tpl.format(to=self._vns.get_name(to), from_=self._vns.get_name(from_)))

        # Add additional commands
        sdc += self.additional_sdc_commands

        # Generate .sdc
        tools.write_to_file("{}.sdc".format(self._build_name), "\n".join(sdc))
        return (self._build_name + ".sdc", "SDC")

    # Peripheral configuration (.xml) --------------------------------------------------------------

    def get_pin_direction(self, pinname):
        pins = self.platform.constraint_manager.get_io_signals()
        for pin in sorted(pins, key=lambda x: x.duid):
            # Better idea ???
            if (pinname.split("[")[0] == pin.name):
                return pin.direction
        return "Unknown"

    def _create_gpio_instance(self, sig, pins):
        l = ""
        if len(pins) > 1:
            l = ",{},0".format(len(pins) - 1)
        d = self.get_pin_direction(sig)
        return 'design.create_{d}_gpio("{name}"{len})'.format(d=d, name=sig, len=l)

    def _format_constraint(self, c, signame, fmt_r):
        # IO location constraints
        if isinstance(c, Pins):
            tpl = 'design.assign_pkg_pin("{signame}","{pin}")\n'
            return tpl.format(signame=signame, name=fmt_r, pin=c.identifiers[0])

        # IO standard property
        elif isinstance(c, IOStandard):
            prop = ""
            valid = [ "3.3_V_LVTTL_/_LVCMOS", "2.5_V_LVCMOS", "1.8_V_LVCMOS",
                      "1.2_V_Differential_HSTL", "1.2_V_Differential_SSTL",
                      "1.2_V_HSTL", "1.2_V_LVCMOS", "1.2_V_SSTL", "1.5_V_Differential_HSTL",
                      "1.5_V_Differential_SSTL", "1.5_V_HSTL", "1.5_V_LVCMOS", "1.5_V_SSTL",
                      "1.8_V_Differential_HSTL", "1.8_V_Differential_SSTL", "1.8_V_HSTL",
                      "1.8_V_LVCMOS", "1.8_V_SSTL", "2.5_V_LVCMOS", "3.0_V_LVCMOS",
                      "3.0_V_LVTTL", "3.3_V_LVCMOS", "3.3_V_LVTTL"
            ]

            if c.name in valid:
                prop = "IO_STANDARD"

            if prop == "":
                print("{} has a wrong IOStandard format [{}]".format(signame, c.name))
                print("Sould be selected from {}\n".format(valid))
                # Print error, warning ??
                return ""

            tpl = 'design.set_property(  "{signame}","{prop}","{val}")\n'
            return tpl.format(signame=signame, prop=prop, val=c.name)

        # Others constraints
        elif isinstance(c, Misc):
            prop = ""
            if c.misc in ["WEAK_PULLUP", "WEAK_PULLDOWN"]:
                prop = "PULL_OPTION"
                val = c.misc

            if c.misc == "SCHMITT_TRIGGER":
                prop = "SCHMITT_TRIGGER"
                val = "1"

            if "DRIVE_STRENGTH" in c.misc:
                prop = "DRIVE_STRENGTH"
                val = c.misc.split("=")[1]
                valid = ["1", "2", "3", "4"] if self.platform.family == "Trion" else [
                         "2", "4", "6", "8", "10", "12", "16" ]
                assert val in valid, f"DRIVE_STRENGTH {val} is not in {valid}"

            if "SLEWRATE" in c.misc:
                prop = "SLEW_RATE"
                val = "1" # FAST

            if prop == "":
                # Print error, warning ??
                return ""

            tpl = 'design.set_property(  "{signame}","{prop}","{val}")\n'
            return tpl.format(signame=signame, prop=prop, val=val)

    def _format_conf_constraint(self, signame, pin, others, resname):
        fmt_r = "{}:{}".format(*resname[:2])
        if resname[2] is not None:
            fmt_r += "." + resname[2]
        fmt_c = [self._format_constraint(c, signame, fmt_r) for c in ([Pins(pin)] + others)]
        return "".join(fmt_c)

    def _build_iface_gpio(self):
        conf = []
        inst = []

        # GPIO
        for sig, pins, others, resname in self.named_sc:
            excluded = False
            for excluded_io in self.excluded_ios:
                if isinstance(excluded_io, str):
                    if sig == excluded_io:
                        excluded = True
                elif isinstance(excluded_io, Signal):
                    if sig == excluded_io.name:
                        excluded = True
            if excluded:
                continue
            inst.append(self._create_gpio_instance(sig, pins))
            if len(pins) > 1:
                for i, p in enumerate(pins):
                    conf.append(self._format_conf_constraint("{}[{}]".format(sig, i), p, others, resname))
            else:
                conf.append(self._format_conf_constraint(sig, pins[0], others, resname))
        if self.named_pc:
            conf.append("\n\n".join(self.named_pc))

        conf = inst + conf

        return "\n".join(conf)

    def resolve_iface_signal_names(self):
        # Iterate over each block
        for block in self.platform.toolchain.ifacewriter.blocks:

            # Iterate over each key-value pair in the block
            for key, value in block.items():

                # Only process specific keys, skip others.
                if key not in ["name", "in_clk_pin", "out_clk_pin", "rx_fifoclk", "fast_clk", "slow_clk"]:
                    continue

                # If the value is a ClockSignal, resolve its name
                if isinstance(value, ClockSignal):
                    clock_domain = value.cd
                    signal_name = self._vns.get_name(self._vns.clock_domains[clock_domain].clk)
                    block[key] = signal_name  # Replace with the resolved name

                # If the value is a Signal, directly resolve its name
                elif isinstance(value, Signal):
                    signal_name = self._vns.get_name(value)
                    block[key] = signal_name  # Replace with the resolved name

    def build_io_constraints(self):
        pythonpath = ""

        self.resolve_iface_signal_names()

        header = self.ifacewriter.header(self._build_name, self.platform.device)
        iobank = self.ifacewriter.iobank_info(self.platform.iobank_info)
        gen    = self.ifacewriter.generate(self.platform.device)
        #TODO  : move this to ifacewriter
        gpio   = self._build_iface_gpio()
        add    = "\n".join(self.additional_iface_commands)
        footer = self.ifacewriter.footer()

        tools.write_to_file("iface.py", header + iobank + gen + gpio + add + footer)

    # Project configuration (.xml) -----------------------------------------------------------------

    def build_project(self):
        now  = datetime.datetime.now()

        # Create Project.
        root = et.Element("efx:project")
        root.attrib["xmlns:efx"]        = "http://www.efinixinc.com/enf_proj"
        root.attrib["name"]             = self._build_name
        root.attrib["location"]         = str(pathlib.Path().resolve())
        # read efinity version  in scripts/sw_version.txt
        with open(os.path.join(self.efinity_path, "scripts/sw_version.txt"), "r") as fd:
           root.attrib["sw_version"]= fd.readline().strip()
        root.attrib["last_change_date"] = f"Date : {now.strftime('%Y-%m-%d %H:%M')}"

        # Add Device.
        device_info = et.SubElement(root, "efx:device_info")
        et.SubElement(device_info, "efx:family",       name=self.platform.family)
        et.SubElement(device_info, "efx:device",       name=self.platform.device)
        et.SubElement(device_info, "efx:timing_model", name=self.platform.timing_model)

        # Add Design Info.
        design_info = et.SubElement(root, "efx:design_info", {
                                    "def_veri_version": "verilog_2k",
                                    "def_vhdl_version": "vhdl_2008"})
        et.SubElement(design_info, "efx:top_module", name=self._build_name)

        # Add Design Sources.
        for filename, language, library, *copy in self.platform.sources:
            if language is None:
                continue
            et.SubElement(design_info, "efx:design_file", {
                "name"    : filename,
                "version" : "default",
                "library" : "default" if ".vh" not in filename else library,
            })

        # Add Timing Constraints.
        constraint_info  = et.SubElement(root, "efx:constraint_info")
        et.SubElement(constraint_info, "efx:sdc_file", name=f"{self._build_name}_merged.sdc")

        # Add Misc Info.
        misc_info  = et.SubElement(root, "efx:misc_info")

        # Add IP Info.
        ip_info  = et.SubElement(root, "efx:ip_info")

        efx_map  = et.SubElement(root, "efx:synthesis", {"tool_name": "efx_map"})      
        _add_custom_params(efx_map, self._efx_map_params)

        efx_pnr = et.SubElement(root, "efx:place_and_route", {"tool_name": "efx_pnr"})
        _add_custom_params(efx_pnr, self._efx_pnr_params)

        efx_pgm = et.SubElement(root, "efx:bitstream_generation", {"tool_name": "efx_pgm"})

        et.SubElement(efx_pgm, "efx:param", {
            "name" : "mode",
            "value": self.platform.spi_mode,
            "value_type": "e_option",
        })
        et.SubElement(efx_pgm, "efx:param", {
            "name" : "width",
            "value": self.platform.spi_width,
            "value_type": "e_option",
        })
        
        _add_custom_params(efx_pgm, self._efx_pgm_params)

        efx_dbg = et.SubElement(root, "efx:debugger")
        _add_custom_params(efx_dbg, self._efx_debugger_params)

        efx_security = et.SubElement(root, "efx:security")
        _add_custom_params(efx_security, self._efx_security_params)

        # Generate .xml
        xml_str = et.tostring(root, "utf-8")
        xml_str = expatbuilder.parseString(xml_str, False)
        xml_str = xml_str.toprettyxml(indent="  ")
        tools.write_to_file("{}.xml".format(self._build_name), xml_str)

        # get environment variables from the efinity setup.sh
        pipe = subprocess.Popen(". %s && env -0" % (self.efinity_path + "/bin/setup.sh"),
                                stdout=subprocess.PIPE, shell=True, cwd=self.efinity_path, executable='/bin/bash')
        output = pipe.communicate()[0].decode('utf-8')
        output = output[:-1] # fix for index out for range in 'env[ line[0] ] = line[1]'

        env = {}
        # split using null char
        for line in output.split('\x00'):
            line = line.split( '=', 1)
            # print(line)
            env[line[0]] = line[1]

        self.env = env

        if len(self.ipmwriter.blocks) > 0:
            ipm_header = self.ipmwriter.header(self._build_name, self.platform.device, self.platform.family)
            ipm    = self.ipmwriter.generate(self.platform.device)

            tools.write_to_file("ipm.py", ipm_header + ipm )

            if tools.subprocess_call_filtered([self.efinity_path + "/bin/python3", "ipm.py"], common.colors, env=self.env) != 0:
                raise OSError("Error occurred during Efinity ip script execution.")

        if tools.subprocess_call_filtered([self.efinity_path + "/bin/python3", "iface.py"], common.colors, env=self.env) != 0:
            raise OSError("Error occurred during Efinity peri script execution.")

        # Some IO blocks don't have Python API so we need to configure them
        # directly in the peri.xml file
        if self.ifacewriter.xml_blocks:
            self.ifacewriter.generate_xml_blocks()

        # Because the Python API is sometimes bugged, we need to tweak the generated xml
        if self.ifacewriter.fix_xml:
            self.ifacewriter.fix_xml_values()

        # FIXME: peri.xml is generated from Efinity, why does it require patching?
        tools.replace_in_file(f"{self._build_name}.peri.xml", 'adv_out_phase_shift="0.0"', 'adv_out_phase_shift="0"')
        tools.replace_in_file(f"{self._build_name}.peri.xml", 'adv_out_phase_shift="90.0"', 'adv_out_phase_shift="90"')

    def build_script(self):
        return "" # not used

    def run_script(self, script):
        # Merge SDC.
        with open(f"{self._build_name}_merged.sdc", 'w') as outfile:
            with open(f"outflow/{self._build_name}.pt.sdc") as infile:
                outfile.write(infile.read())
            outfile.write("\n")
            outfile.write("#########################\n")
            outfile.write("\n")
            with open(f"{self._build_name}.sdc") as infile:
                outfile.write(infile.read())

        # Define / Remove .log file.
        log_file = f"outflow/{self._build_name}.log"
        if os.path.exists(log_file):
            os.remove(log_file)

        # Call efx_run script.
        r = tools.subprocess_call_filtered([self.efinity_path + "/bin/python3",
            self.efinity_path + "/scripts/efx_run.py",
            f"{self._build_name}.xml",
            "--flow", "compile",
        ], common.colors, env=self.env, tail_log=log_file)
        if r != 0:
           raise OSError("Error occurred during efx_run execution.")

        # Copy Bistream to build directory.
        files = glob.glob('outflow/*.bin')
        files.extend(glob.glob('outflow/*.bit'))
        files.extend(glob.glob('outflow/*.hex'))
        for file in files:
            print(file)
            shutil.copy(file, self._build_dir)

def build_args(parser):
    toolchain = parser.add_argument_group(title="Efinity toolchain options")
    toolchain.add_argument("--synth-mode",               default="speed", help="Synthesis optimization mode.",                  choices=["speed", "area", "area2"])
    toolchain.add_argument("--infer-clk-enable",         default="3",     help="infers the flip-flop clock enable signal.",     choices=["0", "1", "2", "3", "4",])
    toolchain.add_argument("--infer-sync-set-reset",     default="1",     help="Infer synchronous set/reset signals.",          choices=["0", "1"])
    toolchain.add_argument("--bram-output-regs-packing", default="1",     help="Pack registers into the output of BRAM.",       choices=["0", "1"])
    toolchain.add_argument("--retiming",                 default="1",     help="Perform retiming optimization.",                choices=["0", "1", "2"])
    toolchain.add_argument("--seq-opt",                  default="1",     help="Turn on sequential optimization.",              choices=["0", "1"])
    toolchain.add_argument("--mult-input-regs-packing",  default="1",     help="Allow packing of multiplier input registers.",  choices=["0", "1"]),
    toolchain.add_argument("--mult-output-regs-packing", default="1",     help="Allow packing of multiplier output registers.", choices=["0", "1"])
    toolchain.add_argument("--generate-bitbin",          action="store_true", help="Generate bitbin file (default: False).")
    toolchain.add_argument("--generate-hexbin",          action="store_true", help="Generate hexbin file (default: False).")

def build_argdict(args):
    return{
        "efx_map_params"           : {
            "mode"                      : [args.synth_mode, "e_option"],
            "infer-clk-enable"          : [args.infer_clk_enable, "e_option"],
            "bram_output_regs_packing"  : [args.bram_output_regs_packing, "e_option"],
            "retiming"                  : [args.retiming, "e_option"],
            "seq_opt"                   : [args.seq_opt, "e_option"],
            "mult_input_regs_packing"   : [args.mult_input_regs_packing, "e_option"],
            "mult_output_regs_packing"  : [args.mult_output_regs_packing, "e_option"],
        },
        "efx_pgm_params"           : {
            "generate_bitbin"           : args.generate_bitbin,
            "generate_hexbin"           : args.generate_hexbin,
            "oscillator_clock_divider"  : ["DIV8", "e_option"],
            "spi_low_power_mode"        : False,
            "io_weak_pullup"            : True,
            "enable_roms"               : True,
            "enable_crc_check"          : True,

        },
    }
