import os
import top

# list Verilog sources before changing directory
verilog_sources = []
def add_core_dir(d):
	for root, subFolders, files in os.walk(os.path.join("verilog", d)):
		for f in files:
			verilog_sources.append(os.path.join(root, f))
def add_core_files(d, files):
	for f in files:
		verilog_sources.append(os.path.join("verilog", d, f))
add_core_dir("m1reset")
add_core_files("lm32", ["lm32_cpu.v", "lm32_instruction_unit.v", "lm32_decoder.v",
	"lm32_load_store_unit.v", "lm32_adder.v", "lm32_addsub.v", "lm32_logic_op.v",
	"lm32_shifter.v", "lm32_multiplier_spartan6.v", "lm32_mc_arithmetic.v",
	"lm32_interrupt.v", "lm32_ram.v", "lm32_dp_ram.v", "lm32_icache.v",
	"lm32_dcache.v", "lm32_top.v", "lm32_debug.v", "lm32_jtag.v", "jtag_cores.v",
	"jtag_tap_spartan6.v"])

os.system("rm -rf build/*")
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
#raise SystemExit
# xst
xst_prj = ""
for s in verilog_sources:
	xst_prj += "verilog work ../" + s + "\n"
str2file("soc.prj", xst_prj)
str2file("soc.xst", """run
-ifn soc.prj
-top soc
-ifmt MIXED
-opt_mode SPEED
-opt_level 2
-resource_sharing no
-reduce_control_sets auto
-ofn soc.ngc
-p xc6slx45-fgg484-2""")
os.system("xst -ifn soc.xst")

# ngdbuild
os.system("ngdbuild -uc soc.ucf soc.ngc")

# map
os.system("map -ol high -w soc.ngd")

# par
os.system("par -ol high -w soc.ncd soc-routed.ncd")

# bitgen
os.system("bitgen -g LCK_cycle:6 -g Binary:Yes -g INIT_9K:Yes -w soc-routed.ncd soc.bit")
