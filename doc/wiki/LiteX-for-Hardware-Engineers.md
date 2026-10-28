Coming from Verilog and Vivado? Here is what each thing you do becomes in LiteX, and where to
read more. The long version, bunnie's 2018 introduction for engineers coming from Verilog, kept
with dated notes, is on [its own page](LiteX-for-Hardware-Engineers-2018.md); the reasons
behind the choices are on [The LiteX approach](LiteX-Approach.md).

## Verilog to LiteX

| In Verilog and Vivado | In LiteX and Migen | Read more |
| --- | --- | --- |
| `module` with ports and parameters | A class deriving from `LiteXModule`; the ports are `Signal` attributes, the parameters arguments. | [Add a new core](Add-A-New-Core.md) |
| `wire`, `reg`, widths, signedness | `Signal(n)`, `Signal((n, True))` for signed; widths checked at elaboration, values extended. | [Migen manual](https://m-labs.hk/migen/manual) |
| `assign` | `self.comb += a.eq(b)` | |
| `always @(posedge clk)` | `self.sync += a.eq(b)` in the `sys` domain, `self.sync.<domain> += ...` in another one. | [What is Migen?](LiteX-for-Hardware-Engineers-2018.md#what-is-migen) |
| the reset | Implicit and synchronous; `Signal(reset=...)` gives the value, `ResetInserter()` a reset of yours. | |
| `if`, `case`, the ternary operator | `If(...).Elif(...).Else(...)`, `Case(sel, {...})`, `Mux(sel, a, b)`; `Cat()`, slices `a[7:0]`. | |
| a state machine | `FSM()` with `fsm.act("STATE", ...)`, `NextState()`, `NextValue()`. | [FSMs](LiteX-for-Hardware-Engineers-2018.md#fsms) |
| `generate` loops, parameterized logic | Plain Python `for` and `if` building the statements and the submodules. | |
| a netlist, an IP core, a primitive | `Instance("name", i_a=..., o_b=..., p_PARAM=...)`; `platform.add_source()` for the files. | [Reuse a core](Reuse-An-Existing-Core.md) |
| `.xdc` pins and constraints | The platform file (`Pins`, `IOStandard`, `Misc`); `add_period_constraint()` and the false paths. | [Add a new board](Add-A-New-Board.md) |
| the rest of the `.xdc` | `platform.add_platform_command("...")`, passed to the toolchain as is. | [Build backends](Build-Backends.md) |
| clocks, PLL and MMCM, resets | `ClockDomain`; a CRG module with `S7PLL`, `S7MMCM`, `ECP5PLL`... from `litex.soc.cores.clock`. | [SoC builder](SoC-builder.md) |
| clock domain crossing | `MultiReg`, `PulseSynchronizer`, `BusSynchronizer`; `stream.AsyncFIFO`, `stream.ClockDomainCrossing` | [Streams](Streams.md) |
| an AXI-Stream data path | `stream.Endpoint(layout)` with `valid`, `ready`, `first`, `last`, `payload`; FIFOs, converters... | [Streams](Streams.md) |
| memory-mapped control registers | `CSRStorage`, `CSRStatus` with `CSRField`; the software side is generated in `csr.h`. | [CSR bus](CSR-Bus.md) |
| interrupts | An `EventManager` in the core, `self.irq.add("core")` in the SoC. | [Add a new core](Add-A-New-Core.md) |
| the bus fabric (AXI interconnect) | Wishbone or AXI, `self.bus.add_master()` and `add_slave()`; shared bus or crossbar, converters. | [Wishbone](Wishbone-Bus.md), [AXI](AXI-Bus.md) |
| block RAM | `Memory(width, depth, init=...)` with `get_port()` in a core; `add_ram()`, `add_rom()` in a SoC. | [SoC builder](SoC-builder.md) |
| a testbench | `run_simulation(dut, generator)` with Python generators; `litex_sim` (Verilator) for a whole SoC. | [SoC simulator](SoC-Simulator.md) |
| an ILA (ChipScope, SignalTap) | LiteScope, read through a UART, JTAG, Ethernet or PCIe bridge, no CPU needed. | [Use LiteScope](Use-LiteScope-To-Debug-A-SoC.md) |
| the Vivado project and the Tcl flow | The Builder: `python3 target.py --build --load` writes Verilog, constraints and Tcl, runs the tools. | [Build backends](Build-Backends.md) |
| a top level with a MicroBlaze or a Zynq | `SoCCore` with a soft CPU (VexRiscv by default) or the hard CPU of the device. | [CPUs](CPUs.md), [Create a minimal SoC](Create-A-minimal-SoC.md) |

## Ten lines of Migen

```python
from migen import *
from litex.gen import *

class Blink(LiteXModule):
    def __init__(self, led, period=100_000_000):
        counter = Signal(max=period)                         # a register wide enough for period-1
        self.sync += If(counter == period - 1,               # the sys clock domain, implicit reset
                        counter.eq(0), led.eq(~led)
                     ).Else(counter.eq(counter + 1))
```

Everything is a Python object until the build: a `Signal` is a wire or a register depending on
whether it is assigned in `comb` or `sync`, a statement list is logic, a class instance a module
with its submodules. Reading `build/<platform>/gateware/<platform>.v` after a build is the
fastest way to see what Migen made of your code: a flat netlist with readable names
(`<module>_<signal>`), next to the generated constraints and the toolchain script.

## Next

- [Add a new core](Add-A-New-Core.md): your first core, registers and interrupt included.
- [LiteX for Hardware Engineers (2018)](LiteX-for-Hardware-Engineers-2018.md): bunnie's long version, Migen, CSRs, interrupts and memories from a Verilog point of view.
- [The LiteX approach](LiteX-Approach.md): why Python, why Migen, why these interfaces.
- [Reuse an existing core](Reuse-An-Existing-Core.md): your Verilog, VHDL or SystemVerilog as it is.
