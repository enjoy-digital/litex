# This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *
from migen.fhdl.specials import Tristate

from litex.soc.interconnect.csr import *

# I2C Master Bit-Banging ---------------------------------------------------------------------------

I2C_W_SCL = 0
I2C_W_OE  = 1
I2C_W_SDA = 2

I2C_R_SDA = 0

class I2CMaster(Module, AutoCSR):
    """I2C Master Bit-Banging

    Provides the minimal hardware to do software I2C Master bit banging.

    On the same write CSRStorage (_w), software can control SCL (I2C_SCL), SDA direction and value
    (I2C_OE, I2C_W). Software get back SDA value with the read CSRStatus (_r).
    """
    pads_layout = [("scl", 1), ("sda", 1)]
    def __init__(self, pads=None):
        if pads is None:
            pads = Record(self.pads_layout)
        self.pads = pads
        self._w = CSRStorage(8, name="w")
        self._r = CSRStatus(1,  name="r")

        # # #

        _sda_w  = Signal()
        _sda_oe = Signal()
        _sda_r  = Signal()
        self.comb += [
            pads.scl.eq(self._w.storage[I2C_W_SCL]),
            _sda_oe.eq( self._w.storage[I2C_W_OE]),
            _sda_w.eq(  self._w.storage[I2C_W_SDA]),
            self._r.status[I2C_R_SDA].eq(_sda_r),
        ]
        self.specials += Tristate(pads.sda, _sda_w, _sda_oe, _sda_r)


# SPI Master Bit-Banging ---------------------------------------------------------------------------

SPI_W_CLK  = 0
SPI_W_MOSI = 1
SPI_W_OE   = 2
SPI_W_CS   = 4

SPI_R_MOSI = 1
SPI_R_MISO = 0

class SPIMaster(Module, AutoCSR):
    """3/4-wire SPI Master Bit-Banging

    Provides the minimal hardware to do software 3/4-wire SPI Master bit banging.

    On the same write CSRStorage (_w), software can control CLK (SPI_CLK), MOSI (SPI_MOSI), MOSI
    direction (SPI_OE) in the case 3-wire SPI and up to 4 Chip Selects (SPI_CS). Software get back
    MISO (SPI_MISO) with the read CSRStatus (_r).
    """
    pads_layout = [("clk", 1), ("cs_n", 4), ("mosi", 1), ("miso", 1)]
    def __init__(self, pads=None):
        if pads is None:
            pads = Record(self.pads_layout)
        self.pads = pads
        assert len(pads.cs_n) <= 4
        self._w = CSRStorage(8, name="w")
        self._r = CSRStatus(2,  name="r")

        # # #

        _mosi_w  = Signal()
        _mosi_oe = Signal()
        _mosi_r  = Signal()
        _cs      = Signal(4)
        self.comb += [
            pads.clk.eq(  self._w.storage[SPI_W_CLK]),
            _mosi_w.eq(   self._w.storage[SPI_W_MOSI]),
            _mosi_oe.eq(  self._w.storage[SPI_W_OE]),
            pads.cs_n.eq(~self._w.storage[SPI_W_CS]),
            self._r.status[SPI_R_MOSI].eq(_mosi_r),
        ]
        if hasattr(pads, "miso"):
            self._r.status[SPI_R_MISO].eq(pads.miso)
        self.specials += Tristate(pads.mosi, _mosi_w, _mosi_oe, _mosi_r)
