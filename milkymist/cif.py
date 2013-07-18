from operator import itemgetter
import re

from migen.fhdl.std import *
from migen.bank.description import CSRStatus

def get_macros(filename):
	f = open(filename, "r")
	r = {}
	for line in f:
		match = re.match("\w*#define\s+(\w+)\s+(.*)", line, re.IGNORECASE)
		if match:
			r[match.group(1)] = match.group(2)
	return r

def _get_rw_functions(reg_name, reg_base, size, read_only):
	r = ""
	if size > 8:
		raise NotImplementedError("Register too large")
	elif size > 4:
		ctype = "unsigned long long int"
	elif size > 2:
		ctype = "unsigned int"
	elif size > 1:
		ctype = "unsigned short int"
	else:
		ctype = "unsigned char"

	r += "static inline "+ctype+" "+reg_name+"_read(void) {\n"
	if size > 1:
		r += "\t"+ctype+" r = MMPTR("+hex(reg_base)+");\n"
		for byte in range(1, size):
			r += "\tr <<= 8;\n\tr |= MMPTR("+hex(reg_base+4*byte)+");\n"
		r += "\treturn r;\n}\n"
	else:
		r += "\treturn MMPTR("+hex(reg_base)+");\n}\n"

	if not read_only:
		r += "static inline void "+reg_name+"_write("+ctype+" value) {\n"
		for byte in range(size):
			shift = (size-byte-1)*8
			if shift:
				value_shifted = "value >> "+str(shift)
			else:
				value_shifted = "value"
			r += "\tMMPTR("+hex(reg_base+4*byte)+") = "+value_shifted+";\n"
		r += "}\n"
	return r

def get_csr_header(csr_base, bank_array, interrupt_map):
	r = "#ifndef __HW_CSR_H\n#define __HW_CSR_H\n#include <hw/common.h>\n"
	for name, csrs, mapaddr, rmap in bank_array.banks:
		r += "\n/* "+name+" */\n"
		reg_base = csr_base + 0x800*mapaddr
		r += "#define "+name.upper()+"_BASE "+hex(reg_base)+"\n"
		for csr in csrs:
			nr = (csr.size + 7)//8
			r += _get_rw_functions(name + "_" + csr.name, reg_base, nr, isinstance(csr, CSRStatus))
			reg_base += 4*nr
		try:
			interrupt_nr = interrupt_map[name]
		except KeyError:
			pass
		else:
			r += "#define "+name.upper()+"_INTERRUPT "+str(interrupt_nr)+"\n"
	r += "\n#endif\n"
	return r

def get_sdram_phy_header(sdram_phy):
	if sdram_phy.phy_settings.memtype not in ["SDR", "DDR", "LPDDR", "DDR2"]:
		raise NotImplementedError("The SDRAM PHY header generator only supports SDR, DDR, LPDDR and DDR2")

	r = "#ifndef __HW_SDRAM_PHY_H\n#define __HW_SDRAM_PHY_H\n"
	r += "#include <hw/common.h>\n#include <hw/csr.h>\n#include <hw/flags.h>\n\n"

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

	for comment, a, ba, cmd, delay in init_sequence:
		r += gen_cmd(comment, a, ba, cmd, delay)

	r += "}\n"
	r += "#endif\n"

	return r
