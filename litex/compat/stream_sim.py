####################################################################################################
#       DISCLAIMER: Provides retro-compatibility layer for stream_sim based designs.
#              Will soon no longer work, please don't use in new designs.
####################################################################################################

#
# This file is part of LiteX.
#
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import random
import math
from copy import deepcopy

from migen import *

from litex.soc.interconnect import stream

__all__ = [
    "print_with_prefix",
    "seed_to_data",
    "split_bytes",
    "merge_bytes",
    "get_field_data",
    "comp",
    "check",
    "randn",
    "Packet",
    "PacketStreamer",
    "PacketLogger",
    "Randomizer"
]

def print_with_prefix(s, prefix=""):
    if not isinstance(s, str):
        s = s.__repr__()
    s = s.split("\n")
    for l in s:
        print(prefix + l)


def seed_to_data(seed, random=True):
    if random:
        return (seed * 0x31415979 + 1) & 0xffffffff
    else:
        return seed


def split_bytes(v, n, endianness="big"):
    r = []
    r_bytes = v.to_bytes(n, byteorder=endianness)
    for byte in r_bytes:
        r.append(int(byte))
    return r


def merge_bytes(b, endianness="big"):
    return int.from_bytes(bytes(b), endianness)


def get_field_data(field, datas):
    v = merge_bytes(datas[field.byte:field.byte+math.ceil(field.width/8)])
    return (v >> field.offset) & (2**field.width-1)


def comp(p1, p2):
    r = True
    for x, y in zip(p1, p2):
        if x != y:
            r = False
    return r


def check(p1, p2):
    p1 = deepcopy(p1)
    p2 = deepcopy(p2)
    if isinstance(p1, int):
        return 0, 1, int(p1 != p2)
    else:
        if len(p1) >= len(p2):
            ref, res = p1, p2
        else:
            ref, res = p2, p1
        shift = 0
        while((ref[0] != res[0]) and (len(res) > 1)):
            res.pop(0)
            shift += 1
        length = min(len(ref), len(res))
        errors = 0
        for i in range(length):
            if ref.pop(0) != res.pop(0):
                errors += 1
        return shift, length, errors


def randn(max_n):
    return random.randint(0, max_n-1)


class Packet(list):
    def __init__(self, init=[]):
        self.ongoing = False
        self.done = False
        for data in init:
            self.append(data)


class PacketStreamer(Module):
    def __init__(self, description, last_be=None, packet_cls=Packet):
        self.source = stream.Endpoint(description)
        self.last_be = last_be

        # # #

        self.packets = []
        self.packet = packet_cls()
        self.packet.done = True

    def send(self, packet):
        packet = deepcopy(packet)
        self.packets.append(packet)
        return packet

    def send_blocking(self, packet):
        packet = self.send(packet)
        while not packet.done:
            yield

    @passive
    def generator(self):
        while True:
            if len(self.packets) and self.packet.done:
                self.packet = self.packets.pop(0)
            if not self.packet.ongoing and not self.packet.done:
                yield self.source.valid.eq(1)
                yield self.source.data.eq(self.packet.pop(0))
                self.packet.ongoing = True
            elif (yield self.source.valid) and (yield self.source.ready):
                yield self.source.last.eq(len(self.packet) == 1)
                if self.last_be is not None:
                    yield self.source.last_be.eq(self.last_be & (len(self.packet) == 1))
                if len(self.packet):
                    yield self.source.valid.eq(1)
                    yield self.source.data.eq(self.packet.pop(0))
                else:
                    self.packet.done = True
                    yield self.source.valid.eq(0)
            yield


class PacketLogger(Module):
    def __init__(self, description, packet_cls=Packet):
        self.sink = stream.Endpoint(description)

        # # #

        self.packet_cls = packet_cls
        self.packet = packet_cls()
        self.first = True

    def receive(self, length=None):
        self.packet.done = False
        if length is None:
            while not self.packet.done:
                yield
        else:
            while length > len(self.packet):
                yield

    @passive
    def generator(self):
        while True:
            yield self.sink.ready.eq(1)
            if (yield self.sink.valid):
                if self.first:
                    self.packet = self.packet_cls()
                    self.first = False
                self.packet.append((yield self.sink.data))
                if (yield self.sink.last):
                    self.packet.done = True
                    self.first = True
            yield


class Randomizer(Module):
    def __init__(self, description, level=0):
        self.level = level

        self.sink = stream.Endpoint(description)
        self.source = stream.Endpoint(description)

        self.ce = Signal(reset=1)

        self.comb += \
            If(self.ce,
                self.sink.connect(self.source)
            ).Else(
                self.source.valid.eq(0),
                self.sink.ready.eq(0),
            )

    @passive
    def generator(self):
        while True:
            n = randn(100)
            if n < self.level:
                yield self.ce.eq(0)
            else:
                yield self.ce.eq(1)
            yield
