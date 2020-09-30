#
# This file is part of LiteX.
#
# Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# Copyright (c) 2014-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2013-2014 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2015-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause


from migen import *
from migen.genlib.misc import timeline
from migen.fhdl.specials import Tristate

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import *
from litex.soc.cores.spi import SPIMaster

# SpiFlash Quad/Dual/Single (memory-mapped) --------------------------------------------------------

_FAST_READ = 0x0b
_DIOFR     = 0xbb
_QIOFR     = 0xeb
_QIOPP     = 0x12

def _format_cmd(cmd, spi_width):
    """
    `cmd` is the read instruction. Since everything is transmitted on all
    dq lines (cmd, adr and data), extend/interleave cmd to full pads.dq
    width even if dq1-dq3 are don't care during the command phase:
    For example, for N25Q128, 0xeb is the quad i/o fast read, and
    extended to 4 bits (dq1,dq2,dq3 high) is: 0xfffefeff
    """
    c = 2**(8*spi_width)-1
    for b in range(8):
        if not (cmd>>b)%2:
            c &= ~(1<<(b*spi_width))
    return c

def accumulate_timeline_deltas(seq):
    t, tseq = 0, []
    for dt, a in seq:
        tseq.append((t, a))
        t += dt
    return tseq

class SpiFlashCommon(Module):
    def __init__(self, pads):
        if not hasattr(pads, "clk"):
            self.clk_primitive_needed = True
            self.clk_primitive_registered = False
            pads.clk = Signal()
        self.pads = pads

    def add_clk_primitive(self, device):
        if not hasattr(self, "clk_primitive_needed"):
            return
        # Xilinx 7-series
        if device[:3] == "xc7":
            self.specials += Instance("STARTUPE2",
                i_CLK=0,
                i_GSR=0,
                i_GTS=0,
                i_KEYCLEARB=0,
                i_PACK=0,
                i_USRCCLKO=self.pads.clk,
                i_USRCCLKTS=0,
                i_USRDONEO=1,
                i_USRDONETS=1)
        # Lattice ECP5
        elif device[:4] == "LFE5":
            self.specials += Instance("USRMCLK",
                i_USRMCLKI=self.pads.clk,
                i_USRMCLKTS=0)
        else:
            raise NotImplementedError
        self.clk_primitive_registered = True

    def do_finalize(self):
        if hasattr(self, "clk_primitive_needed"):
            assert self.clk_primitive_registered == True

class SpiFlashDualQuad(SpiFlashCommon, AutoCSR):
    def __init__(self, pads, dummy=15, div=2, with_bitbang=True, endianness="big"):
        """
        Simple SPI flash.
        Supports multi-bit pseudo-parallel reads (aka Dual or Quad I/O Fast
        Read). Only supports mode3 (cpol=1, cpha=1).
        """
        SpiFlashCommon.__init__(self, pads)
        self.bus = bus = wishbone.Interface()
        spi_width = len(pads.dq)
        assert spi_width >= 2

        if with_bitbang:
            self.bitbang = CSRStorage(4, reset_less=True, fields=[
                CSRField("mosi", description="Output value for MOSI pin, valid whenever ``dir`` is ``0``."),
                CSRField("clk", description="Output value for SPI CLK pin."),
                CSRField("cs_n", description="Output value for SPI CSn pin."),
                CSRField("dir", description="Sets the direction for *ALL* SPI data pins except CLK and CSn.", values=[
                    ("0", "OUT", "SPI pins are all output"),
                    ("1", "IN", "SPI pins are all input"),
                ])
            ], description="""
                Bitbang controls for SPI output.  Only standard 1x SPI is supported, and as
                a result all four wires are ganged together.  This means that it is only possible
                to perform half-duplex operations, using this SPI core.
            """)
            self.miso = CSRStatus(description="Incoming value of MISO signal.")
            self.bitbang_en = CSRStorage(description="Write a ``1`` here to disable memory-mapped mode and enable bitbang mode.")

        # # #

        cs_n = Signal(reset=1)
        clk = Signal()
        dq_oe = Signal()
        wbone_width = len(bus.dat_r)


        read_cmd_params = {
            4: (_format_cmd(_QIOFR, 4), 4*8),
            2: (_format_cmd(_DIOFR, 2), 2*8),
            1: (_format_cmd(_FAST_READ, 1), 1*8)
        }
        read_cmd, cmd_width = read_cmd_params[spi_width]
        addr_width = 24

        dq = TSTriple(spi_width)
        # Keep DQ2,DQ3 as outputs during bitbang, this ensures they activate ~WP or ~HOLD functions
        self.specials.dq0 = Tristate(pads.dq[0], o=dq.o[0], i=dq.i[0], oe=dq.oe)
        self.specials.dq1 = Tristate(pads.dq[1], o=dq.o[1], i=dq.i[1], oe=dq.oe)
        self.specials.dq2 = Tristate(pads.dq[2], o=dq.o[2], i=dq.i[2], oe=(dq.oe | self.bitbang_en.storage))
        self.specials.dq3 = Tristate(pads.dq[3], o=dq.o[3], i=dq.i[3], oe=(dq.oe | self.bitbang_en.storage))

        sr = Signal(max(cmd_width, addr_width, wbone_width))
        if endianness == "big":
            self.comb += bus.dat_r.eq(sr)
        else:
            self.comb += bus.dat_r.eq(reverse_bytes(sr))

        hw_read_logic = [
            pads.clk.eq(clk),
            pads.cs_n.eq(cs_n),
            dq.o.eq(sr[-spi_width:]),
            dq.oe.eq(dq_oe)
        ]

        if with_bitbang:
            bitbang_logic = [
                pads.clk.eq(self.bitbang.storage[1]),
                pads.cs_n.eq(self.bitbang.storage[2]),

                # In Dual/Quad mode, no single data pin is consistently
                # an input or output thanks to dual/quad reads, so we need a bit
                # to swap direction of the pins. Aside from this additional bit,
                # bitbang mode is identical for Single/Dual/Quad; dq[0] is mosi
                # and dq[1] is miso, meaning remaining data pin values don't
                # appear in CSR registers.
                If(self.bitbang.storage[3],
                    dq.oe.eq(0)
                ).Else(
                    dq.oe.eq(1)
                ),
                If(self.bitbang.storage[1], # CPOL=0/CPHA=0 or CPOL=1/CPHA=1 only.
                    self.miso.status.eq(dq.i[1])
                ),
                dq.o.eq(Cat(self.bitbang.storage[0], Replicate(1, spi_width-1)))
            ]

            self.comb += [
                If(self.bitbang_en.storage,
                    bitbang_logic
                ).Else(
                    hw_read_logic
                )
            ]

        else:
            self.comb += hw_read_logic

        if div < 2:
            raise ValueError("Unsupported value \'{}\' for div parameter for SpiFlash core".format(div))
        else:
            i = Signal(max=div)
            dqi = Signal(spi_width)
            self.sync += [
                If(i == div//2 - 1,
                    clk.eq(1),
                    dqi.eq(dq.i),
                ),
                If(i == div - 1,
                    i.eq(0),
                    clk.eq(0),
                    sr.eq(Cat(dqi, sr[:-spi_width]))
                ).Else(
                    i.eq(i + 1),
                ),
            ]

        # spi is byte-addressed, prefix by zeros
        z = Replicate(0, log2_int(wbone_width//8))

        seq = [
            (cmd_width//spi_width*div,
                [dq_oe.eq(1), cs_n.eq(0), sr[-cmd_width:].eq(read_cmd)]),
            (addr_width//spi_width*div,
                [sr[-addr_width:].eq(Cat(z, bus.adr))]),
            ((dummy + wbone_width//spi_width)*div,
                [dq_oe.eq(0)]),
            (1,
                [bus.ack.eq(1), cs_n.eq(1)]),
            (div, # tSHSL!
                [bus.ack.eq(0)]),
            (0,
                []),
        ]

        # accumulate timeline deltas
        t, tseq = 0, []
        for dt, a in seq:
            tseq.append((t, a))
            t += dt

        self.sync += timeline(bus.cyc & bus.stb & (i == div - 1), tseq)

class SpiFlashSingle(SpiFlashCommon, AutoCSR):
    def __init__(self, pads, dummy=15, div=2, with_bitbang=True, endianness="big"):
        """
        Simple memory-mapped SPI flash.
        Supports 1-bit reads. Only supports mode3 (cpol=1, cpha=1).
        """
        SpiFlashCommon.__init__(self, pads)
        self.bus = bus = wishbone.Interface()

        if with_bitbang:
            self.bitbang = CSRStorage(4, reset_less=True, fields=[
                CSRField("mosi", description="Output value for SPI MOSI pin."),
                CSRField("clk", description="Output value for SPI CLK pin."),
                CSRField("cs_n", description="Output value for SPI CSn pin."),
                CSRField("dir", description="Unused in this design.")
            ], description="""Bitbang controls for SPI output.""")
            self.miso = CSRStatus(description="Incoming value of MISO pin.")
            self.bitbang_en = CSRStorage(description="Write a ``1`` here to disable memory-mapped mode and enable bitbang mode.")

        # # #

        if hasattr(pads, "wp"):
            self.comb += pads.wp.eq(1)

        if hasattr(pads, "hold"):
            self.comb += pads.hold.eq(1)

        cs_n = Signal(reset=1)
        clk = Signal()
        wbone_width = len(bus.dat_r)

        read_cmd = _FAST_READ
        cmd_width = 8
        addr_width = 24

        sr = Signal(max(cmd_width, addr_width, wbone_width))
        if endianness == "big":
            self.comb += bus.dat_r.eq(sr)
        else:
            self.comb += bus.dat_r.eq(reverse_bytes(sr))

        hw_read_logic = [
            pads.clk.eq(clk),
            pads.cs_n.eq(cs_n),
            pads.mosi.eq(sr[-1:])
        ]

        if with_bitbang:
            bitbang_logic = [
                pads.clk.eq(self.bitbang.storage[1]),
                pads.cs_n.eq(self.bitbang.storage[2]),
                If(self.bitbang.storage[1], # CPOL=0/CPHA=0 or CPOL=1/CPHA=1 only.
                    self.miso.status.eq(pads.miso)
                ),
                pads.mosi.eq(self.bitbang.storage[0])
            ]

            self.comb += [
                If(self.bitbang_en.storage,
                    bitbang_logic
                ).Else(
                    hw_read_logic
                )
            ]

        else:
            self.comb += hw_read_logic

        if div < 2:
            raise ValueError("Unsupported value \'{}\' for div parameter for SpiFlash core".format(div))
        else:
            i = Signal(max=div)
            miso = Signal()
            self.sync += [
                If(i == div//2 - 1,
                    clk.eq(1),
                    miso.eq(pads.miso),
                ),
                If(i == div - 1,
                    i.eq(0),
                    clk.eq(0),
                    sr.eq(Cat(miso, sr[:-1]))
                ).Else(
                    i.eq(i + 1),
                ),
            ]

        # spi is byte-addressed, prefix by zeros
        z = Replicate(0, log2_int(wbone_width//8))

        seq = [
            (cmd_width*div,
                [cs_n.eq(0), sr[-cmd_width:].eq(read_cmd)]),
            (addr_width*div,
                [sr[-addr_width:].eq(Cat(z, bus.adr))]),
            ((dummy + wbone_width)*div,
                []),
            (1,
                [bus.ack.eq(1), cs_n.eq(1)]),
            (div, # tSHSL!
                [bus.ack.eq(0)]),
            (0,
                []),
        ]

        # accumulate timeline deltas
        t, tseq = 0, []
        for dt, a in seq:
            tseq.append((t, a))
            t += dt

        self.sync += timeline(bus.cyc & bus.stb & (i == div - 1), tseq)


def SpiFlash(pads, *args, **kwargs):
    if hasattr(pads, "mosi"):
       return SpiFlashSingle(pads, *args, **kwargs)
    else:
        return SpiFlashDualQuad(pads, *args, **kwargs)

# SpiFlash Quad Read/Write (memory-mapped) ---------------------------------------------------------

class SpiFlashQuadReadWrite(SpiFlashCommon, AutoCSR):
    def __init__(self, pads, dummy=15, div=2, with_bitbang=True, endianness="big"):
        """
        Simple SPI flash.
        Supports multi-bit pseudo-parallel reads (aka Dual or Quad I/O Fast
        Read). Only supports mode3 (cpol=1, cpha=1).
        """
        SpiFlashCommon.__init__(self, pads)
        self.bus = bus = wishbone.Interface()
        spi_width = len(pads.dq)
        max_transfer_size = 8*8
        assert spi_width >= 2

        if with_bitbang:
            self.bitbang = CSRStorage(4, reset_less=True, fields=[
                CSRField("mosi", description="Output value for MOSI pin, valid whenever ``dir`` is ``0``."),
                CSRField("clk", description="Output value for SPI CLK pin."),
                CSRField("cs_n", description="Output value for SPI CSn pin."),
                CSRField("dir", description="Sets the direction for *ALL* SPI data pins except CLK and CSn.", values=[
                    ("0", "OUT", "SPI pins are all output"),
                    ("1", "IN", "SPI pins are all input"),
                ])
            ], description="""
                Bitbang controls for SPI output.  Only standard 1x SPI is supported, and as
                a result all four wires are ganged together.  This means that it is only possible
                to perform half-duplex operations, using this SPI core.
            """)
            self.miso = CSRStatus(description="Incoming value of MISO signal.")
            self.bitbang_en = CSRStorage(description="Write a ``1`` here to disable memory-mapped mode and enable bitbang mode.")

        queue = self.queue = CSRStatus(4)
        in_len = self.in_len = CSRStorage(4)
        out_len = self.out_len = CSRStorage(4)
        in_left = self.in_left = Signal(max=2**8)
        out_left = self.out_left = Signal(max=2**8)
        self.quad_transfer = Signal(reset=0)
        spi_in = self.spi_in = CSRStorage(max_transfer_size)
        spi_out = self.spi_out = CSRStatus(max_transfer_size)

        cs_n = Signal(reset=1)
        clk = Signal()
        dq_oe = Signal()
        wbone_width = len(bus.dat_r)

        cmd_width = 8
        addr_width = 24

        dq = TSTriple(spi_width)

        sr = Signal(max(cmd_width, addr_width, wbone_width))
        if endianness == "big":
            self.comb += bus.dat_r.eq(sr)
        else:
            self.comb += bus.dat_r.eq(reverse_bytes(sr))

        self.specials.dq0 = Tristate(pads.dq[0], o=dq.o[0], i=dq.i[0], oe=dq.oe)
        self.specials.dq1 = Tristate(pads.dq[1], o=dq.o[1], i=dq.i[1], oe=dq.oe)
        if with_bitbang:
            # Keep DQ2,DQ3 as outputs during bitbang, this ensures they activate ~WP or ~HOLD functions
            self.specials.dq2 = Tristate(pads.dq[2], o=dq.o[2], i=dq.i[2], oe=(dq.oe | self.bitbang_en.storage))
            self.specials.dq3 = Tristate(pads.dq[3], o=dq.o[3], i=dq.i[3], oe=(dq.oe | self.bitbang_en.storage))
        else:
            self.specials.dq2 = Tristate(pads.dq[2], o=dq.o[2], i=dq.i[2], oe=dq.oe)
            self.specials.dq3 = Tristate(pads.dq[3], o=dq.o[3], i=dq.i[3], oe=dq.oe)

        sr = Signal(max(cmd_width, addr_width, wbone_width, max_transfer_size))

        if endianness == "big":
            self.comb += bus.dat_r.eq(sr[:wbone_width])
        else:
            self.comb += bus.dat_r.eq(reverse_bytes(sr[:wbone_width]))
        hw_read_logic_single = [
            pads.clk.eq(clk),
            pads.cs_n.eq(cs_n),
            dq.o.eq(sr[-spi_width:]),
            dq.oe.eq(dq_oe)
        ]
        hw_read_logic_quad = [
            pads.clk.eq(clk),
            pads.cs_n.eq(cs_n),
            dq.o.eq(Cat(sr[-1:], Replicate(1, 3))),
            dq.oe.eq(dq_oe)
        ]

        if with_bitbang:
            bitbang_logic = [
                pads.clk.eq(self.bitbang.storage[1]),
                pads.cs_n.eq(self.bitbang.storage[2]),

                # In Dual/Quad mode, no single data pin is consistently
                # an input or output thanks to dual/quad reads, so we need a bit
                # to swap direction of the pins. Aside from this additional bit,
                # bitbang mode is identical for Single/Dual/Quad; dq[0] is mosi
                # and dq[1] is miso, meaning remaining data pin values don't
                # appear in CSR registers.
                If(self.bitbang.storage[3],
                    dq.oe.eq(0)
                ).Else(
                    dq.oe.eq(1)
                ),
                If(self.bitbang.storage[1], # CPOL=0/CPHA=0 or CPOL=1/CPHA=1 only.
                    self.miso.status.eq(dq.i[1])
                ),
                dq.o.eq(Cat(self.bitbang.storage[0], Replicate(1, spi_width-1)))
            ]

            self.comb += [
                If(self.bitbang_en.storage,
                    bitbang_logic
                ).Elif(self.quad_transfer,
                    hw_read_logic_single
                ).Else(
                    hw_read_logic_quad
                )
            ]

        else:
            self.comb += [
                If(self.quad_transfer,
                    hw_read_logic_single
                ).Else(
                    hw_read_logic_quad
                )
            ]

        if div < 2:
            raise ValueError("Unsupported value \'{}\' for div parameter for SpiFlash core".format(div))

        # spi is byte-addressed, prefix by zeros
        z = Replicate(0, log2_int(wbone_width//8))
        i = Signal(max=div)
        dqi = Signal(spi_width)

        # SPI or memmap mode
        self.mode = Signal()

        self.sync += [
            If(i == div//2 - 1,
                clk.eq(1),
                dqi.eq(dq.i),
            ),
            If(i == div - 1,
                i.eq(0),
                clk.eq(0),
               If(self.quad_transfer,
                  sr.eq(Cat(dqi, sr[:-spi_width]))
               ).Else(
                   sr.eq(Cat(dqi[1], sr[:-1]))
                  )
            ).Else(
                i.eq(i + 1),
            ),
        ]

        read_seq = [
            (4*cmd_width//spi_width*div,
                [dq_oe.eq(1), cs_n.eq(0), sr[-cmd_width:].eq(_QIOFR), self.quad_transfer.eq(0)]),
            (addr_width//spi_width*div,
                [sr[-addr_width:].eq(Cat(z, bus.adr)), self.quad_transfer.eq(1)]),
            ((1+dummy + wbone_width//spi_width)*div,
                [dq_oe.eq(0)]),
            (1,
                [bus.ack.eq(1), cs_n.eq(1)]),
            (div, # tSHSL!
                [bus.ack.eq(0)]),
            (0,
             [queue.status[0].eq(0)]),
        ]


        write_seq = [
            (4*cmd_width//spi_width*div,
                [dq_oe.eq(1), cs_n.eq(0), sr[-cmd_width:].eq(_QIOPP), self.quad_transfer.eq(0)]),
            (addr_width//spi_width*div,
                [sr[-addr_width:].eq(Cat(z, bus.adr)), self.quad_transfer.eq(1)]),
            ((wbone_width//spi_width)*div,
                [sr[-wbone_width:].eq(reverse_bytes(bus.dat_w))]),
            (1,
                [bus.ack.eq(1), cs_n.eq(1)]),
            (div,
                [bus.ack.eq(0)]),
            (0,
             [queue.status[1].eq(0)]),
        ]

        # prepare spi transfer
        self.sync += If(self.out_len.re & (self.out_len.storage != 0) & self.en_quad.storage[0],
                        self.out_left.eq(Cat(1, self.out_len.storage)
                        )
        )

        self.sync += If(self.out_len.re & (self.out_len.storage == 0),
                        self.out_left.eq(0)
        )
        self.sync += If(self.out_len.re & (self.out_len.storage != 0) & ~self.en_quad.storage[0],
                        self.out_left.eq(Cat(1, Replicate(0, 2), self.out_len.storage))
        )
        self.sync += If(self.in_len.re & (self.in_len.storage != 0) & ~self.en_quad.storage[0],
                        [queue.status[2].eq(1),
                         self.in_left.eq(Cat(Replicate(0, 3), in_len.storage)),
                         self.quad_transfer.eq(0)]
        )

        # write data to sr
        self.sync += If(queue.status[2] & (i == div - 1) & ~self.en_quad.storage[0],
                        sr[-max_transfer_size:].eq(self.spi_in.storage), queue.status[2].eq(0), queue.status[3].eq(1), cs_n.eq(0), dq_oe.eq(1))

        # count spi to slave transfer cycles
        self.sync += If(queue.status[3] & (self.in_left > 0) & (i == div - 1), self.in_left.eq(self.in_left - 1), dq_oe.eq(1))
        # count spi to master transfer cycles
        self.sync += If(queue.status[3] & (self.in_left < 1) & (self.out_left > 0) & (i == div - 1), self.out_left.eq(self.out_left - 1), dq_oe.eq(0))

        #end transmision and read data from sr
        self.sync += If(~self.in_len.re & (in_left < 1) & (out_left < 1) & queue.status[3], queue.status[3].eq(0), cs_n.eq(1),
                        If(self.out_len.storage == 1, self.spi_out.status.eq(Cat(Replicate(0, 8*7), sr))
                        ).Elif(self.out_len.storage == 2, self.spi_out.status.eq(Cat(Replicate(0, 8*6), sr))
                        ).Elif(self.out_len.storage == 3, self.spi_out.status.eq(Cat(Replicate(0, 8*5), sr))
                        ).Elif(self.out_len.storage == 4, self.spi_out.status.eq(Cat(Replicate(0, 8*4), sr))
                        ).Elif(self.out_len.storage == 5, self.spi_out.status.eq(Cat(Replicate(0, 8*3), sr))
                        ).Elif(self.out_len.storage == 6, self.spi_out.status.eq(Cat(Replicate(0, 8*2), sr))
                        ).Elif(self.out_len.storage == 7, self.spi_out.status.eq(Cat(Replicate(0, 8*1), sr))
                        ).Else(self.spi_out.status.eq(sr)))

        # detect mem map access
        self.sync += If(~self.mode & bus.cyc & bus.stb & ~bus.we, queue.status[0].eq(1))
        self.sync += If(~self.mode & bus.cyc & bus.stb & bus.we, queue.status[1].eq(1))

        self.sync += timeline(queue.status[0] & ~self.en_quad.storage[0] & (i == div - 1), accumulate_timeline_deltas(read_seq))
        self.sync += timeline(queue.status[1] & ~self.en_quad.storage[0] & (i == div - 1), accumulate_timeline_deltas(write_seq))

# Xilinx 7-Series FPGAs SPI Flash (non-memory-mapped) ----------------------------------------------

class S7SPIFlash(Module, AutoCSR):
    def __init__(self, pads, sys_clk_freq, spi_clk_freq=25e6):
        self.submodules.spi = spi = SPIMaster(None, 40, sys_clk_freq, spi_clk_freq)
        self.specials += Instance("STARTUPE2",
                i_CLK=0,
                i_GSR=0,
                i_GTS=0,
                i_KEYCLEARB=0,
                i_PACK=0,
                i_USRCCLKO=spi.pads.clk,
                i_USRCCLKTS=0,
                i_USRDONEO=1,
                i_USRDONETS=1
        )
        if hasattr(pads, "vpp"):
            pads.vpp.reset = 1
        if hasattr(pads, "hold"):
            pads.hold.reset = 1
        if hasattr(pads, "cs_n"):
            self.comb += pads.cs_n.eq(spi.pads.cs_n)
        self.comb += [
            pads.mosi.eq(spi.pads.mosi),
            spi.pads.miso.eq(pads.miso)
        ]


# Lattice ECP5 FPGAs SPI Flash (non-memory-mapped) -------------------------------------------------

class ECP5SPIFlash(Module, AutoCSR):
    def __init__(self, pads, sys_clk_freq, spi_clk_freq=25e6):
        self.submodules.spi = spi = SPIMaster(None, 40, sys_clk_freq, spi_clk_freq)
        self.specials += Instance("USRMCLK",
            i_USRMCLKI  = spi.pads.clk,
            i_USRMCLKTS = 0
        )
        if hasattr(pads, "vpp"):
            pads.vpp.reset = 1
        if hasattr(pads, "hold"):
            pads.hold.reset = 1
        if hasattr(pads, "cs_n"):
            self.comb += pads.cs_n.eq(spi.pads.cs_n)
        self.comb += [
            pads.mosi.eq(spi.pads.mosi),
            spi.pads.miso.eq(pads.miso)
        ]
