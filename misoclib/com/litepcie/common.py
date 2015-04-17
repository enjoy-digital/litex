from migen.fhdl.std import *
from migen.genlib.record import *
from migen.flow.actor import *

KB = 1024
MB = 1024*KB
GB = 1024*MB


def get_bar_mask(size):
            mask = 0
            found = 0
            for i in range(32):
                if size%2:
                    found = 1
                if found:
                    mask |= (1 << i)
                size = size >> 1
            return mask


def reverse_bytes(v):
    return Cat(v[24:32], v[16:24], v[8:16], v[0:8])


def reverse_bits(v):
    return Cat(v[3], v[2], v[1], v[0])


def phy_layout(dw):
    layout = [
        ("dat", dw),
        ("be",  dw//8)
    ]
    return EndpointDescription(layout, packetized=True)


def request_layout(dw):
    layout = [
            ("we",       1),
            ("adr",     32),
            ("len",     10),
            ("req_id",  16),
            ("tag",      8),
            ("dat",     dw),
            ("channel",  8),  # for routing
            ("user_id",  8)   # for packet identification
    ]
    return EndpointDescription(layout, packetized=True)


def completion_layout(dw):
    layout = [
            ("adr",    32),
            ("len",    10),
            ("last",    1),
            ("req_id", 16),
            ("cmp_id", 16),
            ("err",     1),
            ("tag",     8),
            ("dat",     dw),
            ("channel",  8),  # for routing
            ("user_id",  8)   # for packet identification
    ]
    return EndpointDescription(layout, packetized=True)


def interrupt_layout():
    return [("dat", 8)]


def dma_layout(dw):
    layout = [("dat", dw)]
    return EndpointDescription(layout, packetized=True)
