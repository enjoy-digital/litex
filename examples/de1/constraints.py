class Constraints:
	def __init__(self, in_clk, in_rst_n, spi2csr0, led0, sw0):
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
		add(in_clk,  "L1")	# CLOCK_50
		
		# sys_rst
		add(in_rst_n,  "R22")	# KEY[0]			
				
		# spi2csr0 
		add(spi2csr0.spi_clk,  "F13")		#GPIO_1[9]
		add(spi2csr0.spi_cs_n, "G15")		#GPIO_1[3]
		add(spi2csr0.spi_mosi, "E15")		#GPIO_1[5]
		add(spi2csr0.spi_miso, "G16")		#GPIO_1[7]
		
		# led0
		add_vec(led0, 	["U22", "U21", "V22", "V21",
					 "W22" , "W21" , "Y22" , "Y21"])
		# sw0
		add_vec(sw0, 	["L22", "L21", "M22", "V12",
					 "W12" , "U12" , "U11" , "M2"])
	
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
set_global_assignment -name FAMILY "Cyclone II"
set_global_assignment -name DEVICE EP2C20F484C7
set_global_assignment -name TOP_LEVEL_ENTITY "de1"
set_global_assignment -name CYCLONEII_RESERVE_NCEO_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_FLASH_NCE_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DATA0_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DATA1_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name RESERVE_DCLK_AFTER_CONFIGURATION "USE AS REGULAR IO"
set_global_assignment -name DUTY_CYCLE 50 -section_id in_clk
set_global_assignment -name FMAX_REQUIREMENT "50.0 MHz" -section_id in_clk
			"""
		return r
