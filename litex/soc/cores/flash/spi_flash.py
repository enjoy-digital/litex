from litex.gen import *
from litex.gen.genlib.misc import timeline

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import AutoCSR, CSRStorage, CSRStatus


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


class SpiFlashDualQuad(Module, AutoCSR):
    def __init__(self, pads, dummy=15, div=2, with_bitbang=True):
        """
        Simple SPI flash, e.g. N25Q128 on the LX9 Microboard.

        Supports multi-bit pseudo-parallel reads (aka Dual or Quad I/O Fast
        Read). Only supports mode0 (cpol=0, cpha=0).
        Optionally supports software bitbanging (for write, erase, or other commands).
        """
        self.bus = bus = wishbone.Interface()
        spi_width = len(pads.dq)
        assert spi_width >= 2
        if with_bitbang:
            self.bitbang = CSRStorage(4)
            self.miso = CSRStatus()
            self.bitbang_en = CSRStorage()

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

        pads.cs_n.reset = 1

        dq = TSTriple(spi_width)
        self.specials.dq = dq.get_tristate(pads.dq)

        sr = Signal(max(cmd_width, addr_width, wbone_width))
        self.comb += bus.dat_r.eq(sr)

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
                If(self.bitbang.storage[3],
                    dq.oe.eq(0)
                ).Else(
                    dq.oe.eq(1)
                ),
                If(self.bitbang.storage[1],
                    self.miso.status.eq(dq.i[1])
                )
            ]
            if spi_width > 1:
                bitbang_logic += [
                    dq.o.eq(Cat(self.bitbang.storage[0], Replicate(1, spi_width-1)))
                ]
            else:
                bitbang_logic += [
                    dq.o.eq(self.bitbang.storage[0])
                ]

            self.comb += \
                If(self.bitbang_en.storage,
                    bitbang_logic
                ).Else(
                    hw_read_logic
                )
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


class SpiFlashSingle(Module, AutoCSR):
    def __init__(self, pads, dummy=8, div=2, with_bitbang=True):
        """
        Simple SPI flash, e.g. N25Q128 on the LX9 Microboard.

        Supports 1-bit reads. Only supports mode0 (cpol=0, cpha=0).
        Optionally supports software bitbanging (for write, erase, or other commands).
        """
        self.bus = bus = wishbone.Interface()
        if with_bitbang:
            self.bitbang = CSRStorage(4)
            self.miso = CSRStatus()
            self.bitbang_en = CSRStorage()

        # # #

        cs_n = Signal(reset=1)
        clk = Signal()
        dq_oe = Signal()
        wbone_width = len(bus.dat_r)

        read_cmd = _FAST_READ
        cmd_width = 8
        addr_width = 24

        pads.cs_n.reset = 1

        sr = Signal(max(8, addr_width, wbone_width))
        self.comb += bus.dat_r.eq(sr)

        hw_read_logic = [
            pads.clk.eq(clk),
            pads.cs_n.eq(cs_n),
            pads.mosi.eq(sr[-1:])
        ]

        if with_bitbang:
            bitbang_logic = [
                pads.clk.eq(self.bitbang.storage[1]),
                pads.cs_n.eq(self.bitbang.storage[2]),
                self.miso.status.eq(pads.miso),
                pads.mosi.eq(self.bitbang.storage[0]),
            ]
            self.comb += \
                If(self.bitbang_en.storage,
                    bitbang_logic
                ).Else(
                    hw_read_logic
                )
        else:
            self.comb += hw_read_logic

        if div < 2:
            raise ValueError("Unsupported value \'{}\' for div parameter for SpiFlash core".format(div))
        else:
            i = Signal(max=div)
            dqi = Signal(1)
            self.sync += [
                If(i == div//2 - 1,
                    clk.eq(1),
                    dqi.eq(pads.miso),
                ),
                If(i == div - 1,
                    i.eq(0),
                    clk.eq(0),
                    sr.eq(Cat(dqi, sr[:-1]))
                ).Else(
                    i.eq(i + 1),
                ),
            ]

        # spi is byte-addressed, prefix by zeros
        z = Replicate(0, log2_int(wbone_width//8))

        seq = [
            (cmd_width//div,
                [cs_n.eq(0), sr[-cmd_width:].eq(read_cmd)]),
            (addr_width//div,
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
