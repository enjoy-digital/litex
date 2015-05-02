#!/usr/bin/env python3
import argparse
import importlib

FTDI_INTERFACE_A = 1
FTDI_INTERFACE_B = 2

def _get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=0, help="USB channel tag")
    parser.add_argument("--busword", default=32, help="CSR busword")

    parser.add_argument("test", nargs="+", help="specify a test")

    return parser.parse_args()

if __name__ == "__main__":
    args = _get_args()
    from misoclib.com.liteusb.software.wishbone import LiteUSBWishboneDriver
    wb = LiteUSBWishboneDriver("ft2232h", FTDI_INTERFACE_B, "asynchronous",
                               tag=int(args.tag),
                               busword=int(args.busword),
                               addrmap="./csr.csv",
                               debug=False)

    def _import(name):
        return importlib.import_module(name)

    for test in args.test:
        t = _import(test)
        t.main(wb)
