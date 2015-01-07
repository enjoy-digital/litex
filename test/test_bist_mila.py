import time
from config import *
from tools import *
from bist import *
from miscope.host.drivers import MiLaDriver

mila = MiLaDriver(wb.regs, "mila")
bist = SATABISTDriver(wb.regs)
wb.open()
regs = wb.regs
###

wr_cond = {
	"sata_con_source_source_stb"			: 1,
	"sata_con_source_source_payload_write"	: 1,
}

rd_cond = {
	"sata_con_source_source_stb"			: 1,
	"sata_con_source_source_payload_read"	: 1,
}


mila.prog_term(port=0, cond=rd_cond)
mila.prog_sum("term")

# Trigger / wait / receive
mila.trigger(offset=32, length=1024)

bist.write(0, 16, 1)
bist.read(0, 16, 1)
mila.wait_done()

mila.read()
mila.export("dump.vcd")
###
wb.close()

print_link_trace(mila,
	tx_data_name="sata_phy_sink_sink_payload_data",
	rx_data_name="sata_phy_source_source_payload_data"
)
