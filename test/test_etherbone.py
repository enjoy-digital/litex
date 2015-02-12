import socket
from liteeth.test.model.etherbone import *

SRAM_BASE = 0x02000000

import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# test probe
packet = EtherbonePacket()
packet.pf = 1
packet.encode()
sock.sendto(bytes(packet), ("192.168.1.40", 20000))
