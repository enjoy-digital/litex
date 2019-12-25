from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import IceStormProgrammer


_io = [
    ("user_led", 0, Pins("B5"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("B4"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("A2"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("A1"), IOStandard("LVCMOS33")),
    ("user_led", 4, Pins("C5"), IOStandard("LVCMOS33")),
    ("user_led", 5, Pins("C4"), IOStandard("LVCMOS33")),
    ("user_led", 6, Pins("B3"), IOStandard("LVCMOS33")),
    ("user_led", 7, Pins("C3"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("rx", Pins("B10")),
        Subsignal("tx", Pins("B12"), Misc("PULLUP")),
        Subsignal("rts", Pins("B13"), Misc("PULLUP")),
        Subsignal("cts", Pins("A15"), Misc("PULLUP")),
        Subsignal("dtr", Pins("A16"), Misc("PULLUP")),
        Subsignal("dsr", Pins("B14"), Misc("PULLUP")),
        Subsignal("dcd", Pins("B15"), Misc("PULLUP")),
        IOStandard("LVCMOS33"),
    ),

    ("spiflash", 0,
        Subsignal("cs_n", Pins("R12"), IOStandard("LVCMOS33")),
        Subsignal("clk", Pins("R11"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("P12"), IOStandard("LVCMOS33")),
        Subsignal("miso", Pins("P11"), IOStandard("LVCMOS33")),
    ),

    ("clk12", 0, Pins("J3"), IOStandard("LVCMOS33"))
]


class Platform(LatticePlatform):
    default_clk_name = "clk12"
    default_clk_period = 83.333

    gateware_size = 0x28000

    # FIXME: Create a "spi flash module" object in the same way we have SDRAM
    spiflash_model = "n25q32"
    spiflash_read_dummy_bits = 8
    spiflash_clock_div = 2
    spiflash_total_size = int((32/8)*1024*1024) # 32Mbit
    spiflash_page_size = 256
    spiflash_sector_size = 0x10000

    def __init__(self):
        LatticePlatform.__init__(self, "ice40-hx8k-ct256", _io,
                                 toolchain="icestorm")

    def create_programmer(self):
        return IceStormProgrammer()
