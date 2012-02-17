import os
import top

# list Verilog sources before changing directory
verilog_sources = []
def add_core_dir(d):
	root = os.path.join("verilog", d)
	files = os.listdir(root)
	for f in files:
		if f[-2:] == ".v":
			verilog_sources.append(os.path.join(root, f))
def add_core_files(d, files):
	for f in files:
		verilog_sources.append(os.path.join("verilog", d, f))
add_core_dir("m1crg")
add_core_dir("s6ddrphy")
add_core_files("lm32", ["lm32_cpu.v", "lm32_instruction_unit.v", "lm32_decoder.v",
	"lm32_load_store_unit.v", "lm32_adder.v", "lm32_addsub.v", "lm32_logic_op.v",
	"lm32_shifter.v", "lm32_multiplier_spartan6.v", "lm32_mc_arithmetic.v",
	"lm32_interrupt.v", "lm32_ram.v", "lm32_dp_ram.v", "lm32_icache.v",
	"lm32_dcache.v", "lm32_top.v", "lm32_debug.v", "lm32_jtag.v", "jtag_cores.v",
	"jtag_tap_spartan6.v"])

os.chdir("build")

def str2file(filename, contents):
	f = open(filename, "w")
	f.write(contents)
	f.close()

# generate source
(src_verilog, src_ucf) = top.get()
str2file("soc.v", src_verilog)
str2file("soc.ucf", src_ucf)
verilog_sources.append("build/soc.v")

# generate XST project file
xst_prj = ""
for s in verilog_sources:
	xst_prj += "verilog work ../" + s + "\n"
str2file("soc.prj", xst_prj)
