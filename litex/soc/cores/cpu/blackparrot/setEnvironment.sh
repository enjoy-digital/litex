#!/bin/bash
## Set common environment variables
export LITEX=$(git rev-parse --show-toplevel)
export BP=$PWD
cp bp_software/cce_ucode.mem /tmp/.
cd pre-alpha-release
TOP=$(git rev-parse --show-toplevel)
export BP_COMMON_DIR=$TOP/bp_common
export BP_FE_DIR=$TOP/bp_fe
export BP_BE_DIR=$TOP/bp_be
export BP_ME_DIR=$TOP/bp_me
export BP_TOP_DIR=$TOP/bp_top
export BP_EXTERNAL_DIR=$TOP/external
export BASEJUMP_STL_DIR=$BP_EXTERNAL_DIR/basejump_stl
export BP_FPGA_DIR=$TOP/bp_fpga
## Setup CAD tools

# If the machine you are working on is bsg_cadenv compliant, then you do not
# need to setup the cad tools, simply put bsg_cadenv in the same root dir.
#BSG_CADENV_DIR=$(TOP)/external/bsg_cadenv
#-include $(BSG_CADENV_DIR)/cadenv.mk

## Sepcify license path if needed
#LM_LICENSE_FILE ?=

## Override tool paths if needed
#GCC       ?= gcc
#VCS_HOME  ?=
#VCS       ?= vcs
#URG       ?= urg
#VERILATOR ?= verilator
#DC_SHELL  ?= dc_shell
#DVE       ?= dve
#PYTHON    ?= python

## Needed for verilator g++ compilations
export SYSTEMC_INCLUDE=$BP_EXTERNAL_DIR/include
export SYSTEMC_LIBDIR=$BP_EXTERNAL_DIR/lib-linux64

## Add external tools and libraries to environment
export LD_LIBRARY_PATH=$SYSTEMC_LIBDIR:$LD_LIBRARY_PATH
#export PATH=$(BP_EXTERNAL_DIR)/bin:$(PATH)
#export SYN_PATH=$(BP_TOP_DIR)/syn
#export TB_PATH=$(BP_TOP_DIR)/test/tb
#export MEM_PATH=$(BP_COMMON_DIR)/test/mem

#export LOG_PATH=$(BP_TOP_DIR)/syn/logs
#export RESULTS_PATH=$(BP_TOP_DIR)/syn/results
#export REPORT_PATH=$(BP_TOP_DIR)/syn/reports

TB="bp_top_trace_demo"
CFG="e_bp_single_core_cfg"
START_PC=0x80000000
TOLERANCE=2

# Select CCE ROM based on CFG and Coherence Protocol
# TODO: is there a more scalable way to do this?
if [ $CFG = "e_bp_half_core_cfg" ]
then
    NUM_LCE_P=1
    N_WG=64
elif [ $CFG = "e_bp_single_core_cfg" ]
then
    NUM_LCE_P=2
    N_WG=64
    #echo "Single Core config"
#elif ($CFG -eq e_bp_dual_core_cfg)
#    NUM_LCE_P=4
#    N_WG=32
#elif ($CFG -eq e_bp_quad_core_cfg)
#    NUM_LCE_P=8
#    N_WG=16
#elif ($CFG -eq e_bp_oct_core_cfg)
#     NUM_LCE_P=16
#     N_WG=8
#elif ($(CFG), e_bp_sexta_core_cfg)
#    NUM_LCE_P=32
#    N_WG=4
#elif ($(CFG), e_bp_quad_core_2d_cfg)
#    NUM_LCE_P=8
#    N_WG=16
#elif ($(CFG), e_bp_oct_core_2d_cfg)
#    NUM_LCE_P=16
#    N_WG=8
fi

COH_PROTO="mesi"
CCE_MEM_PATH=$BP_ME_DIR/src/asm/roms/$COH_PROTO
CCE_MEM=bp_cce_inst_rom_$COH_PROTO_lce$NUM_LCE_P_wg$N_WG_assoc8.mem
#DRAMSIM_CH_CFG=DDR2_micron_16M_8b_x8_sg3E.ini
#DRAMSIM_SYS_CFG=system.ini
#$include $BP_COMMON_DIR/syn/Makefile.verilator
#iinclude $(BP_COMMON_DIR)/syn/Makefile.common
#include $(BP_COMMON_DIR)/syn/Makefile.dc
#include $(BP_COMMON_DIR)/syn/Makefile.regress
#include $(BP_COMMON_DIR)/syn/Makefile.vcs
cd ../
