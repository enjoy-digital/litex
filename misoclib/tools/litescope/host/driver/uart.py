import serial
from struct import *
from misoclib.tools.litescope.host.driver.reg import *

def write_b(uart, data):
	uart.write(pack('B',data))

class LiteScopeUARTDriver:
	cmds = {
		"write"	: 0x01,
		"read"	: 0x02
	}
	def __init__(self, port, baudrate=115200, addrmap=None, busword=8, debug=False):
		self.port = port
		self.baudrate = str(baudrate)
		self.debug = debug
		self.uart = serial.Serial(port, baudrate, timeout=0.25)
		if addrmap is not None:
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

	def read(self, addr, burst_length=None, repeats=None):
		datas = []
		def to_int(v):
			return 1 if v is None else v
		for i in range(to_int(repeats)):
			self.uart.flushInput()
			write_b(self.uart, self.cmds["read"])
			write_b(self.uart, burst_length)
			write_b(self.uart, (addr//4 & 0xff000000) >> 24)
			write_b(self.uart, (addr//4 & 0x00ff0000) >> 16)
			write_b(self.uart, (addr//4 & 0x0000ff00) >> 8)
			write_b(self.uart, (addr//4 & 0x000000ff))
			for j in range(to_int(burst_length)):
				data = 0
				for k in range(4):
					data = data << 8
					data |= ord(self.uart.read())
				if self.debug:
					print("RD %08X @ %08X" %(data, (addr+j)*4))
				datas.append(data)
		return datas

	def write(self, addr, data):
		if isinstance(data, list):
			burst_length = len(data)
		else:
			burst_length = 1
		write_b(self.uart, self.cmds["write"])
		write_b(self.uart, burst_length)
		write_b(self.uart, (addr//4 & 0xff000000) >> 24)
		write_b(self.uart, (addr//4 & 0x00ff0000) >> 16)
		write_b(self.uart, (addr//4 & 0x0000ff00) >> 8)
		write_b(self.uart, (addr//4 & 0x000000ff))
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
