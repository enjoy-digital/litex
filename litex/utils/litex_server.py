#!/usr/bin/env python3

import argparse

import sys
import socket
import time
import threading

from litex.soc.tools.remote.etherbone import EtherbonePacket, EtherboneRecord, EtherboneWrites
from litex.soc.tools.remote.etherbone import EtherboneIPC


class RemoteServer(EtherboneIPC):
    def __init__(self, comm, bind_ip, bind_port=1234):
        self.comm = comm
        self.bind_ip = bind_ip
        self.bind_port = bind_port
        self.lock = False

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
    args = parser.parse_args()


    if args.uart:
        from litex.soc.tools.remote import CommUART
        if args.uart_port is None:
            print("Need to specify --uart-port, exiting.")
            exit()
        uart_port = args.uart_port
        uart_baudrate = int(float(args.uart_baudrate))
        print("[CommUART] port: {} / baudrate: {} / ".format(uart_port, uart_baudrate), end="")
        comm = CommUART(uart_port, uart_baudrate)
    elif args.udp:
        from litex.soc.tools.remote import CommUDP
        udp_ip = args.udp_ip
        udp_port = int(args.udp_port)
        print("[CommUDP] ip: {} / port: {} / ".format(udp_ip, udp_port), end="")
        comm = CommUDP(udp_ip, udp_port)
    elif args.pcie:
        from litex.soc.tools.remote import CommPCIe
        pcie_bar = args.pcie_bar
        if args.pcie_bar is None:
            print("Need to speficy --pcie-bar, exiting.")
            exit()
        print("[CommPCIe] bar: {} / ".format(args.pcie_bar), end="")
        comm = CommPCIe(args.pcie_bar)
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
