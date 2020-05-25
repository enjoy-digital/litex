#!/usr/bin/env python3

# This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

# Proof of Concept to use the JTAG UART with lxterm.

import os
import pty
import threading
import telnetlib
import time

from litex.build.openocd import OpenOCD

telnet_port = 20000

def openocd_jtag_telnet():
	prog = OpenOCD("openocd_xc7_ft2232.cfg")
	prog.stream(telnet_port)

m, s = pty.openpty()
print("LiteX JTAG UART created: {}".format(os.ttyname(s)))

openocd_jtag_telnet_thread = threading.Thread(target=openocd_jtag_telnet)
openocd_jtag_telnet_thread.start()

time.sleep(1)

t = telnetlib.Telnet("localhost", telnet_port)

def pty2telnet(m):
    while True:
        r = os.read(m, 1)
        t.write(r)
        if r == bytes("\n".encode("utf-8")):
        	t.write("\r".encode("utf-8"))
        t.write("\n".encode("utf-8"))

def telnet2pty(m):
	while True:
		r = t.read_some()
		os.write(m, bytes(r))

pty2telnet_thread = threading.Thread(target=pty2telnet, args=[m])
pty2telnet_thread.start()

telnet2pty(m)
