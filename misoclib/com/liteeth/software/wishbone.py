import socket

from misoclib.tools.litescope.software.driver.reg import *

from misoclib.com.liteeth.test.model.etherbone import *


class LiteEthWishboneBridgeDriver:
    def __init__(self, ip_address, udp_port=20000, addrmap=None, busword=8, debug=False):
        self.ip_address = ip_address
        self.udp_port = udp_port
        self.debug = debug

        self.tx_sock = None
        self.rx_sock = None
        if addrmap is not None:
            self.regs = build_map(addrmap, busword, self.read, self.write)

    def open(self):
        self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx_sock.bind(("", self.udp_port))

    def close(self):
        pass

    def read(self, addr, burst_length=1):
        reads_addrs = [addr+4*j for j in range(burst_length)]
        reads = EtherboneReads(base_ret_addr=0x1000, addrs=reads_addrs)
        record = EtherboneRecord()
        record.writes = None
        record.reads = reads
        record.bca = 0
        record.rca = 0
        record.rff = 0
        record.cyc = 0
        record.wca = 0
        record.wff = 0
        record.byte_enable = 0xf
        record.wcount = 0
        record.rcount = len(reads_addrs)

        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()
        self.tx_sock.sendto(bytes(packet), (self.ip_address, self.udp_port))

        datas, addrs = self.rx_sock.recvfrom(8192)
        packet = EtherbonePacket(datas)
        packet.decode()
        datas = packet.records.pop().writes.get_datas()
        if self.debug:
            for i, data in enumerate(datas):
                print("RD {:08X} @ {:08X}".format(data, addr + 4*i))
        if burst_length == 1:
            return datas[0]
        else:
            return datas

    def write(self, addr, datas):
        if not isinstance(datas, list):
            datas = [datas]
        writes_datas = [d for d in datas]
        writes = EtherboneWrites(base_addr=addr, datas=writes_datas)
        record = EtherboneRecord()
        record.writes = writes
        record.reads = None
        record.bca = 0
        record.rca = 0
        record.rff = 0
        record.cyc = 0
        record.wca = 0
        record.wff = 0
        record.byte_enable = 0xf
        record.wcount = len(writes_datas)
        record.rcount = 0

        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()
        self.tx_sock.sendto(bytes(packet), (self.ip_address, self.udp_port))

        if self.debug:
            for i, data in enumerate(datas):
                print("WR {:08X} @ {:08X}".format(data, addr + 4*i))
