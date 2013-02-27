################################################################################
#            _____       _            ____  _     _ _       _ 
#           |   __|___  |_|___ _ _   |    \|_|___|_| |_ ___| |
#           |   __|   | | | . | | |  |  |  | | . | |  _| .'| |
#           |_____|_|_|_| |___|_  |  |____/|_|_  |_|_| |__,|_|
#                     |___|   |___|          |___|
#
#      Copyright 2012 / Florent Kermarrec / florent@enjoy-digital.fr
#
#                  miscope Example on De0 Nano Board
#                  ----------------------------------
################################################################################
#
# In this example signals are generated in the FPGA. 
# We use miscope to record those signals and visualize them.
# 
# Example architecture:
# ----------------------
#        miscope Config  --> Python Client (Host) --> Vcd Output
#             & Trig                |
#                        Arduino (Uart<-->Spi Bridge)
#                                   |
#                                De0 Nano
#                                   |
#              +--------------------+-----------------------+  
#            miIo             Signal Generator           miLa
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

from miscope import trigger, recorder, miio, mila
from miscope.bridges import spi2csr

from timings import *
from constraints import Constraints

from math import sin

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

#Timings Param
clk_freq	= 50*MHz
clk_period_ns	= clk_freq*ns
n		= t2n(clk_period_ns)

# Bus Width
trig0_width = 16
dat0_width = 16

trig1_width = 32
dat1_width = 32

# Record Size
record_size = 4096

# Csr Addr
MIIO0_ADDR  = 0x0000
MILA0_ADDR  = 0x0200
MILA1_ADDR  = 0x0600

#==============================================================================
#       M I S C O P E    E X A M P L E
#==============================================================================
def get():

	# migIo0
	miIo0 = miio.MiIo(MIIO0_ADDR, 8, "IO")
	
	# migLa0
	term0 = trigger.Term(trig0_width)
	trigger0 = trigger.Trigger(trig0_width, [term0])
	recorder0 = recorder.Recorder(dat0_width, record_size)
	
	miLa0 = mila.MiLa(MILA0_ADDR, trigger0, recorder0)
	
	# migLa1
	term1 = trigger.Term(trig1_width)
	trigger1 = trigger.Trigger(trig1_width, [term1])
	recorder1 = recorder.Recorder(dat1_width, record_size)
	
	miLa1 = mila.MiLa(MILA1_ADDR, trigger1, recorder1)
	
	# Spi2Csr
	spi2csr0 = spi2csr.Spi2Csr(16,8)
	
	# Csr Interconnect
	csrcon0 = csr.Interconnect(spi2csr0.csr, 
			[
				miIo0.bank.bus,
				miLa0.trigger.bank.bus,
				miLa0.recorder.bank.bus,
				miLa1.trigger.bank.bus,
				miLa1.recorder.bank.bus,
				
			])
	comb = []
	sync = []
	
	#
	# Signal Generator
	#
	
	# Counter
	cnt_gen = Signal(8)
	sync += [
		cnt_gen.eq(cnt_gen+1)
	]
	
	# Square
	square_gen = Signal(8)
	sync += [
		If(cnt_gen[7],
			square_gen.eq(255)
		).Else(
			square_gen.eq(0)
		)
	]
	
	sinus = [int(128*sin((2*3.1415)/256*(x+1)))+128 for x in range(256)]
	sinus_re = Signal()
	sinus_gen = Signal(8)
	comb +=[sinus_re.eq(1)]
	sinus_mem = Memory(8, 256, init = sinus)
	sinus_port = sinus_mem.get_port(has_re=True)
	comb += [
		sinus_port.adr.eq(cnt_gen),
		sinus_port.re.eq(sinus_re),
		sinus_gen.eq(sinus_port.dat_r)
	]
	
	# Signal Selection
	sig_gen = Signal(8)
	comb += [
		If(miIo0.o == 0,
			sig_gen.eq(cnt_gen)
		).Elif(miIo0.o == 1,
			sig_gen.eq(square_gen)
		).Elif(miIo0.o == 2,
			sig_gen.eq(sinus_gen)
		).Else(
			sig_gen.eq(0)
		)
	]
	
	# Led
	led0 = Signal(8)
	comb += [led0.eq(miIo0.o[:8])]
	
	
	# MigLa0 input
	comb += [
		miLa0.trig.eq(sig_gen),
		miLa0.dat.eq(sig_gen)
	]
	
	# MigLa1 input
	comb += [
		miLa1.trig[:8].eq(spi2csr0.csr.dat_w),
		miLa1.trig[8:24].eq(spi2csr0.csr.adr),
		miLa1.trig[24].eq(spi2csr0.csr.we),
		miLa1.dat[:8].eq(spi2csr0.csr.dat_w),
		miLa1.dat[8:24].eq(spi2csr0.csr.adr),
		miLa1.dat[24].eq(spi2csr0.csr.we)
	]
	
	
	# HouseKeeping
	cd_in = ClockDomain("in")
	in_rst_n = Signal()
	comb += [
		cd_in.rst.eq(~in_rst_n)
	]

	frag = autofragment.from_local()
	frag += Fragment(sync=sync,comb=comb,memories=[sinus_mem])
	cst = Constraints(in_rst_n, cd_in, spi2csr0, led0)
	src_verilog, vns = verilog.convert(frag,
		cst.get_ios(),
		name="de0_nano",
		clock_domains={
			"sys": cd_in
		},
		return_ns=True)
	src_qsf = cst.get_qsf(vns)
	return (src_verilog, src_qsf)