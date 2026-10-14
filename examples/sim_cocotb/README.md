# cocotb + Verilator example (CPU-less)

A minimal, standalone example showing how to drive a LiteX-generated design
with a [cocotb](https://docs.cocotb.org/) testbench under
[Verilator](https://www.veripool.org/verilator/), without touching LiteX's
own C++-driven `litex/build/sim/` simulation backend.

Addresses [enjoy-digital/litex#2380](https://github.com/enjoy-digital/litex/issues/2380)
("support cocotb+verilator for sim"). See "Why not a `CocotbSimulator`
backend?" below for why this starts as a standalone example instead of a
core-framework change.

## What this is

A **CPU-less** LiteX design (`dut.py`): no RISC-V/VexRiscv core, no
Wishbone bus, no CSR bus. cocotb plays the role of the "host", driving
every signal directly -- exactly the workflow a peripheral developer uses
when bringing up a new core in isolation, before it's wired into a full
SoC.

The design (`CocotbDemoTop`) is still built entirely out of real LiteX/Migen
building blocks:

- `litex.gen.LiteXModule`, a `ClockDomain`, and `migen.genlib.cdc.MultiReg`
  (the same 2-flip-flop synchronizer pattern `litex.soc.cores.gpio.GPIOIn`
  uses internally).
- One real LiteX peripheral core, unmodified:
  [`litex.soc.cores.uart.RS232PHY`](https://github.com/enjoy-digital/litex/blob/master/litex/soc/cores/uart.py),
  wired directly to top-level ports instead of a CSR bus.
- A hand-rolled GPIO input/output register pair (LiteX's `GPIOIn`/`GPIOOut`
  are CSR-based and need a bus master to be useful; this example intentionally
  avoids pulling in a full CSR/Wishbone stack).

Ports exposed by the generated `dut` module:

| Port | Direction | Purpose |
|---|---|---|
| `sys_clk`, `sys_rst` | in | clock / reset |
| `gpio_in[8]` | in | asynchronous input pins (e.g. a button/sensor) |
| `gpio_in_sync[8]` | out | 2FF-synchronized view of `gpio_in` |
| `gpio_out_data[8]`, `gpio_out_we` | in | write port for the GPIO output register |
| `gpio_out[8]` | out | registered GPIO output pins |
| `uart_tx_data[8]`, `uart_tx_valid`, `uart_tx_ready` | in/in/out | byte-level handshake INTO the UART PHY |
| `uart_rx_data[8]`, `uart_rx_valid`, `uart_rx_ready` | out/out/in | byte-level handshake OUT OF the UART PHY |
| `uart_tx`, `uart_rx` | out/in | the actual serial line pins |

## Why `verilog.convert()` instead of `SimPlatform.build()`

LiteX's `litex/build/sim/verilator.py` (`SimVerilatorToolchain`/
`VerilatorSimulator`) owns the simulation main loop itself: it generates a
C++ wrapper, compiles it with Verilator, and *that C++ binary* drives the
clock and runs the simulation, calling back into LiteX-provided C models
for peripherals (Ethernet, USB, UART, etc. -- see `litex/build/sim/core/`).

cocotb inverts that: **Python owns the main loop**, and the simulator
(Verilator, in this case, via its VPI layer) is a library that Python calls
into. These two models can't both own the loop at once.

Rather than modify `litex/build/sim/` to somehow support both, this example
sidesteps the conflict entirely: `dut.py` calls Migen's own
`migen.fhdl.verilog.convert()` directly to elaborate `CocotbDemoTop` straight
to a clean Verilog file (`dut.v`), never touching `SimPlatform`/
`VerilatorSimulator`. `verilog.convert()` and `SimPlatform.build()`'s
Verilog-generation step are the same underlying operation -- the difference
is only that this path stops there, instead of continuing on to compile a
C++-driven simulation binary. **Zero changes to `litex/build/sim/` are made
or required.**

## Directory contents

```
examples/sim_cocotb/
├── README.md          -- this file
├── dut.py             -- the CPU-less LiteX design; run standalone to (re)generate dut.v
├── test_dut.py         -- the cocotb testbench (GPIO + UART tests)
├── test_runner.py      -- builds dut.v and runs test_dut.py under Verilator via cocotb-tools
├── requirements.txt    -- Python dependencies (migen, litex, cocotb, cocotb-tools)
└── .gitignore
```

## Setup

### 1. Install Verilator (>= 5.0)

Not a Python package -- install via your OS package manager or build from
source:

```bash
# Debian/Ubuntu
sudo apt-get install verilator   # check `verilator --version` >= 5.0; if your
                                  # distro ships an older version, build from
                                  # source instead: https://verilator.org/guide/latest/install.html

# macOS
brew install verilator

# From source (any platform, gets you the latest release)
git clone https://github.com/verilator/verilator
cd verilator && git checkout stable
autoconf && ./configure && make -j$(nproc) && sudo make install
```

Verify:

```bash
verilator --version   # must be >= 5.0
```

### 2. Install Python dependencies

```bash
cd examples/sim_cocotb
pip install -r requirements.txt
```

This pulls in `migen`, `litex`, `cocotb` (2.x), and `cocotb-tools` (the
separate package that provides the modern `cocotb_tools.runner` Python
build/test API used by `test_runner.py`, replacing the older Makefile-only
flow).

### 3. Run the tests

```bash
python3 test_runner.py
# or, equivalently:
pytest test_runner.py
```

This will:

1. Run `dut.py`, which elaborates `CocotbDemoTop` and writes `dut.v`
   (regenerated fresh on every run, so it can never silently drift from the
   Python source).
2. Invoke Verilator (via `cocotb_tools.runner.get_runner("verilator")`) to
   build a simulation binary from `dut.v`.
3. Run `test_dut.py` against it, exercising:
   - `test_gpio_out_register` -- `gpio_out_we` pulses `gpio_out_data` into
     `gpio_out`.
   - `test_gpio_out_holds_without_write_enable` -- writes are ignored
     unless `gpio_out_we` is pulsed.
   - `test_gpio_in_synchronizer` -- `gpio_in_sync` tracks `gpio_in` after
     the 2FF synchronizer latency.
   - `test_uart_loopback` -- `uart_tx` is looped back to `uart_rx` in
     Python (standing in for a wire bridging the two pins on a board); a
     byte pushed in via the TX stream handshake is confirmed to come back
     out the RX stream handshake unchanged, round-tripping through the real
     `RS232PHY` TX/RX bit-framing state machines.

A waveform (`dut.fst`, via `--trace-fst`) is written under `sim_build/` for
inspection with GTKWave or similar.

## What's been verified vs. what you should verify yourself

Everything up to and including inter-module signal correctness has been
verified in this repository's development sandbox:

- `dut.py` elaborates cleanly and `dut.v` was manually reviewed to confirm
  it declares exactly the intended port list and instantiates a genuine
  `RS232PHY`.
- `test_dut.py` and `test_runner.py` both import cleanly against real
  `cocotb`/`cocotb-tools` installs, and cocotb's `@cocotb.test()` discovery
  finds all four tests.
- `test_runner.py` was run end-to-end and confirmed to progress correctly
  through Verilog generation and into invoking the Verilator build step,
  exactly as designed.

The one thing that could **not** be verified in that sandbox is an actual
Verilator binary run (no Verilator toolchain was installable there -- no
root/apt access, and no prebuilt binary available for that platform). **Run
`python3 test_runner.py` in your own environment with Verilator installed
per Setup step 1** to see the tests actually simulate and pass; if anything
doesn't line up (e.g. a signal-timing edge case in `test_uart_loopback`),
that's the first place to look.

## Performance trade-offs (read before using this for anything bigger)

- Verilator was chosen by LiteX's existing sim backend specifically for
  execution speed; cocotb's VPI/GPI bridge into Python adds call overhead
  at simulation events (e.g. every clock edge a `RisingEdge` trigger is
  awaited).
- For small, peripheral-scale designs like this one, that overhead is
  negligible.
- For system-level simulation (e.g. booting Linux on a full SoC), the
  overhead compounds into an order-of-magnitude slowdown -- cocotb is not a
  drop-in replacement for LiteX's existing C++-model-based peripheral
  simulation at that scale.
- This is exactly the "sweet spot" identified in issue #2380's discussion:
  **CPU-less SoCs / isolated peripheral development**, where the
  convenience of writing testbenches in Python outweighs the performance
  cost, and system-level throughput isn't the goal.

## Scope boundary

This example works for **CPU-less** designs, where cocotb is the sole bus
master driving every signal directly. It does **not** address CPU-based
designs (e.g. a full VexRiscv SoC booting the LiteX BIOS) -- those need
LiteX's existing C++-driven `litex/build/sim/` peripheral models (or
significant additional design work to bridge a running CPU core's bus
transactions into cocotb) and are out of scope here. See "Why not a
`CocotbSimulator` backend?" below for how a future, more integrated version
of this could evolve to help with that.

## Why not a `CocotbSimulator` backend?

Issue #2380's discussion (see `helium729`'s analysis) identified that full,
first-class cocotb support (e.g. `soc.build(simulator="cocotb")`, matching
the existing `simulator="verilator"` API) would require rewriting
`SimBuilder`'s C++-owns-the-loop architecture, plus either reimplementing
LiteX's existing C++ simulation peripherals (Ethernet, USB, PCIe, UART) as
Python/cocotb equivalents (a major performance regression for those) or
wrapping each in a VPI interface. That's a multi-week, maintainer-buy-in-
required change with real risk of the performance trade-offs making it
undesirable for LiteX's primary (system-level, CPU-based) simulation use
case.

This example instead targets the specific, narrower use case the issue's
commenters agreed was valuable and tractable on its own: **CPU-less
peripheral development**, as a fully standalone, zero-core-changes example.
If this proves useful, a natural next step (not included here) would be a
small `CocotbHelper` utility to reduce the boilerplate in `dut.py`/
`test_runner.py` for future cocotb-based examples -- without touching
`litex/build/sim/` itself.
