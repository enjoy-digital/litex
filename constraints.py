def get(ns, clkfx_sys, reset0, norflash0, uart0):
	constraints = []
	def add(signal, pin, vec=-1, iostandard="LVCMOS33", extra=""):
		constraints.append((ns.get_name(signal), vec, pin, iostandard, extra))
	def add_vec(signal, pins, iostandard="LVCMOS33", extra=""):
		i = 0
		for p in pins:
			add(signal, p, i, iostandard, extra)
			i += 1
	
	add(clkfx_sys.clkin, "AB11", extra="TNM_NET = \"GRPclk50\"")
	
	add(reset0.trigger_reset, "AA4")
	add(reset0.ac97_rst_n, "D6")
	add(reset0.videoin_rst_n, "W17")
	add(reset0.flash_rst_n, "P22", extra="SLEW = FAST | DRIVE = 8")
	
	add_vec(norflash0.adr, ["L22", "L20", "K22", "K21", "J19", "H20", "F22",
		"F21", "K17", "J17", "E22", "E20", "H18", "H19", "F20",
		"G19", "C22", "C20", "D22", "D21", "F19", "F18", "D20", "D19"],
		extra="SLEW = FAST | DRIVE = 8")
	add_vec(norflash0.d, ["AA20", "U14", "U13", "AA6", "AB6", "W4", "Y4", "Y7",
		"AA2", "AB2", "V15", "AA18", "AB18", "Y13", "AA12", "AB12"],
		extra = "SLEW = FAST | DRIVE = 8 | PULLDOWN")
	add(norflash0.oe_n, "M22", extra="SLEW = FAST | DRIVE = 8")
	add(norflash0.we_n, "N20", extra="SLEW = FAST | DRIVE = 8")
	add(norflash0.ce_n, "M21", extra="SLEW = FAST | DRIVE = 8")
	
	add(uart0.tx, "L17", extra="SLEW = SLOW")
	add(uart0.rx, "K18", extra="PULLUP")
	
	r = ""
	for c in constraints:
		r += "NET \"" + c[0]
		if c[1] >= 0:
			r += "(" + str(c[1]) + ")"
		r += "\" LOC = " + c[2] 
		r += " | IOSTANDARD = " + c[3]
		if c[4]:
			r += " | " + c[4]
		r += ";\n"
	
	r += """
TIMESPEC "TSclk50" = PERIOD "GRPclk50" 20 ns HIGH 50%;
	"""
	
	return r
