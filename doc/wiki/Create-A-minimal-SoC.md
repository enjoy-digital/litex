# Create a minimal SoC

From nothing to a SoC with a CPU, a BIOS prompt on the serial port and a few lines of your own
logic, first on your computer with Verilator, then on a board. Ten minutes once
[LiteX is installed](Installation.md). What the pieces are is explained on the
[SoC builder](SoC-builder.md) page; this one is the walk-through.

## 1. In simulation, no board needed

```sh
litex_sim
```

Verilator compiles a SoC with a VexRiscv, a ROM holding the BIOS, an SRAM and a UART, and the
BIOS prompt appears in the terminal:

```
        __   _ __      _  __
       / /  (_) /____ | |/_/
      / /__/ / __/ -_)>  <
     /____/_/\__/\__/_/|_|
   Build your hardware, easily!
 ...
--=============== SoC ==================--
CPU:            VexRiscv @ 1MHz
BUS:            wishbone 32-bit @ 4GiB
CSR:            32-bit data
ROM:            128.0KiB
SRAM:           8.0KiB
--============== Boot ==================--
Booting from serial...
...
litex> help
```

`mem_list`, `mem_read 0x10000000 32`, `ident`, `leds` (with `--with-gpio`): the same BIOS as
on hardware. `Ctrl-C` ends it. [SoC-Simulator](SoC-Simulator.md) has the options (DRAM,
Ethernet, tracing, running your firmware).

## 2. A board: the one-line SoC

Every board of [LiteX-Boards](https://github.com/litex-hub/litex-boards) has a target; a
*minimal* SoC for any supported board is the `simple` target with the board's platform:

```sh
python3 -m litex_boards.targets.simple litex_boards.platforms.digilent_arty --build --load
litex_term /dev/ttyUSB1
```

It uses the platform's default clock and serial port: CPU, ROM, SRAM, UART, timer, the BIOS
prompt. The board's own target (`python3 -m litex_boards.targets.digilent_arty --build --load`)
adds what the board has: DRAM, Ethernet, flash, LEDs, with options (`--help`).

## 3. Your own target file

A target is a Python script. This one is the real pattern of the LiteX-Boards targets, reduced
to the minimum, for the Digilent Arty A7 (replace the platform, the clock and the PLL for
yours: [Add a new board](Add-A-New-Board.md)):

```python
#!/usr/bin/env python3
# minimal_soc.py
from migen import *
from litex.gen import *

from litex_boards.platforms import digilent_arty

from litex.soc.cores.clock import S7PLL
from litex.soc.cores.led import LedChaser
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.builder import Builder

# CRG: the clocks and resets of the SoC ------------------------------------------------------------

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.cd_sys = ClockDomain()                      # the "sys" clock domain everything runs in
        self.pll = pll = S7PLL(speedgrade=-1)
        pll.register_clkin(platform.request("clk100"), 100e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)

# BaseSoC ------------------------------------------------------------------------------------------

class BaseSoC(SoCCore):
    def __init__(self, sys_clk_freq=100e6, **kwargs):
        platform = digilent_arty.Platform()
        self.crg = _CRG(platform, sys_clk_freq)
        SoCCore.__init__(self, platform, sys_clk_freq, ident="My minimal LiteX SoC", **kwargs)
        # Your logic: a core with CSRs is picked up automatically.
        self.leds = LedChaser(pads=platform.request_all("user_led"), sys_clk_freq=sys_clk_freq)

# Build --------------------------------------------------------------------------------------------

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=digilent_arty.Platform, description="My minimal LiteX SoC.")
    parser.add_target_argument("--sys-clk-freq", default=100e6, type=float, help="System clock frequency.")
    args = parser.parse_args()

    soc     = BaseSoC(sys_clk_freq=args.sys_clk_freq, **parser.soc_argdict)
    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)
    if args.load:
        prog = soc.platform.create_programmer()
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))

if __name__ == "__main__":
    main()
```

- `SoCCore(platform, sys_clk_freq, **kwargs)` adds the CPU (VexRiscv by default), the ROM with
  the BIOS, the SRAM, the UART on the platform's `serial` pins, the timer and the controller;
  `**kwargs` carries the command-line options (`--cpu-type`, `--integrated-main-ram-size`,
  `--uart-baudrate`...).
- The CRG is the only board-specific logic: which pin is the clock, which PLL class
  (`S7PLL`, `ECP5PLL`, `GW2APLL`, `iCE40PLL`...: [Cores](Cores.md#clocking)).
- `self.leds = ...`: a core assigned as an attribute gets its CSRs (`leds_out`), its place in
  `csr.h` and `csr.csv`, nothing else to declare.

## 4. Build it without the FPGA toolchain first

```sh
python3 minimal_soc.py --build --no-compile-gateware
```

This generates everything and compiles the BIOS, but does not run Vivado: in a few seconds
the log shows the SoC that was built, and `build/digilent_arty/` holds the Verilog, the
constraints, the BIOS and the software headers:

```
Finalized SoC:
32-bit wishbone Bus, 4.0GiB Address Space.
IO Regions: (1)
io0                 : Origin: 0x80000000, Size: 0x80000000, Mode:  RW, Cached: False, Linker: False
Bus Regions: (4)
rom                 : Origin: 0x00000000, Size: 0x00020000, Mode:  RX, Cached:  True, Linker: False
sram                : Origin: 0x10000000, Size: 0x00002000, Mode: RWX, Cached:  True, Linker: False
main_ram            : Origin: 0x40000000, Size: 0x10000000, Mode: RWX, Cached:  True, Linker: False
csr                 : Origin: 0xf0000000, Size: 0x00010000, Mode:  RW, Cached: False, Linker: False
Bus Masters: (2)
- cpu_bus0          : rw
- cpu_bus1          : rw
Bus Slaves: (4)
- rom               : r
- sram              : rw
- main_ram          : rw
- csr               : rw
32-bit CSR Bus, 32-bit Aligned, 16.0KiB Address Space, 2048B Paging, big Ordering (Up to 32 Locations).
CSR Locations: (7)
- ctrl           : 0
- ddrphy         : 1
- identifier_mem : 2
- leds           : 3
- sdram          : 4
- timer0         : 5
- uart           : 6
IRQ Locations: (2)
- uart   : 0
- timer0 : 1
```

```
build/digilent_arty/
    csr.csv  csr.json  litex.log
    gateware/   digilent_arty.v  digilent_arty.xdc  digilent_arty.tcl  build_digilent_arty.sh  *.init
    software/   include/generated/{csr.h,soc.h,mem.h,git.h,...}  bios/{bios.elf,bios.bin}  libbase/ libc/ ...
```

(The regions above are from the full Arty target with its DRAM; the minimal SoC has no
`main_ram`, `ddrphy` and `sdram`.) `--no-compile-gateware` is the way to check a design and
get its headers on a machine without the toolchain, or to see the effect of an option
(`--cpu-type=serv --integrated-sram-size=0x1000`).

## 5. Build, load, talk to it

```sh
python3 minimal_soc.py --build --load          # Vivado in the PATH (or LITEX_ENV_VIVADO), a few minutes
litex_term /dev/ttyUSB1                        # 115200 8N1 by default
```

The BIOS prompt appears after the board resets; the LEDs chase. `litex_term` is the LiteX
serial terminal (any terminal works); `--kernel demo.bin` boots an application
([Create and load software](Create-And-Load-Software-To-The-CPU.md)). If nothing shows:
check the serial device and baudrate, that the clock pin and frequency of the CRG are the
board's, and that the bitstream loaded (the programmer's output).

## 6. Grow it

```sh
python3 minimal_soc.py --build --load --integrated-main-ram-size=0x8000      # 32 KiB of main RAM in block RAM
python3 minimal_soc.py --build --load --cpu-type=serv --cpu-variant=standard # a smaller CPU
python3 minimal_soc.py --build --load --with-uartbone                        # the serial port as a bridge (no CPU console)
python3 minimal_soc.py --build --load --uart-name=crossover+uartbone         # console and bridge on the same port
litex_server --uart --uart-port=/dev/ttyUSB1 && litex_cli --regs            # read the registers from the host
```

Then in the target: `self.add_sdram(...)` for a DRAM, `self.add_ethernet(...)`, a
[core of your own](Add-A-New-Core.md), a [Verilog core](Reuse-a-SystemVerilog-VHDL-Amaranth-Spinal-HDL-Chisel-core.md),
[LiteScope](Use-LiteScope-To-Debug-A-SoC.md) to look inside; the LiteX-Boards target of your
board shows how its DRAM, Ethernet and flash are added
([Create a complex SoC](Create-A-complex-SoC-With-Cores-From-The-Ecosystem.md)).
