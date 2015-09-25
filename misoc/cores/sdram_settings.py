from math import ceil
from collections import namedtuple

from migen import *


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
    def __init__(self, clk_freq, memtype, geom_settings, timing_settings):
        self.clk_freq = clk_freq
        self.memtype = memtype
        self.geom_settings = GeomSettings(
            bankbits=log2_int(geom_settings["nbanks"]),
            rowbits=log2_int(geom_settings["nrows"]),
            colbits=log2_int(geom_settings["ncols"]),
        )
        self.timing_settings = TimingSettings(
            tRP=self.ns(timing_settings["tRP"]),
            tRCD=self.ns(timing_settings["tRCD"]),
            tWR=self.ns(timing_settings["tWR"]),
            tWTR=timing_settings["tWTR"],
            tREFI=self.ns(timing_settings["tREFI"], False),
            tRFC=self.ns(timing_settings["tRFC"])
        )

    def ns(self, t, margin=True):
        clk_period_ns = 1000000000/self.clk_freq
        if margin:
            t += clk_period_ns/2
        return ceil(t/clk_period_ns)


# SDR
class IS42S16160(SDRAMModule):
    geom_settings = {
        "nbanks": 4,
        "nrows":  8192,
        "ncols":  512
    }
    # Note: timings for -7 speedgrade (add support for others speedgrades)
    timing_settings = {
        "tRP":   20,
        "tRCD":  20,
        "tWR":   20,
        "tWTR":  2,
        "tREFI": 64*1000*1000/8192,
        "tRFC":  70
    }
    def __init__(self, clk_freq):
        SDRAMModule.__init__(self, clk_freq,  "SDR", self.geom_settings,
            self.timing_settings)


class MT48LC4M16(SDRAMModule):
    geom_settings = {
        "nbanks": 4,
        "nrows":  4096,
        "ncols":  256
    }
    timing_settings = {
        "tRP":   15,
        "tRCD":  15,
        "tWR":   14,
        "tWTR":  2,
        "tREFI": 64*1000*1000/4096,
        "tRFC":  66
    }
    def __init__(self, clk_freq):
        SDRAMModule.__init__(self, clk_freq, "SDR", self.geom_settings,
            self.timing_settings)


class AS4C16M16(SDRAMModule):
    geom_settings = {
        "nbanks": 4,
        "nrows":  8192,
        "ncols":  512
    }
    # Note: timings for -6 speedgrade (add support for others speedgrades)
    timing_settings = {
        "tRP":   18,
        "tRCD":  18,
        "tWR":   12,
        "tWTR":  2,
        "tREFI": 64*1000*1000/8192,
        "tRFC":  60
    }
    def __init__(self, clk_freq):
        SDRAMModule.__init__(self, clk_freq, "SDR", self.geom_settings,
            self.timing_settings)


# DDR
class MT46V32M16(SDRAMModule):
    geom_settings = {
        "nbanks": 4,
        "nrows":  8192,
        "ncols":  1024
    }
    timing_settings = {
        "tRP":   15,
        "tRCD":  15,
        "tWR":   15,
        "tWTR":  2,
        "tREFI": 64*1000*1000/8192,
        "tRFC":  70
    }
    def __init__(self, clk_freq):
        SDRAMModule.__init__(self, clk_freq, "DDR", self.geom_settings,
            self.timing_settings)


# LPDDR
class MT46H32M16(SDRAMModule):
    geom_settings = {
        "nbanks": 4,
        "nrows":  8192,
        "ncols":  1024
    }
    timing_settings = {
        "tRP":   15,
        "tRCD":  15,
        "tWR":   15,
        "tWTR":  2,
        "tREFI": 64*1000*1000/8192,
        "tRFC":  72
    }
    def __init__(self, clk_freq):
        SDRAMModule.__init__(self, clk_freq, "LPDDR", self.geom_settings,
            self.timing_settings)


# DDR2
class MT47H128M8(SDRAMModule):
    geom_settings = {
        "nbanks": 8,
        "nrows":  16384,
        "ncols":  1024
    }
    timing_settings = {
        "tRP":   15,
        "tRCD":  15,
        "tWR":   15,
        "tWTR":  2,
        "tREFI": 7800,
        "tRFC":  127.5
    }
    def __init__(self, clk_freq):
        SDRAMModule.__init__(self, clk_freq, "DDR2", self.geom_settings,
            self.timing_settings)


class P3R1GE4JGF(SDRAMModule):
    geom_settings = {
        "nbanks": 8,
        "nrows": 8192,
        "ncols": 1024
    }
    timing_settings = {
        "tRP":   12.5,
        "tRCD":  12.5,
        "tWR":   15,
        "tWTR":  3,
        "tREFI": 7800,
        "tRFC":  127.5,
    }

    def __init__(self, clk_freq):
        SDRAMModule.__init__(self, clk_freq, "DDR2", self.geom_settings,
            self.timing_settings)


# DDR3
class MT8JTF12864(SDRAMModule):
    geom_settings = {
        "nbanks": 8,
        "nrows":  16384,
        "ncols":  1024
    }
    timing_settings = {
        "tRP":   15,
        "tRCD":  15,
        "tWR":   15,
        "tWTR":  2,
        "tREFI": 7800,
        "tRFC":  70
    }
    def __init__(self, clk_freq):
        SDRAMModule.__init__(self, clk_freq, "DDR3", self.geom_settings,
            self.timing_settings)


class MT41J128M16(SDRAMModule):
    geom_settings = {
        "nbanks": 8,
        "nrows":  16384,
        "ncols":  1024,
    }
    timing_settings = {
        "tRP":   15,
        "tRCD":  15,
        "tWR":   15,
        "tWTR":  3,
        "tREFI": 64*1000*1000/16384,
        "tRFC":  260,
    }

    def __init__(self, clk_freq):
        SDRAMModule.__init__(self, clk_freq, "DDR3", self.geom_settings,
            self.timing_settings)
