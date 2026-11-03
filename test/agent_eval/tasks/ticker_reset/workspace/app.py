#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Application: arms the ticker for a 200-tick delay and waits for it to expire:
#   ./app.py --port=21101

import time
import argparse

from litex import RemoteClient

def main():
    parser = argparse.ArgumentParser(description="Ticker application.")
    parser.add_argument("--port",    default=21101, type=int, help="litex_server port.")
    parser.add_argument("--csr-csv", default="build/sim/csr.csv", help="CSR configuration file.")
    parser.add_argument("--ticks",   default=200,   type=int, help="Delay (ticks).")
    args = parser.parse_args()

    bus = RemoteClient(port=args.port, csr_csv=args.csr_csv)
    bus.open()
    try:
        start = time.time()
        bus.regs.ticker_load.write(args.ticks)
        while not (bus.regs.ticker_status.read() & 0x1):
            time.sleep(0.01)
        print(f"delay expired after {time.time() - start:.2f}s")
    finally:
        bus.close()

if __name__ == "__main__":
    main()
