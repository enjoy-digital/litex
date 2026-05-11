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

from litex.soc.cores.ram.common import check_value, split_init_data
from litex.soc.interconnect import wishbone

kB = 1024
NX_LRAM_SIZE       = 64*kB
NX_LRAM_DATA_WIDTH = 32
NX_INITVAL_BITS    = 4096
NX_INITVAL_COUNT   = 0x80

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
    check_value("NX LRAM init width", width, [32, 64])
    # Each LRAM is 64KiB == 524288 bits
    if len(contents) != NX_LRAM_SIZE*8//width:
        raise ValueError(
            "Invalid NX LRAM init length for {}-bit width: {}.".format(width, len(contents)))
    chunk_size = NX_INITVAL_BITS//width
    parameters = []
    for i in range(NX_INITVAL_COUNT):
        name = 'INITVAL_{:02X}'.format(i)
        offset = chunk_size * i
        if width == 32:
            value = '0x' + ''.join('00{:08X}'.format(contents[offset + j] & 0xffffffff)
                                   for j in range(chunk_size - 1, -1, -1))
        elif width == 64:
            value = '0x' + ''.join('00{:08X}00{:08X}'.format(
                                    (contents[offset + j] >> 32) & 0xffffffff,
                                    contents[offset + j] & 0xffffffff)
                                   for j in range(chunk_size - 1, -1, -1))
        parameters.append(Instance.Parameter(name, value))
    return parameters


class NXLRAM(LiteXModule):
    def __init__(self, width=32, size=128*kB, init=None):
        self.bus = wishbone.Interface(data_width=width, address_width=32, addressing="word")
        check_value("NX LRAM width", width, [32, 64])
        self.width = width
        self.size = size

        if width == 32:
            check_value("NX LRAM size for 32-bit width", size,
                [64*kB, 128*kB, 192*kB, 256*kB, 320*kB])
            self.depth_cascading = size//NX_LRAM_SIZE
            self.width_cascading = 1
        if width == 64:
            check_value("NX LRAM size for 64-bit width", size, [128*kB, 256*kB])
            self.depth_cascading = size//(2*NX_LRAM_SIZE)
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
                        self.bus.dat_r[32*w:32*(w+1)].eq(dataout),
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

        # The SoC memory region is expected to bound accesses. Out-of-range
        # wrapper accesses still acknowledge, but do not select an LRAM block.
        self.sync += self.bus.ack.eq(self.bus.stb & self.bus.cyc & ~self.bus.ack)

        if init is not None:
            self.add_init(init)

    def add_init(self, data):
        # Split user words into physical 32-bit LRAM blocks. Depth cascading
        # advances to the next 64KiB block, width cascading selects word lanes.
        chunks = split_init_data(
            data             = data,
            data_width       = self.width,
            block_data_width = NX_LRAM_DATA_WIDTH,
            block_words      = NX_LRAM_SIZE//(NX_LRAM_DATA_WIDTH//8),
            depth_cascading  = self.depth_cascading,
            width_cascading  = self.width_cascading,
        )
        for d, depth_chunks in enumerate(chunks):
            for w, chunk in enumerate(depth_chunks):
                self.lram_blocks[d][w].items += initval_parameters(chunk, 32)
