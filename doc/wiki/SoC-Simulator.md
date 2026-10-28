`litex_sim` builds your SoC for [Verilator](https://www.veripool.org/verilator/) and runs it
on your computer: the same CPU, BIOS, buses and cores as on a board, with C++ models for the
outside world (the serial console, DRAM chips, Ethernet on a TAP interface, an SD card, a SPI
flash, a video window). No board, firmware debugging, CI, the waveforms of a whole SoC: all
`litex_sim`. Renode and QEMU are the fast, non-cycle-accurate alternatives, at the end.

![The LiteX simulation](images/litex-simulation.svg)

## Getting started

```sh
sudo apt install libevent-dev libjson-c-dev verilator      # Debian/Ubuntu (brew on macOS)
litex_sim                                                   # VexRiscv, ROM with the BIOS, SRAM, UART
```

The build takes a minute (Verilator compiles the SoC to C++), then the BIOS banner and prompt
appear in the terminal: the console is the terminal itself (`serial2console`). `Ctrl-C` stops
it. The build lands in `build/sim/`, and `--help` lists every option (the SoC and Builder
options of the targets, plus the ones below).

![litex_sim: the build, the BIOS banner, the SoC summary and the prompt](images/litex-sim-boot.svg)

To run a firmware, build the SoC once without compiling (the headers are enough), compile the
application, then start the simulation with the RAM preloaded:

```sh
litex_sim --integrated-main-ram-size=0x10000 --no-compile-gateware
litex_bare_metal_demo --build-path=build/sim
litex_sim --integrated-main-ram-size=0x10000 --ram-init=demo.bin
```

A `--rom-init=firmware.bin` replaces the BIOS by your own code; `--sdram-init` preloads a DRAM.

## What can be simulated

| Option | Model |
| --- | --- |
| `--cpu-type`, `--cpu-variant`, `--integrated-*` | Any CPU that Verilator accepts (the CI boots the BIOS on more than 20 of them), the memories |
| `--with-sdram --sdram-module=MT48LC16M16`, `--with-sdram-bist`, `--sdram-from-spd-dump` | LiteDRAM with a DRAM model (the LiteDRAM catalog, or an SPD dump); `--l2-size`, `--l2-bursting` |
| `--with-ethernet`, `--with-etherbone`, `--ethernet-phy-model`, `--local-ip`, `--remote-ip` | LiteEth on a TAP interface (`tap0`, needs `sudo`): netboot, Linux networking, Etherbone |
| `--with-sdcard`, `--with-spi-flash --spi_flash-init=flash.bin`, `--with-i2c` | LiteSDCard, LiteSPI flash and an I2C SPD EEPROM model |
| `--with-video-framebuffer`, `--with-video-terminal`, `--with-video-colorbars`, `--video-vsync` | The video cores displayed in an SDL window |
| `--with-gpio`, `--with-analyzer` | GPIOs, a LiteScope analyzer on the CPU buses (read through a bridge, below) |
| `--with-jtagremote`, `--with-swdremote` | OpenOCD `remote_bitbang` servers on the CPU's JTAG/SWD (GDB on the simulated CPU) |
| `--uart-tcp --uart-tcp-port=1234`, `--uart-pty --uart-pty-path=/tmp/litex_pty0` | The serial port on a TCP port or a pseudo-terminal (`litex_term /tmp/litex_pty0`) |

The models are C modules in `litex/build/sim/core/modules/` (clocker, serial2console,
serial2tcp, ethernet, gmii_ethernet, xgmii_ethernet, spdeeprom, jtagremote, swdremote, video,
sim_perf, qemu_axi); a `SimConfig` in the target picks them (`sim_config.add_module("serial2console", "serial")`)
and `SimPlatform` declares the pads. Your own target can be simulated the same way: give it a
`SimPlatform`, the `sim` PHYs (`LiteEthPHYModel`, `SDRAMPHYModel`, the `sim` UART) and build it
with `builder.build(sim_config=sim_config)`; `litex/tools/litex_sim.py` is the reference.

## Looking inside

```sh
litex_sim --trace --trace-fst --trace-start=10000000 --trace-end=20000000 --gtkwave-savefile
gtkwave build/sim/gateware/sim.fst build/sim/gateware/sim.gtkw
```

`--trace` dumps a VCD (`--trace-fst` the smaller FST) between `--trace-start` and `--trace-end`
(in picoseconds, `sys_clk` is 1 MHz in the default sim); the SoC's `sim_trace` CSRs start and
stop the dump from software, `sim_marker` puts markers, `sim_finish` ends the simulation.
`--gtkwave-savefile` writes a `.gtkw` with the buses and DRAM phases grouped and colored.
`--sim-debug` prints the SoC's debug output, `--sim-speed` the simulated clock rate, `--threads`
and `--jobs` use several cores, `--opt-level` sets the Verilator optimization, `--save-start`/`--load-start`
save and restore the simulation state to skip a long boot, `--verilator-extra-source` adds your
own C++ to the simulator. `--non-interactive` is for CI.

Inside the simulation, a [bridge](Host-Bridges.md) works as on hardware, and UARTBone on the
simulated serial port needs no root:

```sh
litex_sim --uart-name=crossover+uartbone --uart-pty --csr-csv=csr.csv   # the serial port is the bridge, on /tmp/litex_pty0
litex_server --uart --uart-port=/tmp/litex_pty0                          # in another terminal
litex_cli --regs
litex_term crossover                                                     # the BIOS console, through the bridge
```

`--with-etherbone` (`sudo` for the TAP interface, then `litex_server --udp --udp-ip=192.168.1.50`)
does the same over UDP, as a board with Ethernet would.

## QEMU co-simulation

`--cpu-type=qemu` runs the CPU in a patched [QEMU](https://www.qemu.org/) (variants `rv32` and
`rv64`, QEMU owns the CLINT and PLIC) while the interconnect and the peripherals run in
Verilator: fast software execution (Linux boots in seconds) with the real LiteX gateware for the
I/Os, bridged through a TCP protocol on the CPU's AXI bus. Build the patched QEMU once with
`python3 litex/build/sim/qemu/build_qemu_litex.py`, then:

```sh
litex_sim --cpu-type=qemu --cpu-variant=rv32 --integrated-main-ram-size=0x1000000
litex_sim --cpu-type=qemu --cpu-variant=rv64 --qemu-firmware=fw_jump.bin --qemu-kernel=Image --qemu-dtb=soc.dtb
```

`--qemu-firmware`, `--qemu-kernel`, `--qemu-dtb`, `--qemu-initrd`, `--qemu-append` boot Linux;
with `--integrated-main-ram-size` the main RAM is a file shared between QEMU and Verilator so
the peripherals' DMAs see the same memory. `litex/build/sim/qemu/README.md` has the protocol
and the details.

## Renode

[Renode](https://renode.io) (by [Antmicro](https://antmicro.com)) simulates whole systems
(CPU, peripherals, network) fast enough to run Linux, Zephyr or the BIOS interactively,
without the gateware: LiteX generates the Renode platform of your SoC from `csr.json`, with
Renode's models of the LiteX cores (`litex_json2renode`, written by Antmicro).

### Usage

```sh
python3 -m litex_boards.targets.digilent_arty --cpu-type=vexriscv --with-ethernet --build --no-compile-gateware
litex_json2renode build/digilent_arty/csr.json --resc litex.resc --repl litex.repl \
    --bios-binary build/digilent_arty/software/bios/bios.bin
renode litex.resc
(monitor) start
```

- `litex.repl`: the platform description (CPU, memory regions, the peripherals with their
  addresses and interrupts).
- `litex.resc`: the script that creates the machine, loads the binaries and the network.

Options (`litex_json2renode --help`): `--bios-elf` or `--opensbi-binary` instead of the BIOS
binary, `--firmware-binary` and `--flash-binary <file>@<addr>` to preload the flash,
`--tftp-binary`/`--tftp-server-ip`/`--tftp-server-port` to serve files to the BIOS netboot
from Renode's TFTP server, `--configure-network` to bridge the simulated Ethernet to the
host, `--etherbone <peripheral>` to connect a peripheral to a real one over Etherbone,
`--auto-align <regions>` for the memory regions Renode needs aligned.

A Linux simulation loads the same images as a board: the BIOS netboots them from Renode's
TFTP server, or `--opensbi-binary`/`--firmware-binary` place them directly.

### Supported LiteX components

The generator knows the CPUs (VexRiscv, VexRiscv-SMP, Minerva, Ibex, PicoRV32, Rocket, Mor1kx,
LM32... with the CLINT/PLIC of the Linux variants) and these cores: `uart`, `timer0`,
`ctrl`, `ethmac`/`ethphy`, `spiflash`, `spi`, `i2c0`, `spisdcard` and the SD card
(`sdphy`...), `sdram`/`ddrphy`, `leds`, `switches`, `video_framebuffer`, `cas`, `mmcm`.
Unknown cores are not modeled (their accesses are silenced).

### More

- [litex-renode](https://github.com/litex-hub/litex-renode) holds the earlier version of the
  generator and examples; the [Renode documentation](https://renode.readthedocs.io/) describes
  the monitor, the GDB server (`machine StartGdbServer 3333`), tracing and testing.
- For a cycle-accurate simulation with the real gateware, see [litex_sim](SoC-Simulator.md)
  and its QEMU co-simulation.

## Other simulators

- The Migen simulator (`run_simulation`) and `pytest` for the unit tests of a core, with Python
  models of the other side (`test/` in every repository): [Add a new core](Add-A-New-Core.md).
- The vendor simulators and cocotb on the generated Verilog (`--no-compile-gateware` to
  generate only); [cocotb_verilator_sim_example](https://github.com/litex-hub/cocotb_verilator_sim_example)
  shows a CPU-less SoC driven from cocotb.

## Next

- [Create a minimal SoC](Create-A-minimal-SoC.md): the SoC `litex_sim` runs, on a board.
- [Write firmware for it](Write-Firmware-For-Your-SoC.md): your program in the simulated SoC.
- [Control it from the host](Host-Bridges.md) and [LiteScope](Use-LiteScope-To-Debug-A-SoC.md): the bridge and the analyzer, in simulation too.
- [Debug the CPU with GDB](Debug-With-GDB.md): OpenOCD on the simulated TAP.
