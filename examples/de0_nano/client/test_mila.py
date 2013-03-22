from miscope import trigger, recorder, miio, mila
from miscope.tools.truthtable import *
from miscope.tools.vcd import *
from miscope.bridges.uart2csr.tools.uart2Csr import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================
# Csr Addr
MILA_ADDR 	= 0x01

csr = Uart2Csr(3, 115200, debug=False)

# Mila Param
trig_w		= 16
dat_w		= 16
rec_size	= 512
rec_offset	= 32

# Miscope Configuration
# MiLa
term = trigger.Term(trig_w)
trigger = trigger.Trigger(trig_w, [term])
recorder = recorder.Recorder(dat_w, rec_size)
mila = mila.MiLa(MILA_ADDR, trigger, recorder, csr)

	
#==============================================================================
#                  T E S T  M I G L A 
#==============================================================================
dat_vcd = VcdDat(dat_w)

def capture(size):
	global dat_vcd
	sum_tt = gen_truth_table("term")
	mila.trigger.sum.set(sum_tt)
	mila.recorder.reset()
	recorder.set_size(rec_size)	
	mila.recorder.set_offset(rec_offset)
	mila.recorder.arm()
	print("-Recorder [Armed]")
	print("-Waiting Trigger...", end=' ')
	while(not mila.recorder.is_done()):
		time.sleep(0.1)
	print("[Done]")
	
	print("-Receiving Data...", end=' ')
	sys.stdout.flush()
	dat_vcd += mila.recorder.pull(size)
	print("[Done]")

print("Capturing ...")
print("----------------------")
term.set(0x0000, 0xFFFF)
capture(rec_size)

mila_layout = [
	("freqgen", 1),
	("event_rising", 1),
	("event_falling", 1),
	("cnt", 8),
	]

myvcd = Vcd()
myvcd.add_from_layout(mila_layout, dat_vcd)
myvcd.write("test_mila.vcd")