#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform, VivadoProgrammer
from litex.build.openocd import OpenOCD

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("user_led", 0, Pins("T28"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("V19"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("U30"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("U29"), IOStandard("LVCMOS33")),
    ("user_led", 4, Pins("V20"), IOStandard("LVCMOS33")),
    ("user_led", 5, Pins("V26"), IOStandard("LVCMOS33")),
    ("user_led", 6, Pins("W24"), IOStandard("LVCMOS33")),
    ("user_led", 7, Pins("W23"), IOStandard("LVCMOS33")),

    ("cpu_reset_n", 0, Pins("R19"), IOStandard("LVCMOS33")),

    ("user_btn_c", 0, Pins("E18"), IOStandard("LVCMOS33")),
    ("user_btn_d", 0, Pins("M19"), IOStandard("LVCMOS33")),
    ("user_btn_l", 0, Pins("M20"), IOStandard("LVCMOS33")),
    ("user_btn_r", 0, Pins("C19"), IOStandard("LVCMOS33")),
    ("user_btn_u", 0, Pins("B19"), IOStandard("LVCMOS33")),

    ("user_sw", 0, Pins("G19"), IOStandard("LVCMOS12")),
    ("user_sw", 1, Pins("G25"), IOStandard("LVCMOS12")),
    ("user_sw", 2, Pins("H24"), IOStandard("LVCMOS12")),
    ("user_sw", 3, Pins("K19"), IOStandard("LVCMOS12")),
    ("user_sw", 4, Pins("N19"), IOStandard("LVCMOS12")),
    ("user_sw", 5, Pins("P19"), IOStandard("LVCMOS12")),
    ("user_sw", 6, Pins("P26"), IOStandard("LVCMOS33")),
    ("user_sw", 7, Pins("P27"), IOStandard("LVCMOS33")),

    ("clk200", 0,
        Subsignal("p", Pins("AD12"), IOStandard("LVDS")),
        Subsignal("n", Pins("AD11"), IOStandard("LVDS"))
    ),

    ("serial", 0,
        Subsignal("tx", Pins("Y23")),
        Subsignal("rx", Pins("Y20")),
        IOStandard("LVCMOS33")
    ),

    ("usb_fifo", 0, # Can be used when FT2232H's Channel A configured to ASYNC FIFO 245 mode
        Subsignal("data",  Pins("AD27 W27 W28 W29 Y29 Y28 AA28 AA26")),
        Subsignal("rxf_n", Pins("AB29")),
        Subsignal("txe_n", Pins("AA25")),
        Subsignal("rd_n",  Pins("AB25")),
        Subsignal("wr_n",  Pins("AC27")),
        Subsignal("siwua", Pins("AB28")),
        Subsignal("oe_n",  Pins("AC30")),
        Misc("SLEW=FAST"),
        Drive(8),
        IOStandard("LVCMOS33"),
    ),

    ("sdcard", 0,
        Subsignal("clk", Pins("R28")),
        Subsignal("cmd", Pins("R29"), Misc("PULLUP True")),
        Subsignal("data", Pins("R26 R30 P29 T30"), Misc("PULLUP True")),
        Misc("SLEW=FAST"),
        IOStandard("LVCMOS33")
    ),

    ("spisdcard", 0,
        Subsignal("clk",  Pins("R28")),
        Subsignal("cs_n", Pins("T30")),
        Subsignal("mosi", Pins("R29"), Misc("PULLUP")),
        Subsignal("miso", Pins("R26"), Misc("PULLUP")),
        Misc("SLEW=FAST"),
        IOStandard("LVCMOS33")
    ),

    ("ddram", 0,
        Subsignal("a", Pins(
            "AC12 AE8 AD8 AC10 AD9  AA13 AA10 AA11",
            "Y10  Y11 AB8  AA8 AB12 AA12 AH9"),
            IOStandard("SSTL15")),
        Subsignal("ba",    Pins("AE9 AB10 AC11"), IOStandard("SSTL15")),
        Subsignal("ras_n", Pins("AE11"), IOStandard("SSTL15")),
        Subsignal("cas_n", Pins("AF11"), IOStandard("SSTL15")),
        Subsignal("we_n",  Pins("AG13"), IOStandard("SSTL15")),
        Subsignal("cs_n",  Pins("AH12"), IOStandard("SSTL15")),
        Subsignal("dm", Pins("AD4 AF3 AH4 AF8"),
            IOStandard("SSTL15")),
        Subsignal("dq", Pins(
            "AD3 AC2 AC1 AC5 AC4 AD6 AE6 AC7",
            "AF2 AE1 AF1 AE4 AE3 AE5 AF5 AF6",
            "AJ4 AH6 AH5 AH2 AJ2 AJ1 AK1 AJ3",
            "AF7 AG7 AJ6 AK6 AJ8 AK8 AK5 AK4"),
            IOStandard("SSTL15_T_DCI")),
        Subsignal("dqs_p", Pins("AD2 AG4 AG2 AH7"),
            IOStandard("DIFF_SSTL15")),
        Subsignal("dqs_n", Pins("AD1 AG3 AH1 AJ7"),
            IOStandard("DIFF_SSTL15")),
        Subsignal("clk_p", Pins("AB9"), IOStandard("DIFF_SSTL15")),
        Subsignal("clk_n", Pins("AC9"), IOStandard("DIFF_SSTL15")),
        Subsignal("cke",   Pins("AJ9"), IOStandard("SSTL15")),
        Subsignal("odt",   Pins("AK9"), IOStandard("SSTL15")),
        Subsignal("reset_n", Pins("AG5"), IOStandard("LVCMOS15")),
        Misc("SLEW=FAST"),
        Misc("VCCAUX_IO=HIGH")
    ),

    ("eth_clocks", 0,
        Subsignal("tx", Pins("AE10")),
        Subsignal("rx", Pins("AG10")),
        IOStandard("LVCMOS15")
    ),
    ("eth", 0,
        Subsignal("rst_n",   Pins("AH24"), IOStandard("LVCMOS33")),
        Subsignal("int_n",   Pins("AK16"), IOStandard("LVCMOS18")),
        Subsignal("mdio",    Pins("AG12"), IOStandard("LVCMOS15")),
        Subsignal("mdc",     Pins("AF12"), IOStandard("LVCMOS15")),
        Subsignal("rx_ctl",  Pins("AH11"), IOStandard("LVCMOS15")),
        Subsignal("rx_data", Pins("AJ14 AH14 AK13 AJ13"), IOStandard("LVCMOS15")),
        Subsignal("tx_ctl",  Pins(" AK14"), IOStandard("LVCMOS15")),
        Subsignal("tx_data", Pins("AJ12 AK11 AJ11 AK10"), IOStandard("LVCMOS15")),
    ),
]

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
    ("HPC", {
        "DP0_C2M_P":     "Y2",
        "DP0_C2M_N":     "Y1",
        "DP0_M2C_P":     "AA4",
        "DP0_M2C_N":     "AA3",
        "GBTCLK0_M2C_P": "L8",
        "GBTCLK0_M2C_N": "L7",
        }
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(XilinxPlatform):
    default_clk_name   = "clk200"
    default_clk_period = 1e9/200e6

    def __init__(self):
        XilinxPlatform.__init__(self, "xc7k325t-ffg900-2", _io, _connectors, toolchain="vivado")
        self.add_platform_command("set_property INTERNAL_VREF 0.750 [get_iobanks 34]")

    def create_programmer(self):
        return OpenOCD("openocd_genesys2.cfg", "bscan_spi_xc7a325t.bit")

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk200",        loose=True), 1e9/200e6)
        self.add_period_constraint(self.lookup_request("eth_clocks:rx", loose=True), 1e9/125e6)
