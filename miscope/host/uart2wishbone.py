import string
import serial
from struct import *
from migen.fhdl.structure import *
from miscope.host.regs import *

def write_b(uart, data):
	uart.write(pack('B',data))

class Uart2Wishbone:
	WRITE_CMD  = 0x01
	READ_CMD   = 0x02
	def __init__(self, port, baudrate, addrmap=None, debug=False):
		self.port = port
		self.baudrate = baudrate
		self.debug = debug
		self.uart = serial.Serial(port, baudrate, timeout=0.25)
		self.regs = build_map(addrmap, self.read, self.write)

	def open(self):
		self.uart.flushOutput()
		self.uart.close()
		self.uart.open()
		self.uart.flushInput()
		
	def close(self):
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
