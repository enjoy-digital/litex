# Getting started (TODO:update)

## Running BP in LiteX

cd $LITEX/litex/tools  # the folder where litex simulator resides

./litex_sim.py --cpu-type blackparrot --cpu-variant standard --integrated-rom-size 40960 --output-dir build/BP --threads 4 --opt-level=O0 --trace --trace-start 0

#The above command will generate a dut.vcd file under build/BP/gateware folder. gtkwave works fine with the generated dut.vcd.

## Additional Information

The BlackParrot resides in $BP/pre-alpha-release/

core.py in $BP folder is the wrapper that integrates BP into LiteX.

flist.verilator in $BP is all the files that litex_sim fetches for simulation.

The top module is $BP_FPGA_DIR/ExampleBlackParrotSystem.v

The transducer for wishbone communication is $BP_FPGA_DIR/bp2wb_convertor.v

if args.sdram_init is not None: #instead of ram_init for sdram init boot 
        soc.add_constant("ROM_BOOT_ADDRESS", 0x80000000)
