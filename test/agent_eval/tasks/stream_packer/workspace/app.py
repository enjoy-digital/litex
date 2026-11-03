#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Application: runs the packer test of the SoC and reports the counters:
#   ./app.py --port=21601 [--packets=1000] [--length-min=1] [--length-mask=63] [--backpressure=8]

import time
import argparse

from litex import RemoteClient

def main():
    parser = argparse.ArgumentParser(description="Packer test application.")
    parser.add_argument("--port",         default=21601, type=int, help="litex_server port.")
    parser.add_argument("--csr-csv",      default="build/sim/csr.csv", help="CSR configuration file.")
    parser.add_argument("--packets",      default=1000,  type=int, help="Number of packets.")
    parser.add_argument("--length-min",   default=1,     type=int, help="Minimum packet length.")
    parser.add_argument("--length-mask",  default=63,    type=int, help="Random length mask.")
    parser.add_argument("--backpressure", default=8,     type=int, help="Back-pressure level (0-15).")
    args = parser.parse_args()

    bus = RemoteClient(port=args.port, csr_csv=args.csr_csv)
    bus.open()
    try:
        regs = bus.regs
        regs.test_packets.write(args.packets)
        regs.test_length_min.write(args.length_min)
        regs.test_length_mask.write(args.length_mask)
        regs.test_backpressure.write(args.backpressure)
        regs.test_control.write(1)
        while not (regs.test_status.read() & 0x2):
            time.sleep(0.05)
        r = {name: getattr(regs, f"test_{name}").read() for name in
            ["tx_packets", "tx_bytes", "rx_packets", "rx_bytes", "data_errors", "cycles"]}
        print(" ".join(f"{k}={v}" for k, v in r.items()))
        ok = (r["rx_packets"] == r["tx_packets"]) and (r["rx_bytes"] == r["tx_bytes"]) and (r["data_errors"] == 0)
        print("PASS" if ok else "FAIL")
    finally:
        bus.close()

if __name__ == "__main__":
    main()
