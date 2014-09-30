from config import *
from miscope.host.drivers import MiLaDriver

mila = MiLaDriver(wb.regs, "mila", use_rle=False)
wb.open()
###
trigger0 = mila.sataphy_host_gtx_txcominit0_o
mask0 = mila.sataphy_host_gtx_txcominit0_m

mila.prog_term(port=0, trigger=trigger0, mask=mask0)
mila.prog_sum("term")

# Trigger / wait / receive
mila.trigger(offset=8, length=512)
mila.wait_done()
mila.read()
mila.export("dump.vcd")
mila.export("dump.csv")
###
wb.close()
