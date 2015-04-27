import math

from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.test.common import *

from misoclib.mem.litesata.test.model.phy import *
from misoclib.mem.litesata.test.model.link import *
from misoclib.mem.litesata.test.model.transport import *
from misoclib.mem.litesata.test.model.command import *

def print_hdd(s):
    print_with_prefix(s, "[HDD]: ")


class HDDMemRegion:
    def __init__(self, base, count, sector_size):
        self.base = base
        self.count = count
        self.data = [0]*(count*sector_size//4)


class HDD(Module):
    def __init__(self,
            link_debug=False, link_random_level=0,
            transport_debug=False, transport_loopback=False,
            hdd_debug=False,
            ):
        self.submodules.phy = PHYLayer()
        self.submodules.link = LinkLayer(self.phy, link_debug, link_random_level)
        self.submodules.transport = TransportLayer(self.link, transport_debug, transport_loopback)
        self.submodules.command = CommandLayer(self.transport)

        self.command.set_hdd(self)

        self.debug = hdd_debug
        self.mem = None
        self.wr_sector = 0
        self.wr_end_sector = 0
        self.rd_sector = 0
        self.rx_end_sector = 0

    def malloc(self, sector, count):
        if self.debug:
            s = "Allocating {n} sectors: {s} to {e}".format(n=count, s=sector, e=sector+count-1)
            s += " ({} KB)".format(count*logical_sector_size//1024)
            print_hdd(s)
        self.mem = HDDMemRegion(sector, count, logical_sector_size)

    def write(self, sector, data):
        n = math.ceil(dwords2sectors(len(data)))
        if self.debug:
            if n == 1:
                s = "{}".format(sector)
            else:
                s = "{s} to {e}".format(s=sector, e=sector+n-1)
            print_hdd("Writing sector " + s)
        for i in range(len(data)):
            offset = sectors2dwords(sector)
            self.mem.data[offset+i] = data[i]

    def read(self, sector, count):
        if self.debug:
            if count == 1:
                s = "{}".format(sector)
            else:
                s = "{s} to {e}".format(s=sector, e=sector+count-1)
            print_hdd("Reading sector " + s)
        data = []
        for i in range(sectors2dwords(count)):
            data.append(self.mem.data[sectors2dwords(sector)+i])
        return data

    def write_dma_callback(self, fis):
        self.wr_sector = fis.lba_lsb + (fis.lba_msb << 32)
        self.wr_end_sector = self.wr_sector + fis.count
        return [FIS_DMA_ACTIVATE_D2H()]

    def read_dma_callback(self, fis):
        self.rd_sector = fis.lba_lsb + (fis.lba_msb << 32)
        self.rd_end_sector = self.rd_sector + fis.count
        packets = []
        while self.rd_sector != self.rd_end_sector:
            count = min(self.rd_end_sector-self.rd_sector, (fis_max_dwords*4)//logical_sector_size)
            packet = self.read(self.rd_sector, count)
            packet.insert(0, 0)
            packets.append(FIS_DATA(packet, direction="D2H"))
            self.rd_sector += count
        packets.append(FIS_REG_D2H())
        return packets

    def data_callback(self, fis):
        self.write(self.wr_sector, fis.packet[1:])
        self.wr_sector += dwords2sectors(len(fis.packet[1:]))
        if self.wr_sector == self.wr_end_sector:
            return [FIS_REG_D2H()]
        else:
            return [FIS_DMA_ACTIVATE_D2H()]
