import os
import top

# list Verilog sources before changing directory
verilog_sources = []
def add_core_dir(d):
	root = os.path.join("verilog", d, "rtl")
	files = os.listdir(root)
	for f in files:
		if f[-2:] == ".v":
			verilog_sources.append(os.path.join(root, f))
def add_core_files(d, files):
	for f in files:
		verilog_sources.append(os.path.join("verilog", d, f))

def get_qsf_prj():
	r = ""
	for s in verilog_sources:
		r += "set_global_assignment -name VERILOG_FILE " + s + "\n"
	return r

add_core_dir("generic")
add_core_dir("lm32")
add_core_dir("hpdmc_sdr16")
add_core_dir("fmlbrg")
add_core_dir("uart")
add_core_dir("rc5")
add_core_dir("gpio")
add_core_dir("spi_master")

os.chdir("build")

def str2file(filename, contents):
	f = open(filename, "w")
	f.write(contents)
	f.close()

# generate top
(src_verilog, qsf_cst) = top.get()
str2file("soc.v", src_verilog)
verilog_sources.append("build/soc.v")

# generate Quartus project file
qsf_prj = get_qsf_prj()
str2file("soc.qsf", qsf_prj + qsf_cst)