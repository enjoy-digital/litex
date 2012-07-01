class Constraints:
	def __init__(self, crg0, norflash0, uart0, ddrphy0, minimac0, fb0):
		self.constraints = []
		def add(signal, pin, vec=-1, iostandard="LVCMOS33", extra=""):
			self.constraints.append((signal, vec, pin, iostandard, extra))
		def add_vec(signal, pins, iostandard="LVCMOS33", extra=""):
			assert(signal.bv.width == len(pins))
			i = 0
			for p in pins:
				add(signal, p, i, iostandard, extra)
				i += 1
		
		add(crg0.clkin, "AB11", extra="TNM_NET = \"GRPclk50\"")
		add(crg0.ac97_rst_n, "D6")
		add(crg0.videoin_rst_n, "W17")
		add(crg0.flash_rst_n, "P22", extra="SLEW = FAST | DRIVE = 8")
		add(crg0.trigger_reset, "AA4")
		add(crg0.phy_clk, "M20")
		add(crg0.vga_clk_pad, "A11")
		
		add_vec(norflash0.adr, ["L22", "L20", "K22", "K21", "J19", "H20", "F22",
			"F21", "K17", "J17", "E22", "E20", "H18", "H19", "F20",
			"G19", "C22", "C20", "D22", "D21", "F19", "F18", "D20", "D19"],
			extra="SLEW = FAST | DRIVE = 8")
		add_vec(norflash0.d, ["AA20", "U14", "U13", "AA6", "AB6", "W4", "Y4", "Y7",
			"AA2", "AB2", "V15", "AA18", "AB18", "Y13", "AA12", "AB12"],
			extra="SLEW = FAST | DRIVE = 8 | PULLDOWN")
		add(norflash0.oe_n, "M22", extra="SLEW = FAST | DRIVE = 8")
		add(norflash0.we_n, "N20", extra="SLEW = FAST | DRIVE = 8")
		add(norflash0.ce_n, "M21", extra="SLEW = FAST | DRIVE = 8")
		
		add(uart0.tx, "L17", extra="SLEW = SLOW")
		add(uart0.rx, "K18", extra="PULLUP")
		
		ddrsettings = "IOSTANDARD = SSTL2_I"
		add(ddrphy0.sd_clk_out_p, "M3", extra=ddrsettings)
		add(ddrphy0.sd_clk_out_n, "L4", extra=ddrsettings)
		add_vec(ddrphy0.sd_a, ["B1", "B2", "H8", "J7", "E4", "D5", "K7", "F5",
			"G6", "C1", "C3", "D1", "D2"], extra=ddrsettings)
		add_vec(ddrphy0.sd_ba, ["A2", "E6"], extra=ddrsettings)
		add(ddrphy0.sd_cs_n, "F7", extra=ddrsettings)
		add(ddrphy0.sd_cke, "G7", extra=ddrsettings)
		add(ddrphy0.sd_ras_n, "E5", extra=ddrsettings)
		add(ddrphy0.sd_cas_n, "C4", extra=ddrsettings)
		add(ddrphy0.sd_we_n, "D3", extra=ddrsettings)
		add_vec(ddrphy0.sd_dq, ["Y2", "W3", "W1", "P8", "P7", "P6", "P5", "T4", "T3",
			"U4", "V3", "N6", "N7", "M7", "M8", "R4", "P4", "M6", "L6", "P3", "N4",
			"M5", "V2", "V1", "U3", "U1", "T2", "T1", "R3", "R1", "P2", "P1"],
			extra=ddrsettings)
		add_vec(ddrphy0.sd_dm, ["E1", "E3", "F3", "G4"], extra=ddrsettings)
		add_vec(ddrphy0.sd_dqs, ["F1", "F2", "H5", "H6"], extra=ddrsettings)
		
		add(minimac0.phy_rst_n, "R22")
		add(minimac0.phy_dv, "V21")
		add(minimac0.phy_rx_clk, "H22")
		add(minimac0.phy_rx_er, "V22")
		add_vec(minimac0.phy_rx_data, ["U22", "U20", "T22", "T21"])
		add(minimac0.phy_tx_en, "N19")
		add(minimac0.phy_tx_clk, "H21")
		add(minimac0.phy_tx_er, "M19")
		add_vec(minimac0.phy_tx_data, ["M16", "L15", "P19", "P20"])
		add(minimac0.phy_col, "W20")
		add(minimac0.phy_crs, "W22")
		
		add_vec(fb0.vga_r, ["C6", "B6", "A6", "C7", "A7", "B8", "A8", "D9"])
		add_vec(fb0.vga_g, ["C8", "C9", "A9", "D7", "D8", "D10", "C10", "B10"])
		add_vec(fb0.vga_b, ["D11", "C12", "B12", "A12", "C13", "A13", "D14", "C14"])
		add(fb0.vga_hsync_n, "A14")
		add(fb0.vga_vsync_n, "C15")
		add(fb0.vga_psave_n, "B14")
		
		self._phy_rx_clk = minimac0.phy_rx_clk
		self._phy_tx_clk = minimac0.phy_tx_clk

	def get_ios(self):
		return set([c[0] for c in self.constraints])
		
	def get_ucf(self, ns):
		r = ""
		for c in self.constraints:
			r += "NET \"" + ns.get_name(c[0])
			if c[1] >= 0:
				r += "(" + str(c[1]) + ")"
			r += "\" LOC = " + c[2] 
			r += " | IOSTANDARD = " + c[3]
			if c[4]:
				r += " | " + c[4]
			r += ";\n"
		
		r += """
TIMESPEC "TSclk50" = PERIOD "GRPclk50" 20 ns HIGH 50%;
INST "m1crg/wr_bufpll" LOC = "BUFPLL_X0Y2";
INST "m1crg/rd_bufpll" LOC = "BUFPLL_X0Y3";

PIN "m1crg/bufg_x1.O" CLOCK_DEDICATED_ROUTE = FALSE;

NET "{phy_rx_clk}" TNM_NET = "GRPphy_rx_clk";
NET "{phy_tx_clk}" TNM_NET = "GRPphy_tx_clk";
TIMESPEC "TSphy_rx_clk" = PERIOD "GRPphy_rx_clk" 40 ns HIGH 50%;
TIMESPEC "TSphy_tx_clk" = PERIOD "GRPphy_tx_clk" 40 ns HIGH 50%;
TIMESPEC "TSphy_tx_clk_io" = FROM "GRPphy_tx_clk" TO "PADS" 10 ns;
TIMESPEC "TSphy_rx_clk_io" = FROM "PADS" TO "GRPphy_rx_clk" 10 ns;

NET "asfifo*/counter_read/gray_count*" TIG;
NET "asfifo*/counter_write/gray_count*" TIG;
NET "asfifo*/preset_empty*" TIG;

""".format(phy_rx_clk=ns.get_name(self._phy_rx_clk), phy_tx_clk=ns.get_name(self._phy_tx_clk))
	
		return r
