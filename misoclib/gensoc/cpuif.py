from migen.fhdl.std import *
from migen.bank.description import CSRStatus

def get_cpu_mak(cpu_type):
	if cpu_type == "lm32":
		cpuflags = "-mbarrel-shift-enabled -mmultiply-enabled -mdivide-enabled -msign-extend-enabled"
	elif cpu_type == "or1k":
		cpuflags = "-mhard-mul -mhard-div"
	else:
		raise ValueError("Unsupported CPU type: "+cpu_type)
	return "CPU={}\nCPUFLAGS={}\n".format(cpu_type, cpuflags)

def get_linker_output_format(cpu_type):
	return "OUTPUT_FORMAT(\"elf32-{}\")\n".format(cpu_type)

def get_linker_regions(regions):
	r = "MEMORY {\n"
	for name, origin, length in regions:
		r += "\t{} : ORIGIN = 0x{:08x}, LENGTH = 0x{:08x}\n".format(name, origin, length)
	r += "}\n"
	return r

def get_mem_header(regions, flash_boot_address):
	r = "#ifndef __GENERATED_MEM_H\n#define __GENERATED_MEM_H\n\n"
	for name, base, size in regions:
		r += "#define {name}_BASE 0x{base:08x}\n#define {name}_SIZE 0x{size:08x}\n\n".format(name=name.upper(), base=base, size=size)
	if flash_boot_address is not None:
		r += "#define FLASH_BOOT_ADDRESS 0x{:08x}\n\n".format(flash_boot_address)
	r += "#endif\n"
	return r

def _get_rw_functions(reg_name, reg_base, nwords, busword, read_only):
	r = ""

	r += "#define CSR_"+reg_name.upper()+"_ADDR "+hex(reg_base)+"\n"
	r += "#define CSR_"+reg_name.upper()+"_SIZE "+str(nwords)+"\n"

	size = nwords*busword
	if size > 64:
		return r
	elif size > 32:
		ctype = "unsigned long long int"
	elif size > 16:
		ctype = "unsigned int"
	elif size > 8:
		ctype = "unsigned short int"
	else:
		ctype = "unsigned char"

	r += "static inline "+ctype+" "+reg_name+"_read(void) {\n"
	if size > 1:
		r += "\t"+ctype+" r = MMPTR("+hex(reg_base)+");\n"
		for byte in range(1, nwords):
			r += "\tr <<= "+str(busword)+";\n\tr |= MMPTR("+hex(reg_base+4*byte)+");\n"
		r += "\treturn r;\n}\n"
	else:
		r += "\treturn MMPTR("+hex(reg_base)+");\n}\n"

	if not read_only:
		r += "static inline void "+reg_name+"_write("+ctype+" value) {\n"
		for word in range(nwords):
			shift = (nwords-word-1)*busword
			if shift:
				value_shifted = "value >> "+str(shift)
			else:
				value_shifted = "value"
			r += "\tMMPTR("+hex(reg_base+4*word)+") = "+value_shifted+";\n"
		r += "}\n"
	return r

def get_csr_header(csr_base, bank_array, interrupt_map):
	r = "#ifndef __GENERATED_CSR_H\n#define __GENERATED_CSR_H\n#include <hw/common.h>\n"
	for name, csrs, mapaddr, rmap in bank_array.banks:
		r += "\n/* "+name+" */\n"
		reg_base = csr_base + 0x800*mapaddr
		r += "#define "+name.upper()+"_BASE "+hex(reg_base)+"\n"
		busword = flen(rmap.bus.dat_w)
		for csr in csrs:
			nr = (csr.size + busword - 1)//busword
			r += _get_rw_functions(name + "_" + csr.name, reg_base, nr, busword, isinstance(csr, CSRStatus))
			reg_base += 4*nr
		try:
			interrupt_nr = interrupt_map[name]
		except KeyError:
			pass
		else:
			r += "#define "+name.upper()+"_INTERRUPT "+str(interrupt_nr)+"\n"
	for name, memory, mapaddr, mmap in bank_array.srams:
		mem_base = csr_base + 0x800*mapaddr
		fullname = name + "_" + memory.name_override
		r += "#define "+fullname.upper()+"_BASE "+hex(mem_base)+"\n"
	r += "\n#endif\n"
	return r

def get_csr_csv(csr_base, bank_array):
	r = ""
	for name, csrs, mapaddr, rmap in bank_array.banks:
		reg_base = csr_base + 0x800*mapaddr
		busword = flen(rmap.bus.dat_w)
		for csr in csrs:
			nr = (csr.size + busword - 1)//busword
			r += "{}_{},0x{:08x},{},{}\n".format(name, csr.name, reg_base, nr, "ro" if isinstance(csr, CSRStatus) else "rw")
			reg_base += 4*nr
	return r
