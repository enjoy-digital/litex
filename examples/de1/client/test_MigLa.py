from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.bus.transactions import *
from migen.bank import description, csrgen
from migen.bank.description import *

import sys
sys.path.append("../../../")

from migScope import trigger, recorder, migIo
from migScope.tools.truthtable import *
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
MIGIO0_ADDR   = 0x0000
TRIGGER_ADDR  = 0x0200
RECORDER_ADDR = 0x0400

csr = Uart2Spi(1,115200)

# MigScope Configuration
# migIo
migIo0 = migIo.MigIo(MIGIO0_ADDR, 8, "IO",csr)

# Trigger
term0 = trigger.Term(trig_width)
term1 = trigger.Term(trig_width)
term2 = trigger.Term(trig_width)
term3 = trigger.Term(trig_width)
trigger0 = trigger.Trigger(TRIGGER_ADDR, trig_width, dat_width, [term0, term1, term2, term3], csr)

# Recorder
recorder0 = recorder.Recorder(RECORDER_ADDR, dat_width, record_size, csr)

#==============================================================================
#                  T E S T  M I G L A 
#==============================================================================

term0.write(0x5A)
term1.write(0x5A)
term2.write(0x5A)
term3.write(0x5A)
sum_tt = gen_truth_table("term0 & term1 & term2 & term3")
print(sum_tt)
trigger0.sum.write(sum_tt)

migIo0.write(0x5A)

recorder0.reset()
recorder0.size(256)
recorder0.offset(0)
recorder0.arm()

while(not recorder0.is_done()):
	print(".")
	time.sleep(1)

