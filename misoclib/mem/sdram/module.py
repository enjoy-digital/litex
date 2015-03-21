from math import ceil

from migen.fhdl.std import *
from misoclib.mem import sdram

class SDRAMModule:
	def __init__(self, clk_freq, geom_settings, timing_settings):
		self.clk_freq = clk_freq
		self.geom_settings = sdram.GeomSettings(
			bank_a=log2_int(geom_settings["nbanks"]),
			row_a=log2_int(geom_settings["nrows"]),
			col_a=log2_int(geom_settings["ncols"])
		)
		self.timing_settings = sdram.TimingSettings(
			tRP=self.ns(timing_settings["tRP"]),
			tRCD=self.ns(timing_settings["tRCD"]),
			tWR=self.ns(timing_settings["tWR"]),
			tWTR=timing_settings["tWTR"],
			tREFI=self.ns(timing_settings["tREFI"], False),
			tRFC=self.ns(timing_settings["tRFC"])
		)

	def ns(self, t, margin=True):
		clk_period_ns = 1000000000/self.clk_freq
		if margin:
			t += clk_period_ns/2
		return ceil(t/clk_period_ns)

# SDR
class IS42S16160(SDRAMModule):
	geom_settings = {
		"nbanks": 	4,
		"nrows":	8192,
		"ncols":	512
	}
	timing_settings = {
		"tRP":		20,
		"tRCD":		20,
		"tWR":		20,
		"tWTR":		2,
		"tREFI":	7800,
		"tRFC":		70
	}
	def __init__(self, clk_freq):
		SDRAMModule.__init__(self, clk_freq, self.geom_settings, self.timing_settings)

class MT48LC4M16(SDRAMModule):
	geom_settings = {
		"nbanks":	4,
		"nrows":	4096,
		"ncols":	256
	}
	timing_settings = {
		"tRP":		15,
		"tRCD":		15,
		"tWR":		14,
		"tWTR":		2,
		"tREFI":	64*1000*1000/4096,
		"tRFC":		66
	}
	def __init__(self, clk_freq):
		SDRAMModule.__init__(self, clk_freq, self.geom_settings, self.timing_settings)

# DDR

# LPDDR

# DDR2

# DDR3
