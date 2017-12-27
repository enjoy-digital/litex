# This file is Copyright (c) 2015, 2017 William D. Jones <thor0505@comcast.net>
# License: BSD

from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform
from litex.build.xilinx.programmer import XC3SProg


_io = [
    ("clk50", 0, Pins("P43"), IOStandard("LVCMOS33")),

    ("user_btn", 0, Pins("P41"), IOStandard("LVTTL")),

    # The serial interface and flash memory have a shared SPI bus.
    # FPGA is secondary
    ("spiserial", 0,
        Subsignal("cs_n", Pins("P39"), IOStandard("LVTTL")),
        Subsignal("clk", Pins("P53"), IOStandard("LVTTL")),
        Subsignal("mosi", Pins("P46"), IOStandard("LVTTL")),
        Subsignal("miso", Pins("P51"), IOStandard("LVTTL"))
    ),

    # FPGA is primary
    ("spiflash", 0,
        Subsignal("cs_n", Pins("P27"), IOStandard("LVTTL")),
        Subsignal("clk", Pins("P53"), IOStandard("LVTTL")),
        Subsignal("mosi", Pins("P46"), IOStandard("LVTTL")),
        Subsignal("miso", Pins("P51"), IOStandard("LVTTL"))
    ),

    ("spiflash2x", 0,
        Subsignal("cs_n", Pins("P27")),
        Subsignal("clk", Pins("P53")),
        Subsignal("dq", Pins("P46", "P51")),
        IOStandard("LVTTL"), Misc("SLEW=FAST")
    ),

    # ADC over SPI- FPGA is primary
    ("adc", 0,
        Subsignal("cs_n", Pins("P12"), IOStandard("LVTTL")),
        Subsignal("clk",  Pins("P9"), IOStandard("LVTTL")),
        Subsignal("mosi", Pins("P10"), IOStandard("LVTTL")),
        Subsignal("miso", Pins("P21"), IOStandard("LVTTL"))
    ),

    # GPIO control- SRAM and connectors are shared: these pins control how
    # to access each. Recommended to combine with gpio_sram_bus extension,
    # since these pins are related but not exposed on connectors.
    ("gpio_ctl", 0,
        Subsignal("ce_n", Pins("P3")),  # Memory chip-enable. Called MEM_CEN
        # in schematic.
        Subsignal("bussw_oe_n", Pins("P30")),  # 5V tolerant GPIO is shared
        # w/ memory using this pin.
        IOStandard("LVTTL"), Misc("SLEW=FAST")
    )
]

# Perhaps define some connectors as having a specific purpose- i.e. a 5V GPIO
# bus with data, peripheral-select, and control signals?
_connectors = [
    ("GPIO", """P59 P60 P61 P62 P64 P57
                P56 P52 P50 P49 P85 P84
                P83 P78 P77 P65 P70 P71
                P72 P73 P5 P4 P6 P98
                P94 P93 P90 P89 P88 P86"""),  # 5V I/O- LVTTL
    ("DIO", "P20 P32 P33 P34 P35 P36 P37"),  # Fast 3.3V IO (Directly attached
    # to FPGA)- LVCMOS33
    ("CLKIO", "P40 P44"),  # Clock IO (Can be used as GPIO)- LVCMOS33
    ("INPUT", "P68 P97 P7 P82"),  # Input-only pins- LVCMOS33
    ("LED", "P13 P15 P16 P19"),  # LEDs can be used as pins as well- LVTTL.
    ("PMOD", "P5 P4 P6 P98 P94 P93 P90 P89")  # Baseboard PMOD.
    # Overlaps w/ GPIO bus.
]


# Some default useful extensions- use platform.add_extension() to use, e.g.
# from migen.build.platforms import mercury
# plat = mercury.Platform()
# plat.add_extension(mercury.gpio_sram)

# SRAM and 5V-tolerant I/O share a parallel bus on 200k gate version. The SRAM
# controller needs to take care of switching the bus between the two. Meant to
# be Cat() into one GPIO bus, and combined with gpio_ctl.
gpio_sram = [
    ("gpio_sram_bus", 0,
        Subsignal("a", Pins("""GPIO:0 GPIO:1 GPIO:2 GPIO:3
                               GPIO:4 GPIO:5 GPIO:6 GPIO:7
                               GPIO:8 GPIO:9 GPIO:10 GPIO:11
                               GPIO:12 GPIO:13 GPIO:14 GPIO:15
                               GPIO:16 GPIO:17 GPIO:18 GPIO:19""")),
        # A19 is actually unused- free for GPIO
        # 8-bit data bus
        Subsignal("d", Pins("""GPIO:20 GPIO:21 GPIO:22 GPIO:23
                               GPIO:24 GPIO:25 GPIO:26 GPIO:27""")),
        Subsignal("we_n", Pins("GPIO:28")),
        Subsignal("unused", Pins("GPIO:29")),  # Only used by GPIO.
        # Subsignal("oe_n", Pins()),  # If OE wasn't tied to ground on Mercury,
        # this pin would be here.
        IOStandard("LVTTL"), Misc("SLEW=FAST")
    )
]

# The "serial port" is in fact over SPI. The creators of the board provide a
# VHDL file for talking over this interface. In light of space constraints and
# the fact that both the FT245RL and FPGA can BOTH be SPI primaries, however,
# it may be necessary to sacrifice two "high-speed" (DIO, INPUT) pins instead.
serial = [
    ("serial", 0,
        Subsignal("tx", Pins("DIO:0"), IOStandard("LVCMOS33")),  # FTDI D1
        Subsignal("rx", Pins("INPUT:0"), IOStandard("LVCMOS33"))  # FTDI D0
    )
]

leds = [
    ("user_led", 0, Pins("LED:0"), IOStandard("LVTTL")),
    ("user_led", 1, Pins("LED:1"), IOStandard("LVTTL")),
    ("user_led", 2, Pins("LED:2"), IOStandard("LVTTL")),
    ("user_led", 3, Pins("LED:3"), IOStandard("LVTTL"))
]


# The remaining peripherals only make sense w/ the Baseboard installed.
# See: http://www.micro-nova.com/mercury-baseboard/
sw = [
    ("sw", 0, Pins("GPIO:0"), IOStandard("LVTTL")),
    ("sw", 1, Pins("GPIO:1"), IOStandard("LVTTL")),
    ("sw", 2, Pins("GPIO:2"), IOStandard("LVTTL")),
    ("sw", 3, Pins("GPIO:3"), IOStandard("LVTTL")),
    ("sw", 4, Pins("GPIO:4"), IOStandard("LVTTL")),
    ("sw", 5, Pins("GPIO:5"), IOStandard("LVTTL")),
    ("sw", 6, Pins("GPIO:6"), IOStandard("LVTTL")),
    ("sw", 7, Pins("GPIO:7"), IOStandard("LVTTL"))
]

user_btn = [
    ("user_btn", 1, Pins("INPUT:0"), IOStandard("LVTTL")),
    ("user_btn", 2, Pins("INPUT:1"), IOStandard("LVTTL")),
    ("user_btn", 3, Pins("INPUT:2"), IOStandard("LVTTL")),
    ("user_btn", 4, Pins("INPUT:3"), IOStandard("LVTTL"))
]

vga = [
    ("vga_out", 0,
        Subsignal("hsync_n", Pins("LED:2"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("vsync_n", Pins("LED:3"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("r", Pins("DIO:0 DIO:1 DIO:2"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("g", Pins("DIO:3 DIO:4 DIO:5"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST")),
        Subsignal("b", Pins("DIO:6 CLKIO:0"), IOStandard("LVCMOS33"),
                  Misc("SLEW=FAST"))
    )
]

extclk = [
    ("extclk", 0, Pins("CLKIO:1"), IOStandard("LVCMOS33"))
]

sevenseg = [
    ("sevenseg", 0,
        Subsignal("segment7", Pins("GPIO:12"), IOStandard("LVTTL")),  # A
        Subsignal("segment6", Pins("GPIO:13"), IOStandard("LVTTL")),  # B
        Subsignal("segment5", Pins("GPIO:14"), IOStandard("LVTTL")),  # C
        Subsignal("segment4", Pins("GPIO:15"), IOStandard("LVTTL")),  # D
        Subsignal("segment3", Pins("GPIO:16"), IOStandard("LVTTL")),  # E
        Subsignal("segment2", Pins("GPIO:17"), IOStandard("LVTTL")),  # F
        Subsignal("segment1", Pins("GPIO:18"), IOStandard("LVTTL")),  # G
        Subsignal("segment0", Pins("GPIO:19"), IOStandard("LVTTL")),  # Dot
        Subsignal("enable0", Pins("GPIO:8"), IOStandard("LVTTL")),   # EN0
        Subsignal("enable1", Pins("GPIO:9"), IOStandard("LVTTL")),   # EN1
        Subsignal("enable2", Pins("GPIO:10"), IOStandard("LVTTL")),  # EN2
        Subsignal("enable3", Pins("GPIO:11"), IOStandard("LVTTL"))  # EN2
    )
]

ps2 = [
    ("ps2", 0,
        Subsignal("clk", Pins("LED:1"), IOStandard("LVCMOS33")),
        Subsignal("data", Pins("LED:0"), IOStandard("LVCMOS33"))
    )
]

audio = [
    ("audio", 0,
        Subsignal("l", Pins("GPIO:29"), IOStandard("LVTTL")),
        Subsignal("r", Pins("GPIO:28"), IOStandard("LVTTL"))
    )
]


class Platform(XilinxPlatform):
    default_clk_name = "clk50"
    default_clk_period = 20

    def __init__(self, device="xc3s200a-4-vq100"):
        XilinxPlatform.__init__(self, device, _io, _connectors)
        # Small device- optimize for AREA instead of SPEED (LM32 runs at about
        # 60-65MHz in AREA configuration).
        self.toolchain.xst_opt = """-ifmt MIXED
-use_new_parser yes
-opt_mode AREA
-register_balancing yes"""

    def create_programmer(self):
        raise NotImplementedError
