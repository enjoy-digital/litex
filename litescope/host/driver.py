import csv
import time
import sys
import string
import serial
import socket
from struct import *
from migen.fhdl.structure import *
from litescope.host.reg import *
from litescope.host.dump import *
from litescope.host.truthtable import *

# XXX FIXME
try:
	from liteeth.test.model.etherbone import *
except:
	pass

def write_b(uart, data):
	uart.write(pack('B',data))

class LiteScopeUART2WBDriver:
	cmds = {
		"write"	: 0x01,
		"read"	: 0x02
	}
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
		write_b(self.uart, self.cmds["read"])
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
		write_b(self.uart, self.cmds["write"])
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

class LiteScopeEtherboneDriver:
	def __init__(self, ip_address, udp_port=20000, addrmap=None, busword=8, debug=False):
		self.ip_address = ip_address
		self.udp_port = udp_port
		self.debug = debug

		self.tx_sock = None
		self.rx_sock = None
		self.regs = build_map(addrmap, busword, self.read, self.write)

	def open(self):
		self.tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rx_sock.bind(("", self.udp_port))

	def close(self):
		pass

	def read(self, addr, burst_length=1):
		reads_addrs = [addr+4*j for j in range(burst_length)]
		reads = EtherboneReads(base_ret_addr=0x1000, addrs=reads_addrs)
		record = EtherboneRecord()
		record.writes = None
		record.reads = reads
		record.bca = 0
		record.rca = 0
		record.rff = 0
		record.cyc = 0
		record.wca = 0
		record.wff = 0
		record.byte_enable = 0xf
		record.wcount = 0
		record.rcount = len(reads_addrs)

		packet = EtherbonePacket()
		packet.records = [record]
		packet.encode()
		self.tx_sock.sendto(bytes(packet), (self.ip_address, self.udp_port))

		datas, addrs = self.rx_sock.recvfrom(8192)
		packet = EtherbonePacket(datas)
		packet.decode()
		values = packet.records.pop().writes.get_datas()
		if self.debug:
			for i, val in enumerate(values):
				print("RD %08X @ %08X" %(val, addr + 4*i))
		if burst_length == 1:
			return values[0]
		else:
			return values

	def write(self, addr, datas):
		if not isinstance(datas, list):
			datas = [datas]
		writes_datas = [d for d in datas]
		writes = EtherboneWrites(base_addr=addr, datas=writes_datas)
		record = EtherboneRecord()
		record.writes = writes
		record.reads = None
		record.bca = 0
		record.rca = 0
		record.rff = 0
		record.cyc = 0
		record.wca = 0
		record.wff = 0
		record.byte_enable = 0xf
		record.wcount = len(writes_datas)
		record.rcount = 0

		packet = EtherbonePacket()
		packet.records = [record]
		packet.encode()
		self.tx_sock.sendto(bytes(packet), (self.ip_address, self.udp_port))

		if self.debug:
			for i, data in enumerate(datas):
				print("WR %08X @ %08X" %(data, addr + 4*i))

class LiteScopeIODriver():
	def __init__(self, regs, name):
		self.regs = regs
		self.name = name
		self.build()

	def build(self):
		for key, value in self.regs.d.items():
			if self.name in key:
				key = key.replace(self.name +"_", "")
				setattr(self, key, value)

	def write(self, value):
		self.o.write(value)

	def read(self):
		return self.i.read()

class LiteScopeLADriver():
	def __init__(self, regs, name, config_csv=None, use_rle=False, debug=False):
		self.regs = regs
		self.name = name
		self.use_rle = use_rle
		self.debug = debug
		if config_csv is None:
			self.config_csv = name + ".csv"
		self.get_config()
		self.get_layout()
		self.build()
		self.dat = Dat(self.dw)

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
				key = key.replace(self.name + "_", "")
				setattr(self, key, value)
		value = 1
		for name, length in self.layout:
			setattr(self, name + "_o", value)
			value = value*(2**length)
		value = 0
		for name, length in self.layout:
			setattr(self, name + "_m", (2**length-1) << value)
			value += length

	def configure_term(self, port, trigger=0, mask=0, cond=None):
		if cond is not None:
			for k, v in cond.items():
				trigger |= getattr(self, k + "_o")*v
				mask |= getattr(self, k + "_m")
		t = getattr(self, "trigger_port{d}_trig".format(d=int(port)))
		m = getattr(self, "trigger_port{d}_mask".format(d=int(port)))
		t.write(trigger)
		m.write(mask)

	def configure_range_detector(self, port, low, high):
		l = getattr(self, "trigger_port{d}_low".format(d=int(port)))
		h = getattr(self, "trigger_port{d}_high".format(d=int(port)))
		l.write(low)
		h.write(high)

	def configure_edge_detector(self, port, rising_mask, falling_mask, both_mask):
		rm = getattr(self, "trigger_port{d}_rising_mask".format(d=int(port)))
		fm = getattr(self, "trigger_port{d}_falling_mask".format(d=int(port)))
		bm = getattr(self, "trigger_port{d}_both_mask".format(d=int(port)))
		rm.write(rising_mask)
		fm.write(falling_mask)
		bm.write(both_mask)

	def configure_sum(self, equation):
		datas = gen_truth_table(equation)
		for adr, dat in enumerate(datas):
			self.trigger_sum_prog_adr.write(adr)
			self.trigger_sum_prog_dat.write(dat)
			self.trigger_sum_prog_we.write(1)

	def configure_subsampler(self, n):
		self.subsampler_value.write(n-1)

	def configure_qualifier(self, v):
		self.recorder_qualifier.write(v)

	def configure_rle(self, v):
		self.rle_enable.write(v)

	def done(self):
		return self.recorder_done.read()

	def run(self, offset, length):
		if self.debug:
			print("run")
		if self.with_rle:
			self.config_rle(self.use_rle)
		self.recorder_offset.write(offset)
		self.recorder_length.write(length)
		self.recorder_trigger.write(1)

	def upload(self):
		if self.debug:
			print("upload")
		while self.recorder_source_stb.read():
			self.dat.append(self.recorder_source_data.read())
			self.recorder_source_ack.write(1)
		if self.with_rle:
			if self.use_rle:
				self.dat = self.dat.decode_rle()
		return self.dat

	def save(self, filename):
		if self.debug:
			print("save to " + filename)
		dump = Dump()
		dump.add_from_layout(self.layout, self.dat)
		if ".vcd" in filename:
			VCDExport(dump).write(filename)
		elif ".csv" in filename:
			CSVExport(dump).write(filename)
		elif ".py" in filename:
			PYExport(dump).write(filename)
		else:
			raise NotImplementedError
