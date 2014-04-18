
class MiIoDriver():
	def __init__(self, regs, name):
		self.regs = regs
		self.name = name
		self.build_miio()

	def build_miio(self):
		for key, value in self.regs.d.items():
			if self.name in key:
				key.replace(self.name, "miio")
				setattr(self, key, value)

	def write(self, value):
		self.miio_o.write(value)

	def read(self):
		return self.miio_i.read()

class MiLaDriver():
	def __init__(self, regs, name):
		self.regs = regs
		self.name = name
		self.build_mila()

	def build_mila(self):
		for key, value in self.regs.d.items():
			if self.name in key:
				key.replace(self.name, "mila")
				setattr(self, key, value)	

	def prog_term(self, trigger, mask):
		self.mila_trigger_port0_trig.write(trigger)
		self.mila_trigger_port0_mask.write(mask)

	def prog_sum(self, datas):
		for adr, dat in enumerate(datas):
			self.mila_trigger_sum_prog_adr.write(adr)
			self.mila_trigger_sum_prog_dat.write(dat)
			self.mila_trigger_sum_prog_we.write(1)
			
	def enable_rle(self):
		self.mila_rle_enable.write(1)
	
	def disable_rle(self):
		self.mila_rle_enable.write(0)

	def is_done(self):
		return self.mila_recorder_done.read()

	def trigger(self, offset, length):
		self.mila_recorder_offset.write(offset)
		self.mila_recorder_length.write(length)
		self.mila_recorder_trigger.write(1)

	def read(self):
		r = []
		empty = self.mila_recorder_read_empty.read()
		while(not empty):
			r.append(self.mila_recorder_read_dat.read())
			empty = self.mila_recorder_read_empty.read()
			self.mila_recorder_read_en.write(1)
		return r