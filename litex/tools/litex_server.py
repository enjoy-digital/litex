#!/usr/bin/env python3

# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2018 Felix Held <felix-github@felixheld.de>
# License: BSD

import argparse

import sys
import socket
import time
import threading

from litex.tools.remote.etherbone import EtherbonePacket, EtherboneRecord, EtherboneWrites
from litex.tools.remote.etherbone import EtherboneIPC


class RemoteServer(EtherboneIPC):
    def __init__(self, comm, bind_ip, bind_port=1234):
        self.comm = comm
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.lock = False

    def open(self):
        if hasattr(self, "socket"):
            return
        socket_flags = 0
        if hasattr(socket, "SO_REUSEADDR"):
            socket_flags = socket_flags | socket.SO_REUSEADDR
        if hasattr(socket, "SO_REUSEPORT"):
            socket_flags = socket_flags | socket.SO_REUSEPORT
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket_flags, 1)
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

                    # wait for lock
                    while self.lock:
                        time.sleep(0.01)

                    # set lock
                    self.lock = True

                    # handle writes:
                    if record.writes != None:
                        self.comm.write(record.writes.base_addr, record.writes.get_datas())

                    # handle reads
                    if record.reads != None:
                        reads = []
                        for addr in record.reads.get_addrs():
                            reads.append(self.comm.read(addr))

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


def main():
    print("LiteX remote server")
    parser = argparse.ArgumentParser()
    # Common arguments
    parser.add_argument("--bind-ip", default="localhost",
                        help="Host bind address")
    parser.add_argument("--bind-port", default=1234,
                        help="Host bind port")

    # UART arguments
    parser.add_argument("--uart", action="store_true",
                        help="Select UART interface")
    parser.add_argument("--uart-port", default=None,
                        help="Set UART port")
    parser.add_argument("--uart-baudrate", default=115200,
                        help="Set UART baudrate")

    # UDP arguments
    parser.add_argument("--udp", action="store_true",
                        help="Select UDP interface")
    parser.add_argument("--udp-ip", default="192.168.1.50",
                        help="Set UDP remote IP address")
    parser.add_argument("--udp-port", default=1234,
                        help="Set UDP remote port")

    # PCIe arguments
    parser.add_argument("--pcie", action="store_true",
                        help="Select PCIe interface")
    parser.add_argument("--pcie-bar", default=None,
                        help="Set PCIe BAR")

    # USB arguments
    parser.add_argument("--usb", action="store_true",
                        help="Select USB interface")
    parser.add_argument("--usb-vid", default=None,
                        help="Set USB vendor ID")
    parser.add_argument("--usb-pid", default=None,
                        help="Set USB product ID")
    parser.add_argument("--usb-max-retries", default=10,
                        help="Number of times to try reconnecting to USB")
    args = parser.parse_args()


    if args.uart:
        from litex.tools.remote.comm_uart import CommUART
        if args.uart_port is None:
            print("Need to specify --uart-port, exiting.")
            exit()
        uart_port = args.uart_port
        uart_baudrate = int(float(args.uart_baudrate))
        print("[CommUART] port: {} / baudrate: {} / ".format(uart_port, uart_baudrate), end="")
        comm = CommUART(uart_port, uart_baudrate)
    elif args.udp:
        from litex.tools.remote.comm_udp import CommUDP
        udp_ip = args.udp_ip
        udp_port = int(args.udp_port)
        print("[CommUDP] ip: {} / port: {} / ".format(udp_ip, udp_port), end="")
        comm = CommUDP(udp_ip, udp_port)
    elif args.pcie:
        from litex.tools.remote.comm_pcie import CommPCIe
        pcie_bar = args.pcie_bar
        if args.pcie_bar is None:
            print("Need to speficy --pcie-bar, exiting.")
            exit()
        print("[CommPCIe] bar: {} / ".format(args.pcie_bar), end="")
        comm = CommPCIe(args.pcie_bar)
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
        comm = CommUSB(vid=vid, pid=pid, max_retries=args.usb_max_retries)
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
