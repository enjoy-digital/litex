class Constraints:
	def __init__(self, in_rst_n, cd_in, spi2csr0, led0):
		self.constraints = []
		def add(signal, pin, vec=-1, iostandard="3.3-V LVTTL", extra="", sch=""):
			self.constraints.append((signal, vec, pin, iostandard, extra,sch))
		def add_vec(signal, pins, iostandard="3.3-V LVTTL", extra="", sch=""):
			assert(signal.bv.width == len(pins)), "%s size : %d / qsf size : %d" %(signal,signal.bv.width,len(pins))
			i = 0
			for p in pins:
				add(signal, p, i, iostandard, extra)
				i += 1
		# sys_clk
		add(cd_in.clk,  "R8")	# CLOCK_50
		
		# sys_rst
		add(in_rst_n,  "J15")	# KEY[0]			
				
		# spi2csr0 
		add(spi2csr0.spi_clk,  "A14")		#GPIO_2[0]
		add(spi2csr0.spi_cs_n, "B16")		#GPIO_2[1]
		add(spi2csr0.spi_mosi, "C14")		#GPIO_2[2]
		add(spi2csr0.spi_miso, "C16")		#GPIO_2[3]
		
		# led0
		add_vec(led0, 	["A15", "A13", "B13", "A11",
					 "D1" , "F3" , "B1" , "L3"])

		
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
set_global_assignment -name TOP_LEVEL_ENTITY "de0_nano"
set_global_assignment -name CYCLONEII_RESERVE_NCEO_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_FLASH_NCE_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DATA0_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DATA1_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DCLK_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name DUTY_CYCLE 50 -section_id in_clk
set_global_assignment -name FMAX_REQUIREMENT "50.0 MHz" -section_id in_clk
			"""
		return r
