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

class Uart2Csr:
	def __init__(self, port, baudrate, debug=False):
		self.port = port
		self.baudrate = baudrate
		self.debug = debug
		self.uart = serial.Serial(port, baudrate, timeout=0.25)
			
	def read(self, addr, burst_length=1):
		write_b(self.uart, READ_CMD)
		write_b(self.uart, burst_length)
		write_b(self.uart, (addr & 0xff000000) >> 24)
		write_b(self.uart, (addr & 0x00ff0000) >> 16)
		write_b(self.uart, (addr & 0x0000ff00) >> 8)
		write_b(self.uart, (addr & 0x000000ff))
		values = [] 
		for i in range(burst_length):
			read = self.uart.read(1)
			val = int(read[0])
			if self.debug:
				print("RD %02X @ %08X" %(val, addr + 4*i))
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
		write_b(self.uart, WRITE_CMD)
		write_b(self.uart, burst_length)
		self.uart.write([(addr & 0xff000000) >> 24,
										 (addr & 0x00ff0000) >> 16,
										 (addr & 0x0000ff00) >> 8,
										 (addr & 0x000000ff)])
		if isinstance(data, list):
			for i in range(len(data)):
				write_b(self.uart, data[i])
				if self.debug:
					print("WR %02X @ %08X" %(elt, addr + 4*i))
		else:
			write_b(self.uart, data)
			if self.debug:
				print("WR %02X @ %08X" %(data, addr))