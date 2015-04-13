#!/usr/bin/env python3

import argparse
import crc

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CRC32 computation tool and MiSoC image file writer.")
    parser.add_argument("input", help="input file")
    parser.add_argument("-o", "--output", default=None, help="output file (if not specified, use input file)")
    parser.add_argument("-f", "--fbi", default=False, action="store_true", help="build flash boot image (FBI) file")
    args = parser.parse_args()
    crc.insert_crc(args.input, args.fbi, args.output)
