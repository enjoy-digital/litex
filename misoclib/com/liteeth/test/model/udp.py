import math

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.test.common import *

from misoclib.com.liteeth.test.model import ip


def print_udp(s):
    print_with_prefix(s, "[UDP]")


# UDP model
class UDPPacket(Packet):
    def __init__(self, init=[]):
        Packet.__init__(self, init)

    def decode(self):
        header = []
        for byte in self[:udp_header.length]:
            header.append(self.pop(0))
        for k, v in sorted(udp_header.fields.items()):
            setattr(self, k, get_field_data(v, header))

    def encode(self):
        header = 0
        for k, v in sorted(udp_header.fields.items()):
            value = merge_bytes(split_bytes(getattr(self, k),
                                            math.ceil(v.width/8)),
                                            "little")
            header += (value << v.offset+(v.byte*8))
        for d in split_bytes(header, udp_header.length):
            self.insert(0, d)

    def __repr__(self):
        r = "--------\n"
        for k in sorted(udp_header.fields.keys()):
            r += k + " : 0x{:0x}\n".format(getattr(self, k))
        r += "payload: "
        for d in self:
            r += "{:02x}".format(d)
        return r


class UDP(Module):
    def __init__(self, ip, ip_address, debug=False, loopback=False):
        self.ip = ip
        self.ip_address = ip_address
        self.debug = debug
        self.loopback = loopback
        self.tx_packets = []
        self.tx_packet = UDPPacket()
        self.rx_packet = UDPPacket()

        self.etherbone_callback = None

        self.ip.set_udp_callback(self.callback)

    def set_etherbone_callback(self, callback):
        self.etherbone_callback = callback

    def send(self, packet):
        packet.encode()
        if self.debug:
            print_udp(">>>>>>>>")
            print_udp(packet)
        ip_packet = ip.IPPacket(packet)
        ip_packet.version = 0x4
        ip_packet.ihl = 0x5
        ip_packet.total_length = len(packet) + ip_packet.ihl
        ip_packet.identification = 0
        ip_packet.flags = 0
        ip_packet.fragment_offset = 0
        ip_packet.ttl = 0x80
        ip_packet.sender_ip = self.ip_address
        ip_packet.target_ip = 0x12345678  # XXX
        ip_packet.checksum = 0
        ip_packet.protocol = udp_protocol
        self.ip.send(ip_packet)

    def callback(self, packet):
        packet = UDPPacket(packet)
        packet.decode()
        if self.debug:
            print_udp("<<<<<<<<")
            print_udp(packet)
        if self.loopback:
            self.send(packet)
        else:
            self.process(packet)

    def process(self, packet):
        if packet.dst_port == 20000:
            if self.etherbone_callback is not None:
                self.etherbone_callback(packet)

if __name__ == "__main__":
    from misoclib.com.liteeth.test.model.dumps import *
    from misoclib.com.liteeth.test.model.mac import *
    from misoclib.com.liteeth.test.model.ip import *
    errors = 0
    # UDP packet
    packet = MACPacket(udp)
    packet.decode_remove_header()
    # print(packet)
    packet = IPPacket(packet)
    packet.decode()
    # print(packet)
    packet = UDPPacket(packet)
    packet.decode()
    # print(packet)
    if packet.length != (len(packet)+udp_header.length):
        errors += 1
    errors += verify_packet(packet, udp_infos)
    packet.encode()
    packet.decode()
    # print(packet)
    if packet.length != (len(packet)+udp_header.length):
        errors += 1
    errors += verify_packet(packet, udp_infos)

    print("udp errors " + str(errors))
