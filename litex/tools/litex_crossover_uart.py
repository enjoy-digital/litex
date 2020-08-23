#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Proof of Concept to use the crossover UART with lxterm over a bridge.

import os
import pty
import threading
import argparse

from litex import RemoteClient

parser = argparse.ArgumentParser(description="LiteX Crossover UART bridge tool")
parser.add_argument("--host",         default="localhost",  help="Host IP address")
parser.add_argument("--base-address", default="0x00000000", help="Wishbone base address")
args = parser.parse_args()

wb = RemoteClient(host=args.host, base_address=int(args.base_address, 0))
wb.open()

# # #

def pty2crossover(m):
    while True:
        r = os.read(m, 1)
        wb.regs.uart_xover_rxtx.write(ord(r))

def crossover2pty(m):
    while True:
        if wb.regs.uart_xover_rxempty.read() == 0:
            r = wb.regs.uart_xover_rxtx.read()
            os.write(m, bytes(chr(r).encode("utf-8")))

m, s = pty.openpty()
print("LiteX Crossover UART created: {}".format(os.ttyname(s)))

pty2crossover_thread = threading.Thread(target=pty2crossover, args=[m])
pty2crossover_thread.start()

crossover2pty(m)

# # #

wb.close()
