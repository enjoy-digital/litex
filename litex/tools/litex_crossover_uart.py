#!/usr/bin/env python3

# This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

# Proof of Concept to use the crossover UART with lxterm over a bridge.

import os
import pty
import threading

from litex import RemoteClient

wb = RemoteClient()
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
