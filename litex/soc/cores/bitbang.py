#
# This file is part of LiteX.
#
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Tristate

from litex.soc.interconnect.csr import *

# I2C Master Bit-Banging ---------------------------------------------------------------------------

class I2CMaster(Module, AutoCSR):
    """I2C Master Bit-Banging

    Provides the minimal hardware to do software I2C Master bit banging.

    On the same write CSRStorage (_w), software can control:
    - SCL (I2C_SCL).
    - SDA direction and value (I2C_OE, I2C_W).

    Software get back SDA value with the read CSRStatus (_r).
    """
    pads_layout = [("scl", 1), ("sda", 1)]
    def __init__(self, pads=None, default_dev=False):
        self.init = []
        if pads is None:
            pads = Record(self.pads_layout)
        self.pads = pads
        self._w = CSRStorage(fields=[
            CSRField("scl", size=1, offset=0, reset=1),
            CSRField("oe",  size=1, offset=1),
            CSRField("sda", size=1, offset=2, reset=1)],
            name="w")
        self._r = CSRStatus(fields=[
            CSRField("sda", size=1, offset=0)],
            name="r")

        self.default_dev = default_dev

        self.connect(pads)

    def connect(self, pads):
        # SCL
        self.specials += Tristate(pads.scl,
            o  = 0, # I2C uses Pull-ups, only drive low.
            oe = ~self._w.fields.scl # Drive when scl is low.
        )
        # SDA
        self.specials += Tristate(pads.sda,
            o  = 0, # I2C uses Pull-ups, only drive low.
            oe = self._w.fields.oe & ~self._w.fields.sda, # Drive when oe and sda is low.
            i  = self._r.fields.sda
        )

    def add_init(self, addr, init, init_addr_len=1):
        self.init.append((addr, init, init_addr_len))

class I2CMasterSim(I2CMaster):
    """I2C Master Bit-Banging for Verilator simulation

    Uses separate pads for SDA IN/OUT as Verilator does not support tristate pins well.
    """
    pads_layout = [("scl", 1), ("sda_in", 1), ("sda_out", 1)]

    def connect(self, pads):
        _sda_w  = Signal()
        _sda_oe = Signal()
        _sda_r  = Signal()
        _sda_in = Signal()

        self.comb += [
            pads.scl.eq(self._w.fields.scl),
            _sda_oe.eq( self._w.fields.oe),
            _sda_w.eq(  self._w.fields.sda),
            If(_sda_oe,
                pads.sda_out.eq(_sda_w),
                self._r.fields.sda.eq(_sda_w),
            ).Else(
                pads.sda_out.eq(1),
                self._r.fields.sda.eq(pads.sda_in),
            )
        ]

# I2C Master Info Collection  ----------------------------------------------------------------------

# TODO: Find a more generic way to do it that would also apply to other peripherals?

def collect_i2c_info(soc):
    i2c_init = []
    i2c_devs = []
    for name, obj in xdir(soc, True):
        if isinstance(obj, I2CMaster):
            soc.add_config("HAS_I2C", check_duplicate=False)
            i2c_devs.append((name, getattr(obj, "default_dev")))
            if hasattr(obj, "init"):
                for addr, init, init_addr_len in obj.init:
                    i2c_init.append((name, addr, init, init_addr_len))
    return i2c_devs, i2c_init

# SPI Master Bit-Banging ---------------------------------------------------------------------------

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
        self._w = CSRStorage(fields=[
            CSRField("clk",  size=1, offset=0),
            CSRField("mosi", size=1, offset=1),
            CSRField("oe",   size=1, offset=2),
            CSRField("cs",   size=1, offset=4)],
            name="w")
        self._r = CSRStatus(fields=[
            CSRField("miso", size=1, offset=0),
            CSRField("mosi", size=1, offset=1)],
            name="r")

        # # #

        _mosi_w  = Signal()
        _mosi_oe = Signal()
        _mosi_r  = Signal()
        _cs      = Signal(4)
        self.comb += [
            pads.clk.eq(  self._w.fields.clk),
            _mosi_w.eq(   self._w.fields.mosi),
            _mosi_oe.eq(  self._w.fields.oe),
            pads.cs_n.eq(~self._w.fields.cs),
            self._r.fields.mosi.eq(_mosi_r),
        ]
        if hasattr(pads, "miso"):
            self.comb += self._r.fields.miso.eq(pads.miso)
        self.specials += Tristate(pads.mosi, _mosi_w, _mosi_oe, _mosi_r)
