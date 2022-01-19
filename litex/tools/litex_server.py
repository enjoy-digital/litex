#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2015-2021 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Sean Cross <sean@xobs.io>
# Copyright (c) 2018 Felix Held <felix-github@felixheld.de>
# SPDX-License-Identifier: BSD-2-Clause

import argparse

import os
import sys
import socket
import time
import threading

from litex.tools.remote.etherbone import EtherbonePacket, EtherboneRecord, EtherboneWrites
from litex.tools.remote.etherbone import EtherboneIPC

# Read Merger --------------------------------------------------------------------------------------

def _read_merger(addrs, max_length=256, bursts=["incr", "fixed"]):
    """Sequential reads merger

    Take a list of read addresses as input and merge the sequential/fixed reads in (base, length, burst) tuples:
    Example: [0x0, 0x4, 0x10, 0x14, 0x20, 0x20] input  will return [(0x0,2, "incr"), (0x10,2, "incr"), (0x20,2, "fixed")].

    This is useful for UARTBone/Etherbone where command/response roundtrip delay is responsible for
    most of the access delay and allows minimizing number of commands by grouping them in UARTBone
    packets.
    """
    assert "incr" in bursts
    burst_base   = addrs[0]
    burst_length = 1
    burst_type   = "incr"
    for addr in addrs[1:]:
        merged = False
        # Try to merge to a "fixed" burst if supported
        if ("fixed" in bursts):
            # If current burst matches
            if (burst_type in [None, "fixed"]) or (burst_length == 1):
                # If addr matches
                if (addr == burst_base):
                    if (burst_length != max_length):
                        burst_type   = "fixed"
                        burst_length += 1
                        merged       = True

        # Try to merge to an "incr" burst if supported
        if ("incr" in bursts):
            # If current burst matches
            if (burst_type in [None, "incr"]) or (burst_length == 1):
                # If addr matches
                if (addr == burst_base + (4 * burst_length)):
                    if (burst_length != max_length):
                        burst_type   = "incr"
                        burst_length += 1
                        merged       = True

        # Generate current burst if addr has not able to merge
        if not merged:
            yield (burst_base, burst_length, burst_type)
            burst_base   = addr
            burst_length = 1
            burst_type   = "incr"
    yield (burst_base, burst_length, burst_type)

# Remote Server ------------------------------------------------------------------------------------

class RemoteServer(EtherboneIPC):
    def __init__(self, comm, bind_ip, bind_port=1234):
        self.comm      = comm
        self.bind_ip   = bind_ip
        self.bind_port = bind_port
        self.lock      = False

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_REUSEADDR"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.socket.bind((self.bind_ip, self.bind_port))
        print("tcp port: {:d}".format(self.bind_port))
        self.socket.listen(1)
        self.comm.open()

    def close(self):
        self.comm.close()
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket

    def _serve_thread(self):
        while True:
            client_socket, addr = self.socket.accept()
            print("Connected with " + addr[0] + ":" + str(addr[1]))
            try:
                while True:
                    try:
                        packet = self.receive_packet(client_socket)
                        if packet == 0:
                            break
                    except:
                        break
                    packet = EtherbonePacket(packet)
                    packet.decode()

                    record = packet.records.pop()

                    # Wait for lock
                    while self.lock:
                        time.sleep(0.01)

                    # Set lock
                    self.lock = True

                    # Handle writes:
                    if record.writes != None:
                        self.comm.write(record.writes.base_addr, record.writes.get_datas())

                    # Handle reads
                    if record.reads != None:
                        max_length = {
                            "CommUART": 256,
                            "CommUDP":    1,
                        }.get(self.comm.__class__.__name__, 1)
                        bursts = {
                            "CommUART": ["incr", "fixed"]
                        }.get(self.comm.__class__.__name__, ["incr"])
                        reads = []
                        for addr, length, burst in _read_merger(record.reads.get_addrs(),
                            max_length  = max_length,
                            bursts      = bursts):
                            reads += self.comm.read(addr, length, burst)

                        record = EtherboneRecord()
                        record.writes = EtherboneWrites(datas=reads)
                        record.wcount = len(record.writes)

                        packet = EtherbonePacket()
                        packet.records = [record]
                        packet.encode()
                        self.send_packet(client_socket, packet)

                    # release lock
                    self.lock = False

            finally:
                print("Disconnect")
                client_socket.close()

    def start(self, nthreads):
        for i in range(nthreads):
            self.serve_thread = threading.Thread(target=self._serve_thread)
            self.serve_thread.setDaemon(True)
            self.serve_thread.start()

# Run ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX Server utility", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    # Common arguments
    parser.add_argument("--bind-ip",         default="localhost",    help="Host bind address.")
    parser.add_argument("--bind-port",       default=1234,           help="Host bind port.")
    parser.add_argument("--debug",           action="store_true",    help="Enable debug.")

    # UART arguments
    parser.add_argument("--uart",            action="store_true",    help="Select UART interface.")
    parser.add_argument("--uart-port",       default=None,           help="Set UART port.")
    parser.add_argument("--uart-baudrate",   default=115200,         help="Set UART baudrate.")

    # JTAG arguments
    parser.add_argument("--jtag",            action="store_true",             help="Select JTAG interface.")
    parser.add_argument("--jtag-config",     default="openocd_xc7_ft232.cfg", help="OpenOCD JTAG configuration file.")
    parser.add_argument("--jtag-chain",      default=1,                       help="JTAG chain.")

    # UDP arguments
    parser.add_argument("--udp",             action="store_true",    help="Select UDP interface.")
    parser.add_argument("--udp-ip",          default="192.168.1.50", help="Set UDP remote IP address.")
    parser.add_argument("--udp-port",        default=1234,           help="Set UDP remote port.")
    parser.add_argument("--udp-scan",        action="store_true",    help="Scan network for available UDP devices.")

    # PCIe arguments
    parser.add_argument("--pcie",            action="store_true",    help="Select PCIe interface.")
    parser.add_argument("--pcie-bar",        default=None,           help="Set PCIe BAR.")

    # USB arguments
    parser.add_argument("--usb",             action="store_true",    help="Select USB interface.")
    parser.add_argument("--usb-vid",         default=None,           help="Set USB vendor ID.")
    parser.add_argument("--usb-pid",         default=None,           help="Set USB product ID.")
    parser.add_argument("--usb-max-retries", default=10,             help="Number of USB reconecting retries.")
    args = parser.parse_args()


    # UART mode
    if args.uart:
        from litex.tools.remote.comm_uart import CommUART
        if args.uart_port is None:
            print("Need to specify --uart-port, exiting.")
            exit()
        uart_port = args.uart_port
        uart_baudrate = int(float(args.uart_baudrate))
        print("[CommUART] port: {} / baudrate: {} / ".format(uart_port, uart_baudrate), end="")
        comm = CommUART(uart_port, uart_baudrate, debug=args.debug)

    # JTAG mode
    elif args.jtag:
        from litex.tools.litex_term import JTAGUART
        from litex.tools.remote.comm_uart import CommUART
        jtag_uart = JTAGUART(config=args.jtag_config, chain=int(args.jtag_chain))
        jtag_uart.open()
        print("[CommUART] port: JTAG / ", end="")
        comm = CommUART(os.ttyname(jtag_uart.name), debug=args.debug)

    # UDP mode
    elif args.udp:
        from litex.tools.remote.comm_udp import CommUDP
        udp_ip   = args.udp_ip
        udp_port = int(args.udp_port)
        if args.udp_scan:
            udp_ip = udp_ip.split(".")
            assert len(udp_ip) == 4
            udp_ip[3] = "x"
            udp_ip = ".".join(udp_ip)
            comm = CommUDP(udp_ip, udp_port, debug=args.debug)
            comm.open(probe=False)
            comm.scan(udp_ip)
            comm.close()
            exit()
        else:
            print("[CommUDP] ip: {} / port: {} / ".format(udp_ip, udp_port), end="")
            comm = CommUDP(udp_ip, udp_port, debug=args.debug)

    # PCIe mode
    elif args.pcie:
        from litex.tools.remote.comm_pcie import CommPCIe
        pcie_bar = args.pcie_bar
        if pcie_bar is None:
            print("Need to speficy --pcie-bar, exiting.")
            exit()
        print("[CommPCIe] bar: {} / ".format(pcie_bar), end="")
        comm = CommPCIe(pcie_bar, debug=args.debug)

    # USB mode
    elif args.usb:
        from litex.tools.remote.comm_usb import CommUSB
        if args.usb_pid is None and args.usb_vid is None:
            print("Need to speficy --usb-vid or --usb-pid, exiting.")
            exit()
        print("[CommUSB] vid: {} / pid: {} / ".format(args.usb_vid, args.usb_pid), end="")
        pid = args.usb_pid
        if pid is not None:
            pid = int(pid, base=0)
        vid = args.usb_vid
        if vid is not None:
            vid = int(vid, base=0)
        comm = CommUSB(vid=vid, pid=pid, max_retries=args.usb_max_retries, debug=args.debug)

    else:
        parser.print_help()
        exit()

    server = RemoteServer(comm, args.bind_ip, int(args.bind_port))
    server.open()
    server.start(4)
    try:
        import time
        while True: time.sleep(100)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
