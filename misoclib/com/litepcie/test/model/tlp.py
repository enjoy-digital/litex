from misoclib.com.litepcie.common import *
from misoclib.com.litepcie.core.packet.common import *


# TLP Layer model
def get_field_data(field, dwords):
    return (dwords[field.word] >> field.offset) & (2**field.width-1)

tlp_headers_dict = {
    "RD32": tlp_request_header,
    "WR32": tlp_request_header,
    "CPLD": tlp_completion_header,
    "CPL":  tlp_completion_header
}


class TLP():
    def __init__(self, name, dwords=[0, 0, 0]):
        self.name = name
        self.header = dwords[:3]
        self.data = dwords[3:]
        self.dwords = self.header + self.data
        self.decode_dwords()

    def decode_dwords(self):
        for k, v in tlp_headers_dict[self.name].items():
            setattr(self, k, get_field_data(v, self.header))

    def encode_dwords(self, data=[]):
        self.header = [0, 0, 0]
        for k, v in tlp_headers_dict[self.name].items():
            field = tlp_headers_dict[self.name][k]
            self.header[field.word] |= (getattr(self, k) << field.offset)
        self.data = data
        self.dwords = self.header + self.data
        return self.dwords

    def __repr__(self):
        r = self.name + "\n"
        r += "--------\n"
        for k in sorted(tlp_headers_dict[self.name].keys()):
            r += k + " : 0x{:x}".format(getattr(self, k) + "\n")
        if len(self.data) != 0:
            r += "data:\n"
            for d in self.data:
                r += "{:08x}\n".format(d)
        return r


class RD32(TLP):
    def __init__(self, dwords=[0, 0, 0]):
        TLP.__init__(self, "RD32", dwords)


class WR32(TLP):
    def __init__(self, dwords=[0, 0, 0]):
        TLP.__init__(self, "WR32", dwords)


class CPLD(TLP):
    def __init__(self, dwords=[0, 0, 0]):
        TLP.__init__(self, "CPLD", dwords)


class CPL():
    def __init__(self, dwords=[0, 0, 0]):
        TLP.__init__(self, "CPL", dwords)


class Unknown():
    def __repr__(self):
        r = "UNKNOWN\n"
        return r

fmt_type_dict = {
    fmt_type_dict["mem_rd32"]: (RD32, 3),
    fmt_type_dict["mem_wr32"]: (WR32, 4),
    fmt_type_dict["cpld"]:     (CPLD, 4),
    fmt_type_dict["cpl"]:      (CPL, 3)
}


def parse_dwords(dwords):
    f = get_field_data(tlp_common_header["fmt"], dwords)
    t = get_field_data(tlp_common_header["type"], dwords)
    fmt_type = (f << 5) | t
    try:
        tlp, min_len = fmt_type_dict[fmt_type]
        if len(dwords) >= min_len:
            return tlp(dwords)
        else:
            return Unknown()
    except:
        return Unknown()
