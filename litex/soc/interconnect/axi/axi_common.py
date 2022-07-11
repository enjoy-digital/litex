#
# This file is part of LiteX.
#
# Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

"""AXI4-Full/Lite support for LiteX"""

from migen import *
from migen.genlib import roundrobin
from migen.genlib.misc import WaitTimer

from litex.soc.interconnect import stream
from litex.build.generic_platform import *

# AXI Constants ------------------------------------------------------------------------------------

BURST_FIXED    = 0b00
BURST_INCR     = 0b01
BURST_WRAP     = 0b10
BURST_RESERVED = 0b11

RESP_OKAY      = 0b00
RESP_EXOKAY    = 0b01
RESP_SLVERR    = 0b10
RESP_DECERR    = 0b11

AXSIZE = {
     1 : 0b000,
     2 : 0b001,
     4 : 0b010,
     8 : 0b011,
    16 : 0b100,
    32 : 0b110,
    64 : 0b111,
}

# AXI Connection Helpers ---------------------------------------------------------------------------

def connect_axi(master, slave, keep=None, omit=None):
    channel_modes = {
        "aw": "master",
        "w" : "master",
        "b" : "slave",
        "ar": "master",
        "r" : "slave",
    }
    r = []
    for channel, mode in channel_modes.items():
        if mode == "master":
            m, s = getattr(master, channel), getattr(slave, channel)
        else:
            s, m = getattr(master, channel), getattr(slave, channel)
        r.extend(m.connect(s, keep=keep, omit=omit))
    return r

def connect_to_pads(bus, pads, mode="master", axi_full=False):
    assert mode in ["slave", "master"]
    r = []
    def swap_mode(mode): return "master" if mode == "slave" else "slave"
    channel_modes = {
        "aw": mode,
        "w" : mode,
        "b" : swap_mode(mode),
        "ar": mode,
        "r" : swap_mode(mode),
    }
    for channel, mode in channel_modes.items():
        ch = getattr(bus, channel)
        sig_list = [("valid", 1)] + ch.description.payload_layout
        if channel in ["w", "r"] and axi_full:
            sig_list += [("last",  1)]
        for name, width in sig_list:
            sig  = getattr(ch, name)
            pad  = getattr(pads, channel + name)
            if mode == "master":
                r.append(pad.eq(sig))
            else:
                r.append(sig.eq(pad))
        for name, width in [("ready", 1)]:
            sig  = getattr(ch, name)
            pad  = getattr(pads, channel + name)
            if mode == "master":
                r.append(sig.eq(pad))
            else:
                r.append(pad.eq(sig))
    return r

def axi_layout_flat(axi):
    # yields tuples (channel, name, direction)
    def get_dir(channel, direction):
        if channel in ["b", "r"]:
            return {DIR_M_TO_S: DIR_S_TO_M, DIR_S_TO_M: DIR_M_TO_S}[direction]
        return direction
    for ch in ["aw", "w", "b", "ar", "r"]:
        channel = getattr(axi, ch)
        for group in channel.layout:
            if len(group) == 3:
                name, _, direction = group
                yield ch, name, get_dir(ch, direction)
            else:
                _, subgroups = group
                for subgroup in subgroups:
                    name, _, direction = subgroup
                    yield ch, name, get_dir(ch, direction)
