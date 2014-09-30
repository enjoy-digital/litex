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
	
	
	("serial", 0,
		Subsignal("cts", Pins("L27")),
		Subsignal("rts", Pins("K23")),
		Subsignal("tx", Pins("K24")),
		Subsignal("rx", Pins("M19")),
		IOStandard("LVCMOS25")
	),

	("sata_host", 0,
		Subsignal("refclk_p", Pins("G8")), # 125MHz SGMII
		Subsignal("refclk_n", Pins("G7")), # 125MHz SGMII
		Subsignal("txp", Pins("H2")), # SFP
		Subsignal("txn", Pins("H1")), # SFP
		Subsignal("rxp", Pins("G4")), # SFP
		Subsignal("rxn", Pins("G3")), # SFP
	),

	("sata_device", 0,
		Subsignal("refclk_p", Pins("G8")), # 125MHz SGMII
		Subsignal("refclk_n", Pins("G7")), # 125MHz SGMII
		Subsignal("txp", Pins("H2")), # SFP
		Subsignal("txn", Pins("H1")), # SFP
		Subsignal("rxp", Pins("G4")), # SFP
		Subsignal("rxn", Pins("G3")), # SFP
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
		bitgen_opt = "-g LCK_cycle:6 -g Binary:Yes -w -g ConfigRate:12 -g SPI_buswidth:4"

		def __init__(self, crg_factory=lambda p: CRG_DS(p, "clk156", "cpu_reset")):
			xilinx_platform.__init__(self, "xc7k325t-ffg900-2", _io, crg_factory)

		def create_programmer(self):
			return XC3SProg("jtaghs1_fast", "bscan_spi_kc705.bit")

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
