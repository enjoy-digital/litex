from migen.fhdl.std import *
from migen.genlib.record import *
from migen.flow.actor import EndpointDescription, Sink, Source

from misoclib.com.litepcie.common import *

# constants
fmt_type_dict = {
    "mem_rd32": 0b0000000,
    "mem_wr32": 0b1000000,
    "mem_rd64": 0b0100000,
    "mem_wr64": 0b1100000,

    "cpld":     0b1001010,
    "cpl":      0b0001010
}

cpl_dict = {
    "sc":  0b000,
    "ur":  0b001,
    "crs": 0b010,
    "ca":  0b011
}

max_request_size = 512


# headers
class HField():
    def __init__(self, word, offset, width):
        self.word = word
        self.offset = offset
        self.width = width

tlp_header_w = 128

tlp_common_header = {
    "fmt":  HField(0, 29, 2),
    "type": HField(0, 24, 5),
}

tlp_request_header = {
    "fmt":          HField(0, 29,  2),
    "type":         HField(0, 24,  5),
    "tc":           HField(0, 20,  3),
    "td":           HField(0, 15,  1),
    "ep":           HField(0, 14,  1),
    "attr":         HField(0, 12,  2),
    "length":       HField(0,  0, 10),

    "requester_id": HField(1, 16, 16),
    "tag":          HField(1,  8,  8),
    "last_be":      HField(1,  4,  4),
    "first_be":     HField(1,  0,  4),

    "address":      HField(2,  2, 30),
}

tlp_completion_header = {
    "fmt":           HField(0, 29,  2),
    "type":          HField(0, 24,  5),
    "tc":            HField(0, 20,  3),
    "td":            HField(0, 15,  1),
    "ep":            HField(0, 14,  1),
    "attr":          HField(0, 12,  2),
    "length":        HField(0,  0, 10),

    "completer_id":  HField(1, 16, 16),
    "status":        HField(1, 13,  3),
    "bcm":           HField(1, 12,  1),
    "byte_count":    HField(1,  0, 12),

    "requester_id":  HField(2, 16, 16),
    "tag":           HField(2,  8,  8),
    "lower_address": HField(2,  0,  7),
}


# layouts
def _layout_from_header(header):
    _layout = []
    for k, v in sorted(header.items()):
        _layout.append((k, v.width))
    return _layout


def tlp_raw_layout(dw):
    layout = [
        ("header",    tlp_header_w),
        ("dat",        dw),
        ("be",        dw//8)
    ]
    return EndpointDescription(layout, packetized=True)


def tlp_common_layout(dw):
    layout = _layout_from_header(tlp_common_header) + [
        ("dat",        dw),
        ("be",        dw//8)
    ]
    return EndpointDescription(layout, packetized=True)


def tlp_request_layout(dw):
    layout = _layout_from_header(tlp_request_header) + [
        ("dat",        dw),
        ("be",        dw//8)
    ]
    return EndpointDescription(layout, packetized=True)


def tlp_completion_layout(dw):
    layout = _layout_from_header(tlp_completion_header) + [
        ("dat",        dw),
        ("be",        dw//8)
    ]
    return EndpointDescription(layout, packetized=True)
