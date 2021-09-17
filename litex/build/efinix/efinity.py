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

from lxml import etree

from litex.build.generic_platform import *

from migen.fhdl.structure import _Fragment
from migen.fhdl.tools import *
from migen.fhdl.namer import build_namespace

from litex.build.generic_platform import Pins, IOStandard, Misc
from litex.build import tools

_reserved_keywords = {
    "always", "and", "assign", "automatic", "begin", "buf", "bufif0", "bufif1",
    "case", "casex", "casez", "cell", "cmos", "config", "deassign", "default",
    "defparam", "design", "disable", "edge", "else", "end", "endcase",
    "endconfig", "endfunction", "endgenerate", "endmodule", "endprimitive",
    "endspecify", "endtable", "endtask", "event", "for", "force", "forever",
    "fork", "function", "generate", "genvar", "highz0", "highz1", "if",
    "ifnone", "incdir", "include", "initial", "inout", "input",
    "instance", "integer", "join", "large", "liblist", "library", "localparam",
    "macromodule", "medium", "module", "nand", "negedge", "nmos", "nor",
    "noshowcancelled", "not", "notif0", "notif1", "or", "output", "parameter",
    "pmos", "posedge", "primitive", "pull0", "pull1" "pulldown",
    "pullup", "pulsestyle_onevent", "pulsestyle_ondetect", "remos", "real",
    "realtime", "reg", "release", "repeat", "rnmos", "rpmos", "rtran",
    "rtranif0", "rtranif1", "scalared", "showcancelled", "signed", "small",
    "specify", "specparam", "strong0", "strong1", "supply0", "supply1",
    "table", "task", "time", "tran", "tranif0", "tranif1", "tri", "tri0",
    "tri1", "triand", "trior", "trireg", "unsigned", "use", "vectored", "wait",
    "wand", "weak0", "weak1", "while", "wire", "wor","xnor", "xor", "do"
}

def get_pin_direction(fragment, platform, pinname):
    ios = platform.constraint_manager.get_io_signals()
    sigs = list_signals(fragment) | list_special_ios(fragment, True, True, True)
    special_outs = list_special_ios(fragment, False, True, True)
    inouts = list_special_ios(fragment, False, False, True)
    targets = list_targets(fragment) | special_outs

    ns = build_namespace(list_signals(fragment) \
    | list_special_ios(fragment, True, True, True) \
    | ios, _reserved_keywords)
    ns.clock_domains = fragment.clock_domains

    dir = "Unknown"

    for sig in sorted(ios, key=lambda x: x.duid):
        # Better idea ???
        if (pinname.split('[')[0] == ns.get_name(sig)):
            if sig in inouts:
                dir = "inout"
            elif sig in targets:
                dir = "output"
            else:
                dir = "input"

    return dir

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
    return 'design.create_{d}_gpio("{name}"{len})'.format(d =d, name=sig, len=l)

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

def _build_iface_conf(named_sc, named_pc, fragment, platform):
    conf = []
    inst = []

    # GPIO
    for sig, pins, others, resname in named_sc:
        inst.append(_create_gpio_instance(fragment, platform, sig, pins))
        if len(pins) > 1:
            for i, p in enumerate(pins):
                conf.append(_format_conf_constraint("{}[{}]".format(sig, i), p, others, resname, fragment, platform))
        else:
            conf.append(_format_conf_constraint(sig, pins[0], others, resname, fragment, platform))
    if named_pc:
        conf.append("\n\n".join(named_pc))

    # PLL
    #inst.append()

    conf = inst + conf

    return "\n".join(conf)

def _build_peri(efinity_path, build_name, partnumber, named_sc, named_pc, fragment, platform):
    pythonpath = ""

    header = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision()

    header += """
import os
import sys

home = '{0}'

os.environ['EFXPT_HOME']  = home + '/pt'
os.environ['EFXPGM_HOME'] = home + '/pgm'
os.environ['EFXDBG_HOME'] = home + '/debugger'
os.environ['EFXIPM_HOME'] = home + '/ipm'

sys.path.append(home + '/pt/bin')
sys.path.append(home + '/lib/python3.8/site-packages')

from api_service.design import DesignAPI
from api_service.device import DeviceAPI

is_verbose = {1}

design = DesignAPI(is_verbose)
device = DeviceAPI(is_verbose)

design.create('{2}', '{3}', './../build', overwrite=True)

"""

    header = header.format(efinity_path, 'True', build_name, partnumber)

    conf = _build_iface_conf(named_sc, named_pc, fragment, platform)

    footer = """
# Check design, generate constraints and reports
 #design.generate(enable_bitstream=True)
# Save the configured periphery design
design.save()
    """

    tools.write_to_file("iface.py", header + conf + footer)

    subprocess.call([efinity_path + '/bin/python3', 'iface.py'])

# Project configuration ------------------------------------------------------------------------

def _build_xml(name, partnumber, build_name, sources, additional_xml_commands):

    test  = '<project xmlns:efx="http://www.efinixinc.com/enf_proj"'
    test += ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    test += ' name="{}"'.format(name)
    test += ' description=""'
    test += ' last_change_date="mer. sept. 15 2021 12:04:56"'
    test += ' location="{}"'.format(pathlib.Path().resolve())
    test += ' sw_version="2021.1.165.2.19"'
    test += ' last_run_state="" last_run_tool="" last_run_flow=""'
    test += ' config_result_in_sync="sync" design_ood="sync" place_ood="sync" route_ood="sync"'
    test += ' xsi:schemaLocation="http://www.efinixinc.com/enf_proj enf_proj.xsd"'
    test += '/>'

    root = etree.XML(test)

    device_info  = etree.SubElement(root, "device_info")
    etree.SubElement(device_info, "family", name = "Trion")
    etree.SubElement(device_info, "device", name = partnumber)
    etree.SubElement(device_info, "timing_model", name = "C4")

    design_info  = etree.SubElement(root, "design_info")
    etree.SubElement(design_info, "top_module", name = build_name)
    for filename, language, library in sources:
        val = {'name':filename, 'version':'default', 'library':'default'}
        etree.SubElement(design_info, "design_file", val)
    etree.SubElement(design_info, "top_vhdl_arch", name = "")

    constraint_info  = etree.SubElement(root, "constraint_info")
    etree.SubElement(constraint_info, "sdc_file", name = "{}.sdc".format(build_name))

    misc_info  = etree.SubElement(root, "misc_info")
    ip_info  = etree.SubElement(root, "ip_info")

    synthesis  = etree.SubElement(root, "synthesis", tool_name="efx_map")
    for l in additional_xml_commands:
        if l[0] == 'efx_map':
            val = {'name':l[1], 'value':l[2], 'value_type':l[3]}
            etree.SubElement(synthesis, "param", val)

    place_and_route  = etree.SubElement(root, "place_and_route", tool_name="efx_pnr")
    for l in additional_xml_commands:
        if l[0] == 'efx_pnr':
            val = {'name':l[1], 'value':l[2], 'value_type':l[3]}
            etree.SubElement(place_and_route, "param", val)

    bitstream_generation  = etree.SubElement(root, "bitstream_generation", tool_name="efx_pgm")
    for l in additional_xml_commands:
        if l[0] == 'efx_pgm':
            val = {'name':l[1], 'value':l[2], 'value_type':l[3]}
            etree.SubElement(bitstream_generation, "param", val)

    # Hack
    output = etree.tostring(root, pretty_print=True).decode().replace('<', '<efx:')
    output = output.replace('<efx:/', '</efx:')

    # Generate .xml
    tools.write_to_file("{}.xml".format(build_name), output)

class EfinityToolchain():
    attr_translate = {}

    def __init__(self, efinity_path):
        self.clocks      = dict()
        self.false_paths = set()
        self.efinity_path = efinity_path
        self.additional_sdc_commands = []
        self.additional_xml_commands = []

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
            name                    = build_name,
            partnumber              = platform.device,
            build_name              = build_name,
            sources                 = platform.sources,
            additional_xml_commands = self.additional_xml_commands)

        # Generate constraints file (.peri.xml)
        _build_peri(
            efinity_path            = self.efinity_path,
            build_name              = build_name,
            partnumber              = platform.device,
            named_sc                = named_sc,
            named_pc                = named_pc,
            fragment                = fragment,
            platform                = platform)

        # Run
        if run:
            subprocess.call([self.efinity_path + '/scripts/efx_run.py', build_name + '.xml', '-f', 'compile'])

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