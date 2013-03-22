from miscope import miio
from miscope.bridges.uart2csr.tools.uart2Csr import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================

csr = Uart2Csr(3,115200)

# Csr Addr
MIIO_ADDR  = 0x00

# Miscope Configuration
miio = miio.MiIo(MIIO_ADDR, 8, "IO", csr)

def led_anim0():
	for i in range(10):
		miio.set(0xA5)
		time.sleep(0.1)
		miio.set(0x5A)
		time.sleep(0.1)

def led_anim1():
	for j in range(4):
		#Led <<
		ledData = 1
		for i in range(8):
			miio.set(ledData)
			time.sleep(i*i*0.0020)
			ledData = (ledData<<1)
		#Led >>
		ledData = 128
		for i in range(8): 
			miio.set(ledData)
			time.sleep(i*i*0.0020)
			ledData = (ledData>>1)

#==============================================================================
#                  T E S T  M I G I O 
#==============================================================================

print("- Led Animation...")
led_anim0()
time.sleep(1)
led_anim1()
time.sleep(1)

print("- Read Switch: ",end=' ')
print("%02X" %miio.get())
