from config import *
from litescope.host.driver import LiteScopeLADriver

wb.open()
###
la = LiteScopeLADriver(wb.regs, "la")

cond = {"cnt0"	:	128} # trigger on cnt0 = 128
la.prog_term(port=0, cond=cond)
la.prog_sum("term")
la.trigger(offset=128, length=256)

la.wait_done()
la.read()

la.export("dump.vcd")
la.export("dump.csv")
la.export("dump.py")
###
wb.close()
