from miscope import mila
from miscope.std.truthtable import *
from miscope.std.vcd import *
from miscope.com.uart2csr.host.uart2csr import *
from csr import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

uart = Uart2Csr(3, 115200)

class MiLaCtrl():
	def __init__(self, bus):
		self.bus = bus

	def prog_term(self, trigger, mask):
		mila_trigger_port0_trig_write(self.bus, trigger)
		mila_trigger_port0_mask_write(self.bus, mask)

	def prog_sum(self, datas):
		for adr, dat in enumerate(datas):
			mila_trigger_sum_prog_adr_write(self.bus, adr)
			mila_trigger_sum_prog_dat_write(self.bus, dat)
			mila_trigger_sum_prog_we_write(self.bus, 1)

	def is_done(self):
		return mila_recorder_done_read(self.bus)

	def trigger(self, offset, length):
		mila_recorder_offset_write(self.bus, offset)
		mila_recorder_length_write(self.bus, length)
		mila_recorder_trigger_write(self.bus, 1)

	def read(self):
		r = []
		empty = mila_recorder_read_empty_read(self.bus)
		while(not empty):
			r.append(mila_recorder_read_dat_read(self.bus))
			empty = mila_recorder_read_empty_read(self.bus)
			mila_recorder_read_en_write(self.bus, 1)
		return r

# Mila Param
trig_w		= 16
dat_w		= 16
rec_length	= 512
rec_offset	= 0
	
#==============================================================================
#                  T E S T  M I L A 
#==============================================================================
dat_vcd = VcdDat(dat_w)

mila = MiLaCtrl(uart)

def capture():
	global dat_vcd
	sum_tt = gen_truth_table("term")
	mila.prog_sum(sum_tt)
	mila.trigger(rec_offset, rec_length)
	print("-Recorder [Triggered]")
	print("-Waiting Trigger...", end=' ')
	while(not mila.is_done()):
		time.sleep(0.1)
	print("[Done]")
	
	print("-Receiving Data...", end=' ')
	sys.stdout.flush()
	dat_vcd += mila.read()
	print("[Done]")

print("Capturing ...")
print("----------------------")
mila.prog_term(0x0000, 0xFFFF)
capture()

mila_layout = [
	("freqgen", 1),
	("event_rising", 1),
	("event_falling", 1),
	("cnt", 8),
	]

myvcd = Vcd()
myvcd.add_from_layout(mila_layout, dat_vcd)
myvcd.write("test_mila.vcd")