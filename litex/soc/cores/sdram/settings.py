from math import ceil
from collections import namedtuple

from litex.gen import *


PhySettingsT = namedtuple("PhySettings", "memtype dfi_databits nphases rdphase wrphase rdcmdphase wrcmdphase cl cwl read_latency write_latency")
def PhySettings(memtype, dfi_databits, nphases, rdphase, wrphase, rdcmdphase, wrcmdphase, cl, read_latency, write_latency, cwl=0):
    return PhySettingsT(memtype, dfi_databits, nphases, rdphase, wrphase, rdcmdphase, wrcmdphase, cl, cwl, read_latency, write_latency)

GeomSettingsT = namedtuple("_GeomSettings", "bankbits rowbits colbits addressbits")
def GeomSettings(bankbits, rowbits, colbits):
    return GeomSettingsT(bankbits, rowbits, colbits, max(rowbits, colbits))

TimingSettings = namedtuple("TimingSettings", "tRP tRCD tWR tWTR tREFI tRFC")


# TODO:
#   Try to share the maximum information we can between modules:
#    - ex: MT46V32M16 and MT46H32M16 are almost identical (V=DDR, H=LPDDR)
#    - Modules can have different configuration:
#        MT8JTF12864 (1GB), MT8JTF25664 (2GB)
#      but share all others informations, try to create an unique module for all
#      configurations.
#    - Modules can have different speedgrades, add support for it (and also add
#      a check to verify clk_freq is in the supported range)


class SDRAMModule:
    def __init__(self, clk_freq, rate):
        self.clk_freq = clk_freq
        self.rate = rate
        self.geom_settings = GeomSettings(
            bankbits=log2_int(self.nbanks),
            rowbits=log2_int(self.nrows),
            colbits=log2_int(self.ncols),
        )
        self.timing_settings = TimingSettings(
            tRP=self.ns(self.tRP),
            tRCD=self.ns(self.tRCD),
            tWR=self.ns(self.tWR),
            tWTR=self.tWTR,
            tREFI=self.ns(self.tREFI, False),
            tRFC=self.ns(self.tRFC)
        )

    def ns(self, t, margin=True):
        clk_period_ns = 1000000000/self.clk_freq
        if margin:
            margins = {
                "1:1" : 0,
                "1:2" : clk_period_ns/2,
                "1:4" : 3*clk_period_ns/4
            }
            t += margins[self.rate]
        return ceil(t/clk_period_ns)


# SDR
class IS42S16160(SDRAMModule):
    memtype = "SDR"
    # geometry
    nbanks = 4
    nrows  = 8192
    ncols  = 512
    # timings (-7 speedgrade)
    tRP   = 20
    tRCD  = 20
    tWR   = 20
    tWTR  = 2
    tREFI = 64*1000*1000/8192
    tRFC  = 70


class MT48LC4M16(SDRAMModule):
    memtype = "SDR"
    # geometry
    nbanks = 4
    nrows  = 4096
    ncols  = 256
    # timings (-7 speedgrade)
    tRP   = 15
    tRCD  = 15
    tWR   = 14
    tWTR  = 2
    tREFI = 64*1000*1000/4096
    tRFC  = 66


class AS4C16M16(SDRAMModule):
    memtype = "SDR"
    # geometry
    nbanks = 4
    nrows  = 8192
    ncols  = 512
    # timings (-6 speedgrade)
    tRP   = 18
    tRCD  = 18
    tWR   = 12
    tWTR  = 2
    tREFI = 64*1000*1000/8192
    tRFC  = 60


# DDR
class MT46V32M16(SDRAMModule):
    memtype = "DDR"
    # geometry
    nbanks = 4
    nrows  = 8192
    ncols  = 1024
    # timings (-6 speedgrade)
    tRP   = 15
    tRCD  = 15
    tWR   = 15
    tWTR  = 2
    tREFI = 64*1000*1000/8192
    tRFC  = 70


# LPDDR
class MT46H32M16(SDRAMModule):
    memtype = "LPDDR"
    # geometry
    nbanks = 4
    nrows  = 8192
    ncols  = 1024
    # timings
    tRP   = 15
    tRCD  = 15
    tWR   = 15
    tWTR  = 2
    tREFI = 64*1000*1000/8192
    tRFC  = 72


# DDR2
class MT47H128M8(SDRAMModule):
    memtype = "DDR2"
    # geometry
    nbanks = 8
    nrows  = 16384
    ncols  = 1024
    # timings
    tRP   = 15
    tRCD  = 15
    tWR   = 15
    tWTR  = 2
    tREFI = 7800
    tRFC  = 127.5


class P3R1GE4JGF(SDRAMModule):
    memtype = "DDR2"
    # geometry
    nbanks = 8
    nrows  = 8192
    ncols  = 1024
    # timings
    tRP   = 12.5
    tRCD  = 12.5
    tWR   = 15
    tWTR  = 3
    tREFI = 7800
    tRFC  = 127.5


# DDR3
class MT8JTF12864(SDRAMModule):
    memtype = "DDR3"
    # geometry
    nbanks = 8
    nrows  = 16384
    ncols  = 1024
    # timings
    tRP   = 15
    tRCD  = 15
    tWR   = 15
    tWTR  = 2
    tREFI = 7800
    tRFC  = 70


class MT41J128M16(SDRAMModule):
    memtype = "DDR3"
    # geometry
    nbanks = 8
    nrows  = 16384
    ncols  = 1024
    # timings
    tRP   = 15
    tRCD  = 15
    tWR   = 15
    tWTR  = 3
    tREFI = 64*1000*1000/16384
    tRFC  = 260
