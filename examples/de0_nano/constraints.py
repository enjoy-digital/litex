class Constraints:
	def __init__(self):
		self.constraints = []
		def add(signal, pin, vec=-1, iostandard="3.3-V LVTTL", extra="", sch=""):
			self.constraints.append((signal, vec, pin, iostandard, extra,sch))
		def add_vec(signal, pins, iostandard="3.3-V LVTTL", extra="", sch=""):
			assert(signal.bv.width == len(pins)), "%s size : %d / qsf size : %d" %(signal,signal.bv.width,len(pins))
			i = 0
			for p in pins:
				add(signal, p, i, iostandard, extra)
				i += 1
	
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
