#!/usr/bin/env python3

import sys, os, argparse, subprocess, struct, importlib

from mibuild.tools import write_to_file
from migen.util.misc import autotype
from migen.fhdl import verilog, edif
from migen.fhdl.structure import _Fragment
from mibuild import tools

from misoclib.gensoc import cpuif

from litesata.common import *

def _import(default, name):
	return importlib.import_module(default + "." + name)

def _get_args():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
		description="""\
LiteSATA verilog rtl generator - based on Migen.

This program builds and/or loads LiteSATA components.
One or several actions can be specified:

clean           delete previous build(s).
build-rtl       build verilog rtl.
build-bitstream build-bitstream build FPGA bitstream.
build-csr-csv   save CSR map into CSV file.

load-bitstream  load bitstream into volatile storage.

all             clean, build-csr-csv, build-bitstream, load-bitstream.
""")

	parser.add_argument("-t", "--target", default="bist", help="Core type to build")
	parser.add_argument("-s", "--sub-target", default="", help="variant of the Core type to build")
	parser.add_argument("-p", "--platform", default=None, help="platform to build for")
	parser.add_argument("-Ot", "--target-option", default=[], nargs=2, action="append", help="set target-specific option")
	parser.add_argument("-Op", "--platform-option", default=[("programmer", "vivado")], nargs=2, action="append", help="set platform-specific option")
	parser.add_argument("--csr_csv", default="./test/csr.csv", help="CSV file to save the CSR map into")

	parser.add_argument("action", nargs="+", help="specify an action")

	return parser.parse_args()

# Note: misoclib need to be installed as a python library

if __name__ == "__main__":
	args = _get_args()

	# create top-level Core object
	target_module = _import("targets", args.target)
	if args.sub_target:
		top_class = getattr(target_module, args.sub_target)
	else:
		top_class = target_module.default_subtarget

	if args.platform is None:
		platform_name = top_class.default_platform
	else:
		platform_name = args.platform
	platform_module = _import("platforms", platform_name)
	platform_kwargs = dict((k, autotype(v)) for k, v in args.platform_option)
	platform = platform_module.Platform(**platform_kwargs)

	build_name = top_class.__name__.lower() +  "-" + platform_name
	top_kwargs = dict((k, autotype(v)) for k, v in args.target_option)
	soc = top_class(platform, **top_kwargs)
	soc.finalize()

	# decode actions
	action_list = ["clean", "build-csr-csv", "build-core", "build-bitstream", "load-bitstream", "all"]
	actions = {k: False for k in action_list}
	for action in args.action:
		if action in actions:
			actions[action] = True
		else:
			print("Unknown action: "+action+". Valid actions are:")
			for a in action_list:
				print("  "+a)
			sys.exit(1)


	revision = soc.sata_phy.revision
	frequency = frequencies[soc.sata_phy.revision]
	has_bist = hasattr(soc.sata, "bist")
	has_crossbar = hasattr(soc.sata, "crossbar")
	ports = 1 if not has_crossbar else len(soc.sata.crossbar.slaves)

	print("""
       __   _ __      _______ _________
      / /  (_) /____ / __/ _ /_  __/ _ |
     / /__/ / __/ -_)\ \/ __ |/ / / __ |
    /____/_/\__/\__/___/_/ |_/_/ /_/ |_|

A small footprint and configurable SATA core
          based on Migen/MiSoC

====== Building options: ======
SATA revision: {} / {} MHz
BIST: {}
Crossbar: {}
Ports: {}
===============================""".format(
	revision, frequency,
	has_bist,
	has_crossbar,
	ports
	)
)

	# dependencies
	if actions["all"]:
		actions["clean"] = True
		actions["build-csr-csv"] = True
		actions["build-bitstream"] = True
		actions["load-bitstream"] = True

	if actions["build-core"]:
		actions["clean"] = True

	if actions["build-bitstream"]:
		actions["clean"] = True
		actions["build-csr-csv"] = True
		actions["build-bitstream"] = True
		actions["load-bitstream"] = True

	if actions["clean"]:
		subprocess.call(["rm", "-rf", "build/*"])

	if actions["build-csr-csv"]:
		csr_csv = cpuif.get_csr_csv(soc.cpu_csr_regions)
		write_to_file(args.csr_csv, csr_csv)

	if actions["build-core"]:
		ios = soc.get_ios()
		if not isinstance(soc, _Fragment):
			soc = soc.get_fragment()
		platform.finalize(soc)
		src = verilog.convert(soc, ios)
		tools.write_to_file("build/litesata.v", src)

	if actions["build-bitstream"]:
		platform.build(soc, build_name=build_name)

	if actions["load-bitstream"]:
		prog = platform.create_programmer()
		prog.load_bitstream("build/" + build_name + platform.bitstream_ext)
