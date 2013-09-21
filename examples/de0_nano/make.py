#!/usr/bin/env python3

import argparse, os, subprocess, struct, shutil

from mibuild.tools import write_to_file
import mibuild.platforms.de0nano as de0nano

from miscope.std import cif

import top

def build(build_bitstream, build_header):
	platform = de0nano.Platform()
	soc = top.SoC(platform)

	platform.add_platform_command("""
set_global_assignment -name FAMILY "Cyclone IV E"
set_global_assignment -name TOP_LEVEL_ENTITY "top"
set_global_assignment -name VERILOG_INPUT_VERSION SYSTEMVERILOG_2005
""")

	if build_bitstream:
		build_name = "soc-de0nano"
		platform.build(soc, build_name=build_name)
	else:
		soc.finalize()
	if build_header:

		csr_py_header = cif.get_py_csr_header(soc.csr_base, soc.csrbankarray)
		write_to_file(os.path.join("client", "csr.py"), csr_py_header)


def main():
	parser = argparse.ArgumentParser(description="miscope")
	parser.add_argument("-B", "--no-bitstream", default=False, action="store_true", help="do not build bitstream file")
	parser.add_argument("-H", "--no-header", default=False, action="store_true", help="do not build C header file with CSR defs")
	args = parser.parse_args()

	build(not args.no_bitstream, not args.no_header)

if __name__ == "__main__":
	main()
