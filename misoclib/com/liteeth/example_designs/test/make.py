#!/usr/bin/env python3
import argparse
import importlib


def _get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--bridge", default="uart", help="Bridge to use")
    parser.add_argument("--port", default="2", help="UART port")
    parser.add_argument("--baudrate", default=115200, help="UART baudrate")
    parser.add_argument("--ip_address", default="192.168.0.42", help="Etherbone IP address")
    parser.add_argument("--udp_port", default=20000, help="Etherbone UDP port")
    parser.add_argument("--busword", default=32, help="CSR busword")

    parser.add_argument("test", nargs="+", help="specify a test")

    return parser.parse_args()

if __name__ == "__main__":
    args = _get_args()
    if args.bridge == "uart":
        from misoclib.com.uart.software.wishbone import UARTWishboneBridgeDriver
        port = args.port if not args.port.isdigit() else int(args.port)
        wb = UARTWishboneBridgeDriver(port, args.baudrate, "./csr.csv", int(args.busword), debug=False)
    elif args.bridge == "etherbone":
        from misoclib.com.liteeth.software.wishbone import LiteETHWishboneBridgeDriver
        wb = LiteETHWishboneBridgeDriver(args.ip_address, int(args.udp_port), "./csr.csv", int(args.busword), debug=False)
    else:
        ValueError("Invalid bridge {}".format(args.bridge))

    def _import(name):
        return importlib.import_module(name)

    for test in args.test:
        t = _import(test)
        t.main(wb)
