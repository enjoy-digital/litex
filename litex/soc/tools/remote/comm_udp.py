import socket

from litex.soc.tools.remote.etherbone import EtherbonePacket, EtherboneRecord
from litex.soc.tools.remote.etherbone import EtherboneReads, EtherboneWrites


class CommUDP:
    def __init__(self, host="localhost", port=1234, debug=False):
        self.host = host
        self.port = port
        self.debug = debug

    def open(self):
        if hasattr(self, "tx_socket"):
            return
        self.tx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_socket.bind(("", self.port))

    def close(self):
        if not hasattr(self, "tx_socket"):
            return
        self.tx_socket.close()
        del self.tx_socket
        self.rx_socket.close()
        del self.rx_socket

    def read(self, addr, length=None):
        length_int = 1 if length is None else length
        record = EtherboneRecord()
        record.reads = EtherboneReads(addrs=[addr+4*j for j in range(length_int)])
        record.rcount = len(record.reads)

        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()
        self.tx_socket.sendto(bytes(packet), (self.server, self.port))

        data, dummy = self.rx_socket.recvfrom(8192)
        packet = EtherbonePacket(datas)
        packet.decode()
        data = packet.records.pop().writes.get_datas()
        if self.debug:
            for i, value in enumerate(data):
                print("RD {:08X} @ {:08X}".format(data, addr + 4*i))
        return data[0] if length is None else data

    def write(self, addr, data):
        data = data if isinstance(data, list) else [data]
        length = len(data)
        record = EtherboneRecord()
        record.writes = EtherboneWrites(base_addr=addr, datas=iter(data))
        record.wcount = len(record.write)

        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()
        self.tx_socket.sendto(bytes(packet), (self.server, self.port))

        if self.debug:
            for i, value in enumerate(data):
                print("WR {:08X} @ {:08X}".format(data, addr + 4*i))
