import socket
import time
from misoclib.com.liteeth.test.model.etherbone import *

SRAM_BASE = 0x02000000

import socket


def main(wb):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # test probe
    packet = EtherbonePacket()
    packet.pf = 1
    packet.encode()
    sock.sendto(bytes(packet), ("192.168.0.42", 20000))
    time.sleep(0.01)

    # test writes
    writes_datas = [j for j in range(16)]
    writes = EtherboneWrites(base_addr=SRAM_BASE, datas=writes_datas)
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
    sock.sendto(bytes(packet), ("192.168.0.42", 20000))
    time.sleep(0.01)

    # test reads
    reads_addrs = [SRAM_BASE+4*j for j in range(16)]
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
    sock.sendto(bytes(packet), ("192.168.0.42", 20000))
    time.sleep(0.01)
