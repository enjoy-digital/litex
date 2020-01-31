# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import datetime
import enum
import json
import math
import os
import struct
import time

from collections import namedtuple

from migen import *

# Helpers ----------------------------------------------------------------------------------------

def mem_decoder(address, size=0x10000000):
    address &= ~0x80000000
    size = 2**log2_int(size, False)
    assert (address & (size - 1)) == 0
    address >>= 2 # bytes to words aligned
    size    >>= 2 # bytes to words aligned
    return lambda a: (a[log2_int(size):-1] == (address >> log2_int(size)))

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


class SoCMemRegion(namedtuple("SoCMemRegion", "origin length properties")):
    """
    >>> SoCMemRegion(-4, 10, "io")
    Traceback (most recent call last):
        ...
    TypeError: origin must be positive: -4
    >>> SoCMemRegion(3, 10, "random")
    Traceback (most recent call last):
        ...
    TypeError: Invalid property: random.
    >>> SoCMemRegion("hello", 20, "cached+linker")
    Traceback (most recent call last):
        ...
    TypeError: origin must be a int: 'hello'
    >>> SoCMemRegion(20, "hello", "cached+linker")
    Traceback (most recent call last):
        ...
    TypeError: length must be a int: 'hello'
    >>> a = SoCMemRegion(0, 10, "io")
    >>> a
    SoCMemRegion(origin=0, length=10, properties=<Properties.io: 1>)
    >>> a.io
    True
    >>> a.cached
    False
    >>> a.linker_only
    False
    >>> a = SoCMemRegion(20, 10, "cached+linker")
    >>> a
    SoCMemRegion(origin=20, length=10, properties=<Properties.linker_only|cached: 6>)
    >>> a.io
    False
    >>> a.cached
    True
    >>> a.linker_only
    True

    """

    class Properties(enum.IntFlag):
        io = enum.auto()
        cached = enum.auto()
        linker_only = enum.auto()

        @classmethod
        def from_string(cls, s):
            """
            >>> SoCMemRegion.Properties.from_string("io")
            <Properties.io: 1>
            >>> SoCMemRegion.Properties.from_string("io+linker")
            <Properties.linker_only|io: 5>
            >>> SoCMemRegion.Properties.from_string("io+cached")
            Traceback (most recent call last):
                ...
            TypeError: Can't both be io and cached!
            >>> SoCMemRegion.Properties.from_string("random")
            Traceback (most recent call last):
                ...
            TypeError: Invalid property: random.
            """
            r = cls(0)
            errors = []
            for p in s.split('+'):
                if p == "linker":
                    p = "linker_only"
                try:
                    r |= getattr(cls, p)
                except AttributeError:
                    errors.append("Invalid property: {}.".format(p))
            if cls.io in r and cls.cached in r:
                errors.append("Can't both be io and cached!")
            if errors:
                raise TypeError(" ".join(errors))
            return r

    def __new__(cls, origin, length, properties):
        if isinstance(properties, str):
            properties = SoCMemRegion.Properties.from_string(properties)
        if not isinstance(origin, int):
            raise TypeError("origin must be a int: {}".format(repr(origin)))
        if not isinstance(length, int):
            raise TypeError("length must be a int: {}".format(repr(length)))
        if origin < 0:
            raise TypeError("origin must be positive: {}".format(origin))
        return super().__new__(cls, origin, length, properties)

    def __init__(self, origin, length, properties):
        pass

    @property
    def io(self):
        return self.Properties.io in self.properties

    @property
    def cached(self):
        return self.Properties.cached in self.properties

    @property
    def linker_only(self):
        return self.Properties.linker_only in self.properties

    @property
    def start(self):
        return self.origin

    @property
    def end(self):
        """
        >>> a = SoCMemRegion(0x0, 8, "io")
        >>> a.start
        0
        >>> a.end
        8
        >>> b = SoCMemRegion(0x4, 8, "io")
        >>> b.start
        4
        >>> b.end
        12
        """
        return self.origin + self.length

    def overlaps(self, other):
        """Does this region overlap with another SoCMemRegion?

        >>> a = SoCMemRegion(0x0, 8, "io")
        >>> b = SoCMemRegion(0x4, 8, "io")
        >>> c = SoCMemRegion(0x8, 8, "io")
        >>> a.overlaps(b)
        True
        >>> b.overlaps(a)
        True
        >>> a.overlaps(c)
        False
        >>> c.overlaps(a)
        False
        >>> b.overlaps(c)
        True
        >>> c.overlaps(b)
        True
        """
        if self.origin == other.origin:
            return True
        elif self.origin < other.origin:
            first = self
            second = other
        elif self.origin > other.origin:
            first = other
            second = self

        return first.end > second.start

    def contains(self, other):
        """Does this region fully contain another SoCMemRegion?

        >>> a = SoCMemRegion(0x0, 8, "io")
        >>> b = SoCMemRegion(0x0, 8, "io")
        >>> a.contains(b), a.overlaps(b)
        (True, True)
        >>> b = SoCMemRegion(0x0, 9, "io")
        >>> a.contains(b), a.overlaps(b)
        (False, True)
        >>> b = SoCMemRegion(0x0, 4, "io")
        >>> a.contains(b), a.overlaps(b)
        (True, True)
        >>> b = SoCMemRegion(0x0, 4, "io")
        >>> a.contains(b), a.overlaps(b)
        (True, True)
        >>> b = SoCMemRegion(0x4, 4, "io")
        >>> a.contains(b), a.overlaps(b)
        (True, True)
        >>> b = SoCMemRegion(0x4, 5, "io")
        >>> a.contains(b), a.overlaps(b)
        (False, True)
        >>> b = SoCMemRegion(0x8, 4, "io")
        >>> a.contains(b), a.overlaps(b)
        (False, False)
        >>> a = SoCMemRegion(0x8, 8, "io")
        >>> b = SoCMemRegion(0x4, 4, "io")
        >>> a.contains(b), a.overlaps(b)
        (False, False)
        """
        if not self.overlaps(other):
            return False

        if self.length < other.length:
            return False

        if other.origin < self.origin:
            return False

        if other.end > self.end:
            return False

        return True

    @classmethod
    def merge(cls, regions):
        """Create a SoCMemRegion covering all the given regions.

        >>> a = SoCMemRegion(0x0, 4, "io")
        >>> b = SoCMemRegion(0x4, 4, "io")
        >>> c = SoCMemRegion(0x8, 4, "io")
        >>> SoCMemRegion.merge([a, b])
        SoCMemRegion(origin=0, length=8, properties=<Properties.io: 1>)
        >>> SoCMemRegion.merge([a, c])
        SoCMemRegion(origin=0, length=12, properties=<Properties.io: 1>)
        >>> SoCMemRegion.merge([b, c])
        SoCMemRegion(origin=4, length=8, properties=<Properties.io: 1>)
        >>> SoCMemRegion.merge([c, b])
        SoCMemRegion(origin=4, length=8, properties=<Properties.io: 1>)
        >>> d = SoCMemRegion(0x2, 4, "cached")
        >>> SoCMemRegion.merge([a, d])
        Traceback (most recent call last):
            ...
        TypeError: Can't merge regions with mismatch properties: SoCMemRegion(origin=0, length=4, properties=<Properties.io: 1>) SoCMemRegion(origin=2, length=4, properties=<Properties.cached: 2>)
        """
        assert len(regions) > 0, regions

        f = regions.pop(0)
        start = f.start
        end = f.end
        while len(regions) > 0:
            r = regions.pop(0)
            assert isinstance(r, cls)
            if f.properties != r.properties:
                raise TypeError(
                    "Can't merge regions with mismatch properties: {} {}".format(
                        f, r))
            start = min(start, r.start)
            end = max(end, r.end)
        return cls(start, end-start, f.properties)


class SoCCSRRegion(namedtuple("SoCCSRRegion", "origin busword obj")):
    pass


if __name__ == "__main__":
    import doctest
    doctest.testmod()
