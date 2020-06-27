#!/bin/bash
## Set common environment variables
export LITEX=$(git rev-parse --show-toplevel)
export BP=$LITEX/../pythondata-cpu-blackparrot/pythondata_cpu_blackparrot/system_verilog
export BP_LITEX_DIR=$LITEX/litex/soc/cores/cpu/blackparrot/bp_litex

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

##Minor changes in some of the BP files for memory management
sed -i "s/localparam dram_base_addr_gp         = 40'h00_8000_0000;/localparam dram_base_addr_gp         = 40'h00_7000_0000;/" $BP_COMMON_DIR/src/include/bp_common_pkg.vh
sed -i "s/localparam bp_pc_entry_point_gp=39'h00_8000_0000/localparam bp_pc_entry_point_gp=39'h00_7000_0000/" $BP_ME_DIR/test/common/bp_cce_mmio_cfg_loader.v
sed -i "s/wire local_cmd_li        = (cmd_fifo_selected_lo.header.addr < dram_base_addr_gp);/wire local_cmd_li        = (cmd_fifo_selected_lo.header.addr < 32'h5000_0000);/" $BP_TOP_DIR/src/v/bp_softcore.v

## Copy config loader to /tmp
cp $BP_LITEX_DIR/cce_ucode.mem /tmp/.
