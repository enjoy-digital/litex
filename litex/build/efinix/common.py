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

def gpio_info(platform, sig):
    if len(sig) == 1:
        return (
            platform.get_pin_name(sig),
            platform.get_pin_location(sig),
            platform.get_pin_properties(sig),
        )
    return (
        platform.get_pins_name(sig),
        platform.get_pins_location(sig),
        platform.get_pin_properties(sig[0]),
    )

def add_gpio_block(platform, block, sig):
    platform.toolchain.ifacewriter.blocks.append(block)
    platform.toolchain.excluded_ios.append(platform.get_pin(sig))

def use_unified_netlist_flow(platform):
    return getattr(platform.toolchain, "unified", False)

def signal_bit(sig, bit):
    return sig if len(sig) == 1 else sig[bit]

def signal_bits(sig):
    return range(len(sig))

def get_pull_option(platform, sig):
    properties = platform.get_pin_properties(sig)
    if properties is None:
        return "NONE"
    return dict(properties).get("PULL_OPTION", "NONE")

def get_oe_bit(oe, bit, nbits):
    return signal_bit(oe, bit) if len(oe) == nbits else oe

def get_gpio_ddr_primitive(platform):
    return "EFX_GPIO_V2" if platform.family == "Trion" else "EFX_GPIO_V3"

def get_lvds_tx_primitive(platform):
    return "EFX_LVDS_TX_V1" if platform.family == "Trion" else "EFX_LVDS_TX_V2"

def get_lvds_rx_primitive(platform):
    return "EFX_LVDS_RX_V1" if platform.family == "Trion" else "EFX_LVDS_RX_V2"

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

class EfinixUnifiedClkInputImpl(LiteXModule):
    def __init__(self, i, o):
        if isinstance(o, str):
            raise NotImplementedError("Efinity unified netlist flow requires ClkInput output to be a Signal")
        platform = LiteXContext.platform
        if isinstance(o, Signal):
            platform.clks.setdefault(o.name_override, platform.get_pin_name(i))
        self.specials += Instance("EFX_IBUF",
            p_PULL_OPTION = get_pull_option(platform, i),
            i_I           = i,
            o_O           = o,
        )

class EfinixClkInput(LiteXModule):
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedClkInputImpl(dr.i, dr.o)
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

class EfinixUnifiedClkOutputImpl(LiteXModule):
    def __init__(self, i, o):
        assert_is_signal_or_clocksignal(i)
        self.specials += Instance("EFX_OBUF",
            i_I = i,
            o_O = o,
        )

class EfinixClkOutput(LiteXModule):
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedClkOutputImpl(dr.i, dr.o)
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
        io_name, io_pad, io_prop = gpio_info(platform, io)
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
        add_gpio_block(platform, block, io)

class EfinixUnifiedTristateImpl(LiteXModule):
    def __init__(self, io, o, oe, i=None):
        # FIXME: TSTriple is not supported and only used by EfinixHyperRAM to connect HyperRAM core
        # HYPERRAM block
        from migen.fhdl.specials import TSTriple
        if isinstance(io, TSTriple):
            self.comb += [
                io.oe.eq(oe),
                io.o.eq(o),
            ]
            if i is not None:
                self.comb += i.eq(io.i)
            return

        platform = LiteXContext.platform
        pull_option = get_pull_option(platform, io[0] if len(io) > 1 else io)

        for bit in signal_bits(io):
            i_bit = Signal() if i is None else signal_bit(i, bit)
            self.specials += Instance("EFX_IO_BUF",
                p_PULL_OPTION = pull_option,
                i_I           = signal_bit(o, bit),
                i_OE          = get_oe_bit(oe, bit, len(io)),
                o_O           = i_bit,
                io_IO         = signal_bit(io, bit),
            )

class EfinixTristate(LiteXModule):
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedTristateImpl(dr.target, dr.o, dr.oe, dr.i)
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

class EfinixUnifiedDifferentialOutputImpl(LiteXModule):
    def __init__(self, i, o_p, o_n):
        platform = LiteXContext.platform
        primitive = get_lvds_tx_primitive(platform)

        if primitive == "EFX_LVDS_TX_V1":
            self.specials += Instance(primitive,
                p_SERIALIZATION_WIDTH = 8,
                p_SERIALIZATION_EN    = 0,
                p_MODE                = "DATA",
                p_OUTPUT_LOAD         = 7,
                p_REDUCED_SWING       = 0,
                i_O                   = Cat(i, Replicate(0, 7)),
                i_OE                  = 1,
                i_SLOWCLK             = 0,
                i_FASTCLK             = 0,
                o_P                   = o_p,
                o_N                   = o_n,
            )
        else:
            self.specials += Instance(primitive,
                p_SERIALIZATION_WIDTH = 1,
                p_HALF_RATE_EN        = 0,
                p_SERIALIZATION_EN    = 0,
                p_MODE                = "DATA",
                p_PRE_EMPHASIS        = "MEDIUM_LOW",
                p_DIFF_TYPE           = "LVDS",
                p_VOD                 = "TYPICAL",
                p_DELAY               = 0,
                i_O                   = Cat(i, Replicate(0, 9)),
                i_OE                  = 1,
                i_RST                 = 0,
                i_SLOWCLK             = 0,
                i_FASTCLK             = 0,
                o_P                   = o_p,
                o_N                   = o_n,
            )

class EfinixDifferentialOutput:
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedDifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)
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

class EfinixUnifiedDifferentialInputImpl(LiteXModule):
    def __init__(self, i_p, i_n, o):
        platform = LiteXContext.platform
        primitive = get_lvds_rx_primitive(platform)

        if primitive == "EFX_LVDS_RX_V1":
            i_data = Signal(8)
            self.specials += Instance(primitive,
                p_DESERIALIZATION_WIDTH = 8,
                p_DESERIALIZATION_EN    = 0,
                p_TERMINATION_TYPE      = "ON",
                p_CONNECTION_TYPE       = "NORMAL",
                p_DELAY                 = 0,
                i_P                     = i_p,
                i_N                     = i_n,
                i_SLOWCLK               = 0,
                i_FASTCLK               = 0,
                o_I                     = i_data,
                o_ALT                   = Signal(),
            )
        else:
            i_data = Signal(10)
            self.specials += Instance(primitive,
                p_DESERIALIZATION_WIDTH = 1,
                p_HALF_RATE_EN          = 0,
                p_DESERIALIZATION_EN    = 0,
                p_FIFO_EN               = 0,
                p_TERMINATION_TYPE      = "ON",
                p_CONNECTION_TYPE       = "NORMAL",
                p_DIFF_TYPE             = "LVDS",
                p_DELAY_MODE            = "STATIC",
                p_DELAY                 = 0,
                p_VOC_DRIVER_EN         = 0,
                i_P                     = i_p,
                i_N                     = i_n,
                i_SLOWCLK               = 0,
                i_FASTCLK               = 0,
                i_FIFOCLK               = 0,
                i_FIFO_RD               = 0,
                i_RST                   = 0,
                i_ENA                   = 1,
                i_TERM                  = 1,
                i_DLY_ENA               = 0,
                i_DLY_INC               = 0,
                i_DLY_RST               = 0,
                o_I                     = i_data,
                o_ALT                   = Signal(),
                o_FIFO_EMPTY            = Signal(),
                o_LOCK                  = Signal(),
                o_DBG                   = Signal(6),
            )

        self.comb += o.eq(i_data[0])

class EfinixDifferentialInput:
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedDifferentialInputImpl(dr.i_p, dr.i_n, dr.o)
        return EfinixDifferentialInputImpl(dr.i_p, dr.i_n, dr.o)

# Efinix DDRTristate -------------------------------------------------------------------------------

class EfinixTrionDDRTristateImpl(LiteXModule):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk, i_async):
        assert oe2 is None
        assert_is_signal_or_clocksignal(clk)
        if i_async is not None and (i1 is not None or i2 is not None):
            raise ValueError("Efinix DDRTristate i_async cannot be combined with registered inputs")
        platform     = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, io)
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
        if i_async is not None:
            io_data_o    = platform.add_iface_io(io_name + "_IN", len(io))
            self.comb += i_async.eq(io_data_o)
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
        add_gpio_block(platform, block, io)

class EfinixTitaniumDDRTristateImpl(LiteXModule):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk, i_async):
        assert oe2 is None
        assert_is_signal_or_clocksignal(clk)
        if i_async is not None and (i1 is not None or i2 is not None):
            raise ValueError("Efinix DDRTristate i_async cannot be combined with registered inputs")
        platform     = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, io)
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
        if i_async is not None:
            io_data_o    = platform.add_iface_io(io_name + "_IN", len(io))
            self.comb += i_async.eq(io_data_o)
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
        add_gpio_block(platform, block, io)

class EfinixDDRTristate:
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedDDRTristateImpl(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk, dr.i_async)
        if LiteXContext.platform.family == "Trion":
            return EfinixTrionDDRTristateImpl(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk, dr.i_async)
        else:
            return EfinixTitaniumDDRTristateImpl(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk, dr.i_async)

class EfinixUnifiedDDRTristateImpl(LiteXModule):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk, i_async):
        assert oe2 is None
        assert_is_signal_or_clocksignal(clk)
        if i_async is not None and (i1 is not None or i2 is not None):
            raise ValueError("Efinix DDRTristate i_async cannot be combined with registered inputs")

        platform = LiteXContext.platform
        primitive = get_gpio_ddr_primitive(platform)
        pull_option = get_pull_option(platform, io[0] if len(io) > 1 else io)

        registered_input = i1 is not None and i2 is not None
        in_reg = "DDIO_RESYNC" if registered_input else "BYPASS"

        for bit in signal_bits(io):
            i_hi = signal_bit(i1, bit) if registered_input else Signal()
            i_lo = signal_bit(i2, bit) if registered_input else Signal()
            i_async_bit = signal_bit(i_async, bit) if i_async is not None else Signal()
            if primitive == "EFX_GPIO_V2":
                self.specials += Instance(primitive,
                    p_MODE                = "INOUT",
                    p_OUT_REG             = "DDIO_RESYNC",
                    p_IN_REG              = in_reg,
                    p_OE_REG              = "REG",
                    p_PULL_OPTION         = pull_option,
                    p_IS_OUTCLK_INVERTED  = 0,
                    p_IS_INCLK_INVERTED   = 0,
                    i_O                   = Cat(signal_bit(o1, bit), signal_bit(o2, bit)),
                    i_OE                  = get_oe_bit(oe1, bit, len(io)),
                    i_OUTCLK              = clk,
                    i_INCLK               = clk,
                    o_I                   = Cat(i_hi, i_lo) if registered_input else Cat(i_async_bit, Signal()),
                    o_ALT                 = Signal(),
                    io_IO                 = signal_bit(io, bit),
                )
            else:
                self.specials += Instance(primitive,
                    p_MODE                   = "INOUT",
                    p_OUT_REG                = "DDIO_RESYNC",
                    p_IN_REG                 = in_reg,
                    p_OE_REG                 = "REG",
                    p_PULL_OPTION            = pull_option,
                    p_IS_OUTCLK_INVERTED     = 0,
                    p_IS_OUTFASTCLK_INVERTED = 0,
                    p_IS_INCLK_INVERTED      = 0,
                    p_IS_INFASTCLK_INVERTED  = 0,
                    p_IS_DLYCLK_INVERTED     = 0,
                    i_O                      = Cat(signal_bit(o1, bit), signal_bit(o2, bit), 0, 0),
                    i_OE                     = get_oe_bit(oe1, bit, len(io)),
                    i_OEN                    = 1,
                    i_PULL_UP_ENA            = 0,
                    i_DLY_ENA                = 0,
                    i_DLY_INC                = 0,
                    i_DLY_RST                = 0,
                    i_OUTCLK                 = clk,
                    i_INCLK                  = clk,
                    i_DLYCLK                 = 0,
                    i_OUTFASTCLK             = 0,
                    i_INFASTCLK              = 0,
                    o_I                      = Cat(i_hi, i_lo, Signal(), Signal()) if registered_input else Cat(i_async_bit, Signal(), Signal(), Signal()),
                    o_ALT                    = Signal(),
                    io_IO                    = signal_bit(io, bit),
                )

class EfinixDDRResyncTristateImpl(LiteXModule):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk, i_async):
        assert oe2 is None
        assert_is_signal_or_clocksignal(clk)
        if i_async is not None and (i1 is not None or i2 is not None):
            raise ValueError("Efinix DDRTristate i_async cannot be combined with registered inputs")
        platform     = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, io)
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
        if i_async is not None:
            io_data_o    = platform.add_iface_io(io_name + "_IN", len(io))
            self.comb += i_async.eq(io_data_o)
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
        add_gpio_block(platform, block, io)

class EfinixDDRResyncTristate(DDRTristate):
    @staticmethod
    def lower(dr):
        return EfinixDDRResyncTristateImpl(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk, dr.i_async)

# Efinix SDRTristate -------------------------------------------------------------------------------

class EfinixSDRTristateImpl(LiteXModule):
    def __init__(self, io, o, oe, i, clk):
        assert_is_signal_or_clocksignal(clk)
        platform     = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, io)
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
        add_gpio_block(platform, block, io)


class EfinixUnifiedSDRTristateImpl(LiteXModule):
    def __init__(self, io, o, oe, i, clk):
        assert_is_signal_or_clocksignal(clk)
        platform = LiteXContext.platform
        pull_option = get_pull_option(platform, io[0] if len(io) > 1 else io)
        for bit in signal_bits(io):
            i_bit = Signal() if i is None else signal_bit(i, bit)
            self.specials += Instance("EFX_IOREG",
                p_PULL_OPTION        = pull_option,
                p_IS_OUTCLK_INVERTED = 0,
                p_IS_INCLK_INVERTED  = 0,
                i_I                  = signal_bit(o, bit),
                i_OE                 = get_oe_bit(oe, bit, len(io)),
                i_INCLK              = clk,
                i_OUTCLK             = clk,
                o_O                  = i_bit,
                io_IO                = signal_bit(io, bit),
            )

class EfinixSDRTristate(LiteXModule):
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedSDRTristateImpl(dr.io, dr.o, dr.oe, dr.i, dr.clk)
        return EfinixSDRTristateImpl(dr.io, dr.o, dr.oe, dr.i, dr.clk)

# Efinix SDROutput ---------------------------------------------------------------------------------

class EfinixSDROutputImpl(LiteXModule):
    def __init__(self, i, o, clk):
        assert_is_signal_or_clocksignal(clk)
        platform     = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, o)
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
        add_gpio_block(platform, block, o)

class EfinixUnifiedSDROutputImpl(LiteXModule):
    def __init__(self, i, o, clk):
        assert_is_signal_or_clocksignal(clk)
        for bit in signal_bits(o):
            self.specials += Instance("EFX_OREG",
                p_IS_CLK_INVERTED = 0,
                i_I               = signal_bit(i, bit),
                i_CLK             = clk,
                o_O               = signal_bit(o, bit),
            )

class EfinixSDROutput(LiteXModule):
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedSDROutputImpl(dr.i, dr.o, dr.clk)
        return EfinixSDROutputImpl(dr.i, dr.o, dr.clk)

# Efinix DDROutput ---------------------------------------------------------------------------------

class EfinixDDROutputImpl(LiteXModule):
    def __init__(self, i1, i2, o, clk):
        assert_is_signal_or_clocksignal(clk)
        platform     = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, o)
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
        add_gpio_block(platform, block, o)

class EfinixDDROutput:
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)
        return EfinixDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

class EfinixUnifiedDDROutputImpl(LiteXModule):
    def __init__(self, i1, i2, o, clk):
        assert_is_signal_or_clocksignal(clk)
        for bit in signal_bits(o):
            self.specials += Instance("EFX_ODDIO",
                p_MODE            = "DDIO_RESYNC",
                p_IS_CLK_INVERTED = 0,
                i_CLK             = clk,
                i_I_HI            = signal_bit(i1, bit),
                i_I_LO            = signal_bit(i2, bit),
                o_O               = signal_bit(o, bit),
            )

# Efinix SDRInput ----------------------------------------------------------------------------------

class EfinixSDRInputImpl(LiteXModule):
    def __init__(self, i, o, clk):
        assert_is_signal_or_clocksignal(clk)
        platform = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, i)
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
        add_gpio_block(platform, block, i)

class EfinixUnifiedSDRInputImpl(LiteXModule):
    def __init__(self, i, o, clk):
        assert_is_signal_or_clocksignal(clk)
        platform = LiteXContext.platform
        pull_option = get_pull_option(platform, i[0] if len(i) > 1 else i)
        for bit in signal_bits(i):
            self.specials += Instance("EFX_IREG",
                p_PULL_OPTION     = pull_option,
                p_IS_CLK_INVERTED = 0,
                i_I               = signal_bit(i, bit),
                i_CLK             = clk,
                o_O               = signal_bit(o, bit),
            )

class EfinixSDRInput:
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedSDRInputImpl(dr.i, dr.o, dr.clk)
        return EfinixSDRInputImpl(dr.i, dr.o, dr.clk)

# Efinix DDRInput ----------------------------------------------------------------------------------

class EfinixTrionDDRInputImpl(LiteXModule):
    def __init__(self, i, o1, o2, clk):
        assert_is_signal_or_clocksignal(clk)
        platform  = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, i)
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
        add_gpio_block(platform, block, i)

class EfinixTitaniumDDRInputImpl(LiteXModule):
    def __init__(self, i, o1, o2, clk):
        assert_is_signal_or_clocksignal(clk)
        platform  = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, i)
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
        add_gpio_block(platform, block, i)

class EfinixDDRInput:
    @staticmethod
    def lower(dr):
        if use_unified_netlist_flow(LiteXContext.platform):
            return EfinixUnifiedDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)
        if LiteXContext.platform.family == "Trion":
            return EfinixTrionDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)
        else:
            return EfinixTitaniumDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

class EfinixUnifiedDDRInputImpl(LiteXModule):
    def __init__(self, i, o1, o2, clk):
        assert_is_signal_or_clocksignal(clk)
        platform = LiteXContext.platform
        pull_option = get_pull_option(platform, i[0] if len(i) > 1 else i)
        for bit in signal_bits(i):
            self.specials += Instance("EFX_IDDIO",
                p_MODE            = "DDIO_RESYNC",
                p_PULL_OPTION     = pull_option,
                p_IS_CLK_INVERTED = 0,
                i_I               = signal_bit(i, bit),
                i_CLK             = clk,
                o_O_HI            = signal_bit(o1, bit),
                o_O_LO            = signal_bit(o2, bit),
            )

class EfinixDDRResyncInputImpl(LiteXModule):
    def __init__(self, i, o1, o2, clk):
        assert_is_signal_or_clocksignal(clk)
        platform  = LiteXContext.platform
        io_name, io_pad, io_prop = gpio_info(platform, i)
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
        add_gpio_block(platform, block, i)

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
