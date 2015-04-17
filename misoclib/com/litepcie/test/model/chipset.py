from misoclib.com.litepcie.common import *
from misoclib.com.litepcie.core.packet.common import *
from misoclib.com.litepcie.test.common import *
from misoclib.com.litepcie.test.model.tlp import *


def print_chipset(s):
    print_with_prefix(s, "[CHIPSET] ")


def find_cmp_tags(queue):
    tags = []
    for tag, dwords in queue:
        if tag not in tags:
            tags.append(tag)
    return tags


def find_first_cmp_msg(queue, msg_tag):
    for i, (tag, dwords) in enumerate(queue):
        if tag == msg_tag:
            return i


# Chipset model
class Chipset(Module):
    def __init__(self, phy, root_id, debug=False, with_reordering=False):
        self.phy = phy
        self.root_id = root_id
        self.debug = debug
        self.with_reordering = with_reordering
        ###
        self.rd32_data = []
        self.cmp_queue = []
        self.en = False

    def set_host_callback(self, callback):
        self.host_callback = callback

    def enable(self):
        self.en = True

    def disable(self):
        self.en = False

    def wr32(self, adr, data):
        wr32 = WR32()
        wr32.fmt             = 0b10
        wr32.type             = 0b00000
        wr32.length         = len(data)
        wr32.first_be        = 0xf
        wr32.address         = adr
        wr32.requester_id    = self.root_id
        dwords = wr32.encode_dwords(data)
        if self.debug:
            print_chipset(">>>>>>>>")
            print_chipset(parse_dwords(dwords))
        yield from self.phy.send_blocking(dwords)

    def rd32(self, adr, length=1):
        rd32 = RD32()
        rd32.fmt             = 0b00
        rd32.type             = 0b00000
        rd32.length         = length
        rd32.first_be        = 0xf
        rd32.address         = adr
        rd32.requester_id    = self.root_id
        dwords = rd32.encode_dwords()
        if self.debug:
            print_chipset(">>>>>>>>")
            print_chipset(parse_dwords(dwords))
        yield from self.phy.send_blocking(dwords)
        dwords = None
        while dwords is None:
            dwords = self.phy.receive()
            yield
        cpld = CPLD(dwords)
        self.rd32_data = cpld.data
        if self.debug:
            print_chipset("<<<<<<<<")
            print_chipset(cpld)

    def cmp(self, req_id, data, byte_count=None, lower_address=0, tag=0, with_split=False):
        if with_split:
            d = random.choice([64, 128, 256])
            n = byte_count//d
            if n == 0:
                self.cmp(req_id, data, byte_count=byte_count, tag=tag)
            else:
                for i in range(n):
                    cmp_data = data[i*byte_count//(4*n):(i+1)*byte_count//(4*n)]
                    self.cmp(req_id, cmp_data, byte_count=byte_count-i*byte_count//n, tag=tag)
        else:
            if len(data) == 0:
                fmt = 0b00
                cpl = CPL()
            else:
                fmt = 0b10
                cpl = CPLD()
            cpl.fmt = fmt
            cpl.type = 0b01010
            cpl.length = len(data)
            cpl.lower_address = lower_address
            cpl.requester_id = req_id
            cpl.completer_id = self.root_id
            if byte_count is None:
                cpl.byte_count = len(data)*4
            else:
                cpl.byte_count = byte_count
            cpl.tag = tag
            if len(data) == 0:
                dwords = cpl.encode_dwords()
            else:
                dwords = cpl.encode_dwords(data)
            self.cmp_queue.append((tag, dwords))

    def cmp_callback(self):
        if len(self.cmp_queue):
            if self.with_reordering:
                tags = find_cmp_tags(self.cmp_queue)
                tag = random.choice(tags)
                n = find_first_cmp_msg(self.cmp_queue, tag)
                tag, dwords = self.cmp_queue.pop(n)
            else:
                tag, dwords = self.cmp_queue.pop(0)
            if self.debug:
                print_chipset(">>>>>>>>")
                print_chipset(parse_dwords(dwords))
            self.phy.send(dwords)

    def gen_simulation(self, selfp):
        while True:
            if self.en:
                dwords = self.phy.receive()
                if dwords is not None:
                    msg = parse_dwords(dwords)
                    if self.debug:
                        print_chipset(" <<<<<<<< (Callback)")
                        print_chipset(msg)
                    self.host_callback(msg)
                self.cmp_callback()
            yield
