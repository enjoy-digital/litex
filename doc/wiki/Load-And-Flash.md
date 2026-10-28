You load a bitstream in the FPGA with `--load` (gone at power off) and write it in the SPI
flash the FPGA boots from with `--flash`, through the programmer the platform declares in
`create_programmer()`. Most boards use one of the two open-source tools below; the vendor
programmers (Vivado, Quartus, Gowin, Efinity, Diamond, Libero, TangDynasty) and a few
board-specific ones (`iceprog`, `ecpprog`, `ecpdap`, `ujprog`, `tinyprog`, DFU) are wrapped the
same way in `litex/build/<vendor>/programmer.py`.

```sh
python3 -m litex_boards.targets.digilent_arty --build --load      # SRAM
python3 -m litex_boards.targets.digilent_arty --build --flash     # SPI flash (when the target has --flash)
```

A programmer can also be used from Python: `prog = platform.create_programmer();
prog.load_bitstream("build/<board>/gateware/<board>.bit")`, `prog.flash(0, "<board>.bin")`.

## openFPGALoader

[openFPGALoader](https://github.com/trabucayre/openFPGALoader) (by @trabucayre) supports most
boards of the open-FPGA communities, the exotic ones included, with the usual cables (FTDI,
Digilent, DirtyJTAG, ...): it is the default programmer of most LiteX-Boards targets (Xilinx,
Lattice, Gowin, Efinix, CologneChip, Intel). Use the upstream version:

```sh
sudo apt install openfpgaloader                      # Debian/Ubuntu (a recent release), or build it:
sudo apt install libftdi1-2 libftdi1-dev libhidapi-hidraw0 libhidapi-dev libudev-dev cmake pkg-config make g++
git clone https://github.com/trabucayre/openFPGALoader && cd openFPGALoader
mkdir build && cd build && cmake ../ && make && sudo make install
openFPGALoader --detect                              # the cable and the device
```

In a platform: `OpenFPGALoader(board="arty_a7_35t")`, or `OpenFPGALoader(cable="ft2232", fpga_part="xc7a35t")`
with `--freq`, `--index-chain`, `--ftdi-serial` when needed; `flash()` takes the address and
accepts the tool's `--unprotect-flash`/`--verify`/external flash options.

## OpenOCD

[OpenOCD](https://openocd.org/) loads bitstreams on Xilinx and Lattice devices and flashes the
SPI flash through JTAG with the bscan SPI proxy bitstreams (downloaded on first use from
[quartiq/bscan_spi_bitstreams](https://github.com/quartiq/bscan_spi_bitstreams) into `~/.litex`).
It is also the JTAG transport of the [JTAGBone bridge](Host-Bridges.md) and of the
[CPU debugging](Debug-With-GDB.md) with GDB. The upstream OpenOCD works;
our fork adds a few cables and fixes:

```sh
git clone https://github.com/enjoy-digital/openocd && cd openocd
./bootstrap && ./configure --enable-ftdi && make && sudo make install
```

In a platform: `OpenOCD("openocd_xc7_ft2232.cfg", "bscan_spi_xc7a35t.bit")`; the configuration
files are in the `prog/` directory of LiteX and of LiteX-Boards, and the `OPENOCD` environment
variable selects another binary.

## Vendor tools and others

- **Vivado** (`VivadoProgrammer(flash_part="n25q256-3.3v-spi-x1_x2_x4")`): JTAG through the
  hardware manager, flashing through Vivado's flash programming; `vivado_path`/`vivado_ver` when
  several versions are installed.
- **Quartus** (`USBBlaster(cable_name="USB-Blaster")`): `quartus_pgm` with the `.sof`; `.rbf`
  and `.svf` can be generated for other tools.
- **Gowin** (`GowinProgrammer(devname, cable=...)`): `programmer_cli` of the Gowin EDA, SRAM
  and flash (`fifile`/`mcufile` for the EMCU devices), GWU2X or FT2CH cables.
- **Efinix** (`EfinixProgrammer`): Efinity's `ftdi_program.py` (JTAG) and `jtag_bridge` for the
  flash; `EfinixAtmelProgrammer` for the boards with the Atmel USB bridge.
- **Lattice**: `IceStormProgrammer` (`iceprog`, iCE40), `EcpprogProgrammer`/`EcpDapProgrammer`
  (ECP5), `UJProg`/`fujprog` (ULX3S), `TinyProgProgrammer` (TinyFPGA), `LatticeProgrammer`
  (`pgrcmd` with an `.xcf`), `OpenOCDJTAGProgrammer` (SVF through OpenOCD).
- **DFU** (`DFUProg(vid, pid, alt)`): boards with a DFU bootloader (OrangeCrab, Fomu, ...):
  `dfu-suffix` then `dfu-util --download`.
- **Microsemi** (`LiberoProgrammer`), **Anlogic** (`TangDynastyProgrammer`), **Xilinx** legacy
  (`iMPACT`, `XC3SProg`, `UrJTAG`, `Adept`).

Permissions: on Linux, the USB cables need udev rules (openFPGALoader ships `99-openfpgaloader.rules`,
OpenOCD `60-openocd.rules`) or `sudo`.

## Next

- [Create a minimal SoC](Create-A-minimal-SoC.md): `--build --load` on your first target.
- [Add a new board](Add-A-New-Board.md): `create_programmer()` in a platform of yours.
- [Write firmware for it](Write-Firmware-For-Your-SoC.md): the firmware next to the bitstream in the flash.
- [Build backends](Build-Backends.md): the toolchains the programmers come with.
