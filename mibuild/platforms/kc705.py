from mibuild.generic_platform import *
from mibuild.xilinx_common import CRG_SE, CRG_DS
from mibuild.xilinx_ise import XilinxISEPlatform
from mibuild.xilinx_vivado import XilinxVivadoPlatform

_io = [
	("user_led", 0, Pins("AB8"), IOStandard("LVCMOS15")),
	("user_led", 1, Pins("AA8"), IOStandard("LVCMOS15")),
	("user_led", 2, Pins("AC9"), IOStandard("LVCMOS15")),
	("user_led", 3, Pins("AB9"), IOStandard("LVCMOS15")),
	("user_led", 4, Pins("AE26"), IOStandard("LVCMOS25")),
	("user_led", 5, Pins("G19"), IOStandard("LVCMOS25")),
	("user_led", 6, Pins("E18"), IOStandard("LVCMOS25")),
	("user_led", 7, Pins("F16"), IOStandard("LVCMOS25")),
	
	("cpu_reset", 0, Pins("AB7"), IOStandard("LVCMOS15")),
	
	("user_btn_c", 0, Pins("G12"), IOStandard("LVCMOS25")),
	("user_btn_n", 0, Pins("AA12"), IOStandard("LVCMOS15")),
	("user_btn_s", 0, Pins("AB12"), IOStandard("LVCMOS15")),
	("user_btn_w", 0, Pins("AC6"), IOStandard("LVCMOS15")),
	("user_btn_e", 0, Pins("AG5"), IOStandard("LVCMOS15")),
	
	("user_dip_btn", 0, Pins("Y29"), IOStandard("LVCMOS25")),
	("user_dip_btn", 1, Pins("W29"), IOStandard("LVCMOS25")),
	("user_dip_btn", 2, Pins("AA28"), IOStandard("LVCMOS25")),
	("user_dip_btn", 3, Pins("Y28"), IOStandard("LVCMOS25")),
	
	("clk200", 0,
		Subsignal("p", Pins("AD12"), IOStandard("LVDS")),
		Subsignal("n", Pins("AD11"), IOStandard("LVDS"))
	),
	
	("clk156", 0,
		Subsignal("p", Pins("K28"), IOStandard("LVDS_25")),
		Subsignal("n", Pins("K29"), IOStandard("LVDS_25"))
	),
	
	("i2c", 0,
		Subsignal("scl", Pins("K21")),
		Subsignal("sda", Pins("L21")),
		IOStandard("LVCMOS25")),
	
	("serial", 0,
		Subsignal("cts", Pins("L27")),
		Subsignal("rts", Pins("K23")),
		Subsignal("tx", Pins("K24")),
		Subsignal("rx", Pins("M19")),
		IOStandard("LVCMOS25")),
		
	("mmc", 0,
		Subsignal("wp", Pins("Y21")),
		Subsignal("det", Pins("AA21")),
		Subsignal("cmd", Pins("AB22")),
		Subsignal("clk", Pins("AB23")),
		Subsignal("dat", Pins("AC20 AA23 AA22 AC21")),
		IOStandard("LVCMOS25")),
	
	("lcd", 0,
		Subsignal("db", Pins("AA13 AA10 AA11 Y10")),
		Subsignal("e", Pins("AB10")),
		Subsignal("rs", Pins("Y11")),
		Subsignal("rw", Pins("AB13")),
		IOStandard("LVCMOS15")),
		
	("rotary", 0,
		Subsignal("a", Pins("Y26")),
		Subsignal("b", Pins("Y25")),
		Subsignal("push", Pins("AA26")),
		IOStandard("LVCMOS25")),
	
	("hdmi", 0,
		Subsignal("d", Pins("B23 A23 E23 D23 F25 E25 E24 D24 F26 E26 G23 G24 J19 H19 L17 L18 K19 K20")),
		Subsignal("de", Pins("H17")),
		Subsignal("clk", Pins("K18")),
		Subsignal("vsync", Pins("H20")),
		Subsignal("hsync", Pins("J18")),
		Subsignal("int", Pins("AH24")),
		Subsignal("spdif", Pins("J17")),
		Subsignal("spdif_out", Pins("G20")),
		IOStandard("LVCMOS25")),
]

def Platform(*args, toolchain="ise", **kwargs):
	if toolchain == "ise":
		xilinx_platform = XilinxISEPlatform
	elif toolchain == "vivado":
		xilinx_platform = XilinxVivadoPlatform
	else:
		raise ValueError

	class RealPlatform(xilinx_platform):
		def __init__(self, crg_factory=lambda p: CRG_DS(p, "clk156", "cpu_reset", 6.4)):
			xilinx_platform.__init__(self, "xc7k325t-ffg900-1", _io, crg_factory)

	return RealPlatform(*args, **kwargs)
