# LiteX Simulation Environment

The LiteX simulation environment, also called as LiteX Sim, allows you to create, run, and test an entire LiteX System-on-Chip (SoC) within a simulated environment, rather than on actual hardware. LiteX Sim uses Verilator, a fast, open-source simulator, to create cycle-accurate simulations of your LiteX designs.

This environment is useful for a variety of tasks, such as testing new hardware designs, debugging firmware, or prototyping SoC configurations. The speed of Verilator allows for running larger designs for extended periods, making it possible to test complex behaviors, interact directly with the hardware and test edge cases.

## Getting Started with LiteX Sim

Start with the basic LiteX Sim command:

````sh
litex_sim
````

By default, this command creates an SoC simulation with a minimal configuration. You'll have a LiteX SoC with an integrated CPU (VexRiscv), main RAM, and ROM, and a UART for communication - just like a light version of a SoC you could run on actual hardware:

<p align="center"></p>

## Running Bare Metal Demo on LiteX Sim

Now, let's get more practical. You can run a bare metal demo on the SoC you've simulated. Here's how you can do it:

First, generate an SoC without compiling the gateware:
````sh
litex_sim --integrated-main-ram-size=0x10000 --cpu-type=vexriscv --no-compile-gateware
````

The `--no-compile-gateware` option is used to skip the gateware compilation step, which are not necessary since we are just preparing the SoC
here for bare-metal demo compilation.

Next, compile a bare-metal demo application:

````sh
litex_bare_metal_demo --build-path=build/sim/
````

Finally, initialize the RAM with the demo application and start the simulation:

````sh
litex_sim --integrated-main-ram-size=0x10000 --cpu-type=vexriscv --ram-init=demo.bin
````
<p align="center"></p>

## Extending Simulation Capabilities with LiteX Sim

LiteX Sim also offers several extension options to simulate more complex SoC configurations:

- Add the LiteDRAM core (SDRAM controller) with the `--with-sdram` option.
- Include the LiteEth core (Ethernet MAC) with the `--with-ethernet` option.
- Incorporate the Etherbone core (Ethernet-to-Wishbone bridge) with the `--with-etherbone` option.
- Add the LiteSPI core (Quad SPI flash controller) using the `--with-spi-flash` option.

For example, if you want to simulate an SoC with Etherbone support:

````sh
litex_sim --with-etherbone --csr-csv=csr.csv
````

Once the simulation is running, you can interact with the simulated SoC through Etherbone as if it were a physical SoC:
````sh
litex_server --udp --udp-ip=192.168.1.51
litex_cli --regs
````

Through LiteX Sim, you have a versatile and effective simulation environment at your disposal. **This ability to prototype and test your designs in a simulated environment can considerably enhance your development process.**
