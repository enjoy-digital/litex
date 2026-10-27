# Tools

The command-line tools installed with LiteX (`setup.py` entry points, sources in
`litex/tools/`). Every one of them has `--help`; this page says what each is for and where it
is documented.

## Talking to a SoC

| Tool | Purpose | Typical use | Page |
| --- | --- | --- | --- |
| `litex_term` | Serial console for the BIOS and the firmware, with the serial boot (`--kernel`), several images (`--images boot.json`), and the console through a bridge (`crossover`) or JTAG (`jtag`) | `litex_term /dev/ttyUSB1 --kernel=demo.bin` | [Load application code](Load-Application-Code-To-CPU.md) |
| `litex_server` | The bridge server: owns the UART/JTAG/UDP/PCIe/USB/devmem transport and serves the clients over TCP | `litex_server --uart --uart-port=/dev/ttyUSB0` | [Host-Bridges](Host-Bridges.md) |
| `litex_cli` | Command-line client: identifier, register dump, memory read/write, GUI | `litex_cli --regs`, `litex_cli --gui` | [Host-Bridges](Host-Bridges.md) |
| `litex_jtag` | OpenOCD `remote_bitbang` server driving the CPU debug TAP through CSRs and `litex_server`, for GDB over any bridge | `litex_jtag --csr-csv=csr.csv` then `openocd` with `remote_bitbang` | [JTAG/GDB debugging](JTAG-GDB-Debugging-with-VexRiscv-SMP-NaxRiscv-VexiiRiscv-CPUs.md) |
| `litescope_cli` (LiteScope) | Configure, trigger and capture the LiteScope analyzer through the bridge | `litescope_cli -r main_basesoc_cpu_ibus_stb --dump capture.vcd` | [Use LiteScope](Use-LiteScope-To-Debug-A-SoC.md) |

## Building SoCs and cores

| Tool | Purpose | Typical use | Page |
| --- | --- | --- | --- |
| `litex_sim` | A full SoC in Verilator: CPU, BIOS, DRAM, Ethernet, SD card, SPI flash, video models, tracing, QEMU co-simulation | `litex_sim --cpu-type=vexriscv --with-sdram` | [SoC-Simulator](SoC-Simulator.md) |
| `litex_soc_gen` | Generates a standalone LiteX SoC as a Verilog core (CPU, memories, peripherals, bus exposed as ports) for another flow | `litex_soc_gen --cpu-type=vexriscv --bus-standard=axi-lite --build` | [Export](Export-Your-Core-SoC-To-Verilog.md) |
| `litex_periph_gen` | Generates a standalone peripheral SoC (no CPU, CSRs/peripherals behind a bus) | `litex_periph_gen --bus-standard=axi-lite --build` | [Export](Export-Your-Core-SoC-To-Verilog.md) |
| `litex_bare_metal_demo` | Builds the demo application against the generated headers of a build | `litex_bare_metal_demo --build-path=build/digilent_arty` | [Create and load software](Create-And-Load-Software-To-The-CPU.md) |
| `litex_build_bundle`, `litex_remote_build` | Record the inputs of a build in an archive and replay it, locally or on a remote host over SSH | `litex_remote_build --host build@server -- python3 target.py --build` | [Build-Backends](Build-Backends.md) |
| `litex_read_verilog` | Parses a Verilog module with Yosys and prints its ports as a LiteX `Instance` skeleton (JSON intermediate) | `litex_read_verilog core.v` | [Reuse a core](Reuse-a-SystemVerilog-VHDL-Amaranth-Spinal-HDL-Chisel-core.md) |
| `litedram_gen`, `liteeth_gen`, `litepcie_gen`, `litesata_gen`, `litesdcard_gen`, `litespi_gen`, `litenvme_gen`, `litedsp_gen` (ecosystem) | The standalone core generators: a YAML configuration in, a Verilog core and its software headers out | `liteeth_gen eth.yml` | [Export](Export-Your-Core-SoC-To-Verilog.md), [Cores-Ecosystem](Cores-Ecosystem.md) |

## Exporting the SoC description

The Builder always writes `csr.csv` and `csr.json` (`--soc-csv`, `--soc-json` to choose the
path; `--soc-svd` for the SVD, `--memory-x` for Rust); these tools consume them:

| Tool | Purpose | Typical use | Page |
| --- | --- | --- | --- |
| `litex_json2dts_linux` | Linux device tree from `csr.json` (initrd, root device, polling options) | `litex_json2dts_linux build/<board>/csr.json > soc.dts` | [Run Linux](Run-Linux-On-Your-SoC.md) |
| `litex_json2dts_zephyr` | Zephyr device tree overlay and configuration overlay (`--generate-soc-nodes` for full nodes) | `litex_json2dts_zephyr --dts soc.overlay --config soc.conf csr.json` | [Run Zephyr](Run-Zephyr-On-Your-SoC.md) |
| `litex_json2renode` | Renode platform (`.repl`) and script (`.resc`) from `csr.json`, with the BIOS/firmware/Linux images and the network | `litex_json2renode --repl soc.repl --resc soc.resc csr.json` | [Generate Renode simulation](Generate-Renode-simulation.md) |
| `svd2rust` (external) | Rust peripheral access crate from `--soc-svd` | | [OSes-Ecosystem](OSes-Ecosystem.md) |

## Maintenance

| Tool | Purpose |
| --- | --- |
| `litex_setup.py` | Install, update, uninstall LiteX and the ecosystem, install the CPU toolchains ([Installation](Installation.md)) |
| `litex_release.py` | Release helper of the maintainers: version bumps, tags, PyPI ([release process](https://github.com/enjoy-digital/litex/blob/master/doc/release_process.md)) |
| `litex_contributors` | Updates the `CONTRIBUTORS` file from the git history |

All the tools accept `--help`; the SoC generators and `litex_sim` share the SoC and Builder
options of the targets ([SoC-builder](SoC-builder.md)).
