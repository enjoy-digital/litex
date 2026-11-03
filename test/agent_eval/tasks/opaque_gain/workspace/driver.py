#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Host driver of the ACME scaler IP (see ip/DATASHEET.md), through a litex_server (RemoteClient).

import time

SCALER_BASE = 0x30000000

ID     = SCALER_BASE + 0x00
CTRL   = SCALER_BASE + 0x04
GAIN   = SCALER_BASE + 0x08
OFFSET = SCALER_BASE + 0x0c
DIN    = SCALER_BASE + 0x10
DOUT   = SCALER_BASE + 0x14
STATUS = SCALER_BASE + 0x1c

def configure(bus, gain, offset):
    """Configure the scaler for DOUT = min(DIN*gain + offset, 0xffff) and enable it."""
    bus.write(CTRL,   0)
    bus.write(GAIN,   int(round(gain*256)) & 0xffff)
    bus.write(OFFSET, int(offset) & 0xffff)
    bus.write(CTRL,   1)

def process(bus, sample, timeout=1.0):
    """Process one sample and return the result."""
    bus.write(DIN, sample & 0xffff)
    start = time.time()
    while not (bus.read(STATUS) & 0x1):
        if (time.time() - start) > timeout:
            raise TimeoutError("Scaler timeout.")
    return bus.read(DOUT)
