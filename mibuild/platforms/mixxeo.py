from mibuild.generic_platform import *
from mibuild.xilinx_ise import XilinxISEPlatform, CRG_SE

_io = [
	("user_led", 0, Pins("V5"), IOStandard("LVCMOS33"), Drive(24), Misc("SLEW=QUIETIO")),

	("clk50", 0, Pins("AB13"), IOStandard("LVCMOS33")),

	# When executing softcore code in-place from the flash, we want
	# the flash reset to be released before the system reset.
	("norflash_rst_n", 0, Pins("P22"), IOStandard("LVCMOS33"), Misc("SLEW=FAST"), Drive(8)),
	("norflash", 0,
		Subsignal("adr", Pins("L22 L20 K22 K21 J19 H20 F22",
			"F21 K17 J17 E22 E20 H18 H19 F20",
			"G19 C22 C20 D22 D21 F19 F18 D20 D19")),
		Subsignal("d", Pins("AA20 U14 U13 AA6 AB6 W4 Y4 Y7",
			"AA2 AB2 V15 AA18 AB18 Y13 AA12 AB12"), Misc("PULLDOWN")),
		Subsignal("oe_n", Pins("M22")),
		Subsignal("we_n", Pins("N20")),
		Subsignal("ce_n", Pins("M21")),
		IOStandard("LVCMOS33"), Misc("SLEW=FAST"), Drive(8)
	),
	
	("serial", 0,
		Subsignal("tx", Pins("L17"), IOStandard("LVCMOS33"), Misc("SLEW=SLOW")),
		Subsignal("rx", Pins("K18"), IOStandard("LVCMOS33"), Misc("PULLUP"))
	),
	
	("ddram_clock", 0,
		Subsignal("p", Pins("M3")),
		Subsignal("n", Pins("L4")),
		IOStandard("SSTL2_I")
	),	
	("ddram", 0,
		Subsignal("a", Pins("B1 B2 H8 J7 E4 D5 K7 F5 G6 C1 C3 D1 D2")),
		Subsignal("ba", Pins("A2 E6")),
		Subsignal("cs_n", Pins("F7")),
		Subsignal("cke", Pins("G7")),
		Subsignal("ras_n", Pins("E5")),
		Subsignal("cas_n", Pins("C4")),
		Subsignal("we_n", Pins("D3")),
		Subsignal("dq", Pins("Y2 W3 W1 P8 P7 P6 P5 T4 T3",
			"U4 V3 N6 N7 M7 M8 R4 P4 M6 L6 P3 N4",
			"M5 V2 V1 U3 U1 T2 T1 R3 R1 P2 P1")),
		Subsignal("dm", Pins("E1 E3 F3 G4")),
		Subsignal("dqs", Pins("F1 F2 H5 H6")),
		IOStandard("SSTL2_I")
	),

	("eth_clocks", 0,
		Subsignal("phy", Pins("M20")),
		Subsignal("rx", Pins("H22")),
		Subsignal("tx", Pins("H21")),
		IOStandard("LVCMOS33")
	),
	("eth", 0,
		Subsignal("rst_n", Pins("R22")),
		Subsignal("dv", Pins("V21")),
		Subsignal("rx_er", Pins("V22")),
		Subsignal("rx_data", Pins("U22 U20 T22 T21")),
		Subsignal("tx_en", Pins("N19")),
		Subsignal("tx_er", Pins("M19")),
		Subsignal("tx_data", Pins("M16 L15 P19 P20")),
		Subsignal("col", Pins("W20")),
		Subsignal("crs", Pins("W22")),
		IOStandard("LVCMOS33")
	),

	("vga_clock", 0, Pins("A10"), IOStandard("LVCMOS33")),
	("vga", 0,
		Subsignal("r", Pins("C6 B6 A6 C7 A7 B8 A8 D9")),
		Subsignal("g", Pins("C8 C9 A9 D7 D8 D10 C10 B10")),
		Subsignal("b", Pins("D11 C12 B12 A12 C13 A13 D14 C14")),
		Subsignal("hsync_n", Pins("A14")),
		Subsignal("vsync_n", Pins("C15")),
		Subsignal("psave_n", Pins("B14")),
		IOStandard("LVCMOS33")
	),

	("mmc", 0,
		Subsignal("clk", Pins("J3")),
		Subsignal("cmd", Pins("K1")),
		Subsignal("dat", Pins("J6 K6 N1 K5")),
		IOStandard("LVCMOS33")
	),

	("dvi_in", 0,
		Subsignal("clk_p", Pins("K20"), IOStandard("TMDS_33")),
		Subsignal("clk_n", Pins("K19"), IOStandard("TMDS_33")),
		Subsignal("data0_p", Pins("B21"), IOStandard("TMDS_33")),
		Subsignal("data0_n", Pins("B22"), IOStandard("TMDS_33")),
		Subsignal("data1_p", Pins("A20"), IOStandard("TMDS_33")),
		Subsignal("data1_n", Pins("A21"), IOStandard("TMDS_33")),
		Subsignal("data2_p", Pins("K16"), IOStandard("TMDS_33")),
		Subsignal("data2_n", Pins("J16"), IOStandard("TMDS_33")),
		Subsignal("scl", Pins("G20"), IOStandard("LVCMOS33")),
		Subsignal("sda", Pins("H16"), IOStandard("LVCMOS33")),
		Subsignal("hpd_notif", Pins("G22"), IOStandard("LVCMOS33")),
		Subsignal("hpd_en", Pins("G17"), IOStandard("LVCMOS33"))
	),
	("dvi_in", 1,
		Subsignal("clk_p", Pins("C11"), IOStandard("TMDS_33")),
		Subsignal("clk_n", Pins("A11"), IOStandard("TMDS_33")),
		Subsignal("data0_p", Pins("C17"), IOStandard("TMDS_33")),
		Subsignal("data0_n", Pins("A17"), IOStandard("TMDS_33")),
		Subsignal("data1_p", Pins("B18"), IOStandard("TMDS_33")),
		Subsignal("data1_n", Pins("A18"), IOStandard("TMDS_33")),
		Subsignal("data2_p", Pins("E16"), IOStandard("TMDS_33")),
		Subsignal("data2_n", Pins("D17"), IOStandard("TMDS_33")),
		Subsignal("scl", Pins("F17"), IOStandard("LVCMOS33")),
		Subsignal("sda", Pins("F16"), IOStandard("LVCMOS33")),
		Subsignal("hpd_notif", Pins("G16"), IOStandard("LVCMOS33")),
		Subsignal("hpd_en", Pins("B20"), IOStandard("LVCMOS33"))
	),
	("dvi_in", 2,
		Subsignal("clk_p", Pins("Y11"), IOStandard("TMDS_33")),
		Subsignal("clk_n", Pins("AB11"), IOStandard("TMDS_33")),
		Subsignal("data0_p", Pins("V11"), IOStandard("TMDS_33")),
		Subsignal("data0_n", Pins("W11"), IOStandard("TMDS_33")),
		Subsignal("data1_p", Pins("AA10"), IOStandard("TMDS_33")),
		Subsignal("data1_n", Pins("AB10"), IOStandard("TMDS_33")),
		Subsignal("data2_p", Pins("R11"), IOStandard("TMDS_33")),
		Subsignal("data2_n", Pins("T11"), IOStandard("TMDS_33")),
		Subsignal("scl", Pins("C16"), IOStandard("LVCMOS33")),
		Subsignal("sda", Pins("B16"), IOStandard("LVCMOS33")),
		Subsignal("hpd_notif", Pins("D6"), IOStandard("LVCMOS33")),
		Subsignal("hpd_en", Pins("A4"), IOStandard("LVCMOS33"))
	),
	("dvi_in", 3,
		Subsignal("clk_p", Pins("J20"), IOStandard("TMDS_33")),
		Subsignal("clk_n", Pins("J22"), IOStandard("TMDS_33")),
		Subsignal("data0_p", Pins("P18"), IOStandard("TMDS_33")),
		Subsignal("data0_n", Pins("R19"), IOStandard("TMDS_33")),
		Subsignal("data1_p", Pins("P17"), IOStandard("TMDS_33")),
		Subsignal("data1_n", Pins("N16"), IOStandard("TMDS_33")),
		Subsignal("data2_p", Pins("M17"), IOStandard("TMDS_33")),
		Subsignal("data2_n", Pins("M18"), IOStandard("TMDS_33")),
		Subsignal("scl", Pins("P21"), IOStandard("LVCMOS33")),
		Subsignal("sda", Pins("N22"), IOStandard("LVCMOS33")),
		Subsignal("hpd_notif", Pins("H17"), IOStandard("LVCMOS33")),
		Subsignal("hpd_en", Pins("C19"), IOStandard("LVCMOS33"))
	),
]

class Platform(XilinxISEPlatform):
	def __init__(self):
		XilinxISEPlatform.__init__(self, "xc6slx45-fgg484-2", _io,
			lambda p: CRG_SE(p, "clk50", None))
		self.add_platform_command("CONFIG VCCAUX=\"3.3\";\n")

	def do_finalize(self, fragment):
		try:
			self.add_platform_command("""
NET "{clk50}" TNM_NET = "GRPclk50";
TIMESPEC "TSclk50" = PERIOD "GRPclk50" 20 ns HIGH 50%;
""", clk50=self.lookup_request("clk50"))
		except ConstraintError:
			pass

		try:
			eth_clocks = self.lookup_request("eth_clocks")
			self.add_platform_command("""
NET "{phy_rx_clk}" TNM_NET = "GRPphy_rx_clk";
NET "{phy_tx_clk}" TNM_NET = "GRPphy_tx_clk";
TIMESPEC "TSphy_rx_clk" = PERIOD "GRPphy_rx_clk" 40 ns HIGH 50%;
TIMESPEC "TSphy_tx_clk" = PERIOD "GRPphy_tx_clk" 40 ns HIGH 50%;
TIMESPEC "TSphy_tx_clk_io" = FROM "GRPphy_tx_clk" TO "PADS" 10 ns;
TIMESPEC "TSphy_rx_clk_io" = FROM "PADS" TO "GRPphy_rx_clk" 10 ns;
""", phy_rx_clk=eth_clocks.rx, phy_tx_clk=eth_clocks.tx)
		except ConstraintError:
			pass

		for i in range(4):
			si = "dviclk"+str(i)
			try:
				self.add_platform_command("""
NET "{dviclk}" TNM_NET = "GRP"""+si+"""";
TIMESPEC "TS"""+si+"""" = PERIOD "GRP"""+si+"""" 26.7 ns HIGH 50%;
""", dviclk=self.lookup_request("dvi_in", i).clk_p)
			except ConstraintError:
				pass
