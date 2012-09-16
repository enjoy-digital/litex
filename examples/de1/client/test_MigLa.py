from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.bus.transactions import *
from migen.bank import description, csrgen
from migen.bank.description import *

import sys
sys.path.append("../../../")

from migScope import trigger, recorder, migIo
from migScope.tools.truthtable import *
from migScope.tools.vcd import *
import spi2Csr
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
MIGIO0_ADDR   = 0x0000
TRIGGER_ADDR  = 0x0200
RECORDER_ADDR = 0x0400

csr = Uart2Spi(1,115200)

# MigScope Configuration
# migIo
migIo0 = migIo.MigIo(MIGIO0_ADDR, 8, "IO",csr)

# Trigger
term0 = trigger.Term(trig_width)
trigger0 = trigger.Trigger(TRIGGER_ADDR, trig_width, dat_width, [term0], csr)

# Recorder
recorder0 = recorder.Recorder(RECORDER_ADDR, dat_width, record_size, csr)

#==============================================================================
#                  T E S T  M I G L A 
#==============================================================================
dat_vcd = []
recorder0.size(1024)

def capture():
	global trigger0
	global recorder0
	global dat_vcd
	sum_tt = gen_truth_table("term0")
	trigger0.sum.write(sum_tt)
	recorder0.reset()
	recorder0.offset(0)
	recorder0.arm()
	print("-Recorder [Armed]")
	print("-Waiting Trigger...", end = ' ')
	while(not recorder0.is_done()):
		time.sleep(0.1)
	print("[Done]")
	
	print("-Receiving Data...", end = ' ')
	sys.stdout.flush()
	dat_vcd += recorder0.read(1024)
	print("[Done]")
	
print("Capturing Ramp..")
print("----------------------")
term0.write(0x0000)
csr.write(0x0000, 0)
capture()

print("Capturing Square..")
print("----------------------")
term0.write(0x0000)
csr.write(0x0000, 1)
capture()

print("Capturing Sinus..")
print("----------------------")
term0.write(0x0080)
csr.write(0x0000, 2)
capture()

myvcd = Vcd()
myvcd.add(Var("wire", 16, "trig_dat", dat_vcd))
myvcd.write("test_MigLa.vcd")