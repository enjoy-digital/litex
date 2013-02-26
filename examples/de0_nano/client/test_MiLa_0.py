from miscope import trigger, recorder, miIo, miLa
from miscope.tools.truthtable import *
from miscope.tools.vcd import *

import sys
sys.path.append("../../../")

from spi2Csr.tools.uart2Spi import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================
# Bus Width
trig_width = 16
dat_width = 16

# Record Size
record_size = 4096

# Csr Addr
MIIO_ADDR   = 0x0000
MILA_ADDR   = 0x0200

csr = Uart2Spi(1, 115200, debug=False)

# MiScope Configuration
# miIo0
miIo0 = miIo.MigIo(MIIO_ADDR, 8, "IO",csr)

# miLa0
term0 = trigger.Term(trig_width)
trigger0 = trigger.Trigger(trig_width, [term0])
recorder0 = recorder.Recorder(dat_width, record_size)

miLa0 = miLa.MiLa(MILA_ADDR, trigger0, recorder0, csr)

#==============================================================================
#                  T E S T  M I G L A 
#==============================================================================
dat_vcd = []
recorder0.size(1024)

def capture(size):
	global trigger0
	global recorder0
	global dat_vcd
	sum_tt = gen_truth_table("term0")
	miLa0.trig.sum.write(sum_tt)
	miLa0.rec.reset()
	miLa0.rec.offset(0)
	miLa0.rec.arm()
	print("-Recorder [Armed]")
	print("-Waiting Trigger...", end = ' ')
	while(not miLa0.rec.is_done()):
		time.sleep(0.1)
	print("[Done]")
	
	print("-Receiving Data...", end = ' ')
	sys.stdout.flush()
	dat_vcd += miLa0.rec.read(size)
	print("[Done]")
	
print("Capturing Ramp..")
print("----------------------")
term0.write(0x0000,0xFFFF)
csr.write(0x0000, 0)
capture(1024)

print("Capturing Square..")
print("----------------------")
term0.write(0x0000,0xFFFF)
csr.write(0x0000, 1)
capture(1024)

print("Capturing Sinus..")
print("----------------------")
term0.write(0x0080,0xFFFF)
csr.write(0x0000, 2)
capture(1024)

myvcd = Vcd()
myvcd.add(Var("wire", 16, "trig_dat", dat_vcd))
myvcd.write("test_MiLa_0.vcd")