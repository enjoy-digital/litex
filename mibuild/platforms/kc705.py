from mibuild.generic_platform import *
from mibuild.crg import SimpleCRG
from mibuild.xilinx_common import CRG_DS
from mibuild.xilinx_ise import XilinxISEPlatform
from mibuild.xilinx_vivado import XilinxVivadoPlatform
from mibuild.programmer import XC3SProg

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

	("ddram", 0,
		Subsignal("a", Pins(
			"AH12 AG13 AG12 AF12 AJ12 AJ13 AJ14 AH14",
			"AK13 AK14 AF13 AE13 AJ11 AH11 AK10 AK11"),
			IOStandard("SSTL15")),
		Subsignal("ba", Pins("AH9 AG9 AK9"), IOStandard("SSTL15")),
		Subsignal("cke", Pins("AF10 AE10"), IOStandard("SSTL15")),
		Subsignal("ras_n", Pins("AD9"), IOStandard("SSTL15")),
		Subsignal("cas_n", Pins("AC11"), IOStandard("SSTL15")),
		Subsignal("we_n", Pins("AE9"), IOStandard("SSTL15")),
		Subsignal("cs_n", Pins("AC12 AE8"), IOStandard("SSTL15")),
		Subsignal("odt", Pins("AD8 AC10"), IOStandard("SSTL15")),
		Subsignal("dm", Pins("Y16 AB17 AF17 AE16 AK5 AJ3 AF6 AC7"),
			IOStandard("SSTL15")),
		Subsignal("dq", Pins(
			"AA15 AA16 AC14 AD14 AA17 AB15 AE15 Y15",
			"AB19 AD16 AC19 AD17 AA18 AB18 AE18 AD18",
			"AG19 AK19 AG18 AF18 AH19 AJ19 AE19 AD19",
			"AK16 AJ17 AG15 AF15 AH17 AG14 AH15 AK15",
			"AK8 AK6 AG7 AF7 AF8 AK4 AJ8 AJ6",
			"AH5 AH6 AJ2 AH2 AH4 AJ4 AK1 AJ1",
			"AF1 AF2 AE4 AE3 AF3 AF5 AE1 AE5",
			"AC1 AD3 AC4 AC5 AE6 AD6 AC2 AD4"),
			IOStandard("SSTL15")),
		Subsignal("dqs_p", Pins("AC16 Y19 AJ18 AH16 AH7 AG2 AG4 AD2"),
			IOStandard("DIFF_SSTL15")),
		Subsignal("dqs_n", Pins("AC15 Y18 AK18 AJ16 AJ7 AH1 AG3 AD1"),
			IOStandard("DIFF_SSTL15")),
		Subsignal("clk_p", Pins("AG10"), IOStandard("DIFF_SSTL15")),
		Subsignal("clk_n", Pins("AH10"), IOStandard("DIFF_SSTL15")),
		Subsignal("rst_n", Pins("AK3"), IOStandard("LVCMOS15")),
		Misc("SLEW=FAST"),
		Misc("VCCAUX_IO=HIGH")
	),
]

def Platform(*args, toolchain="vivado", **kwargs):
	if toolchain == "ise":
		xilinx_platform = XilinxISEPlatform
	elif toolchain == "vivado":
		xilinx_platform = XilinxVivadoPlatform
	else:
		raise ValueError

	class RealPlatform(xilinx_platform):
		def __init__(self, crg_factory=lambda p: CRG_DS(p, "clk156", "cpu_reset")):
			xilinx_platform.__init__(self, "xc7k325t-ffg900-2", _io, crg_factory)

		def create_programmer(self):
			return XC3SProg("jtaghs1", "bscan_spi_kc705.bit")

		def do_finalize(self, fragment):
			try:
				self.add_period_constraint(self.lookup_request("clk156").p, 6.4)
			except ConstraintError:
				pass
			try:
				self.add_period_constraint(self.lookup_request("clk200").p, 5.0)
			except ConstraintError:
				pass
	return RealPlatform(*args, **kwargs)
