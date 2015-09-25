from migen import *
from migen.genlib.record import *

from misoc.interconnect.csr import *


# TODO: rewrite without dataflow or implement those
# from migen.flow.actor import *
# from migen.actorlib.structuring import Converter, Pipeline
# from migen.actorlib.fifo import SyncFIFO, AsyncFIFO
# from migen.actorlib.packet import *


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
