from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.test.common import *

from misoclib.mem.litesata.test.model.transport import FIS_REG_H2D, FIS_DATA


class CommandLayer(Module):
    def __init__(self, transport):
        self.transport = transport
        self.transport.set_command(self)

        self.hdd = None
        self.n = None

    def set_hdd(self, hdd):
        self.hdd = hdd
        self.transport.n = hdd.n
        self.transport.link.n = hdd.n

    def callback(self, fis):
        resp = None
        if isinstance(fis, FIS_REG_H2D):
            if fis.command == regs["WRITE_DMA_EXT"]:
                resp = self.hdd.write_dma_callback(fis)
            elif fis.command == regs["READ_DMA_EXT"]:
                resp = self.hdd.read_dma_callback(fis)
        elif isinstance(fis, FIS_DATA):
            resp = self.hdd.data_callback(fis)

        if resp is not None:
            for packet in resp:
                self.transport.send(packet)
