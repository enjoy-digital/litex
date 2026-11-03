#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Application: runs the checksum engine on a block and compares the result with the expected sum:
#   ./app.py --port=21201

import time
import argparse

from litex import RemoteClient

def main():
    parser = argparse.ArgumentParser(description="Checksum engine application.")
    parser.add_argument("--port",    default=21201, type=int, help="litex_server port.")
    parser.add_argument("--csr-csv", default="build/sim/csr.csv", help="CSR configuration file.")
    parser.add_argument("--length",  default=1000,  type=int, help="Block length (words).")
    parser.add_argument("--seed",    default=0x100, type=lambda s: int(s, 0), help="First word.")
    parser.add_argument("--timeout", default=10.0,  type=float, help="Run timeout (s).")
    args = parser.parse_args()

    bus = RemoteClient(port=args.port, csr_csv=args.csr_csv)
    bus.open()
    try:
        bus.regs.engine_length.write(args.length)
        bus.regs.engine_seed.write(args.seed)
        bus.regs.engine_control.write(1)
        start = time.time()
        while not (bus.regs.engine_status.read() & 0x2):
            if (time.time() - start) > args.timeout:
                raise SystemExit(f"Engine timeout (status: {bus.regs.engine_status.read():#x}).")
            time.sleep(0.01)
        result   = bus.regs.engine_result.read()
        expected = sum(args.seed + i for i in range(args.length)) & 0xffffffff
        print(f"result: {result:#010x} (expected {expected:#010x}): {'OK' if result == expected else 'KO'}")
    finally:
        bus.close()

if __name__ == "__main__":
    main()
