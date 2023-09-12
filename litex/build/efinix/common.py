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
                o_Q   = rst1
            ),
            Instance("EFX_FF",
                p_SR_VALUE = 1,
                i_D   = rst1,
                i_SR  = async_reset,
                i_CLK = cd.clk,
                i_CE  = 1,
                o_Q   = cd.rst
            )
        ]


class EfinixAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return EfinixAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# Efinix Clk Input ---------------------------------------------------------------------------------

class EfinixClkInputImpl(Module):
    def __init__(self, platform, i, o):
        o_clk  = platform.add_iface_io(o) # FIXME.
        block = {
            "type"       : "GPIO",
            "size"       : 1,
            "location"   : platform.get_pin_location(i)[0],
            "properties" : platform.get_pin_properties(i),
            "name"       : platform.get_pin_name(o_clk),
            "mode"       : "INPUT_CLK",
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(i)


class EfinixClkInput(Module):
    @staticmethod
    def lower(dr):
        return EfinixClkInputImpl(dr.platform, dr.i, dr.o)

# Efinix Clk Output ---------------------------------------------------------------------------------

class EfinixClkOutputImpl(Module):
    def __init__(self, platform, i, o):
        block = {
            "type"       : "GPIO",
            "size"       : 1,
            "location"   : platform.get_pin_location(o)[0],
            "properties" : platform.get_pin_properties(o),
            "name"       : i, # FIXME.
            "mode"       : "OUTPUT_CLK",
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(o)


class EfinixClkOutput(Module):
    @staticmethod
    def lower(dr):
        return EfinixClkOutputImpl(dr.platform, dr.i, dr.o)

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
        platform.toolchain.excluded_ios.append(platform.get_pin(io))

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

# Efinix DDROutput ---------------------------------------------------------------------------------

class EfinixDDROutputImpl(Module):
    def __init__(self, platform, i1, i2, o, clk):
        io_name = platform.get_pin_name(o)
        io_pad  = platform.get_pin_location(o)
        io_prop = platform.get_pin_properties(o)
        io_data_h  = platform.add_iface_io(io_name + "_HI")
        io_data_l  = platform.add_iface_io(io_name + "_LO")
        self.comb += io_data_h.eq(i1)
        self.comb += io_data_l.eq(i2)
        block = {
            "type"              : "GPIO",
            "mode"              : "OUTPUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : 1,
            "out_reg"           : "DDIO_RESYNC",
            "out_clk_pin"       : clk, # FIXME.
            "is_inclk_inverted" : False,
            "drive_strength"    : 4 # FIXME: Get it from constraints.
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(o))

class EfinixDDROutput:
    @staticmethod
    def lower(dr):
        return EfinixDDROutputImpl(dr.platform, dr.i1, dr.i2, dr.o, dr.clk)

# Efinix DDRInput ----------------------------------------------------------------------------------

class EfinixDDRInputImpl(Module):
    def __init__(self, platform, i, o1, o2, clk):
        io_name   = platform.get_pin_name(i)
        io_pad    = platform.get_pin_location(i)
        io_prop   = platform.get_pin_properties(i)
        io_data_h = platform.add_iface_io(io_name + "_HI")
        io_data_l = platform.add_iface_io(io_name + "_LO")
        self.comb += o1.eq(io_data_h)
        self.comb += o2.eq(io_data_l)
        block = {
            "type"              : "GPIO",
            "mode"              : "INPUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : 1,
            "in_reg"            : "DDIO_RESYNC",
            "in_clk_pin"        : clk, # FIXME.
            "is_inclk_inverted" : False
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(i))

class EfinixDDRInput:
    @staticmethod
    def lower(dr):
        return EfinixDDRInputImpl(dr.platform, dr.i, dr.o1, dr.o2, dr.clk)

# Efinix Special Overrides -------------------------------------------------------------------------

efinix_special_overrides = {
    AsyncResetSynchronizer : EfinixAsyncResetSynchronizer,
    ClkInput               : EfinixClkInput,
    ClkOutput              : EfinixClkOutput,
    Tristate               : EfinixTristate,
    SDRTristate            : EfinixSDRTristate,
    DDROutput              : EfinixDDROutput,
    DDRInput               : EfinixDDRInput,
}
