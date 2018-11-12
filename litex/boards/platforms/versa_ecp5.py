# This file is Copyright (c) 2017 Serge 'q3k' Bazanski <serge@bazanski.pl>
# License: BSD

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import LatticeProgrammer


_io = [
    ("clk100", 0, Pins("P3"), IOStandard("LVDS")),
    ("rst_n", 0, Pins("T1"), IOStandard("LVCMOS33")),

    ("user_led", 0, Pins("E16"), IOStandard("LVCMOS25")),
    ("user_led", 1, Pins("D17"), IOStandard("LVCMOS25")),
    ("user_led", 2, Pins("D18"), IOStandard("LVCMOS25")),
    ("user_led", 3, Pins("E18"), IOStandard("LVCMOS25")),
    ("user_led", 4, Pins("F17"), IOStandard("LVCMOS25")),
    ("user_led", 5, Pins("F18"), IOStandard("LVCMOS25")),
    ("user_led", 6, Pins("E17"), IOStandard("LVCMOS25")),
    ("user_led", 7, Pins("F16"), IOStandard("LVCMOS25")),

    ("user_dip_btn", 0, Pins("H2"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 1, Pins("K3"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 2, Pins("G3"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 3, Pins("F2"), IOStandard("LVCMOS15")),
    ("user_dip_btn", 4, Pins("J18"), IOStandard("LVCMOS25")),
    ("user_dip_btn", 5, Pins("K18"), IOStandard("LVCMOS25")),
    ("user_dip_btn", 6, Pins("K19"), IOStandard("LVCMOS25")),
    ("user_dip_btn", 7, Pins("K20"), IOStandard("LVCMOS25")),

    ("serial", 0,
        Subsignal("rx", Pins("C11"), IOStandard("LVCMOS33")),
        Subsignal("tx", Pins("A11"), IOStandard("LVCMOS33")),
    ),

    ("eth_clocks", 0,
        Subsignal("tx", Pins("P19")),
        Subsignal("rx", Pins("L20")),
        IOStandard("LVCMOS25")
    ),
    ("eth", 0,
        Subsignal("rst_n", Pins("U17")),
        Subsignal("mdio", Pins("U18")),
        Subsignal("mdc", Pins("T18")),
        Subsignal("rx_ctl", Pins("U19")),
        Subsignal("rx_data", Pins("T20 U20 T19 R18")),
        Subsignal("tx_ctl", Pins("R20")),
        Subsignal("tx_data", Pins("N19 N20 P18 P20")),
        IOStandard("LVCMOS25")
    ),

    ("eth_clocks", 1,
        Subsignal("tx", Pins("C20")),
        Subsignal("rx", Pins("J19")),
        IOStandard("LVCMOS25")
    ),
    ("eth", 1,
        Subsignal("rst_n", Pins("F20")),
        Subsignal("mdio", Pins("H20")),
        Subsignal("mdc", Pins("G19")),
        Subsignal("rx_ctl", Pins("F19")),
        Subsignal("rx_data", Pins("G18 G16 H18 H17")),
        Subsignal("tx_ctl", Pins("E19")),
        Subsignal("tx_data", Pins("J17 J16 D19 D20")),
        IOStandard("LVCMOS25")
    ),
]


_ecp5_soc_hat_io = [
    ("sdram_clock", 0, Pins("E14"), IOStandard("LVCMOS33")),
    ("sdram", 0,
         Subsignal("a", Pins(
            "C6 E15 A16 B16 D15 C15 B15 E12",
            "D12 B10 C7 A9 C10")),
         Subsignal("dq", Pins(
            "B19 B12 B9 E6 D6 E7 D7 B11",
            "C14 A14 E13 D13 C13 B13 A13 A12")),
         Subsignal("we_n", Pins("E9")),
         Subsignal("ras_n", Pins("B8")),
         Subsignal("cas_n", Pins("D9")),
         Subsignal("cs_n", Pins("C8")),
         Subsignal("cke", Pins("D11")),
         Subsignal("ba", Pins("D8 E8")),
         Subsignal("dm", Pins("B6 D14")),
         IOStandard("LVCMOS33"), Misc("SLEWRATE=FAST")
    ),
]


class Platform(LatticePlatform):
    default_clk_name = "clk100"
    default_clk_period = 10

    def __init__(self, **kwargs):
        LatticePlatform.__init__(self, "LFE5UM5G-45F-8BG381C", _io, **kwargs)

    def do_finalize(self, fragment):
        LatticePlatform.do_finalize(self, fragment)
        try:
            self.add_period_constraint(self.lookup_request("eth_clocks", 0).rx, 8.0)
        except ConstraintError:
            pass
        try:
            self.add_period_constraint(self.lookup_request("eth_clocks", 1).rx, 8.0)
        except ConstraintError:
            pass

    def create_programmer(self):
        _xcf_template = """
<?xml version='1.0' encoding='utf-8' ?>
<!DOCTYPE        ispXCF    SYSTEM    "IspXCF.dtd" >
<ispXCF version="3.4.1">
    <Comment></Comment>
    <Chain>
        <Comm>JTAG</Comm>
        <Device>
            <SelectedProg value="TRUE"/>
            <Pos>1</Pos>
            <Vendor>Lattice</Vendor>
            <Family>ECP5UM5G</Family>
            <Name>LFE5UM5G-45F</Name>
            <IDCode>0x81112043</IDCode>
            <File>{bitstream_file}</File>
            <Operation>Fast Program</Operation>
        </Device>
        <Device>
            <SelectedProg value="FALSE"/>
            <Pos>2</Pos>
            <Vendor>Lattice</Vendor>
            <Family>ispCLOCK</Family>
            <Name>ispPAC-CLK5406D</Name>
            <IDCode>0x00191043</IDCode>
            <Operation>Erase,Program,Verify</Operation>
            <Bypass>
                <InstrLen>8</InstrLen>
                <InstrVal>11111111</InstrVal>
                <BScanLen>1</BScanLen>
                <BScanVal>0</BScanVal>
            </Bypass>
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
        <USBID>LATTICE ECP5_5G VERSA BOARD A Location 0000 Serial Lattice ECP5_5G VERSA Board A</USBID>
    </CableOptions>
</ispXCF>
"""

        return LatticeProgrammer(_xcf_template)
