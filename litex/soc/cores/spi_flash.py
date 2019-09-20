# This file is Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# This file is Copyright (c) 2014-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2013-2014 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2015-2014 Sebastien Bourdeauducq <sb@m-labs.hk>

# License: BSD


from migen import *
from migen.genlib.misc import timeline

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import *
from litex.soc.cores.spi import SPIMaster

# SpiFlash Quad/Dual/Single (memory-mapped) --------------------------------------------------------

_FAST_READ = 0x0b
_DIOFR = 0xbb
_QIOFR = 0xeb


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
        Read). Only supports mode0 (cpol=0, cpha=0).
        """
        SpiFlashCommon.__init__(self, pads)
        self.bus = bus = wishbone.Interface()
        spi_width = len(pads.dq)
        assert spi_width >= 2

        if with_bitbang:
            self.bitbang = CSRStorage(4, fields=[
                CSRField("mosi", description="MOSI output pin, valid whenever `dir` is `0`."),
                CSRField("clk", description="Output value for SPI CLK line."),
                CSRField("cs_n", description="Output value of SPI CSn line."),
                CSRField("dir", description="Dual/Quad SPI reuses pins SPI pin direction.", values=[
                    ("0", "OUT", "SPI pins are all output"),
                    ("1", "IN", "SPI pins are all input"),
                ])
            ], description="""Bitbang controls for SPI output.  Only standard 1x SPI is supported,
                            meaning the IO2 and IO3 lines will be hardwired to `1` during bitbang mode.""")
            self.miso = CSRStatus(description="Incoming value of MISO signal.")
            self.bitbang_en = CSRStorage(description="Write a `1` here to disable memory-mapped mode and enable bitbang mode.")

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
        self.specials.dq = dq.get_tristate(pads.dq)

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
        Simple SPI flash.
        Supports 1-bit reads. Only supports mode0 (cpol=0, cpha=0).
        """
        SpiFlashCommon.__init__(self, pads)
        self.bus = bus = wishbone.Interface()

        if with_bitbang:
            self.bitbang = CSRStorage(4, fields=[
                CSRField("mosi", description="MOSI output pin.  Always valid in this design."),
                CSRField("clk", description="Output value for SPI CLK line."),
                CSRField("cs_n", description="Output value of SPI CSn line."),
                CSRField("dir", description="Unused in this design.")
            ], description="""Bitbang controls for SPI output.""")
            self.miso = CSRStatus(description="Incoming value of MISO signal.")
            self.bitbang_en = CSRStorage(description="Write a `1` here to disable memory-mapped mode and enable bitbang mode.")

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
