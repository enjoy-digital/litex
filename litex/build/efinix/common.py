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

# Colorama -----------------------------------------------------------------------------------------

try:
    import colorama
    colorama.init()  # install escape sequence translation on Windows
    _have_colorama = True
except ImportError:
    _have_colorama = False

colors = []
if _have_colorama:
    colors += [
        ("ERROR", colorama.Fore.RED + colorama.Style.BRIGHT +
         r"\g<0>" + colorama.Style.RESET_ALL),
        ("WARNING", colorama.Fore.YELLOW +
         r"\g<0>" + colorama.Style.RESET_ALL),
        ("INFO", colorama.Fore.CYAN +
         r"\g<0>" + colorama.Style.RESET_ALL),
    ]

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

        for bit in range(nbits):
            io_name = platform.get_pin_name(io[bit])
            io_loc  = platform.get_pin_location(io[bit])
            io_prop = platform.get_pin_properties(io[bit])
            io_o    = platform.add_iface_io(io_name + "_OUT")
            io_oe   = platform.add_iface_io(io_name +  "_OE")
            io_i    = platform.add_iface_io(io_name +  "_IN")
            self.comb += io_o.eq(o >> bit)
            self.comb += io_oe.eq(oe)
            if i is not None:
                self.comb += i[bit].eq(io_i)
            block = {
                "type"       : "GPIO",
                "mode"       : "INOUT",
                "name"       : io_name,
                "location"   : [io_loc[0]],
                "properties" : io_prop
            }

            platform.toolchain.ifacewriter.blocks.append(block)

        # Remove the group from the io list
        exclude = platform.get_pin_name(io[0], without_index=True)

        # In case of a single signal, there is still a '0' index
        # to be remove at the end
        if (nbits == 1) and (exclude[:-1] == '0'):
            exclude = exclude[:-1]

        platform.toolchain.excluded_ios.append(exclude)


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
