#!/usr/bin/env python3

import sys, argparse
import programmer

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Program extra data to flash memory.")
	parser.add_argument("-f", "--flash-proxy-dir", default=None, help="set search directory for flash proxy bitstreams")
	parser.add_argument("platform", help="target platform")
	parser.add_argument("file", help="file to flash")
	parser.add_argument("address", help="flash address to write")
	args = parser.parse_args()

	prog = programmer.create_programmer(args.platform, args.flash_proxy_dir)
	prog.flash(int(args.address, 0), args.file)
