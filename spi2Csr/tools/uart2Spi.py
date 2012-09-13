import string
import time
import serial

def write_ascii(uart, data):
	uart.write(bytes("%c" % data, encoding="ascii"))

class Uart2Spi:
	def __init__(self, port, baudrate):
		self.port = port
		self.baudrate = baudrate
		self.uart = serial.Serial(port, baudrate, timeout=0.01)
	
	def read(self, addr):
		while True:
			write_ascii(self.uart, 0x02)
			write_ascii(self.uart, (addr>>8)&0xFF)
			write_ascii(self.uart, (addr&0xFF))
			write_ascii(self.uart, 0x00)
			read = self.uart.read()
			if len(read) == 1:
				break
		return read[0]
	
	def write(self, addr, data):
		write_ascii(self.uart, 0x01)
		write_ascii(self.uart, (addr>>8)&0xFF)
		write_ascii(self.uart, (addr&0xFF))
		write_ascii(self.uart, data)

def main():
	csr = Uart2Spi(1,115200)
	for i in range(100):
		csr.write(0x0000,i)
		print(csr.read(0x0000))

if __name__ == '__main__':
  main()