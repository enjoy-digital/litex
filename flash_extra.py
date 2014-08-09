#!/usr/bin/env python3

import os, sys, argparse

from migen.util.misc import autotype

from misoc_import import misoc_import

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Program extra data to flash memory.")
	parser.add_argument("-f", "--flash-proxy-dir", default=None, help="set search directory for flash proxy bitstreams")
	parser.add_argument("-X", "--external", default="", help="use external directory for platforms and imports")
	parser.add_argument("-Op", "--platform-option", default=[], nargs=2, action="append", help="set platform-specific option")
	parser.add_argument("platform", help="target platform")
	parser.add_argument("file", help="file to flash")
	parser.add_argument("address", help="flash address to write")
	args = parser.parse_args()

	external_platform = ""
	if args.external:
		external_platform = os.path.join(args.external, "platforms")
		sys.path.insert(1, os.path.abspath(args.external))

	platform_module = misoc_import("mibuild.platforms", external_platform, args.platform)
	platform_kwargs = dict((k, autotype(v)) for k, v in args.platform_option)
	platform = platform_module.Platform(**platform_kwargs)

	prog = platform.create_programmer()
	prog.set_flash_proxy_dir(args.flash_proxy_dir)
	prog.flash(int(args.address, 0), args.file)
