A map of LiteX for a software agent asked to work *in* LiteX (fix, extend, review the
framework or a core) or *with* it (build a SoC, bring up a board, write firmware, drive a
board from the host). Everything here is also true for a human in a hurry. The facts come
from the code; when this page and the code disagree, the code is right and this page needs a
[pull request](Contributing-to-the-Wiki.md).

**Machine-readable index of this wiki:** [llms.txt](https://raw.githubusercontent.com/wiki/enjoy-digital/litex/llms.txt)
(one line per page); the raw markdown of a page is at
`https://raw.githubusercontent.com/wiki/enjoy-digital/litex/<Page-Name>.md`. The sources
of the pages are in [`doc/wiki/`](https://github.com/enjoy-digital/litex/tree/master/doc/wiki)
of the repository. [DeepWiki](https://deepwiki.com/enjoy-digital/litex) indexes the code.

## LiteX in ten lines

1. LiteX builds FPGA SoCs and cores in Python: Migen describes the logic, LiteX provides the
   SoC builder, the interconnect, the cores, the build backends, the BIOS/software support and
   the host tools ([Home](Home.md), [The LiteX approach](LiteX-Approach.md)).
2. A design is a *platform* (the board: pins, clocks, toolchain) and a *target* (the SoC):
   `python3 target.py --build --load`, then `litex_term /dev/ttyUSBx` ([SoC builder](SoC-builder.md)).
3. `SoCCore` adds the CPU, ROM (with the BIOS), SRAM, UART, timer; `add_sdram`,
   `add_ethernet`, `add_pcie`, `add_sdcard`, `add_spi_flash`... add the ecosystem cores.
4. Cores talk through [streams](Streams.md), [Wishbone](Wishbone-Bus.md)/[AXI](AXI-Bus.md)
   buses and [CSRs](CSR-Bus.md); a core is a `LiteXModule` with `CSRStorage`/`CSRStatus`
   attributes and an `EventManager` for interrupts; the SoC derives `csr.h`, `csr.csv`,
   `csr.json`, `csr.svd`, the device trees and the documentation from it.
5. The Builder generates `build/<platform>/gateware/` (Verilog, constraints, toolchain script)
   and `build/<platform>/software/` (headers, BIOS); `--no-compile-gateware` skips the
   toolchain, `--no-compile` skips everything but the generation.
6. The BIOS boots the application from serial, flash, ROM, SD card, SATA or TFTP
   ([BIOS](BIOS.md), [Load application code](Load-Application-Code-To-CPU.md)).
7. The host reaches the running SoC's bus through a [bridge](Host-Bridges.md) (UART, JTAG,
   Ethernet, PCIe): `litex_server` + `litex_cli`/`RemoteClient`, LiteScope for signals.
8. `litex_sim` runs the same SoC in Verilator ([SoC-Simulator](SoC-Simulator.md)); unit tests
   use the Migen simulator and `pytest`.
9. 38 CPUs ([CPUs](CPUs.md)), 9 FPGA vendors ([Build-Backends](Build-Backends.md)), 250+ boards
   (LiteX-Boards), the cores in their own repositories ([Cores ecosystem](Cores-Ecosystem.md)).
10. BSD-2-Clause; development on `master`; releases `YYYY.04/.08/.12` ([CHANGES.md](https://github.com/enjoy-digital/litex/blob/master/CHANGES.md)).

## Repository map

```
litex/                              https://github.com/enjoy-digital/litex
  litex_setup.py, litex_repos.py    install/update the ecosystem; the repository catalog and configs
  litex/gen/                        LiteXModule, genlib (CDC, misc), fhdl (Verilog generation, Instance, memory, hierarchy)
  litex/build/                      generic_platform.py (Pins/IOStandard/Subsignal, request), generic_toolchain.py, parser.py (LiteXArgumentParser),
                                    io.py (generic specials), <vendor>/ (xilinx, altera, lattice, gowin, efinix, colognechip, microsemi, quicklogic, anlogic),
                                    sim/ (Verilator, C models, QEMU co-sim), openfpgaloader.py, openocd.py, dfu.py, vhd2v_converter.py, amaranth2v_converter.py, bundle.py
  litex/soc/interconnect/           stream.py, packet.py, wishbone.py, axi/, avalon/, ahb.py, csr.py, csr_bus.py, csr_eventmanager.py
  litex/soc/cores/                  the in-tree cores; clock/ (PLLs per vendor); cpu/<name>/core.py (the CPU wrappers, + crt0.S, irq.h)
  litex/soc/integration/            soc.py (SoC, LiteXSoC, SoCCore, SoCMini, the handlers, add_*), builder.py (Builder), export.py (csr.h/csv/json/svd), doc.py
  litex/soc/software/               bios/, libbase/, libc (picolibc), liblitedram/, libliteeth/, liblitesdcard/, liblitesata/, liblitespi/, demo/, include/generated/ (per build)
  litex/soc/doc/                    the Sphinx documentation generator
  litex/tools/                      litex_term, litex_server, litex_client (litex_cli), litex_jtag, litex_sim, litex_soc_gen, litex_periph_gen,
                                    litex_json2dts_linux/zephyr, litex_json2renode, litex_read_verilog, litex_build_bundle, litex_remote_build, remote/ (the transports)
  doc/                              coding_style.md, architectural_style.md, release_process.md, socdoc.md, bios_config.md, cpu_jtag_debug.md, stream_byte_enables.md, uninstall.md,
                                    wiki/ (this wiki), diagrams/ (the diagram generator), wiki_sync.py
  test/                             pytest: cores/, interconnect/, soc/ (test_integration.py boots the BIOS on every CPU in Verilator), tools/, software/
  prog/                             OpenOCD configurations
  CHANGES.md, CONTRIBUTORS, setup.py (console_scripts, python_requires ~=3.7)

../litex-boards/litex_boards/       platforms/<vendor>_<board>.py, targets/<vendor>_<board>.py, extensions/ (Pmods, FMC...), prog/
../litedram, liteeth, litepcie, ... one repository per core: <core>/{phy,core,frontend,software}/, gen.py, test/, doc/, examples/
../pythondata-cpu-<name>/           the packaged sources of a CPU (litex-hub)
```

## Where the key things are

| You need | Look at |
| --- | --- |
| How a target is written | any `litex_boards/targets/*.py`; [Create a minimal SoC](Create-A-minimal-SoC.md); `litex/tools/litex_sim.py` for a simulated one |
| The `add_*` helpers and their arguments | `litex/soc/integration/soc.py` (`LiteXSoC`, from line ~2210); [SoC builder](SoC-builder.md) |
| The command-line options of a SoC/Builder | `soc_core_args()` and `builder_args()` in `soc.py`/`builder.py`; `python3 target.py --help` |
| A CPU's variants, buses, flags | `litex/soc/cores/cpu/<name>/core.py` (`CPU_VARIANTS`, `GCC_FLAGS`, `periph_buses`, `mem_map`, `io_regions`); [CPUs](CPUs.md) |
| A core's registers and interrupts | its `CSRStorage`/`CSRStatus`/`EventManager` attributes; the generated `csr.h` and `csr.csv` of a build |
| The generated outputs of a build | `build/<platform>/{csr.csv,csr.json,litex.log,gateware/,software/include/generated/}` |
| The BIOS commands and boot methods | `litex/soc/software/bios/{main.c,boot.c,cmds/}`; [BIOS](BIOS.md) |
| How a vendor toolchain is driven | `litex/build/<vendor>/<toolchain>.py` (`build_project`, `build_script`, `run_script`, `*_args`) |
| The host-side API | `litex/tools/litex_client.py` (`RemoteClient`), `litex/tools/remote/comm_*.py`; [Host-Bridges](Host-Bridges.md) |
| What changed recently | `CHANGES.md` (per release, with commit links) |

## Commands that answer questions fast

```sh
python3 target.py --help                                           # every option of a target, with defaults
python3 target.py --build --no-compile --output-dir=/tmp/x         # the map, CSRs, IRQs and generated files in seconds, no toolchain, no gcc
python3 target.py --build --no-compile-gateware                    # + the BIOS and headers (needs the CPU's gcc and meson)
litex_sim --cpu-type=vexriscv [--with-sdram --with-ethernet ...]   # the SoC in Verilator, BIOS prompt in the terminal
python3 -m pytest test/cores/test_pwm.py                           # one test; test/ holds the suite (slow: test/soc/test_integration.py)
python3 -c "from litex.soc.cores.cpu import CPUS; print(sorted(k for k in CPUS if k))"   # the CPU registry
litex_cli --csr-csv build/<board>/csr.csv --regs                   # the registers of a running board (through litex_server)
./litex_setup.py --freeze                                          # the commit of every installed repository
```

Reading the generated `csr.csv`/`csr.json`/`litex.log` of a `--no-compile` build is the
fastest way to check what a target or an option really produces.

## Conventions

- **Style**: [doc/coding_style.md](https://github.com/enjoy-digital/litex/blob/master/doc/coding_style.md)
  (file header with the SPDX line, section banners `# Name ----`, the `# # #` separator
  between a module's interface and its implementation, aligned argument blocks, HDL
  star-imports in HDL modules only; it has a "Guidance for AI agents" section: inspect
  neighboring files first, keep edits scoped, run the smallest useful check, report what
  could not be run).
- **Architecture**: [doc/architectural_style.md](https://github.com/enjoy-digital/litex/blob/master/doc/architectural_style.md):
  protocol logic in the core, vendor primitives in a device adapter, pins and clocks in the
  platform/target; a new device is a new adapter, not a copy of the protocol; keep public
  class names, constructor arguments, CSR layouts, clock domain names and command-line options
  (or provide a compatibility path).
- **Commits**: `module: Description of the change.` (`litex/soc/cores/uart: Fix RX FIFO
  overflow.`), one change per commit, the pull request says what was tested and on which
  hardware.
- **Tests**: a unit test in `test/` for new logic; CI runs `pytest` on every push and boots
  the BIOS on every CPU in Verilator; `litex_hw_ci` runs designs on real boards.
- **Generated files are never edited**: `build/`, `csr.h`, `.init` files, the Verilog;
  change the Python.
- **Do not bump dependencies, rename options or reformat unrelated code** in a fix.

## How to verify a change

1. Elaborate: a `--build --no-compile` of a target that uses the code (or `litex_sim`
   `--no-compile-gateware`) proves the Python and the Verilog generation; a Python import
   alone proves nothing.
2. Simulate: the relevant `test/` files; `litex_sim` for anything the BIOS exercises (a
   memory, a UART, a timer, a DRAM, Ethernet with `--with-ethernet` and a TAP).
3. Build: one real target with the toolchain when it is available (`--build`), look at the
   timing report; several variants/vendors when the change touches a backend or a PHY.
4. Hardware: say in the pull request what ran on a board and what did not; simulation and
   elaboration cannot establish analog behavior or timing closure.

## Pitfalls

- Options use dashes (`--uart-name`, `--cpu-variant`), integers for sizes and baudrates
  (`--uart-baudrate=1000000`, `--integrated-main-ram-size=0x10000`); variant names are
  exact keys of the CPU's list (`standard+debug` exists for `vexriscv`, not for `serv`).
- `litex_cli`/`litex_term --crossover`/`litescope_cli` read `csr.csv` from the current
  directory unless `--csr-csv` is given; the Builder always writes it in `build/<platform>/`.
- A system Python refuses `pip` installs (PEP 668): use a venv for `litex_setup.py`.
- `litex_sim --with-ethernet`/`--with-etherbone` creates a TAP interface and needs `sudo`;
  Verilator builds take a minute and need `libevent-dev libjson-c-dev`.
- The generated CPUs (`vexriscv_smp`, `naxriscv`, `vexiiriscv`) need Java/sbt the first time;
  `coreblocks` needs Python 3.13 to elaborate; `rocket` needs lots of RAM.
- The ROM is auto-resized to the BIOS; `--no-integrated-rom-auto-size` and the `BIOS_ROM_BUDGET`
  variable are the knobs when the size matters; `--bios-console lite --libc-mode minimal`
  shrink it.
- Uncached peripherals must live in the CPU's IO regions (`0x80000000`+ on most 32-bit soft
  cores); the handler raises a clear error otherwise.
- The vendor toolchains are found through the `PATH` or `LITEX_ENV_VIVADO`/`LITEX_ENV_ISE`/`LITEX_ENV_EFINITY`;
  OpenOCD configurations are in `prog/`.
- The wiki, `CHANGES.md` and the READMEs describe `master`; a release tag may lack the newest
  options.

## Using LiteX from a project, as an agent

```sh
python3 -m venv ~/litex-venv && source ~/litex-venv/bin/activate
wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py && chmod +x litex_setup.py
./litex_setup.py --init --install --config=standard && ./litex_setup.py --gcc=riscv && pip3 install meson ninja
```

Then a target file (copy the closest LiteX-Boards target, or the [40-line one](Create-A-minimal-SoC.md)),
`--build --no-compile` to check the map, `--build --load` when the toolchain is there,
`litex_term` for the console, `--with-uartbone`/`--with-etherbone` + `litex_server` +
`RemoteClient` to script the board from Python, [LiteScope](Use-LiteScope-To-Debug-A-SoC.md)
to see signals, `litex_bare_metal_demo` as the firmware template. For a core that must exist
in a non-LiteX design, the generators ([Export](Export-Your-Core-SoC-To-Verilog.md)).

## The pages of this wiki

Welcome ([Home](Home.md), [Installation](Installation.md), [The LiteX approach](LiteX-Approach.md),
the ecosystems), Internals ([SoC builder](SoC-builder.md), [Cores](Cores.md), [CPUs](CPUs.md),
the buses and [Streams](Streams.md), [Host bridges](Host-Bridges.md), [Build backends](Build-Backends.md),
[BIOS](BIOS.md), [Tools](Tools.md), [Simulator](SoC-Simulator.md)), How to (minimal SoC, board,
core, CPU, software, debugging), Advanced (complex SoC, PCIe, export, Linux/Zephyr/MicroPython/Renode),
[Projects](Projects.md) and [Resources](Tutorials-Resources.md): the full list with one line
each is [llms.txt](https://raw.githubusercontent.com/wiki/enjoy-digital/litex/llms.txt).
