#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess
import pathlib
import math
import sys
import site
import subprocess
import inspect
import datetime

from xml.dom import expatbuilder
import xml.etree.ElementTree as et

from migen.fhdl.structure import _Fragment
from migen.fhdl.tools import *
from migen.fhdl.namer import build_namespace
from migen.fhdl.simplify import FullMemoryWE

from litex.build.generic_platform import *
from litex.build.generic_platform import Pins, IOStandard, Misc
from litex.build import tools

from litex.build.efinix import InterfaceWriter

def get_pin_direction(fragment, platform, pinname):
    pins = platform.constraint_manager.get_io_signals()
    for pin in sorted(pins, key=lambda x: x.duid):
        # Better idea ???
        if (pinname.split('[')[0] == pin.name):
            return pin.direction
    return "Unknown"

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

# Peripheral configuration ------------------------------------------------------------------------

def _create_gpio_instance(fragment, platform, sig, pins):
    l = ""
    if len(pins) > 1:
        l = ',{},0'.format(len(pins) - 1)
    d = get_pin_direction(fragment, platform, sig)
    return 'design.create_{d}_gpio("{name}"{len})'.format(d=d, name=sig, len=l)

def _format_constraint(c, signame, fmt_r, fragment, platform):
    # IO location constraints
    if isinstance(c, Pins):
        tpl = 'design.assign_pkg_pin("{signame}","{pin}")\n'
        return tpl.format(signame=signame, name=fmt_r, pin=c.identifiers[0])

    # IO standard property
    elif isinstance(c, IOStandard):
        prop = ""
        valid = ['3.3_V_LVTTL_/_LVCMOS', '2.5_V_LVCMOS', '1.8_V_LVCMOS']
        if c.name in valid:
            prop = 'IO_STANDARD'

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
        if c.misc in ['WEAK_PULLUP', 'WEAK_PULLDOWN']:
            prop = 'PULL_OPTION'
            val = c.misc

        if 'DRIVE_STRENGTH' in c.misc:
            prop = 'DRIVE_STRENGTH'
            val = c.misc.split('=')[1]

        if prop == "":
            # Print error, warning ??
            return ""

        tpl = 'design.set_property(  "{signame}","{prop}","{val}")\n'
        return tpl.format(signame=signame, prop=prop, val=val)

def _format_conf_constraint(signame, pin, others, resname, fragment, platform):
    fmt_r = "{}:{}".format(*resname[:2])
    if resname[2] is not None:
        fmt_r += "." + resname[2]
    fmt_c = [_format_constraint(c, signame, fmt_r, fragment, platform) for c in ([Pins(pin)] + others)]
    return ''.join(fmt_c)

def _build_iface_gpio(named_sc, named_pc, fragment, platform, excluded_ios):
    conf = []
    inst = []

    # GPIO
    for sig, pins, others, resname in named_sc:
        excluded = False
        for excluded_io in excluded_ios:
            if isinstance(excluded_io, str):
                if sig == excluded_io:
                    excluded = True
            elif isinstance(excluded_io, Signal):
                if sig == excluded_io.name:
                    excluded = True
        if excluded:
            continue
        inst.append(_create_gpio_instance(fragment, platform, sig, pins))
        if len(pins) > 1:
            for i, p in enumerate(pins):
                conf.append(_format_conf_constraint("{}[{}]".format(sig, i), p, others, resname, fragment, platform))
        else:
            conf.append(_format_conf_constraint(sig, pins[0], others, resname, fragment, platform))
    if named_pc:
        conf.append("\n\n".join(named_pc))

    conf = inst + conf

    return "\n".join(conf)

def _build_peri(efinity_path, build_name, partnumber, named_sc, named_pc, fragment, platform, additional_iface_commands, excluded_ios):
    pythonpath = ""

    header    = platform.toolchain.ifacewriter.header(build_name, partnumber)
    gen       = platform.toolchain.ifacewriter.generate(partnumber)
    #TODO: move this to ifacewriter
    gpio      = _build_iface_gpio(named_sc, named_pc, fragment, platform, excluded_ios)
    add       = '\n'.join(additional_iface_commands)
    footer    = platform.toolchain.ifacewriter.footer()

    tools.write_to_file("iface.py", header + gen + gpio + add + footer)

    if subprocess.call([efinity_path + '/bin/python3', 'iface.py']) != 0:
        raise OSError("Error occurred during Efinity peri script execution.")


# Project configuration ------------------------------------------------------------------------

def _build_xml(partnumber, timing_model, build_name, sources, additional_xml_commands):

    root = et.Element('efx:project')

    now = datetime.datetime.now()
    date_str = " Date: " + now.strftime("%Y-%m-%d %H:%M") + " "

    # Add the required attributes
    root.attrib['xmlns:efx'] = 'http://www.efinixinc.com/enf_proj'
    root.attrib['xmlns:xsi'] = "http://www.w3.org/2001/XMLSchema-instance"
    root.attrib['name'] = build_name
    root.attrib['description'] = ''
    root.attrib['last_change_date'] = date_str
    root.attrib['location'] = str(pathlib.Path().resolve())
    root.attrib['sw_version'] = '2021.1.165.2.19' # TODO: read it from sw_version.txt
    root.attrib['last_run_state'] = ''
    root.attrib['last_run_tool'] = ''
    root.attrib['last_run_flow'] = ''
    root.attrib['config_result_in_sync'] = 'sync'
    root.attrib['design_ood'] = 'sync'
    root.attrib['place_ood'] = 'sync'
    root.attrib['route_ood'] = 'sync'
    root.attrib['xsi:schemaLocation'] = 'http://www.efinixinc.com/enf_proj enf_proj.xsd'

    device_info = et.SubElement(root, 'efx:device_info')
    et.SubElement(device_info, 'efx:family', name = 'Trion')
    et.SubElement(device_info, 'efx:device', name = partnumber)
    et.SubElement(device_info, 'efx:timing_model', name = timing_model)

    design_info = et.SubElement(root, 'efx:design_info')
    et.SubElement(design_info, "efx:top_module", name = build_name)
    for filename, language, library in sources:
        if '.vh' not in filename:
            val = {'name':filename, 'version':'default', 'library':'default'}
            et.SubElement(design_info, "efx:design_file", val)
    et.SubElement(design_info, "efx:top_vhdl_arch", name = "")

    constraint_info  = et.SubElement(root, "efx:constraint_info")
    et.SubElement(constraint_info, "efx:sdc_file", name = "{}.sdc".format(build_name))

    misc_info  = et.SubElement(root, "efx:misc_info")
    ip_info  = et.SubElement(root, "efx:ip_info")

    synthesis  = et.SubElement(root, "efx:synthesis", tool_name="efx_map")
    for l in additional_xml_commands:
        if l[0] == 'efx_map':
            val = {'name':l[1], 'value':l[2], 'value_type':l[3]}
            et.SubElement(synthesis, "efx:param", val)

    place_and_route  = et.SubElement(root, "efx:place_and_route", tool_name="efx_pnr")
    for l in additional_xml_commands:
        if l[0] == 'efx_pnr':
            val = {'name':l[1], 'value':l[2], 'value_type':l[3]}
            et.SubElement(place_and_route, "efx:param", val)

    bitstream_generation  = et.SubElement(root, "efx:bitstream_generation", tool_name="efx_pgm")
    for l in additional_xml_commands:
        if l[0] == 'efx_pgm':
            val = {'name':l[1], 'value':l[2], 'value_type':l[3]}
            et.SubElement(bitstream_generation, "efx:param", val)

    xml_string = et.tostring(root, 'utf-8')
    reparsed = expatbuilder.parseString(xml_string, False)
    print_string = reparsed.toprettyxml(indent="  ")

    # Generate .xml
    tools.write_to_file("{}.xml".format(build_name), print_string)

class EfinityToolchain:
    attr_translate = {}

    def __init__(self, efinity_path):
        self.options     = {}
        self.clocks      = dict()
        self.false_paths = set()
        self.efinity_path = efinity_path
        self.additional_sdc_commands = []
        self.additional_xml_commands = [
            [ 'efx_pgm', 'io_weak_pullup', 'on', 'e_bool'],
            [ 'efx_pgm', 'oscillator_clock_divider', 'DIV8', 'e_option'],
            [ 'efx_pgm', 'enable_crc_check', 'on', 'e_bool'],
        ]
        self.ifacewriter = InterfaceWriter(efinity_path)
        self.excluded_ios = []
        self.additional_iface_commands = []

    def build(self, platform, fragment,
        build_dir      = "build",
        build_name     = "top",
        run            = True,
        **kwargs):

        self.ifacewriter.set_build_params(platform, build_name)

        # Create build directory
        cwd = os.getcwd()
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)

        # Apply FullMemoryWE on design (Efiniy does not infer memories correctly otherwise).
        FullMemoryWE()(fragment)

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

        if platform.verilog_include_paths:
            self.options['includ_path'] = '{' + ';'.join(platform.verilog_include_paths) + '}'

        os.environ['EFXPT_HOME'] = self.efinity_path + '/pt'

        # Generate design timing constraints file (.sdc)
        _build_sdc(
            clocks                  = self.clocks,
            false_paths             = self.false_paths,
            vns                     = v_output.ns,
            named_sc                = named_sc,
            build_name              = build_name,
            additional_sdc_commands = self.additional_sdc_commands)

        # Generate project file (.xml)
        _build_xml(
            partnumber              = platform.device,
            timing_model            = platform.timing_model,
            build_name              = build_name,
            sources                 = platform.sources,
            additional_xml_commands = self.additional_xml_commands)

        # Generate constraints file (.peri.xml)
        _build_peri(
            efinity_path              = self.efinity_path,
            build_name                = build_name,
            partnumber                = platform.device,
            named_sc                  = named_sc,
            named_pc                  = named_pc,
            fragment                  = fragment,
            platform                  = platform,
            additional_iface_commands = self.additional_iface_commands,
            excluded_ios              = self.excluded_ios)

        # DDR doesn't have Python API so we need to configure it
        # directly in the peri.xml file
        if self.ifacewriter.xml_blocks:
            self.ifacewriter.generate_xml_blocks()

        # Run
        if run:
            if True: # FIXME: Keep efx_run for now as default.
                if subprocess.call([self.efinity_path + '/scripts/efx_run.py', build_name + '.xml', '-f', 'compile'])  != 0:
                    raise OSError("Error occurred during efx_run script execution.")
            else:
                # Synthesis/Mapping.
                r = subprocess.call([self.efinity_path + "/bin/efx_map",
                    "--project",                    f"{build_name}",
                    "--root",                       f"{build_name}",
                    "--write-efx-verilog",          f"outflow/{build_name}.map.v",
                    "--write-premap-module",        f"outflow/{build_name}.elab.vdb",
                    "--binary-db",                  f"{build_name}.vdb",
                    "--family",                     "Trion",
                    "--device",                     platform.device,
                    "--mode",                       "speed",
                    "--max_ram",                    "-1",
                    "--max_mult",                   "-1",
                    "--infer-clk-enable",           "3",
                    "--infer-sync-set-reset",       "1",
                    "--fanout-limit",               "0",
                    "--bram_output_regs_packing",   "1",
                    "--retiming",                   "1",
                    "--seq_opt",                    "1",
                    "--blast_const_operand_adders", "1",
                    "--mult_input_regs_packing",    "1",
                    "--mult_output_regs_packing",   "1",
                    "--veri_option",                "verilog_mode=verilog_2k,vhdl_mode=vhdl_2008",
                    "--work-dir",                   "work_syn",
                    "--output-dir",                 "outflow",
                    "--project-xml",                f"{build_name}.xml",
                    "--I",                          "./"
                ])
                if r != 0:
                    raise OSError("Error occurred during efx_map execution.")

                # Place and Route.
                r = subprocess.call([self.efinity_path + "/bin/python3",
                    self.efinity_path + "/scripts/efx_run_pt.py",
                    f"{build_name}",
                    "Trion",
                   platform.device
                ])
                if r != 0:
                   raise OSError("Error occurred during efx_run_pt execution.")

                r = subprocess.call([self.efinity_path + "/bin/efx_pnr",
                    "--circuit",              f"{build_name}",
                    "--family",               "Trion",
                    "--device",               platform.device,
                    "--operating_conditions", platform.timing_model,
                    "--pack",
                    "--place",
                    "--route",
                    "--vdb_file",             f"work_syn/{build_name}.vdb",
                    "--use_vdb_file",         "on",
                    "--place_file",           f"outflow/{build_name}.place",
                    "--route_file",           f"outflow/{build_name}.route",
                    "--sdc_file",             f"{build_name}.sdc",
                    #"--sync_file",            f"{build_name}.csv", # FIXME.
                    "--seed",                 "1",
                    "--work_dir",             "work_pnr",
                    "--output_dir",           "outflow",
                    "--timing_analysis",      "on",
                    "--load_delay_matrix"
                ])
                if r != 0:
                    raise OSError("Error occurred during efx_pnr execution.")

                # Bitstream.
                r = subprocess.call([self.efinity_path + "/bin/efx_pgm",
                    "--source",                      f"work_pnr/{build_name}.lbf",
                    "--dest",                        f"outflow/{build_name}.hex",
                    "--device",                      platform.device,
                    "--family",                      "Trion",
                    "--periph",                      f"outflow/{build_name}.lpf",
                    "--interface_designer_settings", f"outflow/{build_name}_or.ini",
                    "--oscillator_clock_divider",    "DIV8",
                    "--spi_low_power_mode",          "off",
                    "--io_weak_pullup",              "on",
                    "--enable_roms",                 "on",
                    "--mode",                        "active",
                    "--width",                        "1",
                    "--enable_crc_check",             "on"
                ])
                if r != 0:
                    raise OSError("Error occurred during efx_pgm execution.")

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
