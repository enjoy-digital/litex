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
conditions = {
	"core_udp_tx_fsm_state"	: 1
}
conditions = {
	"etherbonesocdevel_master_bus_stb"	: 1,
	"etherbonesocdevel_master_bus_we"	: 0
}
la.configure_term(port=0, cond=conditions)
la.configure_sum("term")
# Run Logic Analyzer
la.run(offset=2048, length=4000)

while not la.done():
	pass

la.upload()
la.save("dump.vcd")

###
wb.close()
