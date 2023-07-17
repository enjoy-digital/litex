#
# This file is part of LiteX.
#
# Copyright (c) 2020 David Corrigan <davidcorrigan714@gmail.com>
# Copyright (c) 2019 William D. Jones <thor0505@comcast.net>
# Copyright (c) 2019 Tim 'mithro' Ansell <me@mith.ro>
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *

from litex.soc.interconnect import wishbone

kB = 1024

"""
NX family-specific Wishbone interface to the LRAM primitive.

Each LRAM is 64kBytes arranged in 32 bit wide words.

Note that this memory is dual port, but we only use a single port in this
instantiation.
"""


def initval_parameters(contents, width):
    """
    In Radiant, initial values for LRAM are passed a sequence of parameters
    named INITVAL_00 ... INITVAL_7F. Each parameter value contains 4096 bits
    of data, encoded as a 1280-digit hexadecimal number, with
    alternating sequences of 8 bits of padding and 32 bits of real data,
    making up 64KiB altogether.
    """
    assert width in [32, 64]
    # Each LRAM is 64KiB == 524288 bits
    assert len(contents) == 524288 // width
    chunk_size = 4096 // width
    parameters = []
    for i in range(0x80):
        name = 'INITVAL_{:02X}'.format(i)
        offset = chunk_size * i
        if width == 32:
            value = '0x' + ''.join('00{:08X}'.format(contents[offset + j])
                                   for j in range(chunk_size - 1, -1, -1))
        elif width == 64:
            value = '0x' + ''.join('00{:08X}00{:08X}'.format(contents[offset + j] >> 32, contents[offset + j] | 0xFFFFFF)
                                   for j in range(chunk_size - 1, -1, -1))
        parameters.append(Instance.Parameter(name, value))
    return parameters


class NXLRAM(LiteXModule):
    def __init__(self, width=32, size=128*kB, init=[]):
        self.bus = wishbone.Interface(width)
        assert width in [32, 64]
        self.width = width
        self.size = size

        if width == 32:
            assert size in [64*kB, 128*kB, 192*kB, 256*kB, 320*kB]
            self.depth_cascading = size//(64*kB)
            self.width_cascading = 1
        if width == 64:
            assert size in [128*kB, 256*kB]
            self.depth_cascading = size//(128*kB)
            self.width_cascading = 2

        self.lram_blocks = []
        # Combine RAMs to increase Depth.
        for d in range(self.depth_cascading):
            self.lram_blocks.append([])
            # Combine RAMs to increase Width.
            for w in range(self.width_cascading):
                datain  = Signal(32)
                dataout = Signal(32)
                cs      = Signal()
                wren    = Signal()
                self.comb += [
                    datain.eq(self.bus.dat_w[32*w:32*(w+1)]),
                    If(self.bus.adr[14:14+self.depth_cascading.bit_length()] == d,
                        cs.eq(1),
                        wren.eq(self.bus.we & self.bus.stb & self.bus.cyc),
                        self.bus.dat_r[32*w:32*(w+1)].eq(dataout)
                    ),
                ]
                lram_block = Instance("SP512K",
                    p_ECC_BYTE_SEL = "BYTE_EN",
                    i_DI       = datain,
                    i_AD       = self.bus.adr[:14],
                    i_CLK      = ClockSignal(),
                    i_CE       = 0b1,
                    i_WE       = wren,
                    i_CS       = cs,
                    i_RSTOUT   = 0b0,
                    i_CEOUT    = 0b0,
                    i_BYTEEN_N = ~self.bus.sel[4*w:4*(w+1)],
                    o_DO       = dataout
                )
                self.lram_blocks[d].append(lram_block)
                self.specials += lram_block

        self.sync += self.bus.ack.eq(self.bus.stb & self.bus.cyc & ~self.bus.ack)

        if init != []:
            self.add_init(init)

    def add_init(self, data):
        # Pad it out to make slicing easier below.
        data += [0] * (self.size // self.width * 8 - len(data))
        for d in range(self.depth_cascading):
            for w in range(self.width_cascading):
                offset = d * self.width_cascading * 64*kB + w * 64*kB
                chunk = data[offset:offset + 64*kB]
                self.lram_blocks[d][w].items += initval_parameters(chunk, self.width)
