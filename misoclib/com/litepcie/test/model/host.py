from misoclib.com.litepcie.common import *
from misoclib.com.litepcie.core.packet.common import *
from misoclib.com.litepcie.test.common import *
from misoclib.com.litepcie.test.model.phy import PHY
from misoclib.com.litepcie.test.model.tlp import *
from misoclib.com.litepcie.test.model.chipset import Chipset


def print_host(s):
    print_with_prefix(s, "[HOST] ")


# Host model
class Host(Module):
    def __init__(self, dw, root_id, endpoint_id, bar0_size=1*MB,
            phy_debug=False,
            chipset_debug=False, chipset_split=False, chipset_reordering=False,
            host_debug=False):
        self.debug = host_debug
        self.chipset_split = chipset_split
        ###
        self.submodules.phy = PHY(dw, endpoint_id, bar0_size, phy_debug)
        self.submodules.chipset = Chipset(self.phy, root_id, chipset_debug, chipset_reordering)
        self.chipset.set_host_callback(self.callback)

        self.rd32_queue = []

    def malloc(self, base, length):
        self.base = base
        self.buffer = [0]*(length//4)

    def write_mem(self, adr, data):
        if self.debug:
            print_host("Writing {} bytes at 0x{:08x}".format(len(data)*4, adr))
        current_adr = (adr-self.base)//4
        for i in range(len(data)):
            self.buffer[current_adr+i] = data[i]

    def read_mem(self, adr, length=1):
        if self.debug:
            print_host("Reading {} bytes at 0x{:08x}".format(length, adr))
        current_adr = (adr-self.base)//4
        data = []
        for i in range(length//4):
            data.append(self.buffer[current_adr+i])
        return data

    def callback(self, msg):
        if isinstance(msg, WR32):
            address = msg.address*4
            self.write_mem(address, msg.data)
        elif isinstance(msg, RD32):
            self.rd32_queue.append(msg)

    def gen_simulation(self, selfp):
        while True:
            if len(self.rd32_queue):
                msg = self.rd32_queue.pop(0)
                address = msg.address*4
                length = msg.length*4
                data = self.read_mem(address, length)
                self.chipset.cmp(msg.requester_id, data, byte_count=length, tag=msg.tag, with_split=self.chipset_split)
            else:
                yield
