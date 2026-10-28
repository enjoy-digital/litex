#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

"""litex-host-bridges.svg: how the host reaches the bus of a running SoC, for the Host-Bridges page:
the host tools, litex_server and its transports, the bridges in the gateware and what they give
access to.

    python3 doc/diagrams/litex-host-bridges.py   # -> doc/wiki/images/litex-host-bridges.svg
"""

from litex_diagram import *

W, H = 1400, 700

DESC = ("LiteX host bridges. On the host, the user scripts (RemoteClient), litex_cli, the LiteScope "
        "client, litex_term's crossover console and the GUI talk to litex_server over TCP (Etherbone "
        "packets, port 1234). litex_server drives one transport: a serial port (UARTBone), OpenOCD "
        "(JTAGBone), UDP (Etherbone over LiteEth), the LitePCIe kernel driver (PCIe), USB, or /dev/mem "
        "on a hard CPU. In the FPGA the matching bridge is a bus master on the SoC's main bus, so the "
        "host reads and writes every CSR, memory and core, including LiteScope's capture buffer.")

def draw(d):
    # Host.
    d.box(30, 40, 640, 560, fill=BOARD, c=24)
    d.text(335, 70, "Host PC", 22, weight="bold")
    d.box(50, 100, 330, 190, lines=[("Your scripts", 16, "bold"), ("RemoteClient: read / write", 13), ("regs.<core>_<reg>, mems, constants", 13)])
    d.box(350, 100, 620, 190, lines=[("litex_cli", 16, "bold"), ("--ident · --regs · --read · --write", 13), ("--gui: registers and memory viewer", 13)])
    d.box(50, 210, 330, 300, lines=[("LiteScope client", 16, "bold"), ("litescope_cli · analyzer driver", 13), ("triggers, capture, .vcd / .sr / .csv", 13)])
    d.box(350, 210, 620, 300, lines=[("litex_term crossover · GDB", 15, "bold"), ("the BIOS console through the bridge", 13), ("CPU debug over JTAG (OpenOCD)", 13)])
    for x in (190, 485):
        d.arrow([(x, 300), (x, 360)], double=True)
    d.text(345, 335, "Etherbone over TCP, port 1234", 12, style="italic")
    d.box(50, 360, 620, 420, fill=KEY, c=16, lines=[("litex_server", 17, "bold"), ("one process per board, --bind-ip / --bind-port, several clients", 13)])
    d.arrow([(335, 420), (335, 460)], double=True)
    d.box(50, 460, 620, 540, fill=GROUP, c=16)
    d.text(335, 483, "Transports (litex/tools/remote)", 14, weight="bold")
    d.text(335, 503, "--uart (serial port) · --jtag (OpenOCD) · --udp (Etherbone) · --pcie (BAR mmap)", 12)
    d.text(335, 521, "--usb (vendor requests) · --devmem (/dev/mem on a hard CPU: Zynq, Cyclone V HPS)", 12)

    # Link.
    d.arrow([(640, 500), (760, 500)], double=True, thick=True)
    d.text(700, 486, "UART · JTAG · USB", 12, style="italic")
    d.text(700, 518, "Ethernet · PCIe", 12, style="italic")

    # FPGA.
    d.box(760, 40, 1370, 560, fill=FPGA, c=24)
    d.text(1065, 70, "FPGA: LiteX SoC", 22, weight="bold")
    d.box(780, 460, 1350, 540, fill=KEY, c=16)
    d.text(1065, 483, "Bridge: a bus master in the gateware", 14, weight="bold")
    d.text(1065, 503, "UARTBone (add_uartbone, --with-uartbone) · JTAGBone (add_jtagbone, --with-jtagbone)", 12)
    d.text(1065, 521, "Etherbone (add_etherbone, LiteEth) · LitePCIe MMAP · USB · hard CPU AXI bridge", 12)
    d.arrow([(1065, 460), (1065, 420)], double=True, thick=True)
    d.box(780, 360, 1350, 420, fill=KEY, c=16, lines=[("Main bus: Wishbone · AXI-Lite · AXI", 17, "bold"), ("the whole address map of the SoC", 13)])
    d.box(780, 100, 1065, 190, fill=MEM, lines=[("Memories", 16, "bold"), ("ROM · SRAM · main RAM (DRAM)", 13), ("load, dump, patch firmware", 13)])
    d.box(1085, 100, 1350, 190, lines=[("CSRs of every core", 16, "bold"), ("control, status, configuration", 13), ("from csr.csv: regs.<core>_<reg>", 13)])
    d.box(780, 210, 1065, 300, lines=[("LiteScope analyzer", 16, "bold"), ("capture buffer in BRAM", 13), ("probes on internal signals", 13)])
    d.box(1085, 210, 1350, 300, lines=[("Crossover UART · JTAG UART", 14, "bold"), ("BIOS console without a serial port", 13), ("CPU debug (JTAG, --with-cpu-jtag-debug)", 13)])
    for x in (922, 1217):
        d.arrow([(x, 300), (x, 360)], double=True)
    d.arrow([(922, 190), (922, 210)], double=True)
    d.arrow([(1217, 190), (1217, 210)], double=True)

    d.caption(700, 600, "The host reads and writes the bus of the running SoC", "no CPU involved: bring-up, debug, control and measurement scripts from the host, with the same API over every transport")
    d.footer()

if __name__ == "__main__":
    cli(draw, "litex-host-bridges", W, H, "LiteX host bridges", DESC)
