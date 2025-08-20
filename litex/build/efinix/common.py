#
# This file is part of LiteX.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.gen import *
from litex.build.io import *

from litex.build.generic_platform import Pins
from litex.build.efinix.efinity   import EfinityToolchain

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

# Helpers ------------------------------------------------------------------------------------------

def assert_is_signal_or_clocksignal(obj):
    assert isinstance(obj, (ClockSignal, Signal)), f"Object {obj} is not a ClockSignal or Signal"

def const_output_calc(o, io):
    if o.value == 0:
        const_output = 0
    elif len(o) == 1:
        const_output = 1
    else:
        const_output = []
        for bit in range(len(io)):
            if o.value & (1 << bit):
                const_output.append(1)
            else:
                const_output.append(0)
    return const_output

# Efinix AsyncResetSynchronizer --------------------------------------------------------------------

class EfinixAsyncResetSynchronizerImpl(LiteXModule):
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

class EfinixClkInputImpl(LiteXModule):
    n = 0
    def __init__(self, i, o):
        platform = LiteXContext.platform
        self.name = f"clk_input{self.n}"
        if isinstance(o, Signal):
            clk_out_name = f"{o.name_override}{self.name}_clk"
            clk_out = platform.add_iface_io(clk_out_name)
            platform.clks[o.name_override] = clk_out_name
        else:
            clk_out      = platform.add_iface_io(o) # FIXME.
            clk_out_name = platform.get_pin_name(clk_out)

        block = {
            "type"       : "GPIO",
            "size"       : 1,
            "location"   : platform.get_pin_location(i)[0],
            "properties" : platform.get_pin_properties(i),
            "name"       : clk_out_name,
            "mode"       : "INPUT_CLK",
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(i)

        if isinstance(o, Signal):
            self.comb += o.eq(clk_out)
            o = clk_out
        EfinixClkInputImpl.n += 1 # FIXME: Improve.

class EfinixClkInput(LiteXModule):
    @staticmethod
    def lower(dr):
        return EfinixClkInputImpl(dr.i, dr.o)

# Efinix Clk Output --------------------------------------------------------------------------------

class EfinixClkOutputImpl(LiteXModule):
    def __init__(self, i, o):
        assert_is_signal_or_clocksignal(i)
        platform = LiteXContext.platform
        block = {
            "type"       : "GPIO",
            "size"       : 1,
            "location"   : platform.get_pin_location(o)[0],
            "properties" : platform.get_pin_properties(o),
            "name"       : i,
            "mode"       : "OUTPUT_CLK",
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(o)

class EfinixClkOutput(LiteXModule):
    @staticmethod
    def lower(dr):
        return EfinixClkOutputImpl(dr.i, dr.o)

# Efinix Tristate ----------------------------------------------------------------------------------

class EfinixTristateImpl(LiteXModule):
    def __init__(self, io, o, oe, i=None):
        platform = LiteXContext.platform

        # FIXME: TSTriple is not supported and only used by EfinixHyperRAM to connect HyperRAM core
        # HYPERRAM block
        from migen.fhdl.specials import TSTriple
        if isinstance(io, TSTriple):
            # Simply connect the TSTriple signals to o, oe, and i.
            self.comb += [
                io.oe.eq(oe),
                io.o.eq(o),
            ]
            if i is not None:
                self.comb += i.eq(io.i)
            return
        if len(io) == 1:
            io_name = platform.get_pin_name(io)
            io_pad  = platform.get_pin_location(io)
            io_prop = platform.get_pin_properties(io)
        else:
            io_name = platform.get_pins_name(io)
            io_pad  = platform.get_pins_location(io)
            io_prop = platform.get_pin_properties(io[0])
        io_prop_dict = dict(io_prop)
        if isinstance(o, Constant):
            const_output = const_output_calc(o, io)
        else:
            const_output = "NONE"
            io_data_i = platform.add_iface_io(io_name + "_OUT", len(io))
            self.comb += io_data_i.eq(o)
        io_data_e    = platform.add_iface_io(io_name + "_OE", len(io))
        self.comb += io_data_e.eq(oe if len(oe) == len(io) else Replicate(oe, len(io)))
        if i is not None:
            io_data_o  = platform.add_iface_io(io_name + "_IN", len(io))
            self.comb += i.eq(io_data_o)
        else:
            io_prop.append(("IN_PIN", ""))
        block = {
            "type"           : "GPIO",
            "mode"           : "INOUT",
            "name"           : io_name,
            "location"       : io_pad,
            "properties"     : io_prop,
            "size"           : len(io),
            "const_output"   : const_output,
            "drive_strength" : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(io))

class EfinixTristate(LiteXModule):
    @staticmethod
    def lower(dr):
        return EfinixTristateImpl(dr.target, dr.o, dr.oe, dr.i)

# Efinix DifferentialOutput ------------------------------------------------------------------------

class EfinixDifferentialOutputImpl(LiteXModule):
    def __init__(self, i, o_p, o_n):
        platform = LiteXContext.platform
        # only keep _p
        io_name = platform.get_pin_name(o_p)
        io_pad  = platform.get_pad_name(o_p) # need real pad name
        io_prop = platform.get_pin_properties(o_p)

        if platform.family in ["Titanium", "Topaz"]:
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

        i_data = platform.add_iface_io(io_name)

        self.comb += i_data.eq(i)
        block = {
            "type"     : "LVDS",
            "mode"     : "OUTPUT",
            "tx_mode"  : "DATA",
            "name"     : io_name,
            "sig"      : i_data,
            "location" : io_pad,
            "size"     : 1,
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(o_p))
        platform.toolchain.excluded_ios.append(platform.get_pin(o_n))

class EfinixDifferentialOutput:
    @staticmethod
    def lower(dr):
        return EfinixDifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)

# Efinix DifferentialInput -------------------------------------------------------------------------

class EfinixDifferentialInputImpl(LiteXModule):
    def __init__(self, i_p, i_n, o):
        platform = LiteXContext.platform
        # only keep _p
        io_name = platform.get_pin_name(i_p)
        io_pad  = platform.get_pad_name(i_p) # need real pad name
        io_prop = platform.get_pin_properties(i_p)

        if platform.family in ["Titanium", "Topaz"]:
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

        o_data = platform.add_iface_io(io_name)
        i_ena  = platform.add_iface_io(io_name + "_ena")
        i_term = platform.add_iface_io(io_name + "_term")

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

class EfinixDifferentialInput:
    @staticmethod
    def lower(dr):
        return EfinixDifferentialInputImpl(dr.i_p, dr.i_n, dr.o)

# Efinix DDRTristate -------------------------------------------------------------------------------

class EfinixTrionDDRTristateImpl(LiteXModule):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk):
        assert oe2 is None
        assert_is_signal_or_clocksignal(clk)
        platform     = LiteXContext.platform
        if len(io) == 1:
            io_name      = platform.get_pin_name(io)
            io_pad       = platform.get_pin_location(io)
            io_prop      = platform.get_pin_properties(io)
        else:
            io_name      = platform.get_pins_name(io)
            io_pad       = platform.get_pins_location(io)
            io_prop      = platform.get_pin_properties(io[0])
        io_prop_dict = dict(io_prop)
        io_data_i_h  = platform.add_iface_io(io_name + "_OUT_HI", len(io))
        io_data_i_l  = platform.add_iface_io(io_name + "_OUT_LO", len(io))
        io_data_e    = platform.add_iface_io(io_name + "_OE", len(io))
        self.comb += io_data_i_h.eq(o1)
        self.comb += io_data_i_l.eq(o2)
        self.comb += io_data_e.eq(oe1)
        if i1 is not None:
            sync = getattr(self.sync, clk.cd)
            io_data_o_h  = platform.add_iface_io(io_name + "_IN_HI", len(io))
            sync += i1.eq(io_data_o_h)
        else:
            io_prop.append(("IN_HI_PIN", ""))
        if i2 is not None:
            io_data_o_l  = platform.add_iface_io(io_name + "_IN_LO", len(io))
            self.comb += i2.eq(io_data_o_l)
        else:
            io_prop.append(("IN_LO_PIN", ""))
        block = {
            "type"           : "GPIO",
            "mode"           : "INOUT",
            "name"           : io_name,
            "location"       : io_pad,
            "properties"     : io_prop,
            "size"           : len(io),
            "in_reg"         : "DDIO_RESYNC",
            "in_clk_pin"     : clk,
            "out_reg"        : "DDIO_RESYNC",
            "out_clk_pin"    : clk,
            "oe_reg"         : "REG",
            "in_clk_inv"     : 0,
            "out_clk_inv"    : 0,
            "drive_strength" : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        if i1 is None and i2 is None:
            block.pop("in_reg")
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(io))

class EfinixTitaniumDDRTristateImpl(LiteXModule):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk):
        assert oe2 is None
        assert_is_signal_or_clocksignal(clk)
        platform     = LiteXContext.platform
        if len(io) == 1:
            io_name      = platform.get_pin_name(io)
            io_pad       = platform.get_pin_location(io)
            io_prop      = platform.get_pin_properties(io)
        else:
            io_name      = platform.get_pins_name(io)
            io_pad       = platform.get_pins_location(io)
            io_prop      = platform.get_pin_properties(io[0])
        io_prop_dict = dict(io_prop)
        io_data_i_h  = platform.add_iface_io(io_name + "_OUT_HI", len(io))
        io_data_i_l  = platform.add_iface_io(io_name + "_OUT_LO", len(io))
        io_data_e    = platform.add_iface_io(io_name + "_OE", len(io))
        self.comb += io_data_i_h.eq(o1)
        self.comb += io_data_i_l.eq(o2)
        self.comb += io_data_e.eq(oe1)
        if i1 is not None:
            io_data_o_h  = platform.add_iface_io(io_name + "_IN_HI", len(io))
            self.comb += i1.eq(io_data_o_h)
        else:
            io_prop.append(("IN_HI_PIN", ""))
        if i2 is not None:
            io_data_o_l  = platform.add_iface_io(io_name + "_IN_LO", len(io))
            self.comb += i2.eq(io_data_o_l)
        else:
            io_prop.append(("IN_LO_PIN", ""))
        block = {
            "type"           : "GPIO",
            "mode"           : "INOUT",
            "name"           : io_name,
            "location"       : io_pad,
            "properties"     : io_prop,
            "size"           : len(io),
            "in_reg"         : "DDIO_RESYNC_PIPE",
            "in_clk_pin"     : clk,
            "out_reg"        : "DDIO_RESYNC",
            "out_clk_pin"    : clk,
            "oe_reg"         : "REG",
            "in_clk_inv"     : 0,
            "out_clk_inv"    : 0,
            "drive_strength" : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        if i1 is None and i2 is None:
            block.pop("in_reg")
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(io))

class EfinixDDRTristate:
    @staticmethod
    def lower(dr):
        if LiteXContext.platform.family == "Trion":
            return EfinixTrionDDRTristateImpl(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk)
        else:
            return EfinixTitaniumDDRTristateImpl(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk)

class EfinixDDRResyncTristateImpl(LiteXModule):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk):
        assert oe2 is None
        assert_is_signal_or_clocksignal(clk)
        platform     = LiteXContext.platform
        if len(io) == 1:
            io_name      = platform.get_pin_name(io)
            io_pad       = platform.get_pin_location(io)
            io_prop      = platform.get_pin_properties(io)
        else:
            io_name      = platform.get_pins_name(io)
            io_pad       = platform.get_pins_location(io)
            io_prop      = platform.get_pin_properties(io[0])
        io_prop_dict = dict(io_prop)
        io_data_i_h  = platform.add_iface_io(io_name + "_OUT_HI", len(io))
        io_data_i_l  = platform.add_iface_io(io_name + "_OUT_LO", len(io))
        io_data_e    = platform.add_iface_io(io_name + "_OE", len(io))
        self.comb += io_data_i_h.eq(o1)
        self.comb += io_data_i_l.eq(o2)
        self.comb += io_data_e.eq(oe1)
        if i1 is not None:
            io_data_o_h  = platform.add_iface_io(io_name + "_IN_HI", len(io))
            self.comb += i1.eq(io_data_o_h)
        else:
            io_prop.append(("IN_HI_PIN", ""))
        if i2 is not None:
            io_data_o_l  = platform.add_iface_io(io_name + "_IN_LO", len(io))
            self.comb += i2.eq(io_data_o_l)
        else:
            io_prop.append(("IN_LO_PIN", ""))
        block = {
            "type"           : "GPIO",
            "mode"           : "INOUT",
            "name"           : io_name,
            "location"       : io_pad,
            "properties"     : io_prop,
            "size"           : len(io),
            "in_reg"         : "DDIO_RESYNC",
            "in_clk_pin"     : clk,
            "out_reg"        : "DDIO_RESYNC",
            "out_clk_pin"    : clk,
            "oe_reg"         : "REG",
            "in_clk_inv"     : 0,
            "out_clk_inv"    : 0,
            "drive_strength" : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        if i1 is None and i2 is None:
            block.pop("in_reg")
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(io))

class EfinixDDRResyncTristate(DDRTristate):
    @staticmethod
    def lower(dr):
        return EfinixDDRResyncTristateImpl(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk)

# Efinix SDRTristate -------------------------------------------------------------------------------

class EfinixSDRTristateImpl(LiteXModule):
    def __init__(self, io, o, oe, i, clk):
        assert_is_signal_or_clocksignal(clk)
        platform     = LiteXContext.platform
        if len(io) == 1:
            io_name      = platform.get_pin_name(io)
            io_pad       = platform.get_pin_location(io)
            io_prop      = platform.get_pin_properties(io)
        else:
            io_name      = platform.get_pins_name(io)
            io_pad       = platform.get_pins_location(io)
            io_prop      = platform.get_pin_properties(io[0])
        io_prop_dict = dict(io_prop)
        if isinstance(o, Constant):
            const_output = const_output_calc(o, io)
        else:
            const_output = "NONE"
            io_data_i = platform.add_iface_io(io_name + "_OUT", len(io))
            self.comb += io_data_i.eq(o)                
        io_data_e    = platform.add_iface_io(io_name + "_OE", len(io))
        self.comb += io_data_e.eq(oe)
        if i is not None:
            io_data_o    = platform.add_iface_io(io_name + "_IN", len(io))
            self.comb += i.eq(io_data_o)
        else:
            io_prop.append(("IN_PIN", ""))
        block = {
            "type"           : "GPIO",
            "mode"           : "INOUT",
            "name"           : io_name,
            "location"       : io_pad,
            "properties"     : io_prop,
            "size"           : len(io),
            "in_reg"         : "REG",
            "in_clk_pin"     : clk,
            "out_reg"        : "REG",
            "out_clk_pin"    : clk,
            "const_output"   : const_output,
            "oe_reg"         : "REG",
            "in_clk_inv"     : 0,
            "out_clk_inv"    : 0,
            "drive_strength" : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        if i is None:
            block.pop("in_reg")
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(io))


class EfinixSDRTristate(LiteXModule):
    @staticmethod
    def lower(dr):
        return EfinixSDRTristateImpl(dr.io, dr.o, dr.oe, dr.i, dr.clk)

# Efinix SDROutput ---------------------------------------------------------------------------------

class EfinixSDROutputImpl(LiteXModule):
    def __init__(self, i, o, clk):
        assert_is_signal_or_clocksignal(clk)
        platform     = LiteXContext.platform
        if len(o) == 1:
            io_name      = platform.get_pin_name(o)
            io_pad       = platform.get_pin_location(o)
            io_prop      = platform.get_pin_properties(o)
        else:
            io_name      = platform.get_pins_name(o)
            io_pad       = platform.get_pins_location(o)
            io_prop      = platform.get_pin_properties(o[0])
        io_prop_dict = dict(io_prop)
        if isinstance(i, Constant):
            const_output = const_output_calc(i, o)
        else:
            const_output = "NONE"
            io_data_i    = platform.add_iface_io(io_name, len(o))
            self.comb += io_data_i.eq(i)
        block = {
            "type"           : "GPIO",
            "mode"           : "OUTPUT",
            "name"           : io_name,
            "location"       : io_pad,
            "properties"     : io_prop,
            "size"           : len(o),
            "out_reg"        : "REG",
            "out_clk_pin"    : clk,
            "const_output"   : const_output,
            "out_clk_inv"    : 0,
            "drive_strength" : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(o))


class EfinixSDROutput(LiteXModule):
    @staticmethod
    def lower(dr):
        return EfinixSDROutputImpl(dr.i, dr.o, dr.clk)

# Efinix DDROutput ---------------------------------------------------------------------------------

class EfinixDDROutputImpl(LiteXModule):
    def __init__(self, i1, i2, o, clk):
        assert_is_signal_or_clocksignal(clk)
        platform     = LiteXContext.platform
        if len(o) == 1:
            io_name      = platform.get_pin_name(o)
            io_pad       = platform.get_pin_location(o)
            io_prop      = platform.get_pin_properties(o)
        else:
            io_name      = platform.get_pins_name(o)
            io_pad       = platform.get_pins_location(o)
            io_prop      = platform.get_pin_properties(o[0])
        io_prop_dict = dict(io_prop)
        io_data_h    = platform.add_iface_io(io_name + "_HI", len(o))
        io_data_l    = platform.add_iface_io(io_name + "_LO", len(o))
        self.comb += io_data_h.eq(i1)
        self.comb += io_data_l.eq(i2)
        block = {
            "type"              : "GPIO",
            "mode"              : "OUTPUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : len(o),
            "out_reg"           : "DDIO_RESYNC",
            "out_clk_pin"       : clk,
            "out_clk_inv"       : 0,
            "drive_strength"    : io_prop_dict.get("DRIVE_STRENGTH", "4")
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(o))

class EfinixDDROutput:
    @staticmethod
    def lower(dr):
        return EfinixDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# Efinix SDRInput ----------------------------------------------------------------------------------

class EfinixSDRInputImpl(LiteXModule):
    def __init__(self, i, o, clk):
        assert_is_signal_or_clocksignal(clk)
        platform = LiteXContext.platform
        if len(i) == 1:
            io_name  = platform.get_pin_name(i)
            io_pad   = platform.get_pin_location(i)
            io_prop  = platform.get_pin_properties(i)
        else:
            io_name  = platform.get_pins_name(i)
            io_pad   = platform.get_pins_location(i)
            io_prop  = platform.get_pin_properties(i[0])
        io_data  = platform.add_iface_io(io_name, len(i))
        self.comb += o.eq(io_data)
        block = {
            "type"              : "GPIO",
            "mode"              : "INPUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : len(i),
            "in_reg"            : "REG",
            "in_clk_pin"        : clk,
            "in_clk_inv"        : 0
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(i))

class EfinixSDRInput:
    @staticmethod
    def lower(dr):
        return EfinixSDRInputImpl(dr.i, dr.o, dr.clk)

# Efinix DDRInput ----------------------------------------------------------------------------------

class EfinixTrionDDRInputImpl(LiteXModule):
    def __init__(self, i, o1, o2, clk):
        assert_is_signal_or_clocksignal(clk)
        platform  = LiteXContext.platform
        if len(i) == 1:
            io_name   = platform.get_pin_name(i)
            io_pad    = platform.get_pin_location(i)
            io_prop   = platform.get_pin_properties(i)
        else:
            io_name   = platform.get_pins_name(i)
            io_pad    = platform.get_pins_location(i)
            io_prop   = platform.get_pin_properties(i[0])
        io_data_h = platform.add_iface_io(io_name + "_HI", len(i))
        io_data_l = platform.add_iface_io(io_name + "_LO", len(i))
        sync = getattr(self.sync, clk.cd)
        sync += o1.eq(io_data_h)
        self.comb += o2.eq(io_data_l)
        block = {
            "type"              : "GPIO",
            "mode"              : "INPUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : len(i),
            "in_reg"            : "DDIO_RESYNC",
            "in_clk_pin"        : clk,
            "in_clk_inv"        : 0
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(i))

class EfinixTitaniumDDRInputImpl(LiteXModule):
    def __init__(self, i, o1, o2, clk):
        assert_is_signal_or_clocksignal(clk)
        platform  = LiteXContext.platform
        if len(i) == 1:
            io_name   = platform.get_pin_name(i)
            io_pad    = platform.get_pin_location(i)
            io_prop   = platform.get_pin_properties(i)
        else:
            io_name   = platform.get_pins_name(i)
            io_pad    = platform.get_pins_location(i)
            io_prop   = platform.get_pin_properties(i[0])
        io_data_h = platform.add_iface_io(io_name + "_HI", len(i))
        io_data_l = platform.add_iface_io(io_name + "_LO", len(i))
        self.comb += o1.eq(io_data_h)
        self.comb += o2.eq(io_data_l)
        block = {
            "type"              : "GPIO",
            "mode"              : "INPUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : len(i),
            "in_reg"            : "DDIO_RESYNC_PIPE",
            "in_clk_pin"        : clk,
            "in_clk_inv"        : 0
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(i))

class EfinixDDRInput:
    @staticmethod
    def lower(dr):
        if LiteXContext.platform.family == "Trion":
            return EfinixTrionDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)
        else:
            return EfinixTitaniumDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

class EfinixDDRResyncInputImpl(LiteXModule):
    def __init__(self, i, o1, o2, clk):
        assert_is_signal_or_clocksignal(clk)
        platform  = LiteXContext.platform
        if len(i) == 1:
            io_name   = platform.get_pin_name(i)
            io_pad    = platform.get_pin_location(i)
            io_prop   = platform.get_pin_properties(i)
        else:
            io_name   = platform.get_pins_name(i)
            io_pad    = platform.get_pins_location(i)
            io_prop   = platform.get_pin_properties(i[0])
        io_data_h = platform.add_iface_io(io_name + "_HI", len(i))
        io_data_l = platform.add_iface_io(io_name + "_LO", len(i))
        self.comb += o1.eq(io_data_h)
        self.comb += o2.eq(io_data_l)
        block = {
            "type"              : "GPIO",
            "mode"              : "INPUT",
            "name"              : io_name,
            "location"          : io_pad,
            "properties"        : io_prop,
            "size"              : len(i),
            "in_reg"            : "DDIO_RESYNC",
            "in_clk_pin"        : clk,
            "in_clk_inv"        : 0
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.toolchain.excluded_ios.append(platform.get_pin(i))

class EfinixDDRResyncInput(DDRInput):
    @staticmethod
    def lower(dr):
        return EfinixDDRResyncInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# Efinix Special Overrides -------------------------------------------------------------------------

efinix_special_overrides = {
    AsyncResetSynchronizer : EfinixAsyncResetSynchronizer,
    ClkInput               : EfinixClkInput,
    ClkOutput              : EfinixClkOutput,
    Tristate               : EfinixTristate,
    DifferentialOutput     : EfinixDifferentialOutput,
    DifferentialInput      : EfinixDifferentialInput,
    SDROutput              : EfinixSDROutput,
    SDRInput               : EfinixSDRInput,
    SDRTristate            : EfinixSDRTristate,
    DDROutput              : EfinixDDROutput,
    DDRInput               : EfinixDDRInput,
    DDRTristate            : EfinixDDRTristate,
}
