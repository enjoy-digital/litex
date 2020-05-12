# BlackParrot in LiteX


## Getting Started

TODO: modify getting started [Getting Started (Full)](GETTING_STARTED.md)

### Prerequisites

```
BP sources (https://github.com/litex-hub/pythondata-cpu-blackparrot)
RISC-V toolchain built for IA architecture (prebuilt binaries provided by LiteX works fine)
Verilator (tested with Verilator 4.031)
```

### Installing

```
https://github.com/litex-hub/pythondata-cpu-blackparrot is required to run BP in LiteX. 
source ./setEnvironment.sh #should be sourced each time you open a terminal or just add this line to bashrc
```

## Running BIOS 

### Simulation
```
cd $LITEX/litex/tools
./litex_sim.py --cpu-type blackparrot --cpu-variant standard --output-dir build/BP_Trial
```
[![asciicast](https://asciinema.org/a/326077.svg)](https://asciinema.org/a/326077)

### FPGA
```
Coming soon!
```

## Running Linux 


### Simulation
```
Modify litex_sim.py by replacing soc.add_constant("ROM_BOOT_ADDRESS", 0x40000000) with soc.add_constant("ROM_BOOT_ADDRESS", 0x80000000)

./litex_sim.py --cpu-type blackparrot --cpu-variant standard --integrated-rom-size 40960 --output-dir build/BP_newversion_linux_ram/ --threads 4 --ram-init build/tests/boot.bin.uart.simu.trial

TODO: add prebuilt bbl files into python-data repository

```

### FPGA

```
Coming soon!
```






