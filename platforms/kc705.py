from mibuild.generic_platform import *
from mibuild.crg import SimpleCRG
from mibuild.xilinx_common import CRG_DS
from mibuild.xilinx_ise import XilinxISEPlatform
from mibuild.xilinx_vivado import XilinxVivadoPlatform
from mibuild.programmer import *

def _run_vivado(cmds):
	with subprocess.Popen("vivado -mode tcl", stdin=subprocess.PIPE, shell=True) as process:
		process.stdin.write(cmds.encode("ASCII"))
		process.communicate()

class VivadoProgrammer(Programmer):
	needs_bitreverse = False

	def load_bitstream(self, bitstream_file):
		cmds = """open_hw
connect_hw_server
open_hw_target [lindex [get_hw_targets -of_objects [get_hw_servers localhost]] 0]

set_property PROBES.FILE {{}} [lindex [get_hw_devices] 0]
set_property PROGRAM.FILE {{{bitstream}}} [lindex [get_hw_devices] 0]

program_hw_devices [lindex [get_hw_devices] 0]
refresh_hw_device [lindex [get_hw_devices] 0]

quit
""".format(bitstream=bitstream_file)
		_run_vivado(cmds)

	def flash(self, address, data_file):
		raise NotImplementedError

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
		Subsignal("refclk_p", Pins("C8")),
		Subsignal("refclk_n", Pins("C7")),
		Subsignal("txp", Pins("D2")),
		Subsignal("txn", Pins("D1")),
		Subsignal("rxp", Pins("E4")),
		Subsignal("rxn", Pins("E3")),
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

def Platform(*args, toolchain="vivado", programmer="xc3sprog", **kwargs):
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
			if programmer == "xc3sprog":
				return XC3SProg("jtaghs1_fast", "bscan_spi_kc705.bit")
			elif programmer == "vivado":
				return VivadoProgrammer()
			else:
				raise ValueError

		def do_finalize(self, fragment):
			try:
				self.add_period_constraint(self.lookup_request("clk156").p, 6.4)
			except ConstraintError:
				pass
			try:
				self.add_period_constraint(self.lookup_request("clk200").p, 5.0)
			except ConstraintError:
				pass
			try:
				self.add_period_constraint(self.lookup_request("sata_host").refclk_p, 6.66)
			except ConstraintError:
				pass
			self.add_platform_command("""
create_clock -name sys_clk -period 6 [get_nets sys_clk]
create_clock -name sata_rx_clk -period 6.66 [get_nets sata_rx_clk]
create_clock -name sata_tx_clk -period 6.66 [get_nets sata_tx_clk]

set_false_path -from [get_clocks sys_clk] -to [get_clocks sata_rx_clk]
set_false_path -from [get_clocks sys_clk] -to [get_clocks sata_tx_clk]
set_false_path -from [get_clocks sata_rx_clk] -to [get_clocks sys_clk]
set_false_path -from [get_clocks sata_tx_clk] -to [get_clocks sys_clk]

set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 2.5 [current_design]
""")

	return RealPlatform(*args, **kwargs)
