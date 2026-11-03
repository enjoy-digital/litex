#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Application: prints the board information and tests the scratch register:
#   ./app.py --port=21801

import os
import sys
import argparse

from litex import RemoteClient

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sw"))
import board

def main():
    parser = argparse.ArgumentParser(description="Board information application.")
    parser.add_argument("--port", default=21801, type=int, help="litex_server port.")
    args = parser.parse_args()

    bus = RemoteClient(port=args.port)
    bus.open()
    try:
        ident = board.read(bus, "id")
        print(f"id: 0x{ident:08x} ({'OK' if ident == 0x4c58424f else 'KO'})")
        print(f"serial: 0x{board.read(bus, 'serial'):016x}")
        gain = board.read(bus, "cal_gain")
        print(f"cal_gain: 0x{gain:08x} ({gain/65536:.4f})")
        print(f"cal_offset: {board.read(bus, 'cal_offset')}")
        errors = 0
        for pattern in [0x00000000, 0xffffffff, 0xa5a55a5a, 0x01234567]:
            board.write(bus, "scratch", pattern)
            errors += board.read(bus, "scratch") != pattern
        print(f"scratch: {'OK' if errors == 0 else 'KO'}")
    finally:
        bus.close()

if __name__ == "__main__":
    main()
