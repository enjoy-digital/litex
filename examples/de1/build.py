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

os.chdir("build")

def str2file(filename, contents):
	f = open(filename, "w")
	f.write(contents)
	f.close()

# generate top
(src_verilog, qsf_cst) = top.get()
str2file("de1.v", src_verilog)
verilog_sources.append("build/de1.v")

# generate Quartus project file
qsf_prj = get_qsf_prj()
str2file("de1.qsf", qsf_prj + qsf_cst)