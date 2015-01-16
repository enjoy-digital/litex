import sys
from config import *
from tools import *
from bist import *
from miscope.host.drivers import MiLaDriver

mila = MiLaDriver(wb.regs, "mila")
generator = SATABISTGeneratorDriver(wb.regs, "sata_bist")
checker = SATABISTCheckerDriver(wb.regs, "sata_bist")
wb.open()
regs = wb.regs
###

if len(sys.argv) < 2:
	print("Need trigger condition!")
	sys.exit(0)

conditions = {}
conditions["wr_cmd"] = {
	"bistsocdevel_sata_con_command_sink_stb"			: 1,
	"bistsocdevel_sata_con_command_sink_payload_write"	: 1,
}
conditions["wr_dma_activate"] = {
	"bistsocdevel_sata_con_command_source_source_stb"			: 1,
	"bistsocdevel_sata_con_command_source_source_payload_write"	: 1,
}
conditions["rd_cmd"] = {
	"bistsocdevel_sata_con_command_sink_stb"			: 1,
	"bistsocdevel_sata_con_command_sink_payload_read"	: 1,
}
conditions["rd_data"] = {
	"bistsocdevel_sata_con_command_source_source_stb"			: 1,
	"bistsocdevel_sata_con_command_source_source_payload_read"	: 1,
}

mila.prog_term(port=0, cond=conditions[sys.argv[1]])
mila.prog_sum("term")

# Trigger / wait / receive
mila.trigger(offset=512, length=2000)

generator.run(0, 2, 0)
checker.run(0, 2, 0)
mila.wait_done()

mila.read()
mila.export("dump.vcd")
###
wb.close()

print_link_trace(mila,
	tx_data_name="bistsocdevel_sata_phy_sink_sink_payload_data",
	rx_data_name="bistsocdevel_sata_phy_source_source_payload_data"
)
