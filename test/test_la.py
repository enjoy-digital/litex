from config import *
import time

from litescope.host.driver import LiteScopeLADriver
la = LiteScopeLADriver(wb.regs, "la", debug=True)

wb.open()
regs = wb.regs
###

conditions = {}
conditions = {
	"udpsocdevel_mac_rx_cdc_source_stb"	: 1
}
la.configure_term(port=0, cond=conditions)
la.configure_sum("term")
# Run Logic Analyzer
la.run(offset=64, length=1024)

while not la.done():
	pass

la.upload()
la.save("dump.vcd")

###
wb.close()
