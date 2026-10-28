LiteX provides [a script](https://github.com/enjoy-digital/litex/blob/master/litex/tools/litex_json2renode.py) for automatic generation of [Renode](http://renode.io) scripts from the json file containing configuration of the LiteX SoC.

### Renode

Renode was created by [Antmicro](http://antmicro.com) as a virtual development tool for multinode embedded networks (both wired and wireless) and is intended to enable a scalable workflow for creating effective, tested and secure IoT systems.

With Renode, developing, testing, debugging and simulating unmodified software for IoT devices is fast, cost-effective and reliable.

For details, see [the official webpage](http://renode.io).

## Usage

First, build your LiteX platform with `--csr-json csr.json` switch, e.g.:

    python3 -m litex_boards.targets.digilent_arty --cpu-type vexriscv --with-ethernet --csr-json csr.json

Now, use the generated configuration file as an input for `litex_json2renode.py`:

    litex_json2renode csr.json --resc litex.resc --repl litex.repl --bios-binary soc_ethernetsoc_arty/software/bios/bios.bin

This will generate two files:

* `litex.repl` - platform definition file, containing information about all the peripherals and their configuration,
* `litex.resc` - Renode script file, allowing to easily run the simulation of the generated platform.

You can load the simulation by executing the command:

    renode litex.resc

Finally, in the Renode terminal window execute the start (or s) command to boot the bios

    start

### Additional options

The script provides additional options. To discover them and get more information:

    ./litex_json2renode.py --help

## Supported LiteX components

The script can generate the following elements of the LiteX SoC:

* `uart`,
* `timer0`,
* `ethmac`,
* `cas`,
* `cpu`,
* `spiflash`,
* `spi`,
* `ctrl`,
* `i2c0`,
* `sdphy`,
* `spisdcard`.
