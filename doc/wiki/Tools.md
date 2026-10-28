Every tool installed with LiteX, and what it is for: the ones that talk to a running SoC, the
ones that build SoCs and cores, the ones that export the SoC description to an OS, and the
maintenance scripts. They are the entry points of `setup.py`, with their sources in
`litex/tools/`, and each one answers `--help`.

```sh
ls $(python3 -c "import sysconfig; print(sysconfig.get_path('scripts'))") | grep ^lite   # the tools installed in your environment
```

## Talking to a SoC

| Tool | Purpose | Typical use |
| --- | --- | --- |
| `litex_term` | The serial console, with the serial boot (`--kernel`, `--images`), `crossover` and `jtag` ports. | `litex_term /dev/ttyUSB1 --kernel=demo.bin` |
| `litex_server` | The bridge server: owns the UART, JTAG, UDP, PCIe, USB or devmem transport, serves clients over TCP. | `litex_server --uart --uart-port=/dev/ttyUSB0` |
| `litex_cli` | The command-line client: identifier, register dump, memory read and write, GUI. | `litex_cli --regs`, `litex_cli --gui` |
| `litex_jtag` | An OpenOCD `remote_bitbang` server driving the CPU debug TAP through CSRs, for GDB over any bridge. | `litex_jtag --csr-csv=csr.csv` |
| `litescope_cli` | Configures, triggers and captures the LiteScope analyzer through the bridge (from LiteScope). | `litescope_cli -r ibus_stb --dump capture.vcd` |

The pages: [Write firmware](Write-Firmware-For-Your-SoC.md) for `litex_term`,
[Host bridges](Host-Bridges.md) for `litex_server` and `litex_cli`,
[Debug with GDB](Debug-With-GDB.md) for `litex_jtag`, [LiteScope](Use-LiteScope-To-Debug-A-SoC.md).

## Building SoCs and cores

| Tool | Purpose | Typical use |
| --- | --- | --- |
| `litex_sim` | A full SoC in Verilator: CPU, BIOS, DRAM, Ethernet, SD card, flash and video models, tracing, QEMU. | `litex_sim --cpu-type=vexriscv --with-sdram` |
| `litex_soc_gen` | A standalone LiteX SoC as a Verilog core, its bus exposed as ports, for another flow. | `litex_soc_gen --cpu-type=vexriscv --bus-standard=axi-lite --build` |
| `litex_periph_gen` | A standalone set of peripherals behind a bus slave port, no CPU. | `litex_periph_gen --cpu-type=None --bus-standard=axi-lite --build` |
| `litex_bare_metal_demo` | The demo application, built against the generated headers of a build. | `litex_bare_metal_demo --build-path=build/digilent_arty` |
| `litex_build_bundle`, `litex_remote_build` | Record the inputs of a build in an archive and replay it, locally or on a host over SSH. | `litex_remote_build --host build@server -- python3 target.py --build` |
| `litex_read_verilog` | Parses a Verilog module with Yosys and prints its ports as a LiteX `Instance` skeleton. | `litex_read_verilog core.v` |
| `lite*_gen` | The standalone generators of the cores: a YAML configuration in, a Verilog core and its headers out. | `liteeth_gen eth.yml`, `litedram_gen ddr3.yml` |

The pages: [SoC simulator](SoC-Simulator.md), [Export to Verilog](Export-To-Verilog.md) for the
generators, [Build backends](Build-Backends.md) for the bundles,
[Reuse an existing core](Reuse-An-Existing-Core.md) for `litex_read_verilog`.

## Exporting the SoC description

The Builder always writes `csr.csv` and `csr.json` (`--soc-csv`, `--soc-json` to choose the
path; `--soc-svd` for the SVD, `--memory-x` for Rust); these tools consume them:

| Tool | Purpose | Typical use |
| --- | --- | --- |
| `litex_json2dts_linux` | A Linux device tree from `csr.json` (initrd, root device, polling options). | `litex_json2dts_linux build/<board>/csr.json > soc.dts` |
| `litex_json2dts_zephyr` | A Zephyr device tree overlay and configuration overlay. | `litex_json2dts_zephyr --dts soc.overlay --config soc.conf csr.json` |
| `litex_json2renode` | A Renode platform (`.repl`) and script (`.resc`), with the images and the network. | `litex_json2renode --repl soc.repl --resc soc.resc csr.json` |
| `svd2rust` (external) | A Rust peripheral access crate from the SVD. | `svd2rust -i soc.svd` |

The pages: [Run Linux](Run-Linux-On-Your-SoC.md), [Run Zephyr](Run-Zephyr-On-Your-SoC.md),
[SoC simulator](SoC-Simulator.md#renode), [OSes ecosystem](OSes-Ecosystem.md).

## Maintenance

| Tool | Purpose |
| --- | --- |
| `litex_setup.py` | Install, update and uninstall LiteX and the ecosystem, install the CPU compilers. |
| `litex_release.py` | The release helper of the maintainers: version bumps, tags, PyPI. |
| `litex_contributors` | Updates the `CONTRIBUTORS` file from the git history. |

[Installation](Installation.md) covers `litex_setup.py`, the
[release process](https://github.com/enjoy-digital/litex/blob/master/doc/release_process.md)
the other two. The SoC generators and `litex_sim` share the SoC and Builder options of the
targets ([SoC builder reference](SoC-Builder-Reference.md)).

## Next

- [Control it from the host](Host-Bridges.md): `litex_server` and `litex_cli` at work.
- [SoC simulator](SoC-Simulator.md): `litex_sim` and its models.
- [Export to Verilog](Export-To-Verilog.md): the generators.
- [SoC builder reference](SoC-Builder-Reference.md): the options the tools share.
