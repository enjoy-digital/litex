import csv
import time
import sys
import string
import serial
from struct import *
from migen.fhdl.structure import *
from litescope.host.reg import *
from litescope.host.dump import *
from litescope.host.truthtable import *

def write_b(uart, data):
	uart.write(pack('B',data))

class LiteScopeUART2WBDriver:
	WRITE_CMD  = 0x01
	READ_CMD   = 0x02
	def __init__(self, port, baudrate=115200, addrmap=None, busword=8, debug=False):
		self.port = port
		self.baudrate = str(baudrate)
		self.debug = debug
		self.uart = serial.Serial(port, baudrate, timeout=0.25)
		self.regs = build_map(addrmap, busword, self.read, self.write)

	def open(self):
		self.uart.flushOutput()
		self.uart.close()
		self.uart.open()
		self.uart.flushInput()
		try:
			self.regs.uart2wb_sel.write(1)
		except:
			pass

	def close(self):
		try:
			self.regs.uart2wb_sel.write(0)
		except:
			pass
		self.uart.flushOutput()
		self.uart.close()

	def read(self, addr, burst_length=1):
		self.uart.flushInput()
		write_b(self.uart, self.READ_CMD)
		write_b(self.uart, burst_length)
		addr = addr//4
		write_b(self.uart, (addr & 0xff000000) >> 24)
		write_b(self.uart, (addr & 0x00ff0000) >> 16)
		write_b(self.uart, (addr & 0x0000ff00) >> 8)
		write_b(self.uart, (addr & 0x000000ff))
		values = []
		for i in range(burst_length):
			val = 0
			for j in range(4):
				val = val << 8
				val |= ord(self.uart.read())
			if self.debug:
				print("RD %08X @ %08X" %(val, (addr+i)*4))
			values.append(val)
		if burst_length == 1:
			return values[0]
		else:
			return values

	def write(self, addr, data):
		if isinstance(data, list):
			burst_length = len(data)
		else:
			burst_length = 1
		write_b(self.uart, self.WRITE_CMD)
		write_b(self.uart, burst_length)
		addr = addr//4
		write_b(self.uart, (addr & 0xff000000) >> 24)
		write_b(self.uart, (addr & 0x00ff0000) >> 16)
		write_b(self.uart, (addr & 0x0000ff00) >> 8)
		write_b(self.uart, (addr & 0x000000ff))
		if isinstance(data, list):
			for i in range(len(data)):
				dat = data[i]
				for j in range(4):
					write_b(self.uart, (dat & 0xff000000) >> 24)
					dat = dat << 8
				if self.debug:
					print("WR %08X @ %08X" %(data[i], (addr + i)*4))
		else:
			dat = data
			for j in range(4):
				write_b(self.uart, (dat & 0xff000000) >> 24)
				dat = dat << 8
			if self.debug:
				print("WR %08X @ %08X" %(data, (addr * 4)))

class LiteScopeIODriver():
	def __init__(self, regs, name):
		self.regs = regs
		self.name = name
		self.build()

	def build(self):
		for key, value in self.regs.d.items():
			if self.name in key:
				key.replace(self.name +"_")
				setattr(self, key, value)

	def write(self, value):
		self.o.write(value)

	def read(self):
		return self.i.read()

class LiteScopeLADriver():
	def __init__(self, regs, name, config_csv=None, use_rle=False):
		self.regs = regs
		self.name = name
		self.use_rle = use_rle
		if config_csv is None:
			self.config_csv = name + ".csv"
		self.get_config()
		self.get_layout()
		self.build()
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

	def build(self):
		for key, value in self.regs.d.items():
			if self.name == key[:len(self.name)]:
				key.replace(self.name + "_")
				setattr(self, key, value)
		value = 1
		for name, length in self.layout:
			setattr(self, name + "_o", value)
			value = value*(2**length)
		value = 0
		for name, length in self.layout:
			setattr(self, name + "_m", (2**length-1) << value)
			value += length

	def show_state(self, s):
		print(s, end="|")
		sys.stdout.flush()

	def prog_term(self, port, trigger=0, mask=0, cond=None):
		if cond is not None:
			for k, v in cond.items():
				trigger |= getattr(self, k + "_o")*v
				mask |= getattr(self, k + "_m")
		t = getattr(self, "trigger_port{d}_trig".format(d=int(port)))
		m = getattr(self, "trigger_port{d}_mask".format(d=int(port)))
		t.write(trigger)
		m.write(mask)

	def prog_range_detector(self, port, low, high):
		l = getattr(self, "trigger_port{d}_low".format(d=int(port)))
		h = getattr(self, "trigger_port{d}_high".format(d=int(port)))
		l.write(low)
		h.write(high)

	def prog_edge_detector(self, port, rising_mask, falling_mask, both_mask):
		rm = getattr(self, "trigger_port{d}_rising_mask".format(d=int(port)))
		fm = getattr(self, "trigger_port{d}_falling_mask".format(d=int(port)))
		bm = getattr(self, "trigger_port{d}_both_mask".format(d=int(port)))
		rm.write(rising_mask)
		fm.write(falling_mask)
		bm.write(both_mask)

	def prog_sum(self, equation):
		datas = gen_truth_table(equation)
		for adr, dat in enumerate(datas):
			self.trigger_sum_prog_adr.write(adr)
			self.trigger_sum_prog_dat.write(dat)
			self.trigger_sum_prog_we.write(1)

	def config_rle(self, v):
		self.rle_enable.write(v)

	def is_done(self):
		return self.recorder_done.read()

	def wait_done(self):
		self.show_state("WAIT HIT")
		while(not self.is_done()):
			time.sleep(0.1)

	def trigger(self, offset, length):
		self.show_state("TRIG")
		if self.with_rle:
			self.config_rle(self.use_rle)
		self.recorder_offset.write(offset)
		self.recorder_length.write(length)
		self.recorder_trigger.write(1)

	def read(self):
		self.show_state("READ")
		empty = self.recorder_read_empty.read()
		while(not empty):
			self.dat.append(self.recorder_read_dat.read())
			empty = self.recorder_read_empty.read()
			self.recorder_read_en.write(1)
		if self.with_rle:
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
