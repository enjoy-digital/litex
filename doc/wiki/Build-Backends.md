# Build backends

The build backends are the part of LiteX that knows the FPGA toolchains: for each vendor, a
*platform* class describes the device, the I/Os and the constraints, and a *toolchain* class
generates the project files and scripts, runs the tools and names the bitstream. A LiteX design
never calls a vendor tool itself: the same target builds with Vivado or with Yosys/nextpnr,
and the vendor primitives (I/O buffers, DDR registers, clock managers, SerDes...) are reached
through generic specials that each backend implements. This is what makes the
[cores](Cores-Ecosystem.md) portable ([the LiteX approach](LiteX-Approach.md)).

![The LiteX build flow](images/litex-build-flow.svg)

## Platforms and toolchains

A platform file (`litex_boards/platforms/<board>.py`, or your own) instantiates the vendor
platform with the device name, the I/O list (`Pins`, `IOStandard`, `Misc`, `Subsignal`
constraints), the connectors, the default clock, and says which programmer to use:

```python
from litex.build.generic_platform import *
from litex.build.xilinx import XilinxPlatform
from litex.build.openfpgaloader import OpenFPGALoader

_io = [
    ("clk100",    0, Pins("E3"), IOStandard("LVCMOS33")),
    ("user_led",  0, Pins("H5"), IOStandard("LVCMOS33")),
    ("serial", 0,
        Subsignal("tx", Pins("D10")),
        Subsignal("rx", Pins("A9")),
        IOStandard("LVCMOS33")
    ),
]

class Platform(XilinxPlatform):
    default_clk_name   = "clk100"
    default_clk_period = 1e9/100e6

    def __init__(self, toolchain="vivado"):
        XilinxPlatform.__init__(self, "xc7a35ticsg324-1L", _io, toolchain=toolchain)

    def create_programmer(self):
        return OpenFPGALoader("arty_a7_35t")

    def do_finalize(self, fragment):
        XilinxPlatform.do_finalize(self, fragment)
        self.add_period_constraint(self.lookup_request("clk100", loose=True), 1e9/100e6)
```

The design requests its pins from it (`platform.request("serial")`), adds sources and
constraints (`add_source`, `add_period_constraint`, `add_false_path_constraint`,
`add_platform_command`), and `--toolchain` selects among the toolchains the family supports.
[Add a new board](Add-A-New-Board.md) is the step by step page.

| Vendor (`litex/build/`) | Platform classes | Families | Toolchains (`--toolchain`) | How the tool is found | Programmers |
| --- | --- | --- | --- | --- | --- |
| `xilinx` | `XilinxPlatform`, `XilinxSpartan6Platform`, `Xilinx7SeriesPlatform`, `XilinxUSPlatform`, `XilinxUSPPlatform` | Spartan-6, 7-Series, UltraScale, UltraScale+ | Spartan-6: `ise`; 7-Series: `vivado`, `yosys+nextpnr`, `openxc7`, `f4pga`; UltraScale(+): `vivado` | `vivado`/`ise` in the `PATH`, or `LITEX_ENV_VIVADO`/`LITEX_ENV_ISE` pointing to the install (its `settings64.sh` is sourced); openxc7 needs `CHIPDB`, F4PGA `F4PGA_INSTALL_DIR` | `VivadoProgrammer` (JTAG and flash through Vivado), `OpenFPGALoader`, `OpenOCD`, `XC3SProg`, `UrJTAG`, `iMPACT`, `Adept` |
| `altera` | `AlteraPlatform` | Cyclone IV/V/10, MAX 10, Stratix V, Arria, Agilex 3/5/7 | `quartus` (`--synth-tool quartus_map|quartus_syn`) | `quartus_map`/`quartus_syn` in the `PATH` | `USBBlaster` (`quartus_pgm`), `OpenFPGALoader` |
| `lattice` | `LatticePlatform`, `LatticeiCE40Platform`, `LatticeECP5Platform`, `LatticeNexusPlatform` | iCE40, ECP5, Nexus (CrossLink-NX, Certus-NX) | iCE40: `icestorm`; ECP5: `trellis`, `diamond`; Nexus: `oxide`, `radiant` | `yosys`/`nextpnr-*` in the `PATH`; `diamondc` or `pnmainc` for the vendor tools (WSL supported) | `OpenFPGALoader`, `OpenOCDJTAGProgrammer`, `IceStormProgrammer` (`iceprog`), `EcpprogProgrammer`, `EcpDapProgrammer`, `UJProg`, `TinyProgProgrammer`, `LatticeProgrammer` (`pgrcmd`), `DFUProg` |
| `gowin` | `GowinPlatform(device, devicename=...)` | GW1N, GW2A, GW5A | `gowin` (Gowin EDA), `apicula` (Yosys + nextpnr-himbaechel) | `gw_sh` in the `PATH` (also `gw_sh.exe` from WSL) | `GowinProgrammer` (`programmer_cli`), `OpenFPGALoader` |
| `efinix` | `EfinixPlatform` | Trion, Titanium, Topaz | `efinity` | `LITEX_ENV_EFINITY` pointing to the install, or `efx_run.py` in the `PATH` | `EfinixProgrammer` (`ftdi_program.py`), `EfinixAtmelProgrammer`, `OpenFPGALoader` |
| `colognechip` | `CologneChipPlatform` | GateMate A1/A2/A4 | `colognechip` (Yosys + `p_r`), `peppercorn` (Yosys + nextpnr) | `yosys`, `p_r`/`nextpnr-himbaechel` in the `PATH` | `OpenFPGALoader` |
| `microsemi` | `MicrosemiPlatform` | IGLOO2, PolarFire, ProASIC3 | `libero_soc` | `libero` in the `PATH` | `LiberoProgrammer` |
| `quicklogic` | `QuickLogicPlatform` | EOS S3 | `f4pga` | `f4pga` in the `PATH` | (QORC SDK tools) |
| `anlogic` | `AnlogicPlatform` | Eagle, Elf | `td` (TangDynasty) | `td` in the `PATH` | `TangDynastyProgrammer` |
| `sim` | `SimPlatform` | | `verilator` | `verilator` in the `PATH` | [SoC-Simulator](SoC-Simulator.md) |

The open-source flows share the Yosys/nextpnr options (`--yosys-abc9`, `--yosys-flow3`,
`--yosys-nowidelut`, `--yosys-slang` for SystemVerilog sources, `--nextpnr-seed`,
`--nextpnr-timingstrict`, `--nextpnr-ignoreloops`) plus the packer ones (`--ecppack-compress`,
`--ecppack-freq`, `--ecppack-bootaddr`, `--ecppack-spimode` for ECP5; `--nexus-es-device`;
`--force-die`/`--strategy` for GateMate). Vivado has `--vivado-synth-directive`,
`--vivado-place-directive`, `--vivado-route-directive` and the other directives,
`--vivado-max-threads`, `--vivado-report-level`, `--synth-mode yosys` (Yosys synthesis, Vivado
P&R) and `--no-project-mode`; Efinity `--synth-mode speed|area|area2` and its packing/retiming
options; Radiant `--synth-mode synplify|yosys`. `python3 target.py --toolchain=<x> --help` lists
them. The build scripts and project files are written in `build/<platform>/gateware/`
(`build_<platform>.sh`, `.tcl`, `.xdc`/`.lpf`/`.cst`/`.sdc`/`.pcf`...) and can be re-run by
hand. `--build-backend edalize` hands the generated files to [Edalize](https://github.com/olofk/edalize)
instead of LiteX's own scripts (icestorm and f4pga flows).

## Portability: the generic specials

Vendor primitives are never instantiated by a core directly. `litex/build/io.py` defines
generic specials that each backend lowers to its primitives (`<vendor>/common.py`,
`*_special_overrides`):

| Special | Purpose |
| --- | --- |
| `DifferentialInput`, `DifferentialOutput`, `DifferentialTristate` | LVDS and other differential I/Os |
| `SDRInput`, `SDROutput`, `SDRTristate`, `DDRInput`, `DDROutput`, `DDRTristate` | Registered and double data rate I/Os (I/O registers, ODDR/IDDR, ...) |
| `SerDesInput`, `SerDesOutput`, `SerDesTristate` | I/O serializers/deserializers where the device has them |
| `ClkInput`, `ClkOutput`, `Tristate` | Clock input/output buffers, tristate I/O |
| `MultiReg`, `AsyncResetSynchronizer` | Clock domain crossing registers and reset synchronizers (with the vendor's attributes/primitives) |

The clock managers are in `litex/soc/cores/clock/` ([Cores](Cores.md)), the transceivers in
LiteICLink and the PHYs of the cores (a LiteEth or LiteDRAM PHY is one file per family). A
design that uses only these specials builds on every vendor; a design that needs an `Instance`
of a vendor primitive keeps it in a device adapter, as described in
[architectural_style.md](https://github.com/enjoy-digital/litex/blob/master/doc/architectural_style.md).

## Mixed-language sources

`platform.add_source("core.v")` (or `.sv`, `.vhd`, with `language=`/`library=`) adds files to
the project; the toolchains that read VHDL or SystemVerilog use them directly, and for the ones
that do not:

- `VHD2VConverter` converts VHDL to Verilog with GHDL at build time (`--std=08`), optionally
  flattened with Yosys (used by Microwatt, NEORV32, the CTU CAN FD core...).
- `Amaranth2VConverter` elaborates an Amaranth module to Verilog (Minerva, Sentinel, LUNA).
- `--yosys-slang` makes the Yosys-based flows read SystemVerilog through the slang plugin.

How to wrap an existing core: [Reuse a (System)Verilog, VHDL, Amaranth, SpinalHDL, Chisel core](Reuse-a-SystemVerilog-VHDL-Amaranth-Spinal-HDL-Chisel-core.md).

## Build bundles and remote builds

A build often has to run where the toolchain is (a build server, a Windows machine with the
vendor tools): `--build-bundle` records every input of a build (the sources, the Python
import roots, the command, the environment) in a `.tar.gz` under `<output-dir>/bundles/` with a
manifest, and `litex_build_bundle --run-local <archive>` replays it. `litex_remote_build
--host user@server -- python3 target.py --build` does the round trip over SSH: bundle, upload,
replay there, copy `build/` back ([Tools](Tools.md)).

## Loading and flashing

`--load` calls `platform.create_programmer().load_bitstream(...)` and `--flash`
`prog.flash(address, file)`: openFPGALoader for most boards, OpenOCD (with the bscan SPI proxy
bitstreams for flashing through JTAG), the vendor programmers, DFU for the boards with a DFU
bootloader. Installation and details on [FPGA and SPI Flash programmers](FPGA-and-SPI-Flash-programmers.md).
