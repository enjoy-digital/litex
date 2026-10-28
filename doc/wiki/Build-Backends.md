A target does not know which toolchain builds it. For each vendor, a platform class names the
device, the I/Os and the constraints, a toolchain class writes the project files and the
scripts, runs the tools and names the bitstream, and vendor primitives (I/O buffers, DDR
registers, clock managers) are only reached through generic specials each backend implements.
Swap `--toolchain=diamond` for `trellis` and the same target builds; this is also what keeps
the [cores](Cores-Ecosystem.md) portable ([The LiteX approach](LiteX-Approach.md)).

![The LiteX build flow](images/litex-build-flow.svg)

```sh
python3 -m litex_boards.targets.lattice_ecp5_evn --toolchain=trellis --build     # Yosys, nextpnr, Project Trellis
python3 -m litex_boards.targets.lattice_ecp5_evn --toolchain=diamond --build     # the vendor tool, same target
```

## Platforms and toolchains

A platform file (`litex_boards/platforms/<board>.py`, or your own) instantiates the vendor
platform with the device name, the I/O list, the connectors, the default clock, and says which
programmer to use:

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
`add_platform_command`), and `--toolchain` selects among the toolchains the family supports;
[Add a new board](Add-A-New-Board.md) is the step by step page.

| Vendor (`litex/build/`) | Families | `--toolchain` | Programmers |
| --- | --- | --- | --- |
| `xilinx` | Spartan-6, 7-Series, UltraScale, UltraScale+ | `ise`; `vivado`, `yosys+nextpnr`, `openxc7`, `f4pga`; `vivado` | Vivado, openFPGALoader, OpenOCD, XC3SProg, UrJTAG, iMPACT, Adept |
| `altera` | Cyclone IV, V and 10, MAX 10, Stratix V, Arria, Agilex 3, 5 and 7 | `quartus` | USB-Blaster (`quartus_pgm`), openFPGALoader |
| `lattice` | iCE40, ECP5, Nexus (CrossLink-NX, Certus-NX) | `icestorm`; `trellis`, `diamond`; `oxide`, `radiant` | openFPGALoader, OpenOCD, iceprog, ecpprog, ecpdap, ujprog, tinyprog, pgrcmd, DFU |
| `gowin` | GW1N, GW2A, GW5A | `gowin`, `apicula` | Gowin programmer, openFPGALoader |
| `efinix` | Trion, Titanium, Topaz | `efinity` | Efinix programmer, openFPGALoader |
| `colognechip` | GateMate A1, A2, A4 | `colognechip`, `peppercorn` | openFPGALoader |
| `microsemi` | IGLOO2, PolarFire, ProASIC3 | `libero_soc` | Libero |
| `quicklogic` | EOS S3 | `f4pga` | the QORC SDK tools |
| `anlogic` | Eagle, Elf | `td` (TangDynasty) | TangDynasty programmer |
| `sim` | | `verilator` | [SoC simulator](SoC-Simulator.md) |

<details>
<summary>How each tool is found</summary>

- **Vivado, ISE**: `vivado` or `ise` in the `PATH`, or `LITEX_ENV_VIVADO` and `LITEX_ENV_ISE`
  pointing to the install (its `settings64.sh` is sourced); openxc7 needs `CHIPDB`, F4PGA
  `F4PGA_INSTALL_DIR`.
- **Quartus**: `quartus_map` or `quartus_syn` in the `PATH` (`--synth-tool`).
- **Yosys and nextpnr flows** (icestorm, trellis, oxide, apicula, peppercorn, yosys+nextpnr):
  `yosys` and `nextpnr-*` in the `PATH`.
- **Diamond, Radiant**: `diamondc` or `pnmainc` in the `PATH` (WSL supported).
- **Gowin EDA**: `gw_sh` in the `PATH` (also `gw_sh.exe` from WSL).
- **Efinity**: `LITEX_ENV_EFINITY` pointing to the install, or `efx_run.py` in the `PATH`.
- **CologneChip**: `yosys`, then `p_r` or `nextpnr-himbaechel` in the `PATH`.
- **Libero**: `libero` in the `PATH`; **TangDynasty**: `td` in the `PATH`; **F4PGA**: `f4pga`.

</details>

The open-source flows share the Yosys and nextpnr options (`--yosys-abc9`, `--yosys-flow3`,
`--yosys-nowidelut`, `--yosys-slang` for SystemVerilog sources, `--nextpnr-seed`,
`--nextpnr-timingstrict`, `--nextpnr-ignoreloops`) and the packer ones (`--ecppack-compress`,
`--ecppack-freq`, `--ecppack-bootaddr`, `--ecppack-spimode` on ECP5, `--nexus-es-device`,
`--force-die` and `--strategy` on GateMate). Vivado has its directives
(`--vivado-synth-directive`, `--vivado-place-directive`, `--vivado-route-directive`...),
`--vivado-max-threads`, `--vivado-report-level`, `--synth-mode yosys` (Yosys synthesis, Vivado
place and route) and `--no-project-mode`; Efinity `--synth-mode speed|area|area2`; Radiant
`--synth-mode synplify|yosys`. `python3 target.py --toolchain=<x> --help` lists them.

The scripts and project files land in `build/<platform>/gateware/` (`build_<platform>.sh`,
the `.tcl`, the `.xdc`, `.lpf`, `.cst`, `.sdc` or `.pcf`) and can be re-run by hand.
`--build-backend edalize` hands the generated files to [Edalize](https://github.com/olofk/edalize)
instead of LiteX's own scripts (icestorm and f4pga flows).

## Portability: the generic specials

A core never instantiates a vendor primitive. `litex/build/io.py` defines generic specials
that each backend lowers to its primitives (`<vendor>/common.py`, the `*_special_overrides`):

| Special | Purpose |
| --- | --- |
| `DifferentialInput`, `DifferentialOutput`, `DifferentialTristate` | LVDS and other differential I/Os. |
| `SDRInput`, `SDROutput`, `SDRTristate`, `DDRInput`, `DDROutput`, `DDRTristate` | Registered and double data rate I/Os (I/O registers, ODDR, IDDR). |
| `SerDesInput`, `SerDesOutput`, `SerDesTristate` | I/O serializers and deserializers where the device has them. |
| `ClkInput`, `ClkOutput`, `Tristate` | Clock buffers, tristate I/O. |
| `MultiReg`, `AsyncResetSynchronizer` | Clock domain crossing registers and reset synchronizers, with the vendor's attributes. |

The clock managers are in `litex/soc/cores/clock/` ([Cores](Cores.md#clocking)), the
transceivers in LiteICLink and in the PHYs of the cores (a LiteEth or LiteDRAM PHY is one file
per family). A design that uses only these specials builds on every vendor; one that needs an
`Instance` of a vendor primitive keeps it in a device adapter
([architectural_style.md](https://github.com/enjoy-digital/litex/blob/master/doc/architectural_style.md)).

## Mixed-language sources

`platform.add_source("core.v")` (or `.sv`, `.vhd`, with `language=` and `library=`) adds files
to the project; the toolchains that read VHDL or SystemVerilog use them directly, and for the
ones that do not:

- `VHD2VConverter` converts VHDL to Verilog with GHDL at build time (`--std=08`), flattened with
  Yosys on request (Microwatt, NEORV32, the CTU CAN FD core use it).
- `Amaranth2VConverter` elaborates an Amaranth module to Verilog (Minerva, Sentinel, LUNA).
- `--yosys-slang` makes the Yosys flows read SystemVerilog through the slang plugin.

[Reuse an existing core](Reuse-An-Existing-Core.md) wraps a core written in any of them.

## Build bundles and remote builds

A build often has to run where the toolchain is (a build server, a Windows machine with the
vendor tools): `--build-bundle` records every input of a build (the sources, the Python import
roots, the command, the environment) in a `.tar.gz` under `<output-dir>/bundles/` with a
manifest, and `litex_build_bundle --run-local <archive>` replays it. `litex_remote_build --host
user@server -- python3 target.py --build` does the round trip over SSH: bundle, upload, replay
there, copy `build/` back ([Tools](Tools.md)).

## Loading and flashing

`--load` calls `platform.create_programmer().load_bitstream(...)` and `--flash`
`prog.flash(address, file)`: openFPGALoader for most boards, OpenOCD (with the bscan SPI proxy
bitstreams for flashing through JTAG), the vendor programmers, DFU for the boards with a DFU
bootloader. [Load and flash](Load-And-Flash.md) has the installation and the details.

## Next

- [Add a new board](Add-A-New-Board.md): a platform file of your own, and the platform classes of each vendor.
- [Load and flash](Load-And-Flash.md): the programmers behind `--load` and `--flash`.
- [Reuse an existing core](Reuse-An-Existing-Core.md): Verilog, VHDL, SystemVerilog, Amaranth in your SoC.
- [SoC simulator](SoC-Simulator.md): the `sim` backend, Verilator.
