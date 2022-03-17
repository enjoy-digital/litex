#
# This file is part of LiteX.
#
# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import math
import json
import time
import struct
import datetime

from migen import *

# Helpers ----------------------------------------------------------------------------------------

def get_version(with_time=True):
    fmt = "%Y-%m-%d %H:%M:%S" if with_time else "%Y-%m-%d"
    return datetime.datetime.fromtimestamp(time.time()).strftime(fmt)

def get_mem_regions(filename_or_regions, offset):
    if isinstance(filename_or_regions, dict):
        regions = filename_or_regions
    else:
        filename = filename_or_regions
        if not os.path.isfile(filename):
            raise OSError(f"Unable to find {filename} memory content file.")
        _, ext = os.path.splitext(filename)
        if ext == ".json":
            f = open(filename, "r")
            _regions = json.load(f)
            # .json
            regions = dict()
            for k, v in _regions.items():
                regions[os.path.join(os.path.dirname(filename), k)] = v
            f.close()
        else:
            regions = {filename: f"{offset:08x}"}
    return regions

def get_mem_data(filename_or_regions, endianness="big", mem_size=None, offset=0):
    # Create memory regions.
    regions = get_mem_regions(filename_or_regions, offset)

    # Determine data_size.
    data_size = 0
    for filename, base in regions.items():
        if not os.path.isfile(filename):
            raise OSError(f"Unable to find {filename} memory content file.")
        data_size = max(int(base, 16) + os.path.getsize(filename) - offset, data_size)
    assert data_size > 0
    if mem_size is not None:
        assert data_size < mem_size, (
            "file is too big: {}/{} bytes".format(
             data_size, mem_size))

    # Fill data.
    data = [0]*math.ceil(data_size/4)
    for filename, base in regions.items():
        base = int(base, 16)
        with open(filename, "rb") as f:
            i = 0
            while True:
                w = f.read(4)
                if not w:
                    break
                if len(w) != 4:
                    for _ in range(len(w), 4):
                        w += b'\x00'
                unpack_order = {
                    "little": "<I",
                    "big":    ">I"
                }[endianness]
                data[(base - offset)//4 + i] = struct.unpack(unpack_order, w)[0]
                i += 1
    return data

def get_boot_address(filename_or_regions, offset=0):
    # Create memory regions.
    regions = get_mem_regions(filename_or_regions, offset)

    print(regions)

    # Boot on last region.
    filename, base = regions.popitem()
    return int(base, 0)
