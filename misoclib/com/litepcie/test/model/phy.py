import math
from misoclib.com.litepcie.common import *
from misoclib.com.litepcie.core.packet.common import *
from misoclib.com.litepcie.test.common import *


def print_chipset(s):
    print_with_prefix(s, "[PHY] ")


# PHY Layer model
class PHYPacket():
    def __init__(self, dat=[], be=[]):
        self.dat = dat
        self.be = be
        self.start = 1
        self.done = 0


class PHYSource(Module):
    def __init__(self, dw):
        self.source = Source(phy_layout(dw))
        ###
        self.packets = []
        self.packet = PHYPacket()
        self.packet.done = 1

    def send(self, packet):
        self.packets.append(packet)

    def send_blocking(self, packet):
        self.send(packet)
        while packet.done == 0:
            yield

    def do_simulation(self, selfp):
        if len(self.packets) and self.packet.done:
            self.packet = self.packets.pop(0)
        if self.packet.start and not self.packet.done:
            selfp.source.stb = 1
            selfp.source.sop = 1
            selfp.source.dat = self.packet.dat.pop(0)
            selfp.source.be = self.packet.be.pop(0)
            self.packet.start = 0
        elif selfp.source.stb == 1 and selfp.source.ack == 1:
            selfp.source.sop = 0
            selfp.source.eop = (len(self.packet.dat) == 1)
            if len(self.packet.dat) > 0:
                selfp.source.stb = 1
                selfp.source.dat = self.packet.dat.pop(0)
                selfp.source.be = self.packet.be.pop(0)
            else:
                self.packet.done = 1
                selfp.source.stb = 0


class PHYSink(Module):
    def __init__(self, dw):
        self.sink = Sink(phy_layout(dw))
        ###
        self.packet = PHYPacket()

    def receive(self):
        self.packet.done = 0
        while self.packet.done == 0:
            yield

    def do_simulation(self, selfp):
        self.packet.done = 0
        selfp.sink.ack = 1
        if selfp.sink.stb == 1 and selfp.sink.sop == 1:
            self.packet.start = 1
            self.packet.dat = [selfp.sink.dat]
            self.packet.be = [selfp.sink.be]
        elif selfp.sink.stb:
            self.packet.start = 0
            self.packet.dat.append(selfp.sink.dat)
            self.packet.be.append(selfp.sink.be)
        if (selfp.sink.stb == 1 and selfp.sink.eop == 1):
            self.packet.done = 1


class PHY(Module):
    def __init__(self, dw, id, bar0_size, debug):
        self.dw = dw

        self.id = id

        self.bar0_size = bar0_size
        self.bar0_mask = get_bar_mask(bar0_size)

        self.max_request_size = 512
        self.max_payload_size = 128

        self.submodules.phy_source = PHYSource(dw)
        self.submodules.phy_sink = PHYSink(dw)

        self.source = self.phy_source.source
        self.sink = self.phy_sink.sink

    def dwords2packet(self, dwords):
            ratio = self.dw//32
            length = math.ceil(len(dwords)/ratio)
            dat = [0]*length
            be = [0]*length
            for n in range(length):
                for i in reversed(range(ratio)):
                    dat[n] = dat[n] << 32
                    be[n] = be[n] << 4
                    try:
                        dat[n] |= dwords[2*n+i]
                        be[n] |= 0xF
                    except:
                        pass
            return dat, be

    def send(self, dwords):
        dat, be = self.dwords2packet(dwords)
        packet = PHYPacket(dat, be)
        self.phy_source.send(packet)

    def send_blocking(self, dwords):
        dat, be = self.dwords2packet(dwords)
        packet = PHYPacket(dat, be)
        yield from self.phy_source.send_blocking(packet)

    def packet2dwords(self, p_dat, p_be):
            ratio = self.dw//32
            dwords = []
            for dat, be in zip(p_dat, p_be):
                for i in range(ratio):
                    dword_be = (be >> (4*i)) & 0xf
                    dword_dat = (dat >> (32*i)) & 0xffffffff
                    if dword_be == 0xf:
                        dwords.append(dword_dat)
            return dwords

    def receive(self):
        if self.phy_sink.packet.done:
            self.phy_sink.packet.done = 0
            return self.packet2dwords(self.phy_sink.packet.dat, self.phy_sink.packet.be)
        else:
            return None

