from __future__ import annotations

import random
from enum import Enum, auto
from typing import Optional


class Status(Enum):
    OK = auto()
    DECODE_ERROR = auto()
    SLAVE_ERROR = auto()


class MemoryReferenceModel:
    """
    Simple byte-addressable memory model with per-byte is known tracking.

    - Has word access with little-endian packing/unpacking
    - Writes can be masked with a byte-enable bitmask (bit i -> byte i within the word)
    - If rng is provided, memory is pre-initialized with random bytes
    - If rng is None, memory is zero-initialized and known is all-zero
    """

    def __init__(self, size_bytes: int, word_bytes: int, rng: Optional[random.Random] = None):
        self.size_bytes = size_bytes
        self.word_bytes = word_bytes
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be >= 0")
        if self.word_bytes <= 0:
            raise ValueError("word_bytes must be > 0")

        self.mem = bytearray(self.size_bytes)
        self.known = bytearray(self.size_bytes)

        if rng is not None:
            for i in range(self.size_bytes):
                self.mem[i] = rng.randrange(256)
                self.known[i] = 1

    def read_word_le(self, off: int, word_bytes: Optional[int] = None) -> int:
        n = self.word_bytes if word_bytes is None else word_bytes
        if n <= 0:
            raise ValueError("word_bytes must be > 0")
        if off < 0 or off + n > self.size_bytes:
            raise IndexError("read out of bounds")

        v = 0
        for i in range(n):
            v |= (self.mem[off + i] & 0xFF) << (8 * i)
        return v

    def write_word_le(self, off: int, data: int, byte_en: int, word_bytes: Optional[int] = None) -> None:
        n = self.word_bytes if word_bytes is None else word_bytes
        if n <= 0:
            raise ValueError("word_bytes must be > 0")
        if off < 0 or off + n > self.size_bytes:
            raise IndexError("write out of bounds")

        for i in range(n):
            if (byte_en >> i) & 1:
                self.mem[off + i] = (data >> (8 * i)) & 0xFF
                self.known[off + i] = 1

    def is_known(self, off: int, size: int) -> bool:
        if size < 0:
            raise ValueError("size must be >= 0")
        if off < 0 or off + size > self.size_bytes:
            raise IndexError("range out of bounds")
        return all(self.known[off:off+size])

    def clear_known(self, off: int = 0, size: Optional[int] = None) -> None:
        if size is None:
            size = self.size_bytes - off
        if size < 0:
            raise ValueError("size must be >= 0")
        if off < 0 or off + size > self.size_bytes:
            raise IndexError("range out of bounds")
        self.known[off:off+size] = b"\x00" * size

    def expected_write(self, off: int, data: int, size_bytes: int, byte_en: int) -> Status:
        if off < 0 or off + size_bytes > self.size_bytes:
            return Status.DECODE_ERROR
        # apply + always OK for memory-like
        self.write_word_le(off, data, byte_en, size_bytes)
        return Status.OK

    def expected_read(self, off: int, size_bytes: int) -> tuple[Status, Optional[int], Optional[int]]:
        if off < 0 or off + size_bytes > self.size_bytes:
            return (Status.DECODE_ERROR, None, None)
        data = self.read_word_le(off, size_bytes)
        mask = (1 << (8 * size_bytes)) - 1
        return (Status.OK, data, mask)
