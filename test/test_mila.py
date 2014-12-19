from config import *
from miscope.host.drivers import MiLaDriver

mila = MiLaDriver(wb.regs, "mila", use_rle=False)
wb.open()
###
trigger0 = mila.cont_remover_source_stb_o*1
mask0 = mila.cont_remover_source_stb_m

trigger0 = 0
mask0 = 0

mila.prog_term(port=0, trigger=trigger0, mask=mask0)
mila.prog_sum("term")

# Trigger / wait / receive
mila.trigger(offset=32, length=1024)
mila.wait_done()
mila.read()
mila.export("dump.vcd")
mila.export("dump.csv")
###
wb.close()
