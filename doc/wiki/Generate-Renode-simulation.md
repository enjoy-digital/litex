# Generate a Renode simulation

[Renode](https://renode.io) (by [Antmicro](https://antmicro.com)) simulates whole systems
(CPU, peripherals, network) fast enough to run Linux, Zephyr or the BIOS interactively,
without the gateware: LiteX generates the Renode platform of your SoC from `csr.json`, with
Renode's models of the LiteX cores (`litex_json2renode`, written by Antmicro).

## Usage

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

## Supported LiteX components

The generator knows the CPUs (VexRiscv, VexRiscv-SMP, Minerva, Ibex, PicoRV32, Rocket, Mor1kx,
LM32... with the CLINT/PLIC of the Linux variants) and these cores: `uart`, `timer0`,
`ctrl`, `ethmac`/`ethphy`, `spiflash`, `spi`, `i2c0`, `spisdcard` and the SD card
(`sdphy`...), `sdram`/`ddrphy`, `leds`, `switches`, `video_framebuffer`, `cas`, `mmcm`.
Unknown cores are not modeled (their accesses are silenced).

## More

- [litex-renode](https://github.com/litex-hub/litex-renode) holds the earlier version of the
  generator and examples; the [Renode documentation](https://renode.readthedocs.io/) describes
  the monitor, the GDB server (`machine StartGdbServer 3333`), tracing and testing.
- For a cycle-accurate simulation with the real gateware, see [litex_sim](SoC-Simulator.md)
  and its QEMU co-simulation.
