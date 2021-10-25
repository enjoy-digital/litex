#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

from litex.build.efinix.efinity import EfinityToolchain

# Efinix AsyncResetSynchronizer --------------------------------------------------------------------

class EfinixAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("EFX_FF",
                p_SR_VALUE = 1,
                i_D   = 0,
                i_SR  = async_reset,
                i_CLK = cd.clk,
                i_CE  = 1,
                o_Q   = rst1),
            Instance("EFX_FF",
                p_SR_VALUE = 1,
                i_D   = rst1,
                i_SR  = async_reset,
                i_CLK = cd.clk,
                i_CE  = 1,
                o_Q   = cd.rst)
        ]


class EfinixAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return EfinixAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# Efinix Tristate ----------------------------------------------------------------------------------

class EfinixTristateImpl(Module):
    def __init__(self, platform, io, o, oe, i=None):
        nbits, sign = value_bits_sign(io)
        assert nbits == 1
        io_name = platform.get_pin_name(io)
        io_loc  = platform.get_pin_location(io)
        io_o    = platform.add_iface_io(io_name + "_OUT")
        io_oe   = platform.add_iface_io(io_name +  "_OE")
        io_i    = platform.add_iface_io(io_name +  "_IN")
        self.comb += io_o.eq(o)
        self.comb += io_oe.eq(oe)
        if i is not None:
            self.comb += i.eq(io_i)
        block = {
            "type"     : "GPIO",
            "mode"     : "INOUT",
            "name"     : io_name,
            "location" : [io_loc[0]],
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.delete(io)

class EfinixTristate(Module):
    @staticmethod
    def lower(dr):
        return EfinixTristateImpl(dr.platform, dr.target, dr.o, dr.oe, dr.i)

# Efinix SDRTristate -------------------------------------------------------------------------------

class EfinixSDRTristateImpl(Module):
    def __init__(self, platform, io, o, oe, i, clk):
        _o  = Signal()
        _oe = Signal()
        _i  = Signal()
        self.specials += SDROutput(o, _o, clk)
        self.specials += SDRInput(_i, i, clk)
        self.submodules += InferedSDRIO(oe, _oe, clk)
        tristate = Tristate(io, _o, _oe, _i)
        tristate.platform = platform
        self.specials += tristate

class EfinixSDRTristate(Module):
    @staticmethod
    def lower(dr):
        return EfinixSDRTristateImpl(dr.platform, dr.io, dr.o, dr.oe, dr.i, dr.clk)

# Efinix Special Overrides -------------------------------------------------------------------------

efinix_special_overrides = {
    AsyncResetSynchronizer : EfinixAsyncResetSynchronizer,
    Tristate               : EfinixTristate,
    SDRTristate            : EfinixSDRTristate,
}
