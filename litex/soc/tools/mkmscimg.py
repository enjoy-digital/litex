#!/usr/bin/env python3

import argparse
import binascii


def insert_crc(i_filename, fbi_mode=False, o_filename=None, little_endian=False):
    endian = "little" if little_endian else "big"

    if o_filename is None:
        o_filename = i_filename

    with open(i_filename, "rb") as f:
        fdata = f.read()
    fcrc = binascii.crc32(fdata).to_bytes(4, byteorder=endian)
    flength = len(fdata).to_bytes(4, byteorder=endian)

    with open(o_filename, "wb") as f:
        if fbi_mode:
            f.write(flength)
            f.write(fcrc)
            f.write(fdata)
        else:
            f.write(fdata)
            f.write(fcrc)


def main():
    parser = argparse.ArgumentParser(description="CRC32 computation tool and MiSoC image file writer.")
    parser.add_argument("input", help="input file")
    parser.add_argument("-o", "--output", default=None, help="output file (if not specified, use input file)")
    parser.add_argument("-f", "--fbi", default=False, action="store_true", help="build flash boot image (FBI) file")
    parser.add_argument("-l", "--little", default=False, action="store_true", help="Use little endian to write the CRC32")
    args = parser.parse_args()
    insert_crc(args.input, args.fbi, args.output, args.little)


if __name__ == "__main__":
    main()
