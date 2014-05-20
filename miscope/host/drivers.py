import csv
from miscope.host.vcd import *

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
	def __init__(self, width, regs, name, config_csv=None, use_rle=True):
		self.regs = regs
		self.name = name
		self.build_mila()
		if csv:
			self.build_layout(config_csv)
		self.dat = VcdDat(width)
		self.use_rle = use_rle

	def build_mila(self):
		for key, value in self.regs.d.items():
			if self.name in key:
				key.replace(self.name, "mila")
				setattr(self, key, value)
	
	def build_layout(self, config_csv):
		self.layout = []
		csv_reader = csv.reader(open(config_csv), delimiter=',', quotechar='#')
		for item in csv_reader:
			name, length = item
			self.layout.append((name, int(length)))

	def prog_term(self, port, trigger, mask):
		t = getattr(self, "mila_trigger_port{d}_trig".format(d=int(port)))
		m = getattr(self, "mila_trigger_port{d}_mask".format(d=int(port)))
		t.write(trigger)
		m.write(mask)

	def prog_range_detector(self, port, low, high):
		l = getattr(self, "mila_trigger_port{d}_low".format(d=int(port)))
		h = getattr(self, "mila_trigger_port{d}_high".format(d=int(port)))
		l.write(low)
		h.write(high)

	def prog_edge_detector(self, port, rising_mask, falling_mask, both_mask):
		rm = getattr(self, "mila_trigger_port{d}_rising_mask".format(d=int(port)))
		fm = getattr(self, "mila_trigger_port{d}_falling_mask".format(d=int(port)))
		bm = getattr(self, "mila_trigger_port{d}_both_mask".format(d=int(port)))
		rm.write(rising_mask)
		fm.write(falling_mask)
		bm.write(both_mask)
		
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
		print("T")
		if self.use_rle:
			self.enable_rle()
		self.mila_recorder_offset.write(offset)
		self.mila_recorder_length.write(length)
		self.mila_recorder_trigger.write(1)

	def read(self, vcd=None):
		print("R")
		empty = self.mila_recorder_read_empty.read()
		while(not empty):
			self.dat.append(self.mila_recorder_read_dat.read())
			empty = self.mila_recorder_read_empty.read()
			self.mila_recorder_read_en.write(1)
		if self.use_rle:
			self.dat = self.dat.decode_rle()
		if vcd:
			print("V")
			_vcd = Vcd()
			_vcd.add_from_layout(self.layout, self.dat)
			_vcd.write(vcd)
