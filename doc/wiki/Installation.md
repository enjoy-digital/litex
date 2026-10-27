# LiteX installation guide

LiteX is a set of Python packages (Migen, LiteX, the cores, the boards, the CPUs) installed
from their Git repositories by `litex_setup.py`, plus the compilers of the CPU you use and the
FPGA toolchain of your board (or Verilator to run the SoC on your computer). Ten minutes on
Linux or macOS; on Windows, use WSL.

## 1. Requirements

- Python 3.7 or later (3.9+ recommended), `git`, `make`, a C/C++ compiler.
- For the BIOS and the software: `meson` and `ninja` (`pip3 install meson ninja`).
- For a board: the vendor toolchain (Vivado, Quartus, Diamond/Radiant, Gowin, Efinity,
  Libero...) or the open-source one (Yosys/nextpnr with Project Trellis, IceStorm, Oxide,
  Apicula...), see [Build-Backends](Build-Backends.md). For a simulation: Verilator (step 5).

## 2. Install Migen, LiteX, the cores and the boards

Recent Linux distributions protect the system Python (PEP 668): create a virtual environment
first, or pass `--user` where it is still allowed.

```sh
python3 -m venv ~/litex-venv && source ~/litex-venv/bin/activate   # recommended
mkdir litex && cd litex
wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
chmod +x litex_setup.py
./litex_setup.py --init --install --config=standard
```

`--init` clones the repositories next to the script (in the current directory, or in the
parent directory when the script is run from a LiteX checkout) and `--install` installs them
in development mode (`pip install -e`): a `git pull` or an edit in a repository is used
immediately, without reinstalling. `--config` selects the set of repositories:

| Config | Content |
| --- | --- |
| `minimal` | Migen and LiteX only |
| `standard` (default) | + the cores (LiteDRAM, LiteEth, LitePCIe, LiteSATA, LiteSDCard, LiteICLink, LiteJESD204, LiteDSP, LiteSPI, LiteI2C, LiteScope), LiteX-Boards, the software data (picolibc, compiler-rt) and the common CPUs (VexRiscv, VexRiscv-SMP, NaxRiscv, VexiiRiscv, SERV, Minerva, Sentinel, VeeR, LM32, Mor1kx...) |
| `full` | + every CPU of the catalog (Rocket, CVA5/CVA6, Ibex, CV32E40P/41P, BlackParrot, Coreblocks, Microwatt, Marocchino, OpenC906, PicoRV32, the MIPS cores...) |

The repository list and the configs are in
[litex_repos.py](https://github.com/enjoy-digital/litex/blob/master/litex_repos.py); a CPU can
be added later with `--init --install --config=full`, or by cloning its `pythondata-cpu-*`
repository and installing it.

> **macOS:** install [HomeBrew](https://brew.sh), then `brew install wget`.
> **Windows:** use WSL (Ubuntu); a native install also needs `make` (GnuWin or MSYS2) and
> `SHELL=cmd.exe` in the environment.

## 3. Install the compiler of your CPU

Only needed to build the BIOS and software for a SoC with a CPU (RISC-V for most of them):

```sh
./litex_setup.py --gcc=riscv      # also: openrisc, lm32, powerpc, mips
```

This runs the package manager of your system (`apt install gcc-riscv64-unknown-elf` on
Debian/Ubuntu, `dnf` on Fedora, `pacman` on Arch, `apk` on Alpine, `brew install riscv64-elf-gcc`
on macOS); LM32 comes from the `litex-hub` conda channel. Any `riscv64-unknown-elf-gcc` (or
`riscv64-linux-gnu-gcc`, `riscv-none-elf-gcc`) in the `PATH` works, LiteX picks the first one
it finds.

## 4. Build the SoC of a board

The reference SoCs of 200+ boards are in LiteX-Boards, one target script per board:

```sh
python3 -m litex_boards.targets.digilent_arty --build --load     # Arty A7, Vivado in the PATH
python3 -m litex_boards.targets.lattice_ecp5_evn --build --load  # ECP5, Yosys/nextpnr/Trellis
python3 -m litex_boards.targets.digilent_arty --help             # CPU, memories, peripherals, options
```

`--build` generates the gateware and the BIOS and runs the toolchain; `--load` programs the
board (the programmers are listed in [FPGA and SPI Flash programmers](FPGA-and-SPI-Flash-programmers.md)).
Then open the serial console (115200 8-N-1) and get the BIOS prompt:

```sh
litex_term /dev/ttyUSB1
```

<p align="center"><img src="https://raw.githubusercontent.com/enjoy-digital/litex/master/doc/bios_screenshot.png"></p>

[Create a minimal SoC](Create-A-minimal-SoC.md) walks through a target script;
[Load application code](Load-Application-Code-To-CPU.md) through the boot methods.

## 5. ... or run the SoC on your computer with Verilator

No board needed: `litex_sim` builds the same SoC for Verilator and runs it with its BIOS.

```sh
sudo apt install libevent-dev libjson-c-dev verilator        # Linux (Debian/Ubuntu)
brew install json-c verilator libevent                        # macOS
litex_sim --cpu-type=vexriscv
```

See [SoC-Simulator](SoC-Simulator.md) for the options (DRAM, Ethernet, SD card models, tracing).

## 6. Keep LiteX up to date

```sh
./litex_setup.py --update                  # pull every repository (and litex_setup.py itself)
./litex_setup.py --update --tag=2026.08    # or check out a release of every repository
./litex_setup.py --init --install --config=full   # add the repositories you did not install
```

LiteX and the cores are released together three times a year (`YYYY.04`, `.08`, `.12`), but
most projects follow `master`. With `--dev`, the script does not update itself and uses the
`git@github.com:` URLs (for contributors). `--freeze` prints the commit of every repository,
to reproduce a setup.

The released packages are also on [PyPI](https://pypi.org/project/litex/)
(`pip install litex==2026.08 litex-boards liteeth litedram ...`): practical for a CI or a quick
look, but `litex_setup.py` remains the way to get an editable checkout of everything.

## Uninstall

```sh
./litex_setup.py --uninstall --config=standard --dry-run   # preview
./litex_setup.py --uninstall --config=standard             # remove the Python packages, keep the sources
```

Details in [doc/uninstall.md](https://github.com/enjoy-digital/litex/blob/master/doc/uninstall.md).

## Troubleshooting

- *This Python environment is externally managed (PEP 668)*: use a virtual environment as
  in step 2 (`--break-system-packages` forces the system install if you know what you do).
- *meson/ninja not found* when building a SoC with a CPU: `pip3 install meson ninja` in the
  same environment.
- *riscv64-unknown-elf-gcc: command not found*: step 3, or check that the compiler is in the
  `PATH` of the shell running the build.
- A repository is missing after `--update`: it was added to the config since your install,
  run `--init --install` again with the same `--config`.
- Still stuck? [Ask on Discord or IRC, or open an issue](Feedback-Contribution-Support.md)
  with the full log.
