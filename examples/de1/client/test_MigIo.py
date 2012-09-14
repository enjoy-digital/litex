from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.bus.transactions import *
from migen.bank import description, csrgen
from migen.bank.description import *

import sys
sys.path.append("../../../")

from migScope import trigger, recorder, migIo
import spi2Csr
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
MIGIO0_ADDR  = 0x0000

# MigScope Configuration
# migIo
migIo0 = migIo.MigIo(MIGIO0_ADDR, 8, "IO", csr)

#==============================================================================
#                  T E S T  M I G I O 
#==============================================================================

print("1) Write Led Reg")
for i in range(10):
	migIo0.write(0xA5)
	time.sleep(0.1)
	migIo0.write(0x5A)
	time.sleep(0.1)
	
print("2) Read Switch Reg")
print(migIo0.read())