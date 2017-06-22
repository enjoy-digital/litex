import sys
import socket
import threading

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
                    try:
                        packet = self.receive_packet(client_socket)
                        if packet == 0:
                            break
                    except:
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


def main():
    print("LiteX remote server")
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print("usages:")
        print("litex_server uart [port] [baudrate]")
        print("litex_server udp [server] [server_port]")
        print("litex_server pcie [bar] [bar_size]")
        sys.exit()
    comm = sys.argv[1]
    if comm == "uart":
        from litex.soc.tools.remote import CommUART
        uart_port = None
        uart_baudrate = 115200
        if len(sys.argv) > 2:
            uart_port = sys.argv[2]
        if len(sys.argv) > 3:
            uart_baudrate = int(sys.argv[3])
        print("[CommUART] port: {} / baudrate: {}".format(uart_port, uart_baudrate))
        comm = CommUART(uart_port, uart_baudrate)
    elif comm == "udp":
        from litex.soc.tools.remote import CommUDP
        server = "192.168.1.50"
        server_port = 1234
        if len(sys.argv) > 2:
            server = sys.argv[2]
        if len(sys.argv) > 3:
            server_port = int(sys.argv[3])
        print("[CommUDP] server: {} / port: {}".format(server, server_port))
        comm = CommUDP(server, server_port)
    elif comm == "pcie":
        from litex.soc.tools.remote import CommPCIe
        bar = ""
        bar_size = 1024*1024
        if len(sys.argv) > 2:
            bar = sys.argv[2]
        if len(sys.argv) > 3:
            bar_size = int(sys.argv[3])
        print("[CommPCIe] bar: {} / bar_size: {}".format(bar, bar_size))
        comm = CommPCIe(bar, bar_size)
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
