from config import *
from litescope.host.driver import LiteScopeLADriver

wb.open()
###
la = LiteScopeLADriver(wb.regs, "la", debug=True)

cond = {"cnt0"	:	128} # trigger on cnt0 = 128
la.configure_term(port=0, cond=cond)
la.configure_sum("term")
la.run(offset=128, length=256)

while not la.done():
	pass
la.upload()

la.save("dump.vcd")
la.save("dump.csv")
la.save("dump.py")
###
wb.close()
