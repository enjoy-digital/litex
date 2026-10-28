A board is two Python files: the **platform** (the FPGA, the pins and their I/O standards, the
connectors, the default clock, the programmer) and the **target** (a reference SoC built on
it, with options). [LiteX-Boards](https://github.com/litex-hub/litex-boards) has 250+ of them,
so start from the closest one. With the schematic open (part number, pinout, I/O voltages per
bank, the cable you have), count an hour to the BIOS prompt.

## 1. The platform

```python
#
# This file is part of LiteX-Boards.
#
# Copyright (c) 2026 Your Name <you@example.com>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_platform import *
from litex.build.lattice import LatticeiCE40Platform
from litex.build.lattice.programmer import IceStormProgrammer

# IOs ----------------------------------------------------------------------------------------------

_io = [
    # Clk / Rst
    ("clk12", 0, Pins("35"), IOStandard("LVCMOS33")),

    # Leds
    ("user_led_n", 0, Pins("11"), IOStandard("LVCMOS33")),
    ("user_led_n", 1, Pins("37"), IOStandard("LVCMOS33")),

    # Serial
    ("serial", 0,
        Subsignal("rx", Pins("6")),
        Subsignal("tx", Pins("9"), Misc("PULLUP")),
        IOStandard("LVCMOS33")
    ),

    # SPIFlash
    ("spiflash4x", 0,
        Subsignal("cs_n", Pins("16"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("15"), IOStandard("LVCMOS33")),
        Subsignal("dq",   Pins("14 17 12 13"), IOStandard("LVCMOS33")),
    ),
]

# Connectors ---------------------------------------------------------------------------------------

_connectors = [
    ("PMOD1A", "4   2 47 45  3 48 46 44"),
    ("PMOD1B", "43 38 34 31 42 36 32 28"),
    ("PMOD2",  "27 25 21 19 26 23 20 18"),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticeiCE40Platform):
    default_clk_name   = "clk12"
    default_clk_period = 1e9/12e6

    def __init__(self, toolchain="icestorm"):
        LatticeiCE40Platform.__init__(self, "ice40-up5k-sg48", _io, _connectors, toolchain=toolchain)

    def create_programmer(self):
        return IceStormProgrammer()

    def do_finalize(self, fragment):
        LatticeiCE40Platform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk12", loose=True), 1e9/12e6)
```

Shortened from the iCEBreaker platform. What the pieces are:

- **A resource** is `("name", number, constraints...)`: `Pins("A1 B2 ...")` (several strings
  are concatenated), `IOStandard("LVCMOS33")`, `Misc("SLEW=FAST")` (any vendor attribute),
  `Drive(8)`, `Inverted()`; **`Subsignal("tx", Pins(...), ...)`** groups the pins of an
  interface, a constraint at the resource level applies to all its subsignals. The design
  does `platform.request("serial")` and gets a record with `.tx`/`.rx`;
  `request("user_led", 1)` the second LED, `request_all("user_led")` all of them.
- **Standard names**, so that the cores and targets find the resources:
  `clk<freq>`, `cpu_reset`/`cpu_reset_n`, `serial`, `user_led`/`user_led_n`, `user_btn`,
  `user_sw`, `ddram`, `spiflash`/`spiflash4x`, `sdcard`/`spisdcard`, `eth`/`eth_clocks`,
  `pcie_x4`, `hdmi_out`/`hdmi_in`, `i2c`, `pmod`... Look at a board with the same chips for
  the subsignal names the PHYs expect (`ddram` for LiteDRAM, `eth`/`eth_clocks` for LiteEth,
  `pcie_x4` for LitePCIe).
- **Connectors** are named pin lists: `("pmoda", "G13 B11 A11 D12 D13 B18 A18 K16")` (8
  entries for a Pmod: pins 1-4 then 7-10, `None` for a missing pin) or a dict
  `("j1", {1: "A1", 2: "B2"})`; a resource references them as `Pins("pmoda:0")`. Hardware
  plugged on a connector (a Pmod SD card, a Pmod DVI, an FMC card) is an **extension** in
  `litex_boards/extensions/` (`PmodSDCard`, `PmodDVI`, `PmodGPIO`...), added by the target
  with `platform.add_extension(PmodSDCard("pmodd"))` or from the command line with
  `--pmod pmodd=sdcard`.
- **The vendor platform** class and its device string: `Xilinx7SeriesPlatform("xc7a35ticsg324-1L", ...)`,
  `XilinxUSPPlatform("xczu7ev-ffvc1156-2-i", ...)`, `AlteraPlatform("5CSEBA6U23I7", ...)`,
  `LatticeECP5Platform("LFE5U-25F-6BG256C", ...)`, `LatticeNexusPlatform("LFD2NX-40-8BG256C", ...)`,
  `GowinPlatform("GW2A-LV18PG256C8/I7", ..., devicename="GW2A-18C")`,
  `EfinixPlatform("T120F576I4", ..., iobank_info=[("1A", "3.3 V LVTTL / LVCMOS"), ...])`,
  `CologneChipPlatform("CCGM1A1", ...)`, `MicrosemiPlatform("MPF300TS_ES-1FCG484", ...)`,
  `AnlogicPlatform("EG4S20BG256", ...)`; `toolchain=` selects among the family's toolchains
  ([Build-Backends](Build-Backends.md)).
- **`default_clk_name`/`default_clk_period`**: the clock used when a design has no CRG (the
  `simple` target, cores exported alone) and the period constraint added by `do_finalize`.
- **`create_programmer()`**: `OpenFPGALoader("board_name")` or `OpenFPGALoader(cable=..., fpga_part=...)`,
  `OpenOCD("openocd_xc7_ft2232.cfg", "bscan_spi_xc7a35t.bit")`, `VivadoProgrammer()`,
  `USBBlaster()`, `IceStormProgrammer()`, `EcpprogProgrammer()`, `GowinProgrammer(devname)`,
  `EfinixProgrammer()`, `DFUProg(vid, pid)`... ([programmers](Load-And-Flash.md)).
- **Vendor-specific settings** in `__init__`/`do_finalize`: `self.add_platform_command("set_property INTERNAL_VREF 0.675 [get_iobanks 34]")`
  (any toolchain command), `self.toolchain.bitstream_commands = ["set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]"]`,
  `self.toolchain.additional_commands = ["write_cfgmem ..."]` (Vivado), `add_period_constraint`
  and `add_false_path_constraints` for the clocks that are not derived from the system PLL
  (Ethernet RX/TX clocks, for example).

Smoke-test the platform with the generic target before writing yours:

```sh
python3 -m litex_boards.targets.simple litex_boards.platforms.my_board --build --no-compile   # elaboration only
python3 -m litex_boards.targets.simple litex_boards.platforms.my_board --build --load         # the BIOS prompt on the UART
```

A platform outside LiteX-Boards is any importable module with a `Platform` class:
`--platform mypkg.my_board`, or the positional argument of `simple`.

## 2. The target

The target follows the [style guide](https://github.com/litex-hub/litex-boards/blob/master/docs/board_target_style.md)
of LiteX-Boards (sections in order: imports, `_CRG`, `BaseSoC`, `main()`; options in order:
`--sys-clk-freq`, board `--variant`/`--revision`, Ethernet, storage, video, extras). The Arty
A7 one, shortened:

```python
# Imports: the ones of the minimal SoC, plus the DRAM and Ethernet cores.
from litedram.modules import MT41K128M16
from litedram.phy import s7ddrphy
from liteeth.phy.mii import LiteEthPHYMII

# CRG ----------------------------------------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.rst          = Signal()
        self.cd_sys       = ClockDomain()
        self.cd_sys4x     = ClockDomain()      # LiteDRAM: 4x the system clock, a 90 degree copy, 200 MHz for IDELAYCTRL
        self.cd_sys4x_dqs = ClockDomain()
        self.cd_idelay    = ClockDomain()
        self.cd_eth       = ClockDomain()

        clk100 = platform.request("clk100")
        rst_n  = platform.request("cpu_reset_n")
        self.pll = pll = S7PLL(speedgrade=-1)
        self.comb += pll.reset.eq(~rst_n | self.rst)
        pll.register_clkin(clk100, 100e6)
        pll.create_clkout(self.cd_sys,       sys_clk_freq)
        pll.create_clkout(self.cd_sys4x,     4*sys_clk_freq)
        pll.create_clkout(self.cd_sys4x_dqs, 4*sys_clk_freq, phase=90)
        pll.create_clkout(self.cd_idelay,    200e6)
        pll.create_clkout(self.cd_eth,       25e6)
        self.comb += platform.request("eth_ref_clk").eq(self.cd_eth.clk)
        platform.add_false_path_constraints(self.cd_sys.clk, pll.clkin)   # the input clock is asynchronous to sys
        self.idelayctrl = S7IDELAYCTRL(self.cd_idelay)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, sys_clk_freq=100e6, with_ethernet=False, with_etherbone=False, eth_ip="192.168.1.50", **kwargs):
        platform = digilent_arty.Platform()
        self.crg = _CRG(platform, sys_clk_freq)
        SoCCore.__init__(self, platform, sys_clk_freq, ident="LiteX SoC on Arty A7", **kwargs)

        # DDR3 SDRAM -------------------------------------------------------------------------------
        if not self.integrated_main_ram_size:
            self.ddrphy = s7ddrphy.A7DDRPHY(platform.request("ddram"), memtype="DDR3", nphases=4, sys_clk_freq=sys_clk_freq)
            self.add_sdram("sdram", phy=self.ddrphy, module=MT41K128M16(sys_clk_freq, "1:4"), l2_cache_size=8192)

        # Ethernet / Etherbone ---------------------------------------------------------------------
        if with_ethernet or with_etherbone:
            self.ethphy = LiteEthPHYMII(clock_pads=platform.request("eth_clocks"), pads=platform.request("eth"))
            if with_etherbone:
                self.add_etherbone(phy=self.ethphy, ip_address=eth_ip, with_ethmac=with_ethernet)
            elif with_ethernet:
                self.add_ethernet(phy=self.ethphy, local_ip=eth_ip)

        self.leds = LedChaser(pads=platform.request_all("user_led"), sys_clk_freq=sys_clk_freq)

# Build: the main() of the minimal SoC, with --with-ethernet, --with-etherbone, --eth-ip and
# --with-spi-flash added to the parser and passed to BaseSoC; the full file is in LiteX-Boards.
```

The DRAM needs the PHY of the FPGA family (`s7ddrphy.A7DDRPHY`, `K7DDRPHY`, `usddrphy.USPDDRPHY`,
`ecp5ddrphy.ECP5DDRPHY`, `gw2ddrphy.GW2DDRPHY`, `GENSDRPHY` for SDR SDRAM...) and the module of
the chip (`litedram.modules`: `MT41K128M16`, `MT41K256M16`, `AS4C32M16`, `IS42S16160`... or
your own from the datasheet), the Ethernet the PHY of the interface (`LiteEthPHYMII`,
`LiteEthPHYRMII`, `LiteEthPHYRGMII` per family, `LiteEthPHY1000BaseX`...); the clocks they need
are documented in their classes, the other targets using the same chips are the fastest
reference.

## 3. Bring-up order

1. Platform with the clock, the serial port and the LEDs; `simple` target: BIOS prompt.
2. `--with-uartbone` (or `--uart-name=crossover+uartbone`): `litex_server --uart` and
   `litex_cli --regs` from the host, LiteScope available ([Host bridges](Host-Bridges.md)).
3. DRAM: `add_sdram`; the BIOS calibrates it and runs the memtest at boot (`sdram_*` commands
   to debug: `sdram_cal`, `sdram_test`, `sdram_bist`); start at a lower `--sys-clk-freq` if the
   calibration fails.
4. Ethernet: `--with-ethernet`, `ping 192.168.1.100` from the BIOS, `netboot`; or
   `--with-etherbone` and `litex_server --udp`.
5. Flash, SD card, PCIe, video: one at a time, each has a BIOS command to test it.
6. Linux with [Linux-on-LiteX-VexRiscv](Run-Linux-On-Your-SoC.md) when the board has DRAM.

## 4. Contribute it

- File names `<vendor>_<board>.py` for the platform and the target, the header with your
  copyright and the BSD-2-Clause SPDX line, the section banners of the other files.
- Read `docs/board_target_style.md` and `docs/extensions.md`; run the checks of the CI
  locally: `python3 .github/scripts/sync_readme_boards_list.py` (the README board list is
  generated), `python3 .github/scripts/generate_board_inventory.py`, the parser style checks
  and `python3 -m litex_boards.targets.<board> --build --no-compile` (what the CI builds for
  every target, with `--cpu-type=vexriscv --cpu-variant=minimal --uart-name=stub`).
- In the pull request: which options were tested on hardware (BIOS, DRAM memtest, Ethernet,
  flash), the toolchain version, a photo or the board's link; the maintainers do not have
  every board.

## Next

- [Create a complex SoC](Create-A-Complex-SoC.md): the DRAM, Ethernet, flash and SD card the target above adds, one by one.
- [Build backends](Build-Backends.md): the vendor platform classes, the toolchains and their options.
- [Load and flash](Load-And-Flash.md): the programmer `create_programmer()` returns.
- [Control it from the host](Host-Bridges.md): the second step of the bring-up order.
