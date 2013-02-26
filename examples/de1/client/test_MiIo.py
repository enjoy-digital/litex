from migScope import trigger, recorder, migIo

import sys
sys.path.append("../../../")

from spi2Csr.tools.uart2Spi import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================
# Bus Width
trig_width = 16
dat_width = 16

# Record Size
record_size = 1024

csr = Uart2Spi(1,115200)

# Csr Addr
MIIO_ADDR  = 0x0000

# Miscope Configuration
# miIo
miIo0 = miIo.MiIo(MIIO_ADDR, 8, "IO", csr)

def led_anim0():
	for i in range(10):
		miIo0.write(0xA5)
		time.sleep(0.1)
		miIo0.write(0x5A)
		time.sleep(0.1)

def led_anim1():
	#Led <<
	for j in range(4):
		ledData = 1
		for i in range(8):
			miIo0.write(ledData)
			time.sleep(i*i*0.0020)
			ledData = (ledData<<1)
		#Led >>
		ledData = 128
		for i in range(8): 
			miIo0.write(ledData)
			time.sleep(i*i*0.0020)
			ledData = (ledData>>1)

#==============================================================================
#                  T E S T  M I G I O 
#==============================================================================

print("- Small Led Animation...")
led_anim0()
time.sleep(1)
led_anim1()
time.sleep(1)

print("- Read Switch: ",end=' ')
print(miIo0.read())


