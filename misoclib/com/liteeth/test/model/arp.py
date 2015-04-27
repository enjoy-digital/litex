import math

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.test.common import *

from misoclib.com.liteeth.test.model import mac


def print_arp(s):
    print_with_prefix(s, "[ARP]")

preamble = split_bytes(eth_preamble, 8)


# ARP model
class ARPPacket(Packet):
    def __init__(self, init=[]):
        Packet.__init__(self, init)

    def decode(self):
        header = []
        for byte in self[:arp_header.length]:
            header.append(self.pop(0))
        for k, v in sorted(arp_header.fields.items()):
            setattr(self, k, get_field_data(v, header))

    def encode(self):
        header = 0
        for k, v in sorted(arp_header.fields.items()):
            value = merge_bytes(split_bytes(getattr(self, k),
                                            math.ceil(v.width/8)),
                                            "little")
            header += (value << v.offset+(v.byte*8))
        for d in split_bytes(header, arp_header.length):
            self.insert(0, d)

    def __repr__(self):
        r = "--------\n"
        for k in sorted(arp_header.fields.keys()):
            r += k + " : 0x{:0x}\n".format(getattr(self, k))
        r += "payload: "
        for d in self:
            r += "{:02x}".format(d)
        return r


class ARP(Module):
    def __init__(self, mac, mac_address, ip_address, debug=False):
        self.mac = mac
        self.mac_address = mac_address
        self.ip_address = ip_address
        self.debug = debug
        self.tx_packets = []
        self.tx_packet = ARPPacket()
        self.rx_packet = ARPPacket()
        self.table = {}
        self.request_pending = False

        self.mac.set_arp_callback(self.callback)

    def send(self, packet):
        packet.encode()
        if self.debug:
            print_arp(">>>>>>>>")
            print_arp(packet)
        mac_packet = mac.MACPacket(packet)
        mac_packet.target_mac = packet.target_mac
        mac_packet.sender_mac = packet.sender_mac
        mac_packet.ethernet_type = ethernet_type_arp
        self.mac.send(mac_packet)

    def callback(self, packet):
        packet = ARPPacket(packet)
        packet.decode()
        if self.debug:
            print_arp("<<<<<<<<")
            print_arp(packet)
        self.process(packet)

    def process(self, packet):
        if len(packet) != eth_min_len-arp_header.length:
            raise ValueError
        if packet.hwtype != arp_hwtype_ethernet:
            raise ValueError
        if packet.proto != arp_proto_ip:
            raise ValueError
        if packet.hwsize != 6:
            raise ValueError
        if packet.protosize != 4:
            raise ValueError
        if packet.opcode == arp_opcode_request:
            self.process_request(packet)
        elif packet.opcode == arp_opcode_reply:
            self.process_reply(packet)

    def process_request(self, request):
        if request.target_ip == self.ip_address:
            reply = ARPPacket([0]*(eth_min_len-arp_header.length))
            reply.hwtype = arp_hwtype_ethernet
            reply.proto = arp_proto_ip
            reply.opcode = arp_opcode_reply
            reply.hwsize = 6
            reply.protosize = 4
            reply.sender_mac = self.mac_address
            reply.sender_ip = self.ip_address
            reply.target_mac = request.sender_mac
            reply.target_ip = request.sender_ip
            self.send(reply)

    def process_reply(self, reply):
        self.table[reply.sender_ip] = reply.sender_mac

    def request(self, ip_address):
        request = ARPPacket([0]*(eth_min_len-arp_header.length))
        request.hwtype = arp_hwtype_ethernet
        request.proto = arp_proto_ip
        request.opcode = arp_opcode_request
        request.hwsize = 6
        request.protosize = 4
        request.sender_mac = self.mac_address
        request.sender_ip = self.ip_address
        request.target_mac = 0xffffffffffff
        request.target_ip = ip_address

if __name__ == "__main__":
    from misoclib.com.liteeth.test.model.dumps import *
    from misoclib.com.liteeth.test.model.mac import *
    errors = 0
    # ARP request
    packet = MACPacket(arp_request)
    packet.decode_remove_header()
    packet = ARPPacket(packet)
    # check decoding
    packet.decode()
    # print(packet)
    errors += verify_packet(packet, arp_request_infos)
    # check encoding
    packet.encode()
    packet.decode()
    # print(packet)
    errors += verify_packet(packet, arp_request_infos)

    # ARP Reply
    packet = MACPacket(arp_reply)
    packet.decode_remove_header()
    packet = ARPPacket(packet)
    # check decoding
    packet.decode()
    # print(packet)
    errors += verify_packet(packet, arp_reply_infos)
    # check encoding
    packet.encode()
    packet.decode()
    # print(packet)
    errors += verify_packet(packet, arp_reply_infos)

    print("arp errors " + str(errors))
