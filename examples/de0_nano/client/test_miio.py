from miscope import miio
from miscope.com.uart2csr.host.uart2csr import *

from csr import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

uart = Uart2Csr(3, 115200)

class MiIoCtrl():
	def __init__(self, bus):
		self.bus = bus
	
	def write(self, value):
		miio_o_write(self.bus, value)

	def read(self):
		return miio_i_read(self.bus)

miio = MiIoCtrl(uart)

def led_anim0():
	for i in range(10):
		miio.write(0xA5)
		time.sleep(0.1)
		miio.write(0x5A)
		time.sleep(0.1)

def led_anim1():
	for j in range(4):
		#Led <<
		ledData = 1
		for i in range(8):
			miio.write(ledData)
			time.sleep(i*i*0.0020)
			ledData = (ledData<<1)
		#Led >>
		ledData = 128
		for i in range(8): 
			miio.write(ledData)
			time.sleep(i*i*0.0020)
			ledData = (ledData>>1)

#==============================================================================
#                  T E S T  M I I O 
#==============================================================================

print("- Led Animation...")
led_anim0()
time.sleep(1)
led_anim1()
time.sleep(1)

print("- Read Switch: ",end=' ')
print("%02X" %miio.read())
