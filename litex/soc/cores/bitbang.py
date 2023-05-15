#
# This file is part of LiteX.
#
# Copyright (c) 2019-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2023      Jeremy Herbert <jeremy.006@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Tristate

from litex.soc.interconnect.csr import *

# I2C Master Bit-Banging ---------------------------------------------------------------------------

class I2CMaster(Module, AutoCSR):
    """I2C bus master (bit-banged).

    This core provides minimal hardware for use as a software controlled bit-banged I2C bus master.
    I2C uses a tristate/open-drain output driver configuration with pull-up resistors, and this core
    expects that the pull-ups will be provided externally.

    Further information about the I2C bus can be found in the I2C standard document from NXP, `UM10204`_.

    .. _UM10204: https://www.pololu.com/file/0J435/UM10204.pdf
    """
    pads_layout = [("scl", 1), ("sda", 1)]

    def __init__(self, pads=None, default_dev=False):
        """
        Class constructor.

        :param pads        : (optional) A ``Record`` object containing the pads ``scl`` and ``sda``.
        :param default_dev : (optional) A `bool` indicating whether this I2C master should be used as
                             the default I2C interface (default is ``False``).
        """
        self.init = []
        if pads is None:
            pads = Record(self.pads_layout)
        self.pads = pads
        self._w = CSRStorage(fields=[
            CSRField("scl", size=1, offset=0, reset=1, description="Drives the state of the SCL pad."),
            CSRField("oe",  size=1, offset=1,          description="Output Enable - if 0, both the SCL and SDA output drivers are disconnected."),
            CSRField("sda", size=1, offset=2, reset=1, description="Drives the state of the SDA pad.")],
            name="w")
        self._r = CSRStatus(fields=[
            CSRField("sda", size=1, offset=0, description="Contains the current state of the SDA pad.")],
            name="r")

        self.default_dev = default_dev

        self.connect(pads)

    def connect(self, pads):
        """
        Attaches the signals from inside the core to the input/output pads. This function is normally
        only called from inside the class constructor.

        :param pads: A ``Record`` object containing the pads ``scl`` and ``sda``.
        """
        # SCL
        self.specials += Tristate(pads.scl,
            o  = 0,                  # I2C uses Pull-ups, only drive low.
            oe = ~self._w.fields.scl # Drive when scl is low.
        )
        # SDA
        self.specials += Tristate(pads.sda,
            o  = 0,                                       # I2C uses Pull-ups, only drive low.
            oe = self._w.fields.oe & ~self._w.fields.sda, # Drive when oe and sda is low.
            i  = self._r.fields.sda
        )

    def add_init(self, addr, init, init_addr_len=1):
        """
        Adds an I2C write transaction that will be executed on startup. This method can be called
        multiple times to add multiple transactions that will be executed in order for this core
        instance.

        :param addr          : The I2C slave address to write to.
        :param init          : The bytes to write to the slave.
        :param init_addr_len : (optional) The init address length in bytes (default is 1).
        """
        if init_addr_len not in (1, 2):
            raise ValueError("I2C slave addresses can only have a length of one or two bytes")

        if init_addr_len == 1 and not 0 <= addr <= 127:
            raise ValueError("I2C slave address must be between 0 and 127 (inclusive)")
        elif init_addr_len == 2 and not 0 <= addr <= 1023:
            raise ValueError("I2C slave address must be between 0 and 1023 (inclusive)")

        self.init.append((addr, init, init_addr_len))


class I2CMasterSim(I2CMaster):
    """I2C bus master (bit-banged) for Verilator simulation

    This core uses separate pads for SDA IN/OUT as Verilator does not support tristate pins well.
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
    """
    Collects all the I2C write transactions that have been added to run on startup for all ``I2CMaster``
    instances into a single list. This information is used to generate C header files in
    ``litex.soc.integration.export``.

    See ``I2CMaster.add_init`` for more information.

    :param soc: ``SoCBase`` instance to scan for ``I2CMaster`` instances.
    :return: ``i2c_devs, i2c_init`` where ``i2c_devs`` is a list of all ``I2CMaster`` instances, and
    ``i2c_init`` is a list of tuples, where each tuple is (core instance name, slave address, bytes
    to write, slave address length in bytes).
    """
    i2c_init = []
    i2c_devs = []
    for name, obj in xdir(soc, True):
        if isinstance(obj, I2CMaster):
            soc.add_config("HAS_I2C", check_duplicate=False)
            i2c_devs.append((name, obj.default_dev))
            for addr, init, init_addr_len in obj.init:
                i2c_init.append((name, addr, init, init_addr_len))
    return i2c_devs, i2c_init

# SPI Master Bit-Banging ---------------------------------------------------------------------------

class SPIMaster(Module, AutoCSR):
    """3/4-wire SPI bus master (bit-banged).

    This core provides minimal hardware for use as a software controlled bit-banged SPI bus master.

    This core supports the typical SPI pads (MOSI, MISO, CLK) and a maximum of 4 CS outputs.
    If pull-up resistors are needed for 3 wire operation, they must be added externally.
    """
    pads_layout = [("clk", 1), ("cs_n", 4), ("mosi", 1), ("miso", 1)]

    def __init__(self, pads=None):
        """
        Class constructor.

        :param pads: (optional) A ``Record`` object containing: ``clk``, ``cs_n``, ``mosi`` and ``miso``.
        """
        if pads is None:
            pads = Record(self.pads_layout)
        self.pads = pads

        if len(pads.cs_n) > 4:
            raise ValueError("This core only supports a maximum of 4 CS outputs")

        self._w = CSRStorage(fields=[
            CSRField("clk",  size=1, offset=0, description="Drives the state of the CLK pad."),
            CSRField("mosi", size=1, offset=1, description="Drives the state of the MOSI pad."),
            CSRField("oe",   size=1, offset=2, description="Output Enable for MOSI - if 0, the MOSI output driver is disconnected."),
            CSRField("cs",   size=4, offset=4, description="Drives the state of the CS pads (up to 4, active high).")],
            name="w", description="SPI master output pad controls.")
        self._r = CSRStatus(fields=[
            CSRField("miso", size=1, offset=0, description="Contains the current state of the MISO pad."),
            CSRField("mosi", size=1, offset=1, description="Contains the current state of the MOSI pad.")],
            name="r", description="SPI master input pad states.")

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
