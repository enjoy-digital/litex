# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import os
import math
import json
import time
import struct
import datetime

from migen import *

# Helpers ----------------------------------------------------------------------------------------

def mem_decoder(address, size=0x10000000):
    size = 2**log2_int(size, False)
    assert (address & (size - 1)) == 0
    address >>= 2 # bytes to words aligned
    size    >>= 2 # bytes to words aligned
    return lambda a: (a[log2_int(size):] == (address >> log2_int(size)))

def get_version(with_time=True):
    if with_time:
        return datetime.datetime.fromtimestamp(
                time.time()).strftime("%Y-%m-%d %H:%M:%S")
    else:
        return datetime.datetime.fromtimestamp(
                time.time()).strftime("%Y-%m-%d")

def get_mem_data(filename_or_regions, endianness="big", mem_size=None):
    # create memory regions
    if isinstance(filename_or_regions, dict):
        regions = filename_or_regions
    else:
        filename = filename_or_regions
        _, ext = os.path.splitext(filename)
        if ext == ".json":
            f = open(filename, "r")
            regions = json.load(f)
            f.close()
        else:
            regions = {filename: "0x00000000"}

    # determine data_size
    data_size = 0
    for filename, base in regions.items():
        data_size = max(int(base, 16) + os.path.getsize(filename), data_size)
    assert data_size > 0
    if mem_size is not None:
        assert data_size < mem_size, (
            "file is too big: {}/{} bytes".format(
             data_size, mem_size))

    # fill data
    data = [0]*math.ceil(data_size/4)
    for filename, base in regions.items():
        with open(filename, "rb") as f:
            i = 0
            while True:
                w = f.read(4)
                if not w:
                    break
                if len(w) != 4:
                    for _ in range(len(w), 4):
                        w += b'\x00'
                if endianness == "little":
                    data[int(base, 16)//4 + i] = struct.unpack("<I", w)[0]
                else:
                    data[int(base, 16)//4 + i] = struct.unpack(">I", w)[0]
                i += 1
    return data

# SoC primitives -----------------------------------------------------------------------------------

def SoCConstant(value):
    return value

class SoCMemRegion:
    def __init__(self, origin, length, type):
        assert type in ["cached", "io", "cached+linker", "io+linker"]
        self.origin = origin
        self.length = length
        self.type   = type

    def __str__(self):
        return "<SoCMemRegion 0x{:x} 0x{:x} {}>".format(
            self.origin, self.length, self.type)


class SoCCSRRegion:
    def __init__(self, origin, busword, obj):
        self.origin  = origin
        self.busword = busword
        self.obj     = obj
