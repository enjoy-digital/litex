import csv
import time
import sys
from miscope.host.dump import *
from miscope.host.truthtable import *

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
	def __init__(self, regs, name, config_csv=None, use_rle=True):
		self.regs = regs
		self.name = name
		self.use_rle = use_rle
		if config_csv is None:
			self.config_csv = name + ".csv"
		self.get_config()
		self.get_layout()
		self.build_mila()
		self.dat = Dat(self.width)
		
	def get_config(self):
		csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
		for item in csv_reader:
			t, n, v = item
			if t == "config":
				setattr(self, n, int(v))

	def get_layout(self):
		self.layout = []
		csv_reader = csv.reader(open(self.config_csv), delimiter=',', quotechar='#')
		for item in csv_reader:
			t, n, v = item
			if t == "layout":
				self.layout.append((n, int(v)))

	def build_mila(self):
		for key, value in self.regs.d.items():
			if self.name == key[:len(self.name)]:
				key.replace(self.name, "mila")
				setattr(self, key, value)
		value = 1
		for name, length in self.layout:
			setattr(self, name+"_o", value)
			value = value*(2**length)
		value = 0
		for name, length in self.layout:
			setattr(self, name+"_m", (2**length-1) << value)
			value += length

	def show_state(self, s):
		print(s, end="|")
		sys.stdout.flush()

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
		
	def prog_sum(self, equation):
		datas = gen_truth_table(equation)
		for adr, dat in enumerate(datas):
			self.mila_trigger_sum_prog_adr.write(adr)
			self.mila_trigger_sum_prog_dat.write(dat)
			self.mila_trigger_sum_prog_we.write(1)
			
	def config_rle(self, v):
		self.mila_rle_enable.write(v)

	def is_done(self):
		return self.mila_recorder_done.read()

	def wait_done(self):
		self.show_state("WAIT HIT")
		while(not self.is_done()):
			time.sleep(0.1)

	def trigger(self, offset, length):
		self.show_state("TRIG")
		if self.with_rle:
			self.config_rle(self.use_rle)
		self.mila_recorder_offset.write(offset)
		self.mila_recorder_length.write(length)
		self.mila_recorder_trigger.write(1)

	def read(self):
		self.show_state("READ")
		empty = self.mila_recorder_read_empty.read()
		while(not empty):
			self.dat.append(self.mila_recorder_read_dat.read())
			empty = self.mila_recorder_read_empty.read()
			self.mila_recorder_read_en.write(1)
		if self.use_rle:
			self.dat = self.dat.decode_rle()
		return self.dat

	def export(self, export_fn=None):
		self.show_state("EXPORT")
		dump = Dump()
		dump.add_from_layout(self.layout, self.dat)
		if ".vcd" in export_fn:
			VCDExport(dump).write(export_fn)
		elif ".csv" in export_fn:
			CSVExport(dump).write(export_fn)
		elif ".py" in export_fn:
			PYExport(dump).write(export_fn)
		else:
			raise NotImplementedError
