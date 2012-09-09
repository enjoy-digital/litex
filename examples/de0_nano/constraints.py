class Constraints:
	def __init__(self, uart0, rc50, gpio0, led0, sw0, spi_master0, hpdmc0):
		self.constraints = []
		def add(signal, pin, vec=-1, iostandard="3.3-V LVTTL", extra="", sch=""):
			self.constraints.append((signal, vec, pin, iostandard, extra,sch))
		def add_vec(signal, pins, iostandard="3.3-V LVTTL", extra="", sch=""):
			assert(signal.bv.width == len(pins)), "%s size : %d / qsf size : %d" %(signal,signal.bv.width,len(pins))
			i = 0
			for p in pins:
				add(signal, p, i, iostandard, extra)
				i += 1
		
		# uart0
		#add(uart0.tx, "TBD")
		#add(uart0.rx, "TBD")
		
		# rc50
		#add(rc50.rx, "TBD")
		
		# gpio0
		#add_vec(gpio0.inputs,	["TBD","TBD","TBD","TBD",
		#			 "TBD","TBD","TBD","TBD"])
		#add_vec(gpio0.outputs,	["TBD","TBD","TBD","TBD",
		#			 "TBD","TBD","TBD","TBD"])
		
		# led0
		add_vec(led0.outputs, 	["A15", "A13", "B13", "A11",
					 "D1" , "F3" , "B1" , "L3"])
		
		# sw0
		add_vec(sw0.inputs,	["M1", "T8", "B9", "M15"])
		
		# spi_master0
		add(spi_master0.cs, "TBD")
		add(spi_master0.sck, "TBD")
		add(spi_master0.mosi, "TBD")
		add(spi_master0.miso, "TBD")
		
		# hpdmc0
		add(hpdmc0.sdram_clk, "R4")
		add(hpdmc0.sdram_cke, "L7")
		add(hpdmc0.sdram_cs_n, "P6")
		add(hpdmc0.sdram_we_n, "C2")
		add(hpdmc0.sdram_cas_n, "L1")
		add(hpdmc0.sdram_ras_n, "L2")
		add_vec(hpdmc0.sdram_addr,	["P2","N5","N6","M8",
						 "P8","T7","N8","T6",
						 "R1","P1","N2","N1",
						 "L4",])
		add_vec(hpdmc0.sdram_ba, ["M7","M6"])
		add_vec(hpdmc0.sdram_dqm, ["R6","T5"])
		add_vec(hpdmc0.sdram_dq,	["G2", "G1", "L8", "K5",
						 "K2", "J2", "J1", "R7",
						 "T4", "T2", "T3", "R3",
						 "R5", "P3", "N3", "K1"])

	def get_ios(self):
		return set([c[0] for c in self.constraints])
		
	def get_qsf(self, ns):
		r = ""
		for c in self.constraints:
			r += "set_location_assignment PIN_"+str(c[2])
			r += " -to " + ns.get_name(c[0])
			if c[1] >= 0:
				r += "[" + str(c[1]) + "]"
			r += "\n"

			r += "set_instance_assignment -name IO_STANDARD "
			r += "\"" + c[3] + "\""
			r += " -to " + ns.get_name(c[0])
			if c[1] >= 0:
				r += "[" + str(c[1]) + "]"
			r += "\n"
			
		r += """
set_global_assignment -name FAMILY "Cyclone IV E"
set_global_assignment -name DEVICE EP4CE22F17C6
set_global_assignment -name TOP_LEVEL_ENTITY "soc"
set_global_assignment -name DEVICE_FILTER_PACKAGE FPGA
set_global_assignment -name DEVICE_FILTER_PIN_COUNT 256
set_global_assignment -name DEVICE_FILTER_SPEED_GRADE 6
set_global_assignment -name CYCLONEII_RESERVE_NCEO_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_FLASH_NCE_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DATA0_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DATA1_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DCLK_AFTER_CONFIGURATION "USE AS REGULAR IO"
			"""
		return r
