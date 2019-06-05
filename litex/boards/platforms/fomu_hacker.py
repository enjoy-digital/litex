from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform
from litex.build.lattice.programmer import IceStormProgrammer


_io = [
    ("rgb_led", 0,
        Subsignal("r", Pins("C5")),
        Subsignal("g", Pins("B5")),
        Subsignal("b", Pins("A5")),
        IOStandard("LVCMOS33")
    ),


    ("usb", 0,
        Subsignal("d_p", Pins("A4")),
        Subsignal("d_n", Pins("A2")),
        Subsignal("pullup", Pins("D5")),
        IOStandard("LVCMOS33")
    ),

    ("clk48", 0, Pins("F5"), IOStandard("LVCMOS33")),

    # Adesto AT25SF161 - 16-Mbit - 2 megabyte
    # Supports SPI Modes 0 and 3
    # Supports Dual and Quad Output Read
    #
    ("spiflash", 0,
        Subsignal("cs_n", Pins("C1"), IOStandard("LVCMOS33")),
        Subsignal("clk", Pins("D1"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("F1"), IOStandard("LVCMOS33")),
        Subsignal("miso", Pins("E1"), IOStandard("LVCMOS33")),
    ),
]

spiflash = [
]

_connectors = [
    # Pins
    # Pin 1 - F4 - Outside full square
    # Pin 2 - E5
    # Pin 3 - E4
    # Pin 4 - F2 - Near notch on bottom
    ("pins", "F4 E5 E4 F2"),
]

# The ICE40UP5K-B-EVN does not use the provided FT2232H chip to provide a
# UART port. One must use their own USB-to-serial cable instead to get a UART.
# Using the second 6-pin PMOD port. Follows Digilent PMOD Specification Type 4,
# so e.g. PMOD USBUART can be used.
pins_serial = [
    ("serial", 0,
        Subsignal("rx", Pins("pins:1")),
        Subsignal("tx", Pins("pins:2")),
        IOStandard("LVCMOS33"),
    ),
]

class Platform(LatticePlatform):
    default_clk_name = "clk48"
    default_clk_period = 20.833

    gateware_size = 0x20000

    # FIXME: Create a "spi flash module" object in the same way we have SDRAM
    spiflash_model = "n25q32"
    spiflash_read_dummy_bits = 8
    spiflash_clock_div = 2
    spiflash_total_size = int((16/8)*1024*1024) # 16Mbit, 1megabytes
    spiflash_page_size = 256
    spiflash_sector_size = 0x10000

    def __init__(self):
        LatticePlatform.__init__(
            self, "ice40-up5k-uwg30", _io, _connectors, toolchain="icestorm")

    def create_programmer(self):
        return IceStormProgrammer()
