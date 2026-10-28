`SoCCore(platform, sys_clk_freq)` plus a few cores is a SoC: the builder does the wiring
(address map, interconnect, control registers, interrupts) and writes the `csr.h`, `soc.h` and
`mem.h` the software needs. Every target goes through it, from the
[minimal SoC](Create-A-minimal-SoC.md) to a Linux machine with PCIe. It lives in
`litex/soc/integration/soc.py` and `builder.py`; the arguments and helpers are listed on the
[reference page](SoC-Builder-Reference.md).

![Anatomy of a LiteX SoC](images/litex-soc-architecture.svg)

See it at work without a toolchain: the log prints the SoC it built.

```sh
python3 -m litex_boards.targets.digilent_arty --build --no-compile-gateware    # Finalized SoC: regions, masters, slaves, CSR locations
```

## A target, reduced to what matters

```python
class BaseSoC(SoCCore):
    def __init__(self, sys_clk_freq=100e6, **kwargs):
        platform = digilent_arty.Platform()
        self.crg = _CRG(platform, sys_clk_freq)                  # the clocks: the only board-specific part
        SoCCore.__init__(self, platform, sys_clk_freq, **kwargs) # CPU, ROM + BIOS, SRAM, UART, timer, controller
        self.leds = LedChaser(pads=platform.request_all("user_led"), sys_clk_freq=sys_clk_freq)  # a core: CSRs picked up
        self.add_sdram("sdram", phy=self.ddrphy, module=MT41K128M16(sys_clk_freq, "1:4"))      # one helper per feature
        self.add_ethernet(phy=self.ethphy)

soc     = BaseSoC(**parser.soc_argdict)                          # --cpu-type, --integrated-main-ram-size, --uart-name...
builder = Builder(soc, **parser.builder_argdict)
builder.build()
```

`**kwargs` is how the command line reaches `SoCCore`: `python3 target.py --help` lists the
options of the SoC, the Builder, the toolchain and the CPU. The full forty lines are on
[Create a minimal SoC](Create-A-minimal-SoC.md); every target of
[LiteX-Boards](https://github.com/litex-hub/litex-boards) follows this pattern.

## The classes

| Class | What it brings |
| --- | --- |
| `SoC` | The handlers (`self.bus`, `self.csr`, `self.irq`), the regions, the constants, the finalization. |
| `LiteXSoC` | The `add_*` helpers of the ecosystem: UART, bridges, SDRAM, Ethernet, PCIe, SATA, SD card, video... |
| `SoCCore` | The usual base of a target: builds the standard SoC from its arguments, in a fixed order. |
| `SoCMini` | `SoCCore` with no CPU, UART, timer or SRAM by default: bridge-driven designs, exported cores. |

`SoCCore` adds, in this order: the controller, the CPU, the ROM with the BIOS, the SRAM, the
main RAM, the identifier, UARTBone, the UART, JTAGBone, the CPU JTAG debug, the timer and the
watchdog. Its `mem_map` gives the default origins.

## The address map

Every memory and peripheral is a region with an origin, a size and attributes:
`SoCRegion(origin, size, mode="rw", cached=True, linker=False)`, `SoCIORegion` for the
uncached peripherals. The default origins come from `mem_map`, and a CPU overrides them when
it has constraints:

```python
SoCCore.mem_map = {"rom": 0x00000000, "sram": 0x01000000, "main_ram": 0x40000000}
# VexRiscv (litex/soc/cores/cpu/vexriscv/core.py):
mem_map = {"rom": 0x00000000, "sram": 0x10000000, "main_ram": 0x40000000, "csr": 0xf0000000}
```

A target overrides an origin before `SoCCore.__init__` (`self.mem_map["csr"] = ...`) or lets
the handler allocate one (`self.bus.alloc_region(name, size)`). Uncached peripherals must live
in the CPU's IO regions (`0x80000000` to `0xffffffff` on most 32-bit soft CPUs), which the
handler checks. The final map goes to `mem.h` and `regions.ld` for the software, to `csr.csv`,
`csr.json` and `csr.svd` for the tools, and to the build log:

```
Bus Regions: (4)
rom      : Origin: 0x00000000, Size: 0x00020000, Mode:  RX, Cached:  True, Linker: False
sram     : Origin: 0x10000000, Size: 0x00002000, Mode: RWX, Cached:  True, Linker: False
main_ram : Origin: 0x40000000, Size: 0x10000000, Mode: RWX, Cached:  True, Linker: False
csr      : Origin: 0xf0000000, Size: 0x00010000, Mode:  RW, Cached: False, Linker: False
```

## The bus and its handler

`self.bus` owns the main bus: one standard (`wishbone`, `axi-lite` or `axi`), one data width
(32 to 512 bits), one address width (32 or 64), word or byte addressing, and an interconnect
built at finalization: a shared bus by default (one arbiter, one decoder), or a crossbar
(`--bus-interconnect=crossbar`, every master to every slave). A timeout returns an error
instead of hanging the SoC when a slave does not answer (counted in the controller's
`bus_errors` register), and `--bus-bursting` enables the bursts.

```python
self.bus.add_master(name="dma", master=my_dma.bus)                          # a new bus master
self.bus.add_slave(name="buf", slave=my_sram.bus, region=SoCRegion(size=0x1000, cached=False))
self.bus.add_slave("ext", ext_bus, region=SoCRegion(origin=0x90000000, size=0x100000), clock_domain="eth")
```

A master or a slave of another standard or width is adapted on the way: width converters,
word to byte addressing, the Wishbone, AXI-Lite and AXI bridges in both directions, and a
clock domain crossing when `clock_domain` is given. So a Wishbone CPU, an AXI DMA from a vendor
IP and a 512-bit LiteDRAM port share one SoC; you only name the standard and the width of each
([Wishbone bus](Wishbone-Bus.md), [AXI bus](AXI-Bus.md)).

## CSRs and interrupts

`self.csr` gives every core with `CSRStorage` or `CSRStatus` attributes a *location*, a page
of `csr_paging` bytes (0x800 by default) in the `csr` region, reached through the CSR bridge
the builder adds. The cores are found by name, in alphabetical order, or at a fixed index with
`self.csr.add("uart", n=2)` for a map that does not move between builds; 32 locations by
default, `--csr-address-width=15` doubles them ([CSR bus](CSR-Bus.md)).

`self.irq` assigns the interrupt lines: `self.irq.add("uart")` for a core with an
`EventManager` (the helpers do it), `self.irq.add("mycore", n=5)` for a fixed line. The
numbers are exported as `<NAME>_INTERRUPT` in `soc.h`, for the BIOS and the device trees.

## The helpers

`add_sdram`, `add_ethernet`, `add_etherbone`, `add_pcie`, `add_sata`, `add_sdcard`,
`add_spi_flash`, `add_video_framebuffer`... each instantiates the core, connects its buses as
masters or slaves, allocates its region, registers its CSRs and interrupts, and adds the
constants its driver needs. The module is `self.<name>` afterwards (`self.sdram`,
`self.ethphy`, `self.pcie_phy`), so a target can refine it. The list, with what each one adds
and the naming convention, is on the [reference page](SoC-Builder-Reference.md#the-helpers).

## The Builder

`Builder(soc, output_dir="build/<platform>")` then `builder.build()`:

![The LiteX build flow](images/litex-build-flow.svg)

1. Finalizes the SoC: regions, CSR locations, interrupts, constants, the interconnect.
2. Generates the software support in `software/include/generated/`: `csr.h` (the register
   accessors), `soc.h` (the constants), `mem.h` (the regions), `git.h`, `variables.mak`, the
   linker scripts, `sdram_phy.h` with a DRAM; `csr.csv` and `csr.json` always, `csr.svd` and
   `memory.x` on request.
3. Builds the software packages with `make` (meson 0.59 or later, for picolibc): the libc,
   `libbase`, `libcompiler_rt`, the `lib<core>` of the cores and the [BIOS](BIOS.md), then
   loads `bios.bin` into the ROM, resized to fit.
4. Generates the Verilog and the constraints and runs the toolchain
   ([Build backends](Build-Backends.md)), unless `--no-compile-gateware`.
5. With `--doc`, generates the Sphinx documentation ([SoC documentation](SoC-Documentation.md)).

The target loads or flashes the result afterwards (`--load`, `--flash`) with the programmer of
the platform; `builder.get_bitstream_filename(mode="sram")` and `builder.get_bios_filename()`
give the paths. A SoC without a board, or exported as a Verilog core for another flow, is on
[Export to Verilog](Export-To-Verilog.md).

## Next

- [SoC builder reference](SoC-Builder-Reference.md): every argument of `SoCCore`, every helper, every Builder option.
- [Create a minimal SoC](Create-A-minimal-SoC.md): the forty lines, built and loaded.
- [CSR bus](CSR-Bus.md) and [Wishbone bus](Wishbone-Bus.md): the two buses the builder wires.
- [Choosing a CPU](Choosing-A-CPU.md): what `add_cpu` connects, and which CPU to pick.
