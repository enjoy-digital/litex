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
        synth_mode               = "speed",
        infer_clk_enable         = "3",
        bram_output_regs_packing = "1",
        retiming                 = "1",
        seq_opt                  = "1",
        mult_input_regs_packing  = "1",
        mult_output_regs_packing = "1",
        **kwargs):

        self._synth_mode               = synth_mode
        self._infer_clk_enable         = infer_clk_enable
        self._bram_output_regs_packing = bram_output_regs_packing
        self._retiming                 = retiming
        self._seq_opt                  = seq_opt
        self._mult_input_regs_packing  = mult_input_regs_packing
        self._mult_output_regs_packing = mult_output_regs_packing

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
                if key not in ["name", "in_clk_pin", "out_clk_pin"]:
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
        gen    = self.ifacewriter.generate(self.platform.device)
        #TODO  : move this to ifacewriter
        gpio   = self._build_iface_gpio()
        add    = "\n".join(self.additional_iface_commands)
        footer = self.ifacewriter.footer()

        tools.write_to_file("iface.py", header + gen + gpio + add + footer)

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
        design_info = et.SubElement(root, "efx:design_info")
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

        # Generate .xml
        xml_str = et.tostring(root, "utf-8")
        xml_str = expatbuilder.parseString(xml_str, False)
        xml_str = xml_str.toprettyxml(indent="  ")
        tools.write_to_file("{}.xml".format(self._build_name), xml_str)

        if len(self.ipmwriter.blocks) > 0:
            ipm_header = self.ipmwriter.header(self._build_name, self.platform.device, self.platform.family)
            ipm    = self.ipmwriter.generate(self.platform.device)

            tools.write_to_file("ipm.py", ipm_header + ipm )

            if tools.subprocess_call_filtered([self.efinity_path + "/bin/python3", "ipm.py"], common.colors) != 0:
                raise OSError("Error occurred during Efinity ip script execution.")

        if tools.subprocess_call_filtered([self.efinity_path + "/bin/python3", "iface.py"], common.colors) != 0:
            raise OSError("Error occurred during Efinity peri script execution.")

        # Some IO blocks don't have Python API so we need to configure them
        # directly in the peri.xml file
        # We also need to configure the bank voltage here
        if self.ifacewriter.xml_blocks or self.platform.iobank_info:
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
        # Place and Route.
        r = tools.subprocess_call_filtered([self.efinity_path + "/bin/python3",
            self.efinity_path + "/scripts/efx_run_pt.py",
            f"{self._build_name}",
            self.platform.family,
            self.platform.device
        ], common.colors)
        if r != 0:
           raise OSError("Error occurred during efx_run_pt execution.")

        # Merge SDC
        with open(f"{self._build_name}_merged.sdc", 'w') as outfile:
            with open(f"outflow/{self._build_name}.pt.sdc") as infile:
                outfile.write(infile.read())
            outfile.write("\n")
            outfile.write("#########################\n")
            outfile.write("\n")
            with open(f"{self._build_name}.sdc") as infile:
                outfile.write(infile.read())

        # Synthesis/Mapping.
        r = tools.subprocess_call_filtered([self.efinity_path + "/bin/efx_map",
            "--project",                    f"{self._build_name}",
            "--root",                       f"{self._build_name}",
            "--write-efx-verilog",          f"outflow/{self._build_name}.map.v",
            "--write-premap-module",        f"outflow/{self._build_name}.elab.vdb",
            "--binary-db",                  f"{self._build_name}.vdb",
            "--family",                     self.platform.family,
            "--device",                     self.platform.device,
            "--mode",                       self._synth_mode,
            "--max_ram",                    "-1",
            "--max_mult",                   "-1",
            "--infer-clk-enable",           self._infer_clk_enable,
            "--infer-sync-set-reset",       "1",
            "--fanout-limit",               "0",
            "--bram_output_regs_packing",   self._bram_output_regs_packing,
            "--retiming",                   self._retiming,
            "--seq_opt",                    self._seq_opt,
            "--blast_const_operand_adders", "1",
            "--mult_input_regs_packing",    self._mult_input_regs_packing,
            "--mult_output_regs_packing",   self._mult_output_regs_packing,
            "--veri_option",                "verilog_mode=verilog_2k,vhdl_mode=vhdl_2008",
            "--work-dir",                   "work_syn",
            "--output-dir",                 "outflow",
            "--project-xml",                f"{self._build_name}.xml",
            "--I",                          "./"
        ], common.colors)
        if r != 0:
            raise OSError("Error occurred during efx_map execution.")



        r = tools.subprocess_call_filtered([self.efinity_path + "/bin/efx_pnr",
            "--circuit",              f"{self._build_name}",
            "--family",               self.platform.family,
            "--device",               self.platform.device,
            "--operating_conditions", self.platform.timing_model,
            "--pack",
            "--place",
            "--route",
            "--vdb_file",             f"work_syn/{self._build_name}.vdb",
            "--use_vdb_file",         "on",
            "--place_file",           f"outflow/{self._build_name}.place",
            "--route_file",           f"outflow/{self._build_name}.route",
            "--sdc_file",             f"{self._build_name}_merged.sdc",
            "--sync_file",            f"outflow/{self._build_name}.interface.csv",
            "--seed",                 "1",
            "--work_dir",             "work_pnr",
            "--output_dir",           "outflow",
            "--timing_analysis",      "on",
            "--load_delay_matrix"
        ], common.colors)
        if r != 0:
            raise OSError("Error occurred during efx_pnr execution.")

        # Bitstream.
        r = tools.subprocess_call_filtered([self.efinity_path + "/bin/efx_pgm",
            "--source",                   f"work_pnr/{self._build_name}.lbf",
            "--dest",                     f"{self._build_name}.hex",
            "--device",                   self.platform.device,
            "--family",                   self.platform.family,
            "--periph",                   f"outflow/{self._build_name}.lpf",
            "--oscillator_clock_divider", "DIV8",
            "--spi_low_power_mode",       "off",
            "--io_weak_pullup",           "on",
            "--enable_roms",              "on",
            "--mode",                     self.platform.spi_mode,
            "--width",                    self.platform.spi_width,
            "--enable_crc_check",         "on"
        ], common.colors)
        if r != 0:
            raise OSError("Error occurred during efx_pgm execution.")

        # BINARY
        os.environ['EFXPGM_HOME'] = self.efinity_path + "/pgm"
        r = tools.subprocess_call_filtered([self.efinity_path + "/bin/python3",
            self.efinity_path + "/pgm/bin/efx_pgm/export_bitstream.py",
            "hex_to_bin",
            f"{self._build_name}.hex",
            f"{self._build_name}.bin"
        ], common.colors)
        if r != 0:
           raise OSError("Error occurred during export_bitstream execution.")

def build_args(parser):
    toolchain = parser.add_argument_group(title="Efinity toolchain options")
    toolchain.add_argument("--synth-mode",               default="speed", help="Synthesis optimization mode.",
        choices=["speed", "area", "area2"])
    toolchain.add_argument("--infer-clk-enable",         default="3",     help="infers the flip-flop clock enable signal.",
        choices=["0", "1", "2", "3", "4",])
    toolchain.add_argument("--infer-sync-set-reset",     default="1",     help="Infer synchronous set/reset signals.",
        choices=["0", "1"])
    toolchain.add_argument("--bram-output-regs-packing", default="1",     help="Pack registers into the output of BRAM.",
        choices=["0", "1"])
    toolchain.add_argument("--retiming",                 default="1",     help="Perform retiming optimization.",
        choices=["0", "1", "2"])
    toolchain.add_argument("--seq-opt",                  default="1",     help="Turn on sequential optimization.",
        choices=["0", "1"])
    toolchain.add_argument("--mult-input-regs-packing",  default="1",     help="Allow packing of multiplier input registers.",
        choices=["0", "1"]),
    toolchain.add_argument("--mult-output-regs-packing", default="1",     help="Allow packing of multiplier output registers.",
        choices=["0", "1"])

def build_argdict(args):
    return {
        "synth_mode"               : args.synth_mode,
        "infer_clk_enable"         : args.infer_clk_enable,
        "bram_output_regs_packing" : args.bram_output_regs_packing,
        "retiming"                 : args.retiming,
        "seq_opt"                  : args.seq_opt,
        "mult_input_regs_packing"  : args.mult_input_regs_packing,
        "mult_output_regs_packing" : args.mult_output_regs_packing,
    }
