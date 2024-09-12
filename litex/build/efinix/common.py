#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.module import Module
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

from litex.build.generic_platform import Pins
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
            "name"       : i.name_override, # FIXME
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



# Efinix DifferentialOutput ------------------------------------------------------------------------

class EfinixDifferentialOutputImpl(Module):
    def __init__(self, platform, i, o_p, o_n):
        # only keep _p
        io_name = platform.get_pin_name(o_p)
        io_pad  = platform.get_pad_name(o_p) # need real pad name
        io_prop = platform.get_pin_properties(o_p)

        if platform.family == "Titanium":
            # _p has _P_ and _n has _N_ followed by an optional function
            # lvds block needs _PN_
            pad_split = io_pad.split('_')
            assert pad_split[1] == 'P'
            io_pad = f"{pad_split[0]}_PN_{pad_split[2]}"
        else:
            assert "TXP" in io_pad
            # diff output pins are TXPYY and TXNYY
            # lvds block needs TXYY
            io_pad = io_pad.replace("TXP", "TX")

        platform.add_extension([(io_name, 0, Pins(1))])
        i_data = platform.request(io_name)

        self.comb += i_data.eq(i)
        block = {
            "type"              : "LVDS",
            "mode"              : "OUTPUT",
            "tx_mode"           : "DATA",
            "name"              : io_name,
            "sig"               : i_data,
            "location"          : io_pad,
            "size"              : 1,
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(o_p))
        platform.toolchain.excluded_ios.append(platform.get_pin(o_n))
        platform.toolchain.excluded_ios.append(i_data)

class EfinixDifferentialOutput:
    @staticmethod
    def lower(dr):
        return EfinixDifferentialOutputImpl(dr.platform, dr.i, dr.o_p, dr.o_n)

# Efinix DifferentialInput -------------------------------------------------------------------------

class EfinixDifferentialInputImpl(Module):
    def __init__(self, platform, i_p, i_n, o):
        # only keep _p
        io_name = platform.get_pin_name(i_p)
        io_pad  = platform.get_pad_name(i_p) # need real pad name
        io_prop = platform.get_pin_properties(i_p)

        if platform.family == "Titanium":
            # _p has _P_ and _n has _N_ followed by an optional function
            # lvds block needs _PN_
            pad_split = io_pad.split('_')
            assert pad_split[1] == 'P'
            io_pad = f"{pad_split[0]}_PN_{pad_split[2]}"
        else:
            assert "RXP" in io_pad
            # diff input pins are RXPYY and RXNYY
            # lvds block needs RXYY
            io_pad = io_pad.replace("RXP", "RX")

        platform.add_extension([
            (io_name,           0, Pins(1)),
            (f"{io_name}_ena",  0, Pins(1)),
            (f"{io_name}_term", 0, Pins(1)),
        ])
        o_data = platform.request(io_name)
        i_ena  = platform.request(io_name + "_ena")
        i_term = platform.request(io_name + "_term")

        self.comb += [
           o.eq(o_data),
           i_ena.eq(1),
           i_term.eq(1),
        ]

        block = {
            "type"     : "LVDS",
            "mode"     : "INPUT",
            "rx_mode"  : "NORMAL",
            "name"     : io_name,
            "sig"      : o_data,
            "ena"      : i_ena,
            "term"     : i_term,
            "location" : io_pad,
            "size"     : 1,
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(i_p))
        platform.toolchain.excluded_ios.append(platform.get_pin(i_n))
        platform.toolchain.excluded_ios.append(o_data)
        platform.toolchain.excluded_ios.append(i_term)
        platform.toolchain.excluded_ios.append(i_ena)

class EfinixDifferentialInput:
    @staticmethod
    def lower(dr):
        return EfinixDifferentialInputImpl(dr.platform, dr.i_p, dr.i_n, dr.o)





# Efinix DDRTristate ---------------------------------------------------------------------------------

class EfinixDDRTristateImpl(Module):
    def __init__(self, platform, io, o1, o2, oe1, oe2, i1, i2, clk):
        assert oe1 == oe2
        io_name = platform.get_pin_name(io)
        io_pad  = platform.get_pin_location(io)
        io_prop = platform.get_pin_properties(io)
        io_prop_dict = dict(io_prop)
        io_data_i_h  = platform.add_iface_io(io_name + "_OUT_HI")
        io_data_i_l  = platform.add_iface_io(io_name + "_OUT_LO")
        io_data_o_h  = platform.add_iface_io(io_name + "_IN_HI")
        io_data_o_l  = platform.add_iface_io(io_name + "_IN_LO")
        io_data_e  = platform.add_iface_io(io_name + "_OE")
        self.comb += io_data_i_h.eq(o1)
        self.comb += io_data_i_l.eq(o2)
        self.comb += io_data_e.eq(oe1)
        self.comb += i1.eq(io_data_o_h)
        self.comb += i2.eq(io_data_o_l)
        block = {
            "type"              : "GPIO",
            "mode"              : "INOUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : 1,
            "in_reg"            : "DDIO_RESYNC",
            "in_clk_pin"        : clk.name_override, # FIXME.
            "out_reg"           : "DDIO_RESYNC",
            "out_clk_pin"       : clk.name_override, # FIXME.
            "oe_reg"            : "REG",
            "is_inclk_inverted" : False,
            "drive_strength"    : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(io))

class EfinixDDRTristate:
    @staticmethod
    def lower(dr):
        return EfinixDDRTristateImpl(dr.platform, dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk)

# Efinix SDRTristate -------------------------------------------------------------------------------

class EfinixSDRTristateImpl(EfinixDDRTristateImpl):
    def __init__(self, platform, io, o, oe, i, clk):
        io_name = platform.get_pin_name(io)
        io_pad  = platform.get_pin_location(io)
        io_prop = platform.get_pin_properties(io)
        io_prop_dict = dict(io_prop)
        io_data_i  = platform.add_iface_io(io_name + "_OUT")
        io_data_o  = platform.add_iface_io(io_name + "_IN")
        io_data_e  = platform.add_iface_io(io_name + "_OE")
        self.comb += io_data_i.eq(o)
        self.comb += io_data_e.eq(oe)
        self.comb += i.eq(io_data_o)
        block = {
            "type"              : "GPIO",
            "mode"              : "INOUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : 1,
            "in_reg"            : "REG",
            "in_clk_pin"        : clk.name_override, # FIXME.
            "out_reg"           : "REG",
            "out_clk_pin"       : clk.name_override, # FIXME.
            "oe_reg"            : "REG",
            "is_inclk_inverted" : False,
            "drive_strength"    : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(io))


class EfinixSDRTristate(Module):
    @staticmethod
    def lower(dr):
        return EfinixSDRTristateImpl(dr.platform, dr.io, dr.o, dr.oe, dr.i, dr.clk)

# Efinix SDROutput -------------------------------------------------------------------------------

class EfinixSDROutputImpl(Module):
    def __init__(self, platform, i, o, clk):
        io_name = platform.get_pin_name(o)
        io_pad  = platform.get_pin_location(o)
        io_prop = platform.get_pin_properties(o)
        io_prop_dict = dict(io_prop)
        io_data_i  = platform.add_iface_io(io_name)
        self.comb += io_data_i.eq(i)
        block = {
            "type"              : "GPIO",
            "mode"              : "OUTPUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : 1,
            "out_reg"           : "REG",
            "out_clk_pin"       : clk.name_override, # FIXME.
            "is_inclk_inverted" : False,
            "drive_strength"    : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(o))


class EfinixSDROutput(Module):
    @staticmethod
    def lower(dr):
        return EfinixSDROutputImpl(dr.platform, dr.i, dr.o, dr.clk)


# Efinix DDROutput ---------------------------------------------------------------------------------

class EfinixDDROutputImpl(Module):
    def __init__(self, platform, i1, i2, o, clk):
        io_name = platform.get_pin_name(o)
        io_pad  = platform.get_pin_location(o)
        io_prop = platform.get_pin_properties(o)
        io_prop_dict = dict(io_prop)
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
            "out_clk_pin"       : clk.name_override, # FIXME.
            "is_inclk_inverted" : False,
            "drive_strength"    : io_prop_dict.get("DRIVE_STRENGTH", "4")
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
            "in_clk_pin"        : clk.name_override, # FIXME.
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
    DifferentialOutput     : EfinixDifferentialOutput,
    DifferentialInput      : EfinixDifferentialInput,
    SDROutput              : EfinixSDROutput,
    SDRTristate            : EfinixSDRTristate,
    DDROutput              : EfinixDDROutput,
    DDRInput               : EfinixDDRInput,
    DDRTristate            : EfinixDDRTristate,
}
