Ten minutes to get LiteX, the cores, LiteX-Boards and a RISC-V compiler in a virtual
environment, and to boot a SoC in Verilator; no board yet. Linux or macOS (on Windows, use
WSL). Everything is installed from Git in editable mode: updating is a `git pull`, fixing
something is editing the file.

## 1. What you need

- Python 3.9 or later, `git`, `make` and a C compiler.
- `meson` and `ninja` to build the BIOS and the software (installed in step 2).
- Verilator to run a SoC on your computer (step 4). The toolchain of your board (Vivado,
  Quartus, Yosys/nextpnr...) only when you build for it (step 5): [Build backends](Build-Backends.md).

## 2. Install LiteX

```sh
python3 -m venv ~/litex-venv && source ~/litex-venv/bin/activate   # recent distributions protect the system Python
pip3 install meson ninja
mkdir litex && cd litex
wget https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py
chmod +x litex_setup.py
./litex_setup.py --init --install --config=standard
```

`--init` clones the repositories next to the script and `--install` installs each of them with
`pip install -e`: an edit in a repository is used immediately, with nothing to reinstall. A few
minutes later the directory holds Migen, LiteX, the cores, the boards and the usual CPUs:

```
litex/
    litex_setup.py  migen/  litex/  litex-boards/
    litedram/  liteeth/  litepcie/  litesata/  litesdcard/  litescope/  liteiclink/  litejesd204/  litespi/  litei2c/  litedsp/
    pythondata-software-picolibc/  pythondata-software-compiler_rt/
    pythondata-cpu-vexriscv/  pythondata-cpu-vexriscv-smp/  pythondata-cpu-naxriscv/  pythondata-cpu-vexiiriscv/  pythondata-cpu-serv/  ...
```

`--config` picks the set of repositories; the lists are in
[litex_repos.py](https://github.com/enjoy-digital/litex/blob/master/litex_repos.py):

| Config | Content |
| --- | --- |
| `minimal` | Migen and LiteX |
| `standard` (default) | + the cores, LiteX-Boards, the software data and the usual CPUs (VexRiscv, NaxRiscv, SERV...) |
| `full` | + every CPU of the catalog (Rocket, CVA6, Ibex, CV32E40P, Microwatt, PicoRV32...) |

A CPU can be added later with `--init --install --config=full`, or by cloning its
`pythondata-cpu-*` repository and installing it.

> [!NOTE]
> macOS: install [Homebrew](https://brew.sh), then `brew install wget`. Windows: use WSL
> (Ubuntu); a native install also needs `make` (MSYS2) and `SHELL=cmd.exe` in the environment.

## 3. Install the compiler of your CPU

```sh
./litex_setup.py --gcc=riscv      # also: openrisc, lm32, powerpc, mips
riscv64-unknown-elf-gcc --version
```

The script calls the package manager of your system (`apt install gcc-riscv64-unknown-elf` on
Debian/Ubuntu, `dnf`, `pacman`, `apk`, `brew install riscv64-elf-gcc` on macOS); LM32 comes from
the `litex-hub` conda channel. Any `riscv64-unknown-elf-gcc`, `riscv64-linux-gnu-gcc` or
`riscv-none-elf-gcc` in the `PATH` works, LiteX picks the first one it finds. Only a SoC with a
CPU needs a compiler, and most of them are RISC-V.

## 4. Run a SoC on your computer

```sh
sudo apt install libevent-dev libjson-c-dev verilator   # Debian/Ubuntu; macOS: brew install json-c verilator libevent
litex_sim
```

Verilator compiles a SoC with a VexRiscv CPU, a ROM holding the BIOS, an SRAM and a UART, and
runs it: the BIOS prints its banner, lists what it found and waits at its prompt.

![litex_sim: the BIOS boots in the terminal](images/litex-sim-boot.svg)

It is the same BIOS as on a board: type `help`, `mem_list`, `mem_read 0x10000000 32`. `Ctrl-C`
ends the simulation. [SoC simulator](SoC-Simulator.md) has the options: DRAM and Ethernet
models, your own firmware, waveform tracing.

## 5. Run a SoC on a board

```sh
python3 -m litex_boards.targets.digilent_arty --build --load     # Arty A7: Vivado in the PATH
python3 -m litex_boards.targets.lattice_ecp5_evn --build --load  # ECP5: Yosys, nextpnr, Trellis
litex_term /dev/ttyUSB1                                         # the serial console, 115200 8N1
```

LiteX-Boards has a target script for 250+ boards, and `--help` lists what each one can add
(CPU, DRAM, Ethernet, SD card, PCIe...). `--build` generates the gateware and the BIOS and runs
the toolchain, `--load` programs the board (the programmers are on
[Load and flash](Load-And-Flash.md)). The BIOS prompt appears in `litex_term` once the board
resets.

## 6. Keep LiteX up to date

```sh
./litex_setup.py --update                         # pull every repository, and the script itself
./litex_setup.py --update --tag=2026.08           # or check out a release everywhere
./litex_setup.py --init --install --config=full   # add the repositories you did not install
./litex_setup.py --freeze                         # the commit of every repository, to reproduce a setup
```

LiteX and the cores are released together three times a year (`YYYY.04`, `.08`, `.12`) and most
projects follow `master`. `--dev` keeps the script from updating itself and uses the
`git@github.com:` URLs (for contributors). The released packages are also on
[PyPI](https://pypi.org/project/litex/) (`pip install litex==2026.08 litex-boards liteeth ...`),
practical for a CI; the script stays the way to get an editable checkout of everything.
`--uninstall --config=standard` removes the packages and keeps the sources (`--dry-run` first).

## If something goes wrong

- *This environment is externally managed* (PEP 668): use the virtual environment of step 2
  (`--break-system-packages` forces a system install, if you know what you do).
- *meson: command not found* when building a SoC: `pip3 install meson ninja` in the same
  environment.
- *riscv64-unknown-elf-gcc: command not found*: step 3, and check the `PATH` of the shell that
  runs the build.
- A repository is missing after `--update`: it was added to the config since your install, run
  `--init --install` again with the same `--config`.
- Still stuck? [Ask on Discord or IRC, or open an issue](Feedback-Contribution-Support.md) with
  the full log.

## Next

- [Create a minimal SoC](Create-A-minimal-SoC.md): the next step, a target script of forty lines that you own.
- [SoC simulator](SoC-Simulator.md): everything `litex_sim` can simulate.
- [Build backends](Build-Backends.md): the toolchains and how LiteX finds them.
- [Load and flash](Load-And-Flash.md): the programmers behind `--load` and `--flash`.
