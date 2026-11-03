#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Application: configures the scaler, processes a test vector and compares the results with the
# expected ones:
#   ./app.py --port=22001

import argparse

from litex import RemoteClient

import driver

SAMPLES = [0, 1, 100, 1000, 2500, 4000, 10000, 30000, 50000, 65535]

def main():
    parser = argparse.ArgumentParser(description="Scaler application.")
    parser.add_argument("--port",   default=22001, type=int,   help="litex_server port.")
    parser.add_argument("--gain",   default=1.5,   type=float, help="Gain.")
    parser.add_argument("--offset", default=100,   type=int,   help="Offset.")
    args = parser.parse_args()

    bus = RemoteClient(port=args.port)
    bus.open()
    try:
        driver.configure(bus, args.gain, args.offset)
        errors = 0
        for x in SAMPLES:
            y        = driver.process(bus, x)
            expected = min(int(x*args.gain) + args.offset, 0xffff)
            ok       = abs(y - expected) <= 1
            errors  += not ok
            print(f"x={x:5d} y={y:5d} expected={expected:5d} {'OK' if ok else 'KO'}")
        print(f"{errors} error(s)")
    finally:
        bus.close()

if __name__ == "__main__":
    main()
