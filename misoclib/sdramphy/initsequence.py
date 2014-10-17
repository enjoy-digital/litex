from migen.fhdl.std import log2_int

def get_sdram_phy_header(sdram_phy):
	r = "#ifndef __GENERATED_SDRAM_PHY_H\n#define __GENERATED_SDRAM_PHY_H\n"
	r += "#include <hw/common.h>\n#include <generated/csr.h>\n#include <hw/flags.h>\n\n"

	nphases = sdram_phy.phy_settings.nphases
	r += "#define DFII_NPHASES "+str(nphases)+"\n\n"

	r += "static void cdelay(int i);\n"

	# commands_px functions
	for n in range(nphases):
		r += """
static void command_p{n}(int cmd)
{{
	dfii_pi{n}_command_write(cmd);
	dfii_pi{n}_command_issue_write(1);
}}""".format(n=str(n))
	r += "\n\n"

	# rd/wr access macros
	r += """
#define dfii_pird_address_write(X) dfii_pi{rdphase}_address_write(X)
#define dfii_piwr_address_write(X) dfii_pi{wrphase}_address_write(X)

#define dfii_pird_baddress_write(X) dfii_pi{rdphase}_baddress_write(X)
#define dfii_piwr_baddress_write(X) dfii_pi{wrphase}_baddress_write(X)

#define command_prd(X) command_p{rdphase}(X)
#define command_pwr(X) command_p{wrphase}(X)
""".format(rdphase=str(sdram_phy.phy_settings.rdphase), wrphase=str(sdram_phy.phy_settings.wrphase))
	r +="\n"

	#
	# sdrrd/sdrwr functions utilities
	#
	r += "#define DFII_PIX_DATA_SIZE CSR_DFII_PI0_WRDATA_SIZE\n"
	dfii_pix_wrdata_addr = []
	for n in range(nphases):
		dfii_pix_wrdata_addr.append("CSR_DFII_PI{n}_WRDATA_ADDR".format(n=n))
	r += """
const unsigned int dfii_pix_wrdata_addr[{n}] = {{
	{dfii_pix_wrdata_addr}
}};
""".format(n=nphases, dfii_pix_wrdata_addr=",\n\t".join(dfii_pix_wrdata_addr))

	dfii_pix_rddata_addr = []
	for n in range(nphases):
		dfii_pix_rddata_addr.append("CSR_DFII_PI{n}_RDDATA_ADDR".format(n=n))
	r += """
const unsigned int dfii_pix_rddata_addr[{n}] = {{
	{dfii_pix_rddata_addr}
}};
""".format(n=nphases, dfii_pix_rddata_addr=",\n\t".join(dfii_pix_rddata_addr))
	r +="\n"

	# init sequence
	cmds = {
		"PRECHARGE_ALL" : "DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS",
		"MODE_REGISTER" : "DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS",
		"AUTO_REFRESH"  : "DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_CS",
		"UNRESET"       : "DFII_CONTROL_ODT|DFII_CONTROL_RESET_N",
		"CKE"           : "DFII_CONTROL_CKE|DFII_CONTROL_ODT|DFII_CONTROL_RESET_N"
	}

	cl = sdram_phy.phy_settings.cl

	if sdram_phy.phy_settings.memtype == "SDR":
		bl = sdram_phy.phy_settings.nphases
		mr = log2_int(bl) + (cl << 4)
		reset_dll = 1 << 8

		init_sequence = [
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 20000),
			("Precharge All",  0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Load Mode Register / Reset DLL, CL={0:d}, BL={1:d}".format(cl, bl), mr + reset_dll, 0, cmds["MODE_REGISTER"], 200),
			("Precharge All", 0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Load Mode Register / CL={0:d}, BL={1:d}".format(cl, bl), mr, 0, cmds["MODE_REGISTER"], 200)
		]

	elif sdram_phy.phy_settings.memtype == "DDR":
		bl = 2*sdram_phy.phy_settings.nphases
		mr  = log2_int(bl) + (cl << 4)
		emr = 0
		reset_dll = 1 << 8

		init_sequence = [
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 20000),
			("Precharge All",  0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Load Extended Mode Register", emr, 1, cmds["MODE_REGISTER"], 0),
			("Load Mode Register / Reset DLL, CL={0:d}, BL={1:d}".format(cl, bl), mr + reset_dll, 0, cmds["MODE_REGISTER"], 200),
			("Precharge All", 0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Load Mode Register / CL={0:d}, BL={1:d}".format(cl, bl), mr, 0, cmds["MODE_REGISTER"], 200)
		]

	elif sdram_phy.phy_settings.memtype == "LPDDR":
		bl = 2*sdram_phy.phy_settings.nphases
		mr  = log2_int(bl) + (cl << 4)
		emr = 0
		reset_dll = 1 << 8

		init_sequence = [
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 20000),
			("Precharge All",  0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Load Extended Mode Register", emr, 2, cmds["MODE_REGISTER"], 0),
			("Load Mode Register / Reset DLL, CL={0:d}, BL={1:d}".format(cl, bl), mr + reset_dll, 0, cmds["MODE_REGISTER"], 200),
			("Precharge All", 0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Load Mode Register / CL={0:d}, BL={1:d}".format(cl, bl), mr, 0, cmds["MODE_REGISTER"], 200)
		]

	elif sdram_phy.phy_settings.memtype == "DDR2":
		bl = 2*sdram_phy.phy_settings.nphases
		wr = 2
		mr = log2_int(bl) + (cl << 4) + (wr << 9)
		emr = 0
		emr2 = 0
		emr3 = 0
		reset_dll = 1 << 8
		ocd = 7 << 7

		init_sequence = [
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 20000),
			("Precharge All",  0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Load Extended Mode Register 3", emr3, 3, cmds["MODE_REGISTER"], 0),
			("Load Extended Mode Register 2", emr2, 2, cmds["MODE_REGISTER"], 0),
			("Load Extended Mode Register", emr, 1, cmds["MODE_REGISTER"], 0),
			("Load Mode Register / Reset DLL, CL={0:d}, BL={1:d}".format(cl, bl), mr + reset_dll, 0, cmds["MODE_REGISTER"], 200),
			("Precharge All", 0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Load Mode Register / CL={0:d}, BL={1:d}".format(cl, bl), mr, 0, cmds["MODE_REGISTER"], 200),
			("Load Extended Mode Register / OCD Default", emr+ocd, 1, cmds["MODE_REGISTER"], 0),
			("Load Extended Mode Register / OCD Exit", emr, 1, cmds["MODE_REGISTER"], 0),
		]
	elif sdram_phy.phy_settings.memtype == "DDR3":
		bl = 2*sdram_phy.phy_settings.nphases
		if bl != 8:
			raise NotImplementedError("DDR3 PHY header generator only supports BL of 8")

		def format_mr0(cl, wr, dll_reset):
			cl_to_mr0 = {
				5 : 0b0010,
				6 : 0b0100,
				7 : 0b0110,
				8 : 0b1000,
				9 : 0b1010,
				10: 0b1100,
				11: 0b1110,
				12: 0b0001,
				13: 0b0011,
				14: 0b0101
			}
			wr_to_mr0 = {
				16: 0b000,
				5 : 0b001,
				6 : 0b010,
				7 : 0b011,
				8 : 0b100,
				10: 0b101,
				12: 0b110,
				14: 0b111
			}
			mr0 = (cl_to_mr0[cl] & 1) << 2
			mr0 |= ((cl_to_mr0[cl] >> 1) & 0b111) << 4
			mr0 |= dll_reset << 8
			mr0 |= wr_to_mr0[wr] << 9
			return mr0

		def format_mr1(output_drive_strength, rtt_nom):
			mr1 = ((output_drive_strength >> 0) & 1) << 1
			mr1 |= ((output_drive_strength >> 1) & 1) << 5
			mr1 |= ((rtt_nom >> 0) & 1) << 2
			mr1 |= ((rtt_nom >> 1) & 1) << 6
			mr1 |= ((rtt_nom >> 2) & 1) << 9
			return mr1

		def format_mr2(cwl, rtt_wr):
			mr2 = (cwl-5) << 3
			mr2 |= rtt_wr << 9
			return mr2

		mr0 = format_mr0(cl, 8, 1) # wr=8 FIXME: this should be ceiling(tWR/tCK)
		mr1 = format_mr1(1, 1) # Output Drive Strength RZQ/7 (34 ohm) / Rtt RZQ/4 (60 ohm)
		mr2 = format_mr2(sdram_phy.phy_settings.cwl, 2) # Rtt(WR) RZQ/4
		mr3 = 0

		init_sequence = [
			("Release reset", 0x0000, 0, cmds["UNRESET"], 50000),
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 10000),
			("Load Mode Register 2", mr2, 2, cmds["MODE_REGISTER"], 0),
			("Load Mode Register 3", mr3, 3, cmds["MODE_REGISTER"], 0),
			("Load Mode Register 1", mr1, 1, cmds["MODE_REGISTER"], 0),
			("Load Mode Register 0, CL={0:d}, BL={1:d}".format(cl, bl), mr0, 0, cmds["MODE_REGISTER"], 200),
			("ZQ Calibration", 0x0400, 0, "DFII_COMMAND_WE|DFII_COMMAND_CS", 200),
		]

		# the value of MR1 needs to be modified during write leveling
		r += "#define DDR3_MR1 {}\n\n".format(mr1)
	else:
		raise NotImplementedError("Unsupported memory type: "+sdram_phy.phy_settings.memtype)

	r += "static void init_sequence(void)\n{\n"
	for comment, a, ba, cmd, delay in init_sequence:
		r += "\t/* {0} */\n".format(comment)
		r += "\tdfii_pi0_address_write({0:#x});\n".format(a)
		r += "\tdfii_pi0_baddress_write({0:d});\n".format(ba)
		if cmd[:12] == "DFII_CONTROL":
			r += "\tdfii_control_write({0});\n".format(cmd)
		else:
			r += "\tcommand_p0({0});\n".format(cmd)
		if delay:
			r += "\tcdelay({0:d});\n".format(delay)
		r += "\n"
	r += "}\n"

	r += "#endif\n"

	return r
