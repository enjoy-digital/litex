import math

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.test.common import *

from misoclib.com.liteeth.test.model import mac


def print_ip(s):
    print_with_prefix(s, "[IP]")


def carry_around_add(a, b):
    c = a + b
    return (c & 0xffff) + (c >> 16)


def checksum(msg):
    s = 0
    for i in range(0, len(msg), 2):
        w = msg[i] + (msg[i+1] << 8)
        s = carry_around_add(s, w)
    return ~s & 0xffff


# IP model
class IPPacket(Packet):
    def __init__(self, init=[]):
        Packet.__init__(self, init)

    def get_checksum(self):
        return self[10] | (self[11] << 8)

    def check_checksum(self):
        return checksum(self[:ipv4_header.length]) == 0

    def decode(self):
        header = []
        for byte in self[:ipv4_header.length]:
            header.append(self.pop(0))
        for k, v in sorted(ipv4_header.fields.items()):
            setattr(self, k, get_field_data(v, header))

    def encode(self):
        header = 0
        for k, v in sorted(ipv4_header.fields.items()):
            value = merge_bytes(split_bytes(getattr(self, k),
                                            math.ceil(v.width/8)),
                                            "little")
            header += (value << v.offset+(v.byte*8))
        for d in split_bytes(header, ipv4_header.length):
            self.insert(0, d)

    def insert_checksum(self):
        self[10] = 0
        self[11] = 0
        c = checksum(self[:ipv4_header.length])
        self[10] = c & 0xff
        self[11] = (c >> 8) & 0xff

    def __repr__(self):
        r = "--------\n"
        for k in sorted(ipv4_header.fields.keys()):
            r += k + " : 0x{:0x}\n".format(getattr(self, k))
        r += "payload: "
        for d in self:
            r += "{:02x}".format(d)
        return r


class IP(Module):
    def __init__(self, mac, mac_address, ip_address, debug=False, loopback=False):
        self.mac = mac
        self.mac_address = mac_address
        self.ip_address = ip_address
        self.debug = debug
        self.loopback = loopback
        self.rx_packet = IPPacket()
        self.table = {}
        self.request_pending = False

        self.udp_callback = None
        self.icmp_callback = None

        self.mac.set_ip_callback(self.callback)

    def set_udp_callback(self, callback):
        self.udp_callback = callback

    def set_icmp_callback(self, callback):
        self.icmp_callback = callback

    def send(self, packet):
        packet.encode()
        packet.insert_checksum()
        if self.debug:
            print_ip(">>>>>>>>")
            print_ip(packet)
        mac_packet = mac.MACPacket(packet)
        mac_packet.target_mac = 0x12345678abcd  # XXX
        mac_packet.sender_mac = self.mac_address
        mac_packet.ethernet_type = ethernet_type_ip
        self.mac.send(mac_packet)

    def callback(self, packet):
        packet = IPPacket(packet)
        if not packet.check_checksum():
            received = packet.get_checksum()
            packet.insert_checksum()
            expected = packet.get_checksum()
            raise ValueError("Checksum error received {:04x} / expected {:04x}".format(received, expected))
        packet.decode()
        if self.debug:
            print_ip("<<<<<<<<")
            print_ip(packet)
        if self.loopback:
            self.send(packet)
        else:
            if packet.version != 0x4:
                raise ValueError
            if packet.ihl != 0x5:
                raise ValueError
            self.process(packet)

    def process(self, packet):
        if packet.protocol == udp_protocol:
            if self.udp_callback is not None:
                self.udp_callback(packet)
        elif packet.protocol == icmp_protocol:
            if self.icmp_callback is not None:
                self.icmp_callback(packet)

if __name__ == "__main__":
    from misoclib.com.liteeth.test.model.dumps import *
    from misoclib.com.liteeth.test.model.mac import *
    errors = 0
    # UDP packet
    packet = MACPacket(udp)
    packet.decode_remove_header()
    # print(packet)
    packet = IPPacket(packet)
    # check decoding
    errors += not packet.check_checksum()
    packet.decode()
    # print(packet)
    errors += verify_packet(packet, {})
    # check encoding
    packet.encode()
    packet.insert_checksum()
    errors += not packet.check_checksum()
    packet.decode()
    # print(packet)
    errors += verify_packet(packet, {})

    print("ip errors " + str(errors))
