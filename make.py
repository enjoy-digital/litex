#!/usr/bin/env python3

import argparse, importlib, subprocess, struct

from mibuild.tools import write_to_file

from misoclib.gensoc import cpuif
from misoclib.s6ddrphy import initsequence
import jtag

def _get_args():
	parser = argparse.ArgumentParser(description="MiSoC - a high performance SoC based on Migen.")

	parser.add_argument("-p", "--platform", default="mixxeo", help="platform to build for")
	parser.add_argument("-t", "--target", default="mlabs_video", help="SoC type to build")
	parser.add_argument("-s", "--sub-target", default="", help="variant of the SoC type to build")
	parser.add_argument("-o", "--option", default=[], nargs=2, action="append", help="set target-specific option")
	parser.add_argument("-Xp", "--external-platform", default="", help="use external platform file in the specified path")
	parser.add_argument("-Xt", "--external-target", default="", help="use external target file in the specified path")
	
	parser.add_argument("-B", "--no-bitstream", default=False, action="store_true", help="do not build bitstream file")
	parser.add_argument("-H", "--no-header", default=False, action="store_true", help="do not build C header files with CSR/IRQ/SDRAM_PHY definitions")
	parser.add_argument("-c", "--csr-csv", default="", help="save CSR map into CSV file")

	parser.add_argument("-l", "--load", default=False, action="store_true", help="load bitstream to FPGA volatile memory")
	parser.add_argument("-f", "--flash", default=False, action="store_true", help="load bitstream to flash")

	return parser.parse_args()

def _misoc_import(default, external, name):
	if external:
		loader = importlib.find_loader(name, [external])
		if loader is None:
			raise ImportError("Module not found: "+name)
		return loader.load_module()
	else:
		return importlib.import_module(default + "." + name)

def main():
	args = _get_args()

	platform_module = _misoc_import("mibuild.platforms", args.external_platform, args.platform)
	target_module = _misoc_import("targets", args.external_target, args.target)
	platform = platform_module.Platform()
	if args.sub_target:
		top_class = getattr(target_module, args.sub_target)
	else:
		top_class = target_module.get_default_subtarget(platform)
	build_name = top_class.__name__.lower() + "-" + args.platform
	top_kwargs = dict((k, eval(v)) for k, v in args.option)
	soc = top_class(platform, **top_kwargs)

	soc.finalize()

	if not args.no_header:
		boilerplate = """/*
 * Platform: {}
 * Target: {}
 * Subtarget: {}
 */

""".format(args.platform, args.target, top_class.__name__)
		linker_header = cpuif.get_linker_regions(soc.cpu_memory_regions)
		write_to_file("software/include/generated/regions.ld", boilerplate + linker_header)
		csr_header = cpuif.get_csr_header(soc.csr_base, soc.csrbankarray, soc.interrupt_map)
		write_to_file("software/include/generated/csr.h", boilerplate + csr_header)
		sdram_phy_header = initsequence.get_sdram_phy_header(soc.ddrphy)
		write_to_file("software/include/generated/sdram_phy.h", boilerplate + sdram_phy_header)
	if args.csr_csv:
		csr_csv = cpuif.get_csr_csv(soc.csr_base, soc.csrbankarray)
		write_to_file(args.csr_csv, csr_csv)

	if hasattr(soc, "init_bios_memory"):
		ret = subprocess.call(["make", "-C", "software/bios"])
		if ret:
			raise OSError("BIOS build failed")
		bios_file = open("software/bios/bios.bin", "rb")
		bios_data = []
		while True:
			w = bios_file.read(4)
			if not w:
				break
			bios_data.append(struct.unpack(">I", w)[0])
		bios_file.close()
		soc.init_bios_memory(bios_data)

	if not args.no_bitstream:
		platform.build(soc, build_name=build_name)
		subprocess.call(["tools/byteswap",
			"build/" + build_name + ".bin",
			"build/" + build_name + ".fpg"])

	if args.load:
		jtag.load("build/" + build_name + ".bit")
	if args.flash:
		jtag.flash("build/" + build_name + ".fpg")

if __name__ == "__main__":
	main()
