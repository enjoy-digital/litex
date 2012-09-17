from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment
from migen.bus import csr
from migen.bus.transactions import *
from migen.bank import description, csrgen
from migen.bank.description import *

import sys
sys.path.append("../../../")

from migScope import trigger, recorder, migIo, migLa
from migScope.tools.truthtable import *
from migScope.tools.vcd import *
import spi2Csr
from spi2Csr.tools.uart2Spi import *

#==============================================================================
#	P A R A M E T E R S
#==============================================================================
# Bus Width
trig_width = 32
dat_width = 32

# Record Size
record_size = 4096

# Csr Addr
MIGIO0_ADDR   = 0x0000
MIGLA1_ADDR   = 0x0600

csr = Uart2Spi(1,115200,debug=False)

# MigScope Configuration
# migIo0
migIo0 = migIo.MigIo(MIGIO0_ADDR, 8, "IO",csr)

# migIla1
term1 = trigger.Term(trig_width)
trigger1 = trigger.Trigger(trig_width, [term1])
recorder1 = recorder.Recorder(dat_width, record_size)

migLa1 = migLa.MigLa(MIGLA1_ADDR, trigger1, recorder1, csr)

#==============================================================================
#                  T E S T  M I G L A 
#==============================================================================
dat_vcd = []
recorder1.size(1024)

term1.write(0x0100005A,0x0100005A)
sum_tt = gen_truth_table("term1")
migLa1.trig.sum.write(sum_tt)
migLa1.rec.reset()
migLa1.rec.offset(256)
migLa1.rec.arm()

print("-Recorder [Armed]")
print("-Waiting Trigger...", end = ' ')
csr.write(0x0000,0x5A)
while(not migLa1.rec.is_done()):
	time.sleep(0.1)
print("[Done]")

print("-Receiving Data...", end = ' ')
sys.stdout.flush()
dat_vcd += migLa1.rec.read(1024)
print("[Done]")

myvcd = Vcd()
myvcd.add(Var("wire", 8, "csr_dat_w", get_bits(dat_vcd, 32, 0, 8)))
myvcd.add(Var("wire", 16, "csr_adr", get_bits(dat_vcd, 32, 8, 24)))
myvcd.add(Var("wire", 1, "csr_we", get_bits(dat_vcd, 32, 24)))
myvcd.write("test_MigLa_1.vcd")