#
# This file is part of LiteX.
#
# Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import LatticeProgrammer

# IOs ----------------------------------------------------------------------------------------------

_io = [
    # Clk / Rst
    ("clk12", 0, Pins("C8"), IOStandard("LVCMOS33")),
    ("rst_n", 0, Pins("B3"), IOStandard("LVCMOS33")),

    # Leds
    ("user_led", 0, Pins("H11"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("J13"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("J11"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("L12"), IOStandard("LVCMOS33")),
    ("user_led", 4, Pins("K11"), IOStandard("LVCMOS33")),
    ("user_led", 5, Pins("L13"), IOStandard("LVCMOS33")),
    ("user_led", 6, Pins("N15"), IOStandard("LVCMOS33")),
    ("user_led", 7, Pins("P16"), IOStandard("LVCMOS33")),

    # Switches
    ("user_dip_btn", 0, Pins("N2"), IOStandard("LVCMOS33")),
    ("user_dip_btn", 1, Pins("P1"), IOStandard("LVCMOS33")),
    ("user_dip_btn", 2, Pins("M3"), IOStandard("LVCMOS33")),
    ("user_dip_btn", 3, Pins("N1"), IOStandard("LVCMOS33")),

    # Serial
    ("serial", 0,
        Subsignal("tx", Pins("C11"), IOStandard("LVCMOS33")),
        Subsignal("rx", Pins("A11"), IOStandard("LVCMOS33")),
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticePlatform):
    default_clk_name   = "clk12"
    default_clk_period = 1e9/12e6

    def __init__(self):
        LatticePlatform.__init__(self, "LCMXO3L-6900C-5BG256C", _io)

    def create_programmer(self):
        _xcf_template = """
<?xml version='1.0' encoding='utf-8' ?>
<!DOCTYPE       ispXCF  SYSTEM  "IspXCF.dtd" >
<ispXCF version="3.6.0">
    <Comment></Comment>
    <Chain>
        <Comm>JTAG</Comm>
        <Device>
            <SelectedProg value="TRUE"/>
            <Pos>1</Pos>
            <Vendor>Lattice</Vendor>
            <Family>MachXO3L</Family>
            <Name>LCMXO3L-6900C</Name>
            <IDCode>0x412bd043</IDCode>
            <Package>All</Package>
            <PON>LCMXO3L-6900C</PON>
            <Bypass>
                <InstrLen>8</InstrLen>
                <InstrVal>11111111</InstrVal>
                <BScanLen>1</BScanLen>
                <BScanVal>0</BScanVal>
            </Bypass>
            <File>{bitstream_file}</File>
            <JedecChecksum>N/A</JedecChecksum>
            <Operation>SRAM Fast Configuration</Operation>
            <Option>
                <SVFVendor>JTAG STANDARD</SVFVendor>
                <IOState>HighZ</IOState>
                <PreloadLength>664</PreloadLength>
                <IOVectorData>0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF</IOVectorData>
                <Usercode>0x00000000</Usercode>
                <AccessMode>SRAM</AccessMode>
            </Option>
        </Device>
    </Chain>
    <ProjectOptions>
        <Program>SEQUENTIAL</Program>
        <Process>ENTIRED CHAIN</Process>
        <OperationOverride>No Override</OperationOverride>
        <StartTAP>TLR</StartTAP>
        <EndTAP>TLR</EndTAP>
        <VerifyUsercode value="FALSE"/>
    </ProjectOptions>
    <CableOptions>
        <CableName>USB2</CableName>
        <PortAdd>FTUSB-0</PortAdd>
        <USBID>Lattice XO3L Starter Kit A Location 0000 Serial A</USBID>
    </CableOptions>
</ispXCF>
"""
        return LatticeProgrammer(_xcf_template)

    def do_finalize(self, fragment):
        LatticePlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk12", loose=True), 1e9/12e6)
