#
# This file is part of LiteX.
#
# Copyright (c) 2021 Miodrag Milanovic <mmicko@gmail.com>
# Copyright (c) 2015-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import math
import subprocess
import datetime
from shutil import which

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import *
from litex.build.generic_toolchain import GenericToolchain
from litex.build import tools

# TangDinastyToolchain -----------------------------------------------------------------------------

class TangDinastyToolchain(GenericToolchain):
    attr_translate = {}

    def __init__(self):
        super().__init__()
        self._architecture = ""
        self._family       = ""
        self._package      = ""

    def finalize(self):
        self._architecture, self._family, self._package = self.parse_device()

    # Constraints (.adc ) --------------------------------------------------------------------------

    def build_io_constraints(self):
        adc = []

        flat_sc = []
        for name, pins, other, resource in self.named_sc:
            if len(pins) > 1:
                for i, p in enumerate(pins):
                    flat_sc.append((f"{name}[{i}]", p, other))
            else:
                flat_sc.append((name, pins[0], other))

        for name, pin, other in flat_sc:
            line = f"set_pin_assignment {{{name}}} {{ LOCATION = {pin}; "
            for c in other:
                if isinstance(c, IOStandard):
                    line += f" IOSTANDARD = {c.name}; "
            line += f"}}"
            adc.append(line)

        if self.named_pc:
            adc.extend(self.named_pc)

        tools.write_to_file("top.adc", "\n".join(adc))
        return ("top.adc", "ADC")

    # Timing Constraints (in sdc file) -------------------------------------------------------------

    def build_timing_constraints(self, vns):
        sdc = []
        for clk, [period, name] in sorted(self.clocks.items(), key=lambda x: x[0].duid):
            clk_sig = self._vns.get_name(clk)
            if name is None:
                name = clk_sig
            sdc.append(f"create_clock -name {name} -period {str(period)} [get_ports {{{clk_sig}}}]")
        tools.write_to_file("top.sdc", "\n".join(sdc))
        return ("top.sdc", "SDC")

    # Project (.ai) --------------------------------------------------------------------------------

    def build_project(self):
        xml = []

        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Set Device.
        xml.append(f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        xml.append(f"<Project Version=\"1\" Path=\"...\">")
        xml.append(f"    <Project_Created_Time>{date}</Project_Created_Time>")
        xml.append(f"    <TD_Version>5.0.28716</TD_Version>")
        xml.append(f"    <UCode>00000000</UCode>")
        xml.append(f"    <Name>{self._build_name}</Name>")
        xml.append(f"    <HardWare>")
        xml.append(f"        <Family>{self._family}</Family>")
        xml.append(f"        <Device>{self.platform.device}</Device>")
        xml.append(f"    </HardWare>")
        xml.append(f"    <Source_Files>")
        xml.append(f"        <Verilog>")

        # Add Sources.
        for f, typ, lib in self.platform.sources:
            xml.append(f"            <File Path=\"{f}\">")
            xml.append(f"                <FileInfo>")
            xml.append(f"                    <Attr Name=\"UsedInSyn\" Val=\"true\"/>")
            xml.append(f"                    <Attr Name=\"UsedInP&R\" Val=\"true\"/>")
            xml.append(f"                    <Attr Name=\"BelongTo\" Val=\"design_1\"/>")
            xml.append(f"                    <Attr Name=\"CompileOrder\" Val=\"1\"/>")
            xml.append(f"               </FileInfo>")
            xml.append(f"            </File>")
        xml.append(f"        </Verilog>")

        # Add IOs Constraints.
        xml.append(f"        <ADC_FILE>")
        xml.append(f"            <File Path=\"top.adc\">")
        xml.append(f"                <FileInfo>")
        xml.append(f"                    <Attr Name=\"UsedInSyn\" Val=\"true\"/>")
        xml.append(f"                    <Attr Name=\"UsedInP&R\" Val=\"true\"/>")
        xml.append(f"                    <Attr Name=\"BelongTo\" Val=\"constrain_1\"/>")
        xml.append(f"                    <Attr Name=\"CompileOrder\" Val=\"1\"/>")
        xml.append(f"               </FileInfo>")
        xml.append(f"            </File>")
        xml.append(f"        </ADC_FILE>")
        xml.append(f"        <SDC_FILE>")
        xml.append(f"            <File Path=\"top.sdc\">")
        xml.append(f"                <FileInfo>")
        xml.append(f"                    <Attr Name=\"UsedInSyn\" Val=\"true\"/>")
        xml.append(f"                    <Attr Name=\"UsedInP&R\" Val=\"true\"/>")
        xml.append(f"                    <Attr Name=\"BelongTo\" Val=\"constrain_1\"/>")
        xml.append(f"                    <Attr Name=\"CompileOrder\" Val=\"2\"/>")
        xml.append(f"               </FileInfo>")
        xml.append(f"            </File>")
        xml.append(f"        </SDC_FILE>")
        xml.append(f"    </Source_Files>")
        xml.append(f"   <FileSets>")
        xml.append(f"        <FileSet Name=\"constrain_1\" Type=\"ConstrainFiles\">")
        xml.append(f"        </FileSet>")
        xml.append(f"        <FileSet Name=\"design_1\" Type=\"DesignFiles\">")
        xml.append(f"        </FileSet>")
        xml.append(f"    </FileSets>")
        xml.append(f"    <TOP_MODULE>")
        xml.append(f"        <LABEL></LABEL>")
        xml.append(f"        <MODULE>{self._build_name}</MODULE>")
        xml.append(f"        <CREATEINDEX>auto</CREATEINDEX>")
        xml.append(f"    </TOP_MODULE>")
        xml.append(f"    <Property>")
        xml.append(f"    </Property>")
        xml.append(f"    <Device_Settings>")
        xml.append(f"    </Device_Settings>")
        xml.append(f"    <Configurations>")
        xml.append(f"    </Configurations>")
        xml.append(f"    <Project_Settings>")
        xml.append(f"        <Step_Last_Change>{date}</Step_Last_Change>")
        xml.append(f"        <Current_Step>0</Current_Step>")
        xml.append(f"        <Step_Status>true</Step_Status>")
        xml.append(f"    </Project_Settings>")
        xml.append(f"</Project>")

        # Generate .al.
        tools.write_to_file(self._build_name + ".al", "\n".join(xml))

    # Script ---------------------------------------------------------------------------------------

    def build_script(self):
        tcl = []

        # Set Device.
        tcl.append(f"import_device {self._architecture}.db -package {self._package}")

        # Add project.
        tcl.append(f"open_project {self._build_name}.al")

        # Elaborate.
        tcl.append(f"elaborate -top {self._build_name}")

        # Add IOs Constraints.
        tcl.append("read_adc top.adc")

        tcl.append("optimize_rtl")

        # Add SDC Constraints.
        tcl.append("read_sdc top.sdc")

        # Perform PnR.
        tcl.append("optimize_gate")
        tcl.append("legalize_phy_inst")
        tcl.append("place")
        tcl.append("route")
        tcl.append(f"bitgen -bit \"{self._build_name}.bit\" -version 0X00 -g ucode:000000000000000000000000")

        # Generate .tcl.
        tools.write_to_file("run.tcl", "\n".join(tcl))

        return "run.tcl"

    def run_script(self, script):
            if which("td") is None:
                msg = "Unable to find Tang Dinasty toolchain, please:\n"
                msg += "- Add  Tang Dinasty toolchain to your $PATH."
                raise OSError(msg)

            if subprocess.call(["td", script]) != 0:
                raise OSError("Error occured during Tang Dinasty's script execution.")

    def parse_device(self):
        device = self.platform.device

        devices = {
            "EG4S20BG256" :[ "eagle_s20", "EG4", "BG256" ],
        }

        if device not in devices.keys():
            raise ValueError("Invalid device {}".format(device))

        (architecture, family, package) = devices[device]
        return (architecture, family, package)
