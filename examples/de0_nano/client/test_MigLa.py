from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.bus.transactions import *
from migen.bank import description, csrgen
from migen.bank.description import *

import sys
sys.path.append("../../../")

from migScope import trigger, recorder, migIo, migLa
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
MIGIO_ADDR   = 0x0000
MIGLA_ADDR   = 0x0200

csr = Uart2Spi(1,115200,debug=False)

# MigScope Configuration
# migIo
migIo0 = migIo.MigIo(MIGIO_ADDR, 8, "IO",csr)

# Trigger
term0 = trigger.Term(trig_width)
trigger0 = trigger.Trigger(trig_width, [term0])
recorder0 = recorder.Recorder(dat_width, record_size)

migLa0 = migLa.MigLa(MIGLA_ADDR, trigger0, recorder0, csr)

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
	migLa0.trig.sum.write(sum_tt)
	migLa0.rec.reset()
	migLa0.rec.offset(0)
	migLa0.rec.arm()
	print("-Recorder [Armed]")
	print("-Waiting Trigger...", end = ' ')
	while(not migLa0.rec.is_done()):
		time.sleep(0.1)
	print("[Done]")
	
	print("-Receiving Data...", end = ' ')
	sys.stdout.flush()
	dat_vcd += migLa0.rec.read(1024)
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