transcript on
transcript file CustomTranscript

##############################################################################
# Setup libraries
vlib work
vmap unisims_ver D:/Installs/Logiciels/Xilinx/ISE14.6/14.6/ISE_DS/ISE/verilog/mti_se/10.1c/nt/unisims_ver
vmap secureip D:/Installs/Logiciels/Xilinx/ISE14.6/14.6/ISE_DS/ISE/verilog/mti_se/10.1c/nt/secureip

# Compile design
##############################################################################

source hdl_common/hdl_common.tcl
source hdl_common/hdl_modelsim.tcl

hdl_source compile_rtl.tcl
hdl_source compile_tb.tcl

##############################################################################
# Run simulation
##############################################################################

vsim -t ps -L secureip -L unisims_ver -novopt  glbl top_tb

set NumericStdNoWarnings 1
set StdArithNoWarnings 1

log -r *
do wave.do

onbreak {resume}
run 2000us
