################################################################################
#            _____       _            ____  _     _ _       _ 
#           |   __|___  |_|___ _ _   |    \|_|___|_| |_ ___| |
#           |   __|   | | | . | | |  |  |  | | . | |  _| .'| |
#           |_____|_|_|_| |___|_  |  |____/|_|_  |_|_| |__,|_|
#                     |___|   |___|          |___|
#
#      Copyright 2012 / Florent Kermarrec / florent@enjoy-digital.fr
#
#                  migScope Example on De0 Nano Board
#                  ----------------------------------
################################################################################
#
# In this example signals are generated in the FPGA. 
# We will use migScope to record those signals and visualize them.
# 
# Example architecture:
# ----------------------
#        migScope Config  --> Python Client (Host) --> Vcd Output
#             & Trig                |
#                        Arduino (Uart<-->Spi Bridge)
#                                   |
#                                De0 Nano
#                                   |
#              +--------------------+-----------------------+  
#            migIo             Signal Generator           migLa
#       Control of Signal        Ramp, Sinus,           Logic Analyzer  
#           generator            Square, ...
###############################################################################


#==============================================================================
#	I M P O R T 
#==============================================================================
from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.bus.transactions import *
from migen.bank import description, csrgen
from migen.bank.description import *

import sys
sys.path.append("../../")

from migScope import trigger, recorder
import spi2Csr

from timings import *
from constraints import Constraints

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

#Timings Param
clk_freq	= 50*MHz
clk_period_ns	= clk_freq*ns
n		= t2n(clk_period_ns)

# Bus Width
trig_width = 16
dat_width = 16

# Record Size
record_size = 1024

# Csr Addr
CONTROL_ADDR  = 0x0000
TRIGGER_ADDR  = 0x0200
RECORDER_ADDR = 0x0400

#==============================================================================
#       M I S C O P E    E X A M P L E
#==============================================================================
def get():

	# Control Reg
	control_reg0 = RegisterField("control_reg0", 32, reset=0, access_dev=READ_ONLY)
	regs = [control_reg0]
	bank0 = csrgen.Bank(regs,address=CONTROL_ADDR)

	# Trigger
	term0 = trigger.Term(trig_width)
	trigger0 = trigger.Trigger(TRIGGER_ADDR, trig_width, dat_width, [term0])
	
	# Recorder
	recorder0 = recorder.Recorder(RECORDER_ADDR, dat_width, record_size)
	
	# Spi2Csr
	spi2csr0 = spi2Csr.Spi2Csr(16,8)

	# Csr Interconnect
	csrcon0 = csr.Interconnect(spi2csr0.csr, 
			[
				bank0.interface,
				trigger0.bank.interface,
				recorder0.bank.interface
			])
	comb = []
	sync = []
	
	# Signal Generator
	sig_gen = Signal(BV(trig_width))
	sync += [
		sig_gen.eq(sig_gen+1)
	]
	
	# Led
	led0 = Signal(BV(8))
	comb += [
		led0.eq(control_reg0.field.r[:8])
	]
	
	
	# Dat / Trig Bus
	comb += [
		trigger0.in_trig.eq(sig_gen),
		trigger0.in_dat.eq(sig_gen)
	]
	
	# Trigger --> Recorder	
	comb += [
		recorder0.trig_dat.eq(trigger0.dat),
		recorder0.trig_hit.eq(trigger0.hit)
	]
	

	# HouseKeeping
	in_clk = Signal()
	in_rst_n = Signal()
	in_rst = Signal()
	comb += [
		in_rst.eq(~in_rst_n)
	]
	frag = autofragment.from_local()
	frag += Fragment(sync=sync,comb=comb)
	cst = Constraints(in_clk, in_rst_n, spi2csr0, led0)
	src_verilog, vns = verilog.convert(frag,
		cst.get_ios(),
		name="de0_nano",
		clk_signal = in_clk,
		rst_signal = in_rst,
		return_ns=True)
	src_qsf = cst.get_qsf(vns)
	return (src_verilog, src_qsf)