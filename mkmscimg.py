#!/usr/bin/env python3

import sys, argparse
import crc

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="CRC32 computation tool and MiSoC image file writer.")
	parser.add_argument("-i", default=None, help="input file")
	parser.add_argument("-o", default=None, help="output file (if not specified = input file)")
	args = parser.parse_args()

	i_filename = args.i
	o_filename = args.o

	crc.insert_crc(i_filename, o_filename)
