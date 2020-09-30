# BlackParrot in LiteX


## Prerequisites and Installing

Please visit https://github.com/scanakci/linux-on-litex-blackparrot for the detailed setup instructions and linux boot-up process.

## Set necessary environment variables for BlackParrot

Running BP in LiteX requires setting some environment variables. Please add the following lines to your bashrc to set them up.

```
pushd .
cd  PATH/TO/LITEX/litex/soc/cores/cpu/blackparrot
source ./setEnvironment.sh
popd
```

## Running BIOS 

[![asciicast](https://asciinema.org/a/326077.svg)](https://asciinema.org/a/326077)

### Simulation
```
cd $LITEX/litex/tools
./litex_sim.py --cpu-type blackparrot --cpu-variant standard --output-dir build/BP_Trial
```

### FPGA

Generate the bitstream 'top.bit' under build/BP_trial/gateware folder
```
$LITEX/litex/boards/genesys2.py --cpu-type blackparrot --cpu-variant standard --output-dir $PWD/build/BP_Trial --integrated-rom-size 51200 --build  
```
In another terminal, launch LiteX terminal.
```
sudo $LITEX/litex/tools/litex_term.py /dev/ttyUSBX 
```
Load the FPGA bitstream top.bit to your FPGA (you can use vivado hardware manager)

This step will execute LiteX BIOS.
