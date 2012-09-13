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

# Csr Addr
MIGIO0_ADDR  = 0x0000
TRIGGER_ADDR  = 0x0200
RECORDER_ADDR = 0x0400

# MigScope Configuration
# migIo
migIo0 = migIo.MigIo(MIGIO0_ADDR, 8, "IO")

# Trigger
term0 = trigger.Term(trig_width)
trigger0 = trigger.Trigger(TRIGGER_ADDR, trig_width, dat_width, [term0])

# Recorder
recorder0 = recorder.Recorder(RECORDER_ADDR, dat_width, record_size)

#==============================================================================
#                  T E S T  M I G I O 
#==============================================================================

csr = Uart2Spi(1,115200)

print("1) Write Led Reg")
for i in range(10):
	csr.write(MIGIO0_ADDR + 0,0xA5)
	time.sleep(0.1)
	csr.write(MIGIO0_ADDR + 0,0x5A)
	time.sleep(0.1)
	
print("2) Read Switch Reg")
print(csr.read(MIGIO0_ADDR + 1))
