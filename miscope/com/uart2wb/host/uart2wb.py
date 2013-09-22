import string
import time
import serial
from struct import *
import time

WRITE_CMD  = 0x01
READ_CMD   = 0x02
CLOSE_CMD  = 0x03

def write_b(uart, data):
	uart.write(pack('B',data))

class Uart2Wb:
	def __init__(self, port, baudrate, debug = False):
		self.port = port
		self.baudrate = baudrate
		self.debug = debug
		self.uart = serial.Serial(port, baudrate, timeout=0.25)
	
	def open(self):
		self.uart.write("\nuart2wb\n".encode('ascii'))
		self.uart.flush()
		time.sleep(0.1)
		self.uart.close()
		self.uart.open()
		
	def close(self):
		for i in range(16):
			write_b(self.uart, CLOSE_CMD)
		self.uart.close()
	
	def read(self, addr, burst_length=1):
		write_b(self.uart, READ_CMD)
		write_b(self.uart, burst_length)
		write_b(self.uart, (addr & 0xff000000) >> 24)
		write_b(self.uart, (addr & 0x00ff0000) >> 16)
		write_b(self.uart, (addr & 0x0000ff00) >> 8)
		write_b(self.uart, (addr & 0x000000ff))
		values = [] 
		for i in range(burst_length):
			read = self.uart.read(4)
			val = (int(read[0]) << 24)  | (int(read[1]) << 16) | (int(read[2]) << 8) | int(read[3])
			if self.debug:
				print("RD %08X @ %08X" %(val, addr + 4*i))
			values.append(val)
		if burst_length == 1:
			return values[0]
		else:
			return values
	
	def read_csr(self, addr, burst_length=1):
		values = self.read(addr, burst_length)
		if isinstance(values, list):
			for i in range(len(values)):
				values[i] = values[i]&0xff
		else:
			values = values & 0xff
		return values
	
	def write(self, addr, data):
		if isinstance(data, list):
			burst_length = len(data)
		else:
			burst_length = 1
		write_b(self.uart, WRITE_CMD)
		write_b(self.uart, burst_length)
		self.uart.write([(addr & 0xff000000) >> 24,
										 (addr & 0x00ff0000) >> 16,
										 (addr & 0x0000ff00) >> 8,
										 (addr & 0x000000ff)])
		if isinstance(data, list):
			for i in range(len(data)):
				self.uart.write([(data[i] & 0xff000000) >> 24,
												 (data[i] & 0x00ff0000) >> 16,
												 (data[i] & 0x0000ff00) >> 8,
												 (data[i] & 0x000000ff)])
				if self.debug:
					print("WR %08X @ %08X" %(elt, addr + 4*i))
		else:
			self.uart.write([(data & 0xff000000) >> 24,
											 (data & 0x00ff0000) >> 16,
											 (data & 0x0000ff00) >> 8,
											 (data & 0x000000ff)])
			if self.debug:
				print("WR %08X @ %08X" %(data, addr))
	
	def write_csr(self, addr, data):
		self.write(addr, data)