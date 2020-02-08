#!/bin/bash


##SOFTWARE CHANGES##

#for a reason, provided udivmoddi4.c is not functionally correct when used with either BP or Rocket under IA extension. Another version of udivmoddi4.c is a workaround to run BIOS on these architectures.
cp bp_software/udivmoddi4.c $LITEX/litex/soc/software/compiler_rt/lib/builtins/.
cp bp_software/cce_ucode.mem /tmp/.

##HARDWARE CHANGES## 
#Need to change some files because of memory map differences and proper syntesis
cp bp_hardware/bp_common_pkg.vh $BP_COMMON_DIR/src/include/.
cp bp_hardware/bp_cce_mmio_cfg_loader.v $BP_ME_DIR/test/common/.
cp bp_hardware/bp_nonsynth_host.v $BP_TOP_DIR/test/common/.

# Neccessary files for FPGA Implementations
cp -r bp_fpga $BP_TOP/DIR
