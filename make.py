#!/usr/bin/env python3

import argparse, importlib, subprocess

from mibuild.tools import write_to_file

from misoclib.gensoc import cpuif
from misoclib.s6ddrphy import initsequence
import jtag

def _get_args():
	parser = argparse.ArgumentParser(description="MiSoC - a high performance SoC based on Migen.")

	parser.add_argument("-p", "--platform", default="mixxeo", help="platform to build for")
	parser.add_argument("-t", "--target", default="mlabs_video", help="SoC type to build")
	parser.add_argument("-s", "--sub-target", default="", help="variant of the SoC type to build")
	
	parser.add_argument("-B", "--no-bitstream", default=False, action="store_true", help="do not build bitstream file")
	parser.add_argument("-H", "--no-header", default=False, action="store_true", help="do not build C header files with CSR/IRQ/SDRAM_PHY definitions")
	parser.add_argument("-c", "--csr-csv", default="", help="save CSR map into CSV file")

	parser.add_argument("-l", "--load", default=False, action="store_true", help="load bitstream to FPGA volatile memory")
	parser.add_argument("-f", "--flash", default=False, action="store_true", help="load bitstream to flash")

	return parser.parse_args()

def main():
	args = _get_args()

	platform_module = importlib.import_module("mibuild.platforms." + args.platform)
	target_module = importlib.import_module("targets." + args.target)
	platform = platform_module.Platform()
	if args.sub_target:
		top_class = getattr(target_module, args.sub_target)
	else:
		top_class = target_module.get_default_subtarget(platform)
	build_name = top_class.__name__.lower() + "-" + args.platform
	soc = top_class(platform)

	if not args.no_bitstream:
		platform.build(soc, build_name=build_name)
		subprocess.call(["tools/byteswap",
			"build/" + build_name + ".bin",
			"build/" + build_name + ".fpg"])
	else:
		soc.finalize()
	if not args.no_header:
		boilerplate = """/*
 * Platform: {}
 * Target: {}
 * Subtarget: {}
 */

""".format(args.platform, args.target, top_class.__name__)
		csr_header = cpuif.get_csr_header(soc.csr_base, soc.csrbankarray, soc.interrupt_map)
		write_to_file("software/include/hw/csr.h", boilerplate + csr_header)
		sdram_phy_header = initsequence.get_sdram_phy_header(soc.ddrphy)
		write_to_file("software/include/hw/sdram_phy.h", boilerplate + sdram_phy_header)
	if args.csr_csv:
		csr_csv = cpuif.get_csr_csv(soc.csr_base, soc.csrbankarray)
		write_to_file(args.csr_csv, csr_csv)

	if args.load:
		jtag.load("build/" + build_name + ".bit")
	if args.flash:
		jtag.flash("build/" + build_name + ".fpg")

if __name__ == "__main__":
	main()
