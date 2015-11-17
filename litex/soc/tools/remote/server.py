import socket
import threading
import argparse

from litex.soc.tools.remote.etherbone import EtherbonePacket, EtherboneRecord, EtherboneWrites
from litex.soc.tools.remote.etherbone import EtherboneIPC


class RemoteServer(EtherboneIPC):
    def __init__(self, comm, port=1234):
        self.comm = comm
        self.port = port

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(("localhost", self.port))
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
                    packet = self.receive_packet(client_socket)
                    if packet == 0:
                        break
                    packet = EtherbonePacket(packet)
                    packet.decode()

                    record = packet.records.pop()

                    # writes:
                    if record.writes != None:
                        self.comm.write(record.writes.base_addr, record.writes.get_datas())

                    # reads
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
            finally:
                print("Disconnect")
                client_socket.close()

    def start(self):
        self.serve_thread = threading.Thread(target=self._serve_thread)
        self.serve_thread.setDaemon(True)
        self.serve_thread.start()


def _get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comm", default="uart", help="comm interface")
    parser.add_argument("--port", default="2", help="UART port")
    parser.add_argument("--baudrate", default=115200, help="UART baudrate")
    parser.add_argument("--debug", action="store_true", help="enable debug")
    return parser.parse_args()

def main():
    print("LiteX remote server")
    args = _get_args()
    if args.comm == "uart":
        from litex.soc.tools.remote import CommUART
        print("Using CommUART, port: {} / baudrate: {}".format(args.port, args.baudrate))
        comm = CommUART(args.port if not args.port.isdigit() else int(args.port),
                        args.baudrate,
                        debug=args.debug)
    else:
        raise NotImplementedError

    server = RemoteServer(comm)
    server.open()
    server.start()
    try:
        import time
        while True: time.sleep(100)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
