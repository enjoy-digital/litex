from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.test.common import *

from misoclib.mem.litesata.test.model.link import LinkTXPacket

def print_transport(s):
    print_with_prefix(s, "[TRN]: ")


def get_field_data(field, packet):
    return (packet[field.byte//4] >> field.offset) & (2**field.width-1)


class FIS:
    def __init__(self, packet, description, direction="H2D"):
        self.packet = packet
        self.description = description
        self.direction = direction
        self.decode()

    def decode(self):
        for k, v in self.description.items():
            setattr(self, k, get_field_data(v, self.packet))

    def encode(self):
        for k, v in self.description.items():
            self.packet[v.byte//4] |= (getattr(self, k) << v.offset)

    def __repr__(self):
        if self.direction == "H2D":
            r = ">>>>>>>>\n"
        else:
            r = "<<<<<<<<\n"
        for k in sorted(self.description.keys()):
            r += k + " : 0x{:x}".format(getattr(self, k)) + "\n"
        return r


class FIS_REG_H2D(FIS):
    def __init__(self, packet=[0]*fis_reg_h2d_header.length):
        FIS.__init__(self, packet, fis_reg_h2d_header.fields)
        self.type = fis_types["REG_H2D"]
        self.direction = "H2D"

    def __repr__(self):
        r = "FIS_REG_H2D\n"
        r += FIS.__repr__(self)
        return r


class FIS_REG_D2H(FIS):
    def __init__(self, packet=[0]*fis_reg_d2h_header.length):
        FIS.__init__(self, packet, fis_reg_d2h_header.fields)
        self.type = fis_types["REG_D2H"]
        self.direction = "D2H"

    def __repr__(self):
        r = "FIS_REG_D2H\n"
        r += FIS.__repr__(self)
        return r


class FIS_DMA_ACTIVATE_D2H(FIS):
    def __init__(self, packet=[0]*fis_dma_activate_d2h_header.length):
        FIS.__init__(self, packet, fis_dma_activate_d2h_header.fields)
        self.type = fis_types["DMA_ACTIVATE_D2H"]
        self.direction = "D2H"

    def __repr__(self):
        r = "FIS_DMA_ACTIVATE_D2H\n"
        r += FIS.__repr__(self)
        return r


class FIS_DATA(FIS):
    def __init__(self, packet=[0], direction="H2D"):
        FIS.__init__(self, packet, fis_data_header.fields, direction)
        self.type = fis_types["DATA"]

    def __repr__(self):
        r = "FIS_DATA\n"
        r += FIS.__repr__(self)
        for data in self.packet[1:]:
            r += "{:08x}\n".format(data)
        return r


class FIS_UNKNOWN(FIS):
    def __init__(self, packet=[0], direction="H2D"):
        FIS.__init__(self, packet, {}, direction)

    def __repr__(self):
        r = "UNKNOWN\n"
        if self.direction == "H2D":
            r += ">>>>>>>>\n"
        else:
            r += "<<<<<<<<\n"
        for dword in self.packet:
            r += "{:08x}\n".format(dword)
        return r


class TransportLayer(Module):
    def __init__(self, link, debug=False, loopback=False):
        self.link = link
        self.debug = debug
        self.loopback = loopback
        self.link.set_transport_callback(self.callback)

    def set_command_callback(self, callback):
        self.command_callback = callback

    def send(self, fis):
        fis.encode()
        packet = LinkTXPacket(fis.packet)
        self.link.tx_packets.append(packet)
        if self.debug and not self.loopback:
            print_transport(fis)

    def callback(self, packet):
        fis_type = packet[0] & 0xff
        if fis_type == fis_types["REG_H2D"]:
            fis = FIS_REG_H2D(packet)
        elif fis_type == fis_types["REG_D2H"]:
            fis = FIS_REG_D2H(packet)
        elif fis_type == fis_types["DMA_ACTIVATE_D2H"]:
            fis = FIS_DMA_ACTIVATE_D2H(packet)
        elif fis_type == fis_types["DATA"]:
            fis = FIS_DATA(packet, direction="H2D")
        else:
            fis = FIS_UNKNOWN(packet, direction="H2D")
        if self.debug:
            print_transport(fis)
        if self.loopback:
            self.send(fis)
        else:
            self.command_callback(fis)
