from migen.fhdl.std import log2_int

def get_sdram_phy_header(sdram_phy):
	if sdram_phy.phy_settings.memtype not in ["SDR", "DDR", "LPDDR", "DDR2", "DDR3"]:
		raise NotImplementedError("The SDRAM PHY header generator only supports SDR, DDR, LPDDR, DDR2 and DDR3")

	r = "#ifndef __GENERATED_SDRAM_PHY_H\n#define __GENERATED_SDRAM_PHY_H\n"
	r += "#include <hw/common.h>\n#include <generated/csr.h>\n#include <hw/flags.h>\n\n"

	r += "static void cdelay(int i);\n"

	#
	# commands_px functions
	# 
	for n in range(sdram_phy.phy_settings.nphases):
		r += """
static void command_p{n}(int cmd)
{{
	dfii_pi{n}_command_write(cmd);
	dfii_pi{n}_command_issue_write(1);
}}""".format(n=str(n))
	r += "\n\n"

	#
	# rd/wr access macros
	#
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
	# init sequence
	# 
	cmds = {
		"PRECHARGE_ALL" : "DFII_COMMAND_RAS|DFII_COMMAND_WE|DFII_COMMAND_CS",
		"MODE_REGISTER" : "DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_WE|DFII_COMMAND_CS",
		"AUTO_REFRESH"  : "DFII_COMMAND_RAS|DFII_COMMAND_CAS|DFII_COMMAND_CS",
		"CKE"           : "DFII_CONTROL_CKE"
	}

	def gen_cmd(comment, a, ba, cmd, delay):	
		r = "\t/* {0} */\n".format(comment)
		r += "\tdfii_pi0_address_write({0:#x});\n".format(a)
		r += "\tdfii_pi0_baddress_write({0:d});\n".format(ba)
		if "CKE" in cmd:
			r += "\tdfii_control_write({0});\n".format(cmd)
		else:
			r += "\tcommand_p0({0});\n".format(cmd)
		r += "\tcdelay({0:d});\n".format(delay)
		r += "\n"
		return r


	r += "static void init_sequence(void)\n{\n"

	cl = sdram_phy.phy_settings.cl
	
	if sdram_phy.phy_settings.memtype == "SDR":
		bl = 1*sdram_phy.phy_settings.nphases
		mr  = log2_int(bl) + (cl << 4)
		reset_dll = 1 << 8

		init_sequence = [
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 2000),
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
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 2000),
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
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 2000),
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
		mr  = log2_int(bl) + (cl << 4) + (wr << 9)
		emr = 0
		emr2 = 0
		emr3 = 0
		reset_dll = 1 << 8
		ocd = 7 << 7

		init_sequence = [
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 2000),
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
		if bl is not 8:
			raise NotImplementedError("DDR3 PHY header generator only supports BL of 8")
		wr = cl
		mr  = 0 + ((cl-4) << 4) + ((wr-4) << 9)
		emr1 = 6 # Output Drive Strength RZQ/7(34 Ohms) / Rtt_nom RZQ/4
		emr2 = 0 
		emr3 = 0
		reset_dll = 1 << 8

		init_sequence = [
			("Bring CKE high", 0x0000, 0, cmds["CKE"], 2000),
			("Precharge All",  0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Load Extended Mode Register 3", emr3, 3, cmds["MODE_REGISTER"], 0),
			("Load Extended Mode Register 2", emr2, 2, cmds["MODE_REGISTER"], 0),
			("Load Extended Mode Register 1", emr1, 1, cmds["MODE_REGISTER"], 0),
			("Load Mode Register / Reset DLL, CL={0:d}, BL={1:d}".format(cl, bl), mr + reset_dll, 0, cmds["MODE_REGISTER"], 200),
			("Precharge All", 0x0400, 0, cmds["PRECHARGE_ALL"], 0),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Auto Refresh", 0x0, 0, cmds["AUTO_REFRESH"], 4),
			("Load Mode Register / CL={0:d}, BL={1:d}".format(cl, bl), mr, 0, cmds["MODE_REGISTER"], 200),
			("ZQ Calibration", 0x0400, 0, "DFII_COMMAND_WE|DFII_COMMAND_CS", 200),
		]

	for comment, a, ba, cmd, delay in init_sequence:
		r += gen_cmd(comment, a, ba, cmd, delay)

	r += "}\n"
	r += "#endif\n"

	return r
