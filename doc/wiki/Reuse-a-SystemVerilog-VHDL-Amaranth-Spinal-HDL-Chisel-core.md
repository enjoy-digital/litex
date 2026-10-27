# Intro
Most of the open-source/shared LiteX designs are directly described in Migen/LiteX, but LiteX but is also **heavily used** to integrate/reuse traditional **Verilog/VHDL** cores (commercial or open-source) and also to integrate cores described in **Spinal-HDL, nMigen or other high level HDL DSL** through **Verilog**.

It is for example very common to create mixed language SoC similar to the following one:

![](https://user-images.githubusercontent.com/1450143/141784446-e60d3905-6f1c-4773-89b9-dfe2074b5686.png)

In this SoC, the integration and most of the cores are directly described with Migen/LiteX but external cores are also integrated:

- The [VexRiscv](https://github.com/SpinalHDL/VexRiscv) CPU, described in [Spinal-HDL](https://github.com/SpinalHDL/SpinalHDL) language, is integrated as a verilog standalone core in the LiteX SoC (Pre-generated verilog configuration from https://github.com/litex-hub/pythondata-cpu-vexriscv or https://github.com/litex-hub/pythondata-cpu-vexriscv_smp).
- The [LiteDRAM](https://github.com/enjoy-digital/litedram) core is in this case integrated as verilog standalone core, generated from a [LiteDRAM's Generator](https://github.com/enjoy-digital/litedram/blob/master/litedram/gen.py) and a `.yml` configuration file (ex: [Arty's yml](https://github.com/enjoy-digital/litedram/blob/master/examples/arty.yml))  with: `litedram_gen arty.yml`
- Core 0 is a VHDL core.
- Core 1 is a Verilog core.

>Note: The VexRiscv configurations can also be directly generated from design's parameters/Spinal-HDL sources when the configuration is not cached/present, where verilog is just used as an intermediate language for the integration.

# Basics
Integrating an external core in LiteX that is not written in native Migen/LiteX is pretty straightforward and follows the exact sames rules than other design flows; the tool just needs to know:

- **The configuration of the core (through parameters) and the description of the interfaces** for the integration in the design.
- **The list of sources describing the core** that will be passed to the toolchain for synthesis, place and route.

# Instantiate a core in the design
Doing the instance of the core in the design configures the core and specifies the interfaces. The framework will then consider the **core as a blackbox with known name and interfaces** and will only discover its contents and integrate it during the synthesis of the design.

To instantiate a core in LiteX we are simply reallying on Migen's Instance:
```python3
din    = Signal(32)
dout   = Signal(32)
dinout = Signal(32)
self.specials += Instance("custom_core",
   p_DATA_WIDTH = 32,
   i_din     = din,
   o_dout    = dout,
   io_dinout = dinout
)
```
The first parameters of the `Instance` is the Module's name (`custom_core` in our example) followed by the parameters and ports of the Module:

Prefixes are used to specify the type of interface:
* `p_` for a Parameter (Python's `str` or `int` or Migen's `Const`).
* `i_` for an Input port (Python's `int` or Migen's `Signal`, `Cat`, `Slice`).
* `o_` for an Output port (Python's `int` or Migen's `Signal`, `Cat`, `Slice`).
* `io_` for a Bi-Directional port  (Migen's `Signal`, `Cat`, `Slice`).

If you are **already familiar with VHDL/Verilog**, you can see that the approach is **very similar** to the one you are already using in these languages, with just more flexibility thanks to Python :)

## A few Python's tricks for Instances:
While an instance has to be declared as a single block in (System)Verilog/VHDL, it's not mandatory with Migen/LiteX since Migen's Instance is relying on a Python's Dict: It's possible to have a lot more flexibility and prepare the Instance's parameters in conditionally or in advance:

```python3
# Create a Dict for the Parameters/IOs.
params_ios = dict()

# Add the Parameters.
params_ios.update(
   p_DATA_WIDTH = 32
)
# Add the IOs.
params_ios.update(
   i_din     = din,
   o_dout    = dout,
   io_dinout = dinout
)
# Do the Instance:
self.specials += Instance("custom_core", **self.params_ios)
```
Splitting the Instance allows the use of Python as a powerful pre-processor to define the Parameters and/or assign the IOs.

This can be very useful to update some Parameters/IOs of the Instance from methods; for example allowing the update the CPU reset address from the design:
```python3
def set_reset_address(self, reset_address):
	self.cpu_params.update(i_externalResetVector=Signal(32, reset=reset_address)) 
```

It can also provide some interesting flexibility to connect group of ports, as done for example below to connect an abitrary number of FIFOs ports when re-integrating a LiteDRAM's standalone core in LiteX design:

```python3
for i in range(fifo_ports):
	litedram_params.update(**{
		# FIFO In.
		f"i_user_fifo_{i}_in_valid": axis_in[i].valid,
		f"o_user_fifo_{i}_in_ready": axis_in[i].ready,
		f"i_user_fifo_{i}_in_data" : axis_in[i].data,
		
		# FIFO Out.
		f"o_user_fifo_{i}_out_valid": axis_out[i].valid,
		f"i_user_fifo_{i}_out_ready": axis_out[i].ready,
		f"o_user_fifo_{i}_out_data" : axis_out[i].data,
})
```
...Or do a one-line connect of a bus with a different name for each bit to a bus of the LiteX design, as done for example on the [LiteICLink ECP5's SerDes](https://github.com/enjoy-digital/liteiclink/blob/master/liteiclink/serdes/serdes_ecp5.py):
```python3
serdes_params.update(**{
# CHX TX — data
**{f"i_CHX_FF_TX_D_{n}" : tx_bus[n] for n in range(tx_bus.nbits)}
})
```
>Note: Python restricts Dict creation/update to 255 items, so large Instances have to split the Dict creation as just described above.

# Adding the sources of a core to the design

With the `Instance`,  the design is now aware of the configuration and interfaces of the integrated core but **still don't know from where this core comes and in which language it is described**.

Adding the sources of the core to the design will allow LiteX to pass these informations to the synthesis toolchain and let the toolchain do the synthesis of the core and integration in the design.

Adding the **single source to the LiteX design** is done with `platform.add_source(...)`
```python3
platform.add_source("core.v")   # Will automatically add the core as Verilog source.
platform.add_source("core.sv")  # Will automatically add the core as System-Verilog source.
platform.add_source("core.vhd") # Will automatically add the core as VHDL source.
```
As can be seen, to simplify things for the User, **LiteX automatically determines the language** based on the file extension:
|      Extension    | Language       |
|-------------------|----------------|
| .vhd, .vhdl, .vho | VHDL           |
| .v, .vh, .vo      | Verilog        |
| .sv, .svo         | System Verilog |

Still to simplify things for User, it is possible to **pass multiple sources at once** with `platform.add_sources(...)`:

```python3
platform.add_sources(path="./",
  "core0.v",
  "core1.vhd",
  "core2.sv"
)
```

Or **just provide the path** and let LiteX automatically collect and add the sources:
```python3
platform.add_source_dir(path="./")
```

This last method is **however not always possible** for all external cores: Some projects provide different implementation of the same module: One for simulation, one specialized for one type of FPGA, etc... and the synthesis toolchain will not be able to automatically select the one to use. In theses cases, the previous methods manually specifying the sources should be used.

For more information about the supported parameters of these methods, the LiteX source code be consulted.

# Reusing a (System)Verilog/VHDL core

Just do the `Instance` in your LiteX design and add the source to the LiteX platform as just described just above.

> Note: For verilog cores [litex_read_verilog](https://github.com/enjoy-digital/litex/blob/master/litex/tools/litex_read_verilog.py) tool can be useful to generate the Instance template.

# Reusing a Amaranth/Spinal-HDL/Chisel/etc... core

This is very similar than reusing a Verilog/VHDL core with just one extra step: **Generate** the Amaranth/Spinal-HDL/Chisel/etc.. core **as a verilog core** :)

# Examples of more complex integration

The [Betrusted.io](https://github.com/betrusted-io) project relies on LiteX for the integration and makes heavy use of external Verilog/System Verilog cores. This can then be a good source of integration examples such as [the integration of an I2C core from  OpenCores](https://github.com/betrusted-io/gateware/blob/master/gateware/i2c/core.py).

# Reusing other type of cores

In some cases, some encrypted cores or proprietary core formats needs to be passed to the toolchain: On Xilinx design you'll generally have to integrate `.xci` files or `.tcl` scripts that will automatically generate the cores.

Most of these use-cases are probably already supported by LiteX but aren't (yet) documented here. Please have a look at the LiteX source code, the different LiteX [ressources](Tutorials-Resources.md), [projects](Projects.md) or at the targets from [LiteX-Boards](https://github.com/litex-hub/litex-boards/tree/master/litex_boards/targets) to find similar integration cases.
