*The cheat sheet maps the Verilog and Vivado concepts to their LiteX counterparts as of today and
links to the current pages. bunnie's 2018 introduction for engineers coming from Verilog, kept
with dated notes, is on [its own page](LiteX-for-Hardware-Engineers-2018.md).*

## Verilog to LiteX: the cheat sheet

| In Verilog / Vivado | In LiteX / Migen | Where to read more |
| --- | --- | --- |
| `module` with ports and parameters | a Python class deriving from `LiteXModule` (`from litex.gen import *`); the ports are `Signal` attributes, the parameters are constructor arguments | [Add a new core](Add-A-New-Core.md) |
| `wire`/`reg`, bit widths, signedness | `Signal(n)`, `Signal((n, True))` for signed; widths are checked at elaboration, narrower values are zero/sign extended | [Migen manual](https://m-labs.hk/migen/manual) |
| `assign` | `self.comb += a.eq(b)` | |
| `always @(posedge clk)` | `self.sync += a.eq(b)` in the `sys` clock domain, `self.sync.<domain> += ...` in another one; the reset is implicit (synchronous, `Signal(reset=...)` for the value) | [What is Migen?](LiteX-for-Hardware-Engineers-2018.md#what-is-migen) |
| `if`/`case`, the ternary operator | `If(...).Elif(...).Else(...)`, `Case(sel, {...})`, `Mux(sel, a, b)`; `Cat()`, `Replicate()`, slices `a[7:0]` | |
| a state machine | `FSM()` with `fsm.act("STATE", ...)`, `NextState()`, `NextValue()` | [FSMs](LiteX-for-Hardware-Engineers-2018.md#fsms) |
| `generate` loops, parameterized logic | plain Python `for`/`if` building the statements and submodules | |
| instantiation of a netlist, an IP core, a primitive | `Instance("name", i_a=..., o_b=..., p_PARAM=...)`; sources added with `platform.add_source()`, IP cores with the toolchain's own calls | [Reuse a core](Reuse-An-Existing-Core.md) |
| `.xdc` pins and timing constraints | the platform file (`Pins`, `IOStandard`, `Misc`), `platform.add_period_constraint()`, `platform.add_false_path_constraints()`, `platform.add_platform_command()` for the rest | [Add a new board](Add-A-New-Board.md), [Build backends](Build-Backends.md) |
| clocks, PLL/MMCM, resets | `ClockDomain`, a CRG module with `S7PLL`/`S7MMCM`/`USMMCM`/`ECP5PLL`/... from `litex.soc.cores.clock`; `ResetInserter()`, `ClockDomainsRenamer()` | [SoC builder](SoC-builder.md) |
| clock domain crossing: synchronizers, async FIFOs | `MultiReg`, `PulseSynchronizer`, `BusSynchronizer` (Migen), `stream.AsyncFIFO`, `stream.ClockDomainCrossing` | [Streams](Streams.md) |
| an AXI-Stream style data path | `stream.Endpoint(layout)` with `valid`/`ready`/`first`/`last`/`payload`, and the generic FIFOs, converters, packetizers | [Streams](Streams.md) |
| memory-mapped control registers | `CSRStorage`/`CSRStatus` with `CSRField`; the software side is generated in `csr.h` | [CSR bus](CSR-Bus.md) |
| interrupts | an `EventManager` in the core, `self.irq.add("core")` in the SoC | [Add a new core](Add-A-New-Core.md) |
| the bus fabric (AXI interconnect) | Wishbone or AXI/AXI-Lite, `self.bus.add_master()`/`add_slave()`, shared bus or crossbar, width and burst converters | [Wishbone](Wishbone-Bus.md), [AXI](AXI-Bus.md) |
| block RAM | `Memory(width, depth, init=...)` with `get_port()` in a core; `add_ram()`/`add_rom()` in a SoC | [SoC builder](SoC-builder.md) |
| a testbench | `run_simulation(dut, generator)` with Python generators for a core; `litex_sim` (Verilator) for a whole SoC | [SoC Simulator](SoC-Simulator.md) |
| an ILA (ChipScope, SignalTap) | LiteScope, read through a UART/JTAG/Ethernet/PCIe bridge, no CPU needed | [Use LiteScope](Use-LiteScope-To-Debug-A-SoC.md) |
| the Vivado project and Tcl flow | the Builder: `python3 target.py --build --load` writes the Verilog, the constraints and the Tcl, runs the toolchain and loads the board | [Build backends](Build-Backends.md) |
| a top level with a MicroBlaze/Zynq | `SoCCore` with a soft CPU (VexRiscv by default) or the hard CPU of the device | [CPUs](CPUs.md), [Create a minimal SoC](Create-A-minimal-SoC.md) |

Reading the generated Verilog is the quickest way to see what Migen does with your code:
`build/<platform>/gateware/<platform>.v` is a flat netlist with readable names
(`<module>_<signal>`), next to the generated constraints and the toolchain script.

This is an introduction to LiteX written by and for hardware engineers
who have experience designing FPGAs using Verilog and Vivado.

> **Note:** Experienced Python engineers can skip this and [read the source code](https://github.com/m-labs/migen) for
> documentation. *[2026: LiteX's own `litex_setup.py`/`litex_repos.py` now clone Migen from https://git.m-labs.hk/M-Labs/migen rather than from GitHub.]*

The long version, from the point of view of a Verilog designer discovering LiteX in 2018 (Migen,
CSRs, interrupts, memories, design patterns), is bunnie's
[LiteX for Hardware Engineers (2018)](LiteX-for-Hardware-Engineers-2018.md).
