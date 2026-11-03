#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# Host access to the board information peripheral, through a litex_server (RemoteClient), with the
# register map of regs.py.

from regs import WORD_BITS, REGS

def read(bus, name):
    """Read register name (most significant word first)."""
    address, words = REGS[name]
    value = 0
    for i in range(words):
        value = (value << WORD_BITS) | (bus.read(address + 4*i) & (2**WORD_BITS - 1))
    return value

def write(bus, name, value):
    """Write register name (most significant word first)."""
    address, words = REGS[name]
    for i in range(words):
        shift = WORD_BITS*(words - 1 - i)
        bus.write(address + 4*i, (value >> shift) & (2**WORD_BITS - 1))
