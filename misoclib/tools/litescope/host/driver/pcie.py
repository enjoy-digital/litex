import string
import mmap
from misoclib.tools.litescope.host.driver.reg import *


class LiteScopePCIeDriver:
    def __init__(self, bar, bar_size, addrmap=None, busword=8, debug=False):
        self.bar = bar
        self.bar_size = bar_size
        self.debug = debug
        self.f = None
        self.mmap = None
        self.regs = build_map(addrmap, busword, self.read, self.write)

    def open(self):
        self.f = open(self.bar, "r+b")
        self.f.flush()
        self.mmap = mmap.mmap(self.f.fileno(), self.bar_size)

    def close(self):
        self.mmap.close()
        self.f.close()

    def read(self, addr, burst_length=1):
        datas = []
        for i in range(burst_length):
            self.mmap.seek(addr + 4*i)
            dat = self.mmap.read(4)
            val = dat[3] << 24
            val |= dat[2] << 16
            val |= dat[1] << 8
            val |= dat[0] << 0
            if self.debug:
                print("RD {:08X} @ {:08X}".format(val, addr + 4*i))
            datas.append(val)
        if burst_length == 1:
            return datas[0]
        else:
            return datas

    def write(self, addr, data):
        if isinstance(data, list):
            burst_length = len(data)
        else:
            burst_length = 1
            data = [data]

        for i, dat in enumerate(data):
            dat_bytes = [0, 0, 0, 0]
            dat_bytes[3] = (dat >> 24) & 0xff
            dat_bytes[2] = (dat >> 16) & 0xff
            dat_bytes[1] = (dat >>  8) & 0xff
            dat_bytes[0] = (dat >>  0) & 0xff
            self.mmap[addr + 4*i:addr + 4*(i+1)] = bytes(dat_bytes)
            if self.debug:
                print("WR {:08X} @ {:08X}".format(dat, (addr + i)*4))
