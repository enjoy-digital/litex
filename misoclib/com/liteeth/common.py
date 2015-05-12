import math
from collections import OrderedDict

from migen.fhdl.std import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.record import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import chooser, reverse_bytes, FlipFlop, Counter, WaitTimer
from migen.flow.actor import *
from migen.actorlib.structuring import Converter, Pipeline
from migen.actorlib.fifo import SyncFIFO, AsyncFIFO
from migen.actorlib.packet import *
from migen.bank.description import *

class Port:
    def connect(self, port):
        r = [
            Record.connect(self.source, port.sink),
            Record.connect(port.source, self.sink)
        ]
        return r

eth_mtu = 1532
eth_min_len = 46
eth_interpacket_gap = 12
eth_preamble = 0xD555555555555555
buffer_depth = 2**log2_int(eth_mtu, need_pow2=False)

ethernet_type_ip = 0x800
ethernet_type_arp = 0x806

mac_header_length = 14
mac_header_fields = {
    "target_mac":       HeaderField(0,  0, 48),
    "sender_mac":       HeaderField(6,  0, 48),
    "ethernet_type":    HeaderField(12, 0, 16)
}
mac_header = Header(mac_header_fields,
                    mac_header_length,
                    swap_field_bytes=True)

arp_hwtype_ethernet = 0x0001
arp_proto_ip = 0x0800
arp_opcode_request = 0x0001
arp_opcode_reply = 0x0002

arp_header_length = 28
arp_header_fields = {
    "hwtype":           HeaderField(0,  0, 16),
    "proto":            HeaderField(2,  0, 16),
    "hwsize":           HeaderField(4,  0,  8),
    "protosize":        HeaderField(5,  0,  8),
    "opcode":           HeaderField(6,  0, 16),
    "sender_mac":       HeaderField(8,  0, 48),
    "sender_ip":        HeaderField(14, 0, 32),
    "target_mac":       HeaderField(18, 0, 48),
    "target_ip":        HeaderField(24, 0, 32)
}
arp_header = Header(arp_header_fields,
                    arp_header_length,
                    swap_field_bytes=True)


ipv4_header_length = 20
ipv4_header_fields = {
    "ihl":              HeaderField(0,  0,  4),
    "version":          HeaderField(0,  4,  4),
    "total_length":     HeaderField(2,  0, 16),
    "identification":   HeaderField(4,  0, 16),
    "ttl":              HeaderField(8,  0,  8),
    "protocol":         HeaderField(9,  0,  8),
    "checksum":         HeaderField(10, 0, 16),
    "sender_ip":        HeaderField(12, 0, 32),
    "target_ip":        HeaderField(16, 0, 32)
}
ipv4_header = Header(ipv4_header_fields,
                     ipv4_header_length,
                     swap_field_bytes=True)

icmp_protocol = 0x01

icmp_header_length = 8
icmp_header_fields = {
    "msgtype":          HeaderField(0,  0,  8),
    "code":             HeaderField(1,  0,  8),
    "checksum":         HeaderField(2,  0, 16),
    "quench":           HeaderField(4,  0, 32)
}
icmp_header  = Header(icmp_header_fields,
                      icmp_header_length,
                      swap_field_bytes=True)

udp_protocol = 0x11

udp_header_length = 8
udp_header_fields = {
    "src_port":         HeaderField(0,  0, 16),
    "dst_port":         HeaderField(2,  0, 16),
    "length":           HeaderField(4,  0, 16),
    "checksum":         HeaderField(6,  0, 16)
}
udp_header = Header(udp_header_fields,
                    udp_header_length,
                    swap_field_bytes=True)


etherbone_magic = 0x4e6f
etherbone_version = 1
etherbone_packet_header_length = 8
etherbone_packet_header_fields = {
    "magic":            HeaderField(0,  0, 16),

    "version":          HeaderField(2,  4, 4),
    "nr":               HeaderField(2,  2, 1),
    "pr":               HeaderField(2,  1, 1),
    "pf":               HeaderField(2,  0, 1),

    "addr_size":        HeaderField(3,  4, 4),
    "port_size":        HeaderField(3,  0, 4)
}
etherbone_packet_header = Header(etherbone_packet_header_fields,
                                 etherbone_packet_header_length,
                                 swap_field_bytes=True)

etherbone_record_header_length = 4
etherbone_record_header_fields = {
    "bca":              HeaderField(0,  0, 1),
    "rca":              HeaderField(0,  1, 1),
    "rff":              HeaderField(0,  2, 1),
    "cyc":              HeaderField(0,  4, 1),
    "wca":              HeaderField(0,  5, 1),
    "wff":              HeaderField(0,  6, 1),

    "byte_enable":      HeaderField(1,  0, 8),

    "wcount":           HeaderField(2,  0, 8),

    "rcount":           HeaderField(3,  0, 8)
}
etherbone_record_header = Header(etherbone_record_header_fields,
                                 etherbone_record_header_length,
                                 swap_field_bytes=True)


# layouts
def _remove_from_layout(layout, *args):
    r = []
    for f in layout:
        remove = False
        for arg in args:
            if f[0] == arg:
                remove = True
        if not remove:
            r.append(f)
    return r


def eth_phy_description(dw):
    payload_layout = [
        ("data", dw),
        ("last_be", dw//8),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, packetized=True)


def eth_mac_description(dw):
    payload_layout = mac_header.get_layout() + [
        ("data", dw),
        ("last_be", dw//8),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, packetized=True)


def eth_arp_description(dw):
    param_layout = arp_header.get_layout()
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)

arp_table_request_layout = [
    ("ip_address", 32)
]

arp_table_response_layout = [
    ("failed", 1),
    ("mac_address", 48)
]


def eth_ipv4_description(dw):
    param_layout = ipv4_header.get_layout()
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def eth_ipv4_user_description(dw):
    param_layout = [
        ("length", 16),
        ("protocol", 8),
        ("ip_address", 32)
    ]
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def convert_ip(s):
    ip = 0
    for e in s.split("."):
        ip = ip << 8
        ip += int(e)
    return ip


def eth_icmp_description(dw):
    param_layout = icmp_header.get_layout()
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def eth_icmp_user_description(dw):
    param_layout = icmp_header.get_layout() + [
        ("ip_address", 32),
        ("length", 16)
    ]
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def eth_udp_description(dw):
    param_layout = udp_header.get_layout()
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def eth_udp_user_description(dw):
    param_layout = [
        ("src_port", 16),
        ("dst_port", 16),
        ("ip_address", 32),
        ("length", 16)
    ]
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def eth_etherbone_packet_description(dw):
    param_layout = etherbone_packet_header.get_layout()
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def eth_etherbone_packet_user_description(dw):
    param_layout = etherbone_packet_header.get_layout()
    param_layout = _remove_from_layout(param_layout,
                                       "magic",
                                       "portsize",
                                       "addrsize",
                                       "version")
    param_layout += eth_udp_user_description(dw).param_layout
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def eth_etherbone_record_description(dw):
    param_layout = etherbone_record_header.get_layout()
    payload_layout = [
        ("data", dw),
        ("error", dw//8)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def eth_etherbone_mmap_description(dw):
    param_layout = [
        ("we", 1),
        ("count", 8),
        ("base_addr", 32),
        ("be", dw//8)
    ]
    payload_layout = [
        ("addr", 32),
        ("data", dw)
    ]
    return EndpointDescription(payload_layout, param_layout, packetized=True)


def eth_tty_description(dw):
    payload_layout = [("data", dw)]
    return EndpointDescription(payload_layout, packetized=False)
