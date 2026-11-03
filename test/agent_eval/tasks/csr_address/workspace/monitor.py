#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Temperature monitor: enables the sensor of the SoC, waits for a conversion and prints the
# temperature. Talks to the SoC through a litex_server:
#   ./monitor.py --port=21001

import time
import argparse

from litex import RemoteClient

# Sensor Registers ---------------------------------------------------------------------------------

# From the generated csr.h.
SENSOR_CONTROL = 0x00001000
SENSOR_STATUS  = 0x00001004
SENSOR_ID      = 0x00001008
SENSOR_VALUE   = 0x0000100c

# Monitor ------------------------------------------------------------------------------------------

def read_temperature(bus, timeout=1.0):
    bus.write(SENSOR_CONTROL, 0)
    bus.write(SENSOR_CONTROL, 1)
    start = time.time()
    while not (bus.read(SENSOR_STATUS) & 0x1):
        if (time.time() - start) > timeout:
            raise TimeoutError("Sensor conversion timeout.")
        time.sleep(0.01)
    raw = bus.read(SENSOR_VALUE) & 0xffff
    return raw/16

def main():
    parser = argparse.ArgumentParser(description="Temperature monitor.")
    parser.add_argument("--host", default="localhost", help="litex_server host.")
    parser.add_argument("--port", default=21001, type=int, help="litex_server port.")
    args = parser.parse_args()

    bus = RemoteClient(host=args.host, port=args.port)
    bus.open()
    try:
        print(f"temperature: {read_temperature(bus):.2f} C")
    finally:
        bus.close()

if __name__ == "__main__":
    main()
