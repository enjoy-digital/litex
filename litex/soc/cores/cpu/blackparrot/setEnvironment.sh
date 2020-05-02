#!/bin/bash
## Set common environment variables
export LITEX=$(git rev-parse --show-toplevel)
export BP=$LITEX/../pythondata-cpu-blackparrot/pythondata_cpu_blackparrot/system_verilog
export BP_LITEX_DIR=$BP/bp_litex
export LITEX_SOFTWARE_COMPILER_RT=$LITEX/../pythondata-software-compiler_rt

#TODO: check if BP exists and warn user
export BP_COMMON_DIR=$BP/bp_common
export BP_FE_DIR=$BP/bp_fe
export BP_BE_DIR=$BP/bp_be
export BP_ME_DIR=$BP/bp_me
export BP_TOP_DIR=$BP/bp_top
export BP_EXTERNAL_DIR=$BP/external
export BASEJUMP_STL_DIR=$BP_EXTERNAL_DIR/basejump_stl
export LITEX_FPGA_DIR=$BP_LITEX_DIR/fpga
export LITEX_SIMU_DIR=$BP_LITEX_DIR/simulation
export BP_LITEX_SOFTWARE=$BP_LITEX_DIR/software

##SOFTWARE CHANGES##

#for a reason, provided udivmoddi4.c is not functionally correct when used with either BP or Rocket under IA extension. Another version of udivmoddi4.c is a workaround to run BIOS on these architectures.
cp $BP_LITEX_SOFTWARE/udivmoddi4.c $LITEX_SOFTWARE_COMPILER_RT/pythondata_software_compiler_rt/data/lib/builtins/.

