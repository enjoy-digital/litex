# This file is Copyright (c) 2017 Sergiusz Bazanski <q3k@q3k.org>
# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import LatticeProgrammer

# IOs ----------------------------------------------------------------------------------------------

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

    ("spiflash", 0, # clock needs to be accessed through USRMCLK
        Subsignal("cs_n", Pins("R2")),
        Subsignal("mosi", Pins("W2")),
        Subsignal("miso", Pins("V2")),
        Subsignal("wp", Pins("Y2")),
        Subsignal("hold", Pins("W1")),
        IOStandard("LVCMOS33"),
    ),

    ("spiflash4x", 0, # clock needs to be accessed through USRMCLK
        Subsignal("cs_n", Pins("R2")),
        Subsignal("dq", Pins("W2 V2 Y2 W1")),
        IOStandard("LVCMOS33")
    ),

    ("ddram", 0,
        Subsignal("a", Pins(
            "P2 C4 E5 F5 B3 F4 B5 E4",
            "C5 E3 D5 B4 C3"),
            IOStandard("SSTL135_I")),
        Subsignal("ba", Pins("P5 N3 M3"), IOStandard("SSTL135_I")),
        Subsignal("ras_n", Pins("P1"), IOStandard("SSTL135_I")),
        Subsignal("cas_n", Pins("L1"), IOStandard("SSTL135_I")),
        Subsignal("we_n", Pins("M1"), IOStandard("SSTL135_I")),
        Subsignal("cs_n", Pins("K1"), IOStandard("SSTL135_I")),
        Subsignal("dm", Pins("J4 H5"), IOStandard("SSTL135_I")),
        Subsignal("dq", Pins(
            "L5 F1 K4 G1 L4 H1 G2 J3",
            "D1 C1 E2 C2 F3 A2 E1 B1"),
            IOStandard("SSTL135_I"),
            Misc("TERMINATION=75")),
        Subsignal("dqs_p", Pins("K2 H4"), IOStandard("SSTL135D_I"), Misc("TERMINATION=OFF"), Misc("DIFFRESISTOR=100")),
        Subsignal("clk_p", Pins("M4"), IOStandard("SSTL135D_I")),
        Subsignal("cke", Pins("N2"), IOStandard("SSTL135_I")),
        Subsignal("odt", Pins("L2"), IOStandard("SSTL135_I")),
        Subsignal("reset_n", Pins("N4"), IOStandard("SSTL135_I")),
        Misc("SLEWRATE=FAST"),
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

    ("ext_clk", 0,
        Subsignal("p", Pins("A4")),
        Subsignal("n", Pins("A5")),
        IOStandard("LVDS")
    ),

    ("pcie_x1", 0,
        Subsignal("clk_p", Pins("Y11")),
        Subsignal("clk_n", Pins("Y12")),
        Subsignal("rx_p", Pins("Y5")),
        Subsignal("rx_n", Pins("Y6")),
        Subsignal("tx_p", Pins("W4")),
        Subsignal("tx_n", Pins("W5")),
        Subsignal("perst", Pins("A6"), IOStandard("LVCMOS33")),
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

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
   ("X3",
        "None",  # (no pin 0)
        "None",  #  1 GND
        "None",  #  2 N/C
        "None",  #  3 +2V5
        "B19",   #  4 EXPCON_IO29
        "B12",   #  5 EXPCON_IO30
        "B9",    #  6 EXPCON_IO31
        "E6",    #  7 EXPCON_IO32
        "D6",    #  8 EXPCON_IO33
        "E7",    #  9 EXPCON_IO34
        "D7",    # 10 EXPCON_IO35
        "B11",   # 11 EXPCON_IO36
        "B6",    # 12 EXPCON_IO37
        "E9",    # 13 EXPCON_IO38
        "D9",    # 14 EXPCON_IO39
        "B8",    # 15 EXPCON_IO40
        "C8",    # 16 EXPCON_IO41
        "D8",    # 17 EXPCON_IO42
        "E8",    # 18 EXPCON_IO43
        "C7",    # 19 EXPCON_IO44
        "C6",    # 20 EXPCON_IO45
        "None",  # 21 +5V
        "None",  # 22 GND
        "None",  # 23 +2V5
        "None",  # 24 GND
        "None",  # 25 +3V3
        "None",  # 26 GND
        "None",  # 27 +3V3
        "None",  # 28 GND
        "None",  # 29 EXPCON_OSC
        "None",  # 30 GND
        "None",  # 31 EXPCON_CLKIN
        "None",  # 32 GND
        "None",  # 33 EXPCON_CLKOUT
        "None",  # 34 GND
        "None",  # 35 +3V3
        "None",  # 36 GND
        "None",  # 37 +3V3
        "None",  # 38 GND
        "None",  # 39 +3V3
        "None",  # 40 GND
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticePlatform):
    default_clk_name = "clk100"
    default_clk_period = 1e9/100e6

    def __init__(self, **kwargs):
        LatticePlatform.__init__(self, "LFE5UM5G-45F-8BG381C", _io, _connectors, **kwargs)

    def do_finalize(self, fragment):
        try:
            self.add_period_constraint(self.lookup_request("eth_clocks", 0).rx, 1e9/125e6)
        except ConstraintError:
            pass
        try:
            self.add_period_constraint(self.lookup_request("eth_clocks", 1).rx, 1e9/125e6)
        except ConstraintError:
            pass

    def create_programmer(self, with_ispclock=True):
        _xcf_ispclock = """
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
"""

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
            <File>{{bitstream_file}}</File>
            <Operation>Fast Program</Operation>
        </Device>{ispclock}
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
""".format(ispclock=_xcf_ispclock if with_ispclock else "")

        return LatticeProgrammer(_xcf_template)
