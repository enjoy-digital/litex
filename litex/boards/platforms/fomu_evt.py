from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import IceStormProgrammer


_io = [
    ("rgb_led_n", 0,
        Subsignal("r", Pins("40")),
        Subsignal("g", Pins("39")),
        Subsignal("b", Pins("41")),
        IOStandard("LVCMOS33"),
    ),
    # alias blue led
    ("user_led_n",    0, Pins("41"), IOStandard("LVCMOS33")),
    ("user_btn_n",    0, Pins("42"), IOStandard("LVCMOS33")),
    ("user_btn_n",    1, Pins("38"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("rx", Pins("21")),
        Subsignal("tx", Pins("13"), Misc("PULLUP")),
        IOStandard("LVCMOS33")
    ),

    ("usb", 0,
        Subsignal("d_p", Pins("34")),
        Subsignal("d_n", Pins("37")),
        Subsignal("pullup", Pins("35")),
        Subsignal("pulldown", Pins("36")),
        IOStandard("LVCMOS33")
    ),

    ("spiflash", 0,
        Subsignal("cs_n", Pins("16"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("15"), IOStandard("LVCMOS33")),
        Subsignal("miso", Pins("17"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("14"), IOStandard("LVCMOS33")),
        Subsignal("wp",   Pins("18"), IOStandard("LVCMOS33")),
        Subsignal("hold", Pins("19"), IOStandard("LVCMOS33")),
    ),

    ("spiflash4x", 0,
        Subsignal("cs_n", Pins("16"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("15"), IOStandard("LVCMOS33")),
        Subsignal("dq",   Pins("14 17 19 18"), IOStandard("LVCMOS33")),
    ),

    ("clk48", 0, Pins("44"), IOStandard("LVCMOS33")),
]

_connectors = [
    ("touch_pins", "48 47 46 45"),
    ("pmoda_n", "28 27 26 23"),
    ("pmodb_n", "48 47 46 45"),
]


class Platform(LatticePlatform):
    default_clk_name = "clk48"
    default_clk_period = 20.833

    gateware_size = 0x20000

    # FIXME: Create a "spi flash module" object in the same way we have SDRAM
    spiflash_model = "n25q32"
    spiflash_read_dummy_bits = 8
    spiflash_clock_div = 2
    spiflash_total_size = int((16/8)*1024*1024) # 16Mbit
    spiflash_page_size = 256
    spiflash_sector_size = 0x10000

    def __init__(self):
        LatticePlatform.__init__(self, "ice40-up5k-sg48", _io, _connectors,
                                 toolchain="icestorm")

    def create_programmer(self):
        return IceStormProgrammer()
