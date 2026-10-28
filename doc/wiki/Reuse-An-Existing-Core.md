A Verilog, VHDL or SystemVerilog core goes into a LiteX SoC as it is, and so does anything
that generates Verilog (SpinalHDL, Amaranth, Chisel): an `Instance` in the design plus the
source files added to the platform, and the toolchain does the rest. Most LiteX designs do
this somewhere, as in the mixed-language SoC below: the integration and most cores in Migen,
the VexRiscv from SpinalHDL as Verilog, a LiteDRAM standalone core generated from a `.yml`, a
VHDL core and a Verilog core.

![](https://user-images.githubusercontent.com/1450143/141784446-e60d3905-6f1c-4773-89b9-dfe2074b5686.png)

## 1. Instantiate the core

The design configures the core through its parameters and connects its ports; LiteX then
treats the core as a black box with a known name and interface, discovered by the toolchain at
synthesis. The `Instance` of Migen does it, with a prefix for each kind of connection:

```python
din    = Signal(32)
dout   = Signal(32)
dinout = Signal(32)
self.specials += Instance("custom_core",
    p_DATA_WIDTH = 32,      # p_: a parameter (int, str or Const)
    i_din        = din,     # i_: an input port (Signal, Cat, Slice or int)
    o_dout       = dout,    # o_: an output port
    io_dinout    = dinout,  # io_: a bidirectional port
)
```

Same as a Verilog instantiation, except that an `Instance` is a Python dict, so the
parameters and the ports can be prepared in advance, conditionally, or in a loop:

```python
params_ios = dict(p_DATA_WIDTH=32)                       # the parameters...
params_ios.update(i_din=din, o_dout=dout, io_dinout=dinout)   # ...the ports...
self.specials += Instance("custom_core", **params_ios)   # ...the instance

# Updated from a method, as a CPU wrapper does with its reset address:
def set_reset_address(self, reset_address):
    self.cpu_params.update(i_externalResetVector=Signal(32, reset=reset_address))

# A group of ports in a loop (a LiteDRAM standalone core with n FIFO ports):
for i in range(fifo_ports):
    litedram_params.update(**{
        f"i_user_fifo_{i}_in_valid" : axis_in[i].valid,
        f"o_user_fifo_{i}_in_ready" : axis_in[i].ready,
        f"i_user_fifo_{i}_in_data"  : axis_in[i].data,
    })

# A bus with one port per bit, connected in one line (the LiteICLink ECP5 SerDes):
serdes_params.update(**{f"i_CHX_FF_TX_D_{n}": tx_bus[n] for n in range(tx_bus.nbits)})
```

> [!NOTE]
> Python limits a call to 255 keyword arguments: a large `Instance` is built with several
> `update()` calls, as above.

## 2. Add the sources

The toolchain still has to find the core: `platform.add_source()` adds a file, the language
coming from its extension (`.v`, `.vh`, `.vo`, `.vp` for Verilog; `.sv`, `.svo` for
SystemVerilog; `.vhd`, `.vhdl`, `.vho` for VHDL):

```python
platform.add_source("core.v")
platform.add_sources("./", "core0.v", "core1.vhd", "core2.sv")   # several at once
platform.add_source_dir(path="./")                                # a whole directory
```

`add_source_dir` is not always the right tool: some projects ship several implementations of
the same module (one for simulation, one per FPGA family), and the toolchain cannot choose. List
the files yourself in that case. Encrypted or proprietary cores (an `.xci`, a `.tcl` generating
the IP on Xilinx) are added with the toolchain's own calls; the LiteX-Boards
[targets](https://github.com/litex-hub/litex-boards/tree/master/litex_boards/targets) and the
[projects](Projects.md) hold examples of most of these cases.

## 3. Converting at build time

When the toolchain does not read the language of the core, LiteX converts it to Verilog
during the build ([Build backends](Build-Backends.md#mixed-language-sources) has the details):
`VHD2VConverter` runs GHDL on VHDL (NEORV32, Microwatt, the CTU CAN FD core use it),
`Amaranth2VConverter` elaborates an Amaranth module (Minerva, Sentinel, LUNA), `--yosys-slang`
makes the Yosys flows read SystemVerilog. SpinalHDL and Chisel cores generate their Verilog
with sbt, at build time when the parameters depend on the SoC (VexRiscv-SMP, NaxRiscv,
VexiiRiscv) or once and committed (`pythondata-cpu-vexriscv`).

## 4. Examples

- The [Betrusted](https://github.com/betrusted-io) project relies on LiteX for its
  integration and makes heavy use of external Verilog and SystemVerilog cores:
  [the integration of an I2C core from OpenCores](https://github.com/betrusted-io/gateware/blob/master/gateware/i2c/core.py)
  is a good model.
- Every CPU wrapper of `litex/soc/cores/cpu/` is a reused core: `picorv32/core.py` for a plain
  Verilog one, `neorv32/core.py` for VHDL, `minerva/core.py` for Amaranth
  ([Add a new CPU](Add-A-New-CPU.md)).
- The other direction, a LiteX core or SoC as a Verilog module for a vendor flow, is
  [Export to Verilog](Export-To-Verilog.md).

## Next

- [Add a new core](Add-A-New-Core.md): the wrapper around your `Instance`, with CSRs and an interrupt.
- [Build backends](Build-Backends.md): the toolchains, the converters, `--yosys-slang`.
- [Add a new CPU](Add-A-New-CPU.md): the largest `Instance` of a SoC.
- [Export to Verilog](Export-To-Verilog.md): a LiteX core as a Verilog module for a vendor flow.
