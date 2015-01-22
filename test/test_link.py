import sys
from config import *
from tools import *
from bist import *
from miscope.host.drivers import MiLaDriver

mila = MiLaDriver(wb.regs, "mila")
identify = LiteSATABISTIdentifyDriver(wb.regs, "sata_bist")
generator = LiteSATABISTGeneratorDriver(wb.regs, "sata_bist")
checker = LiteSATABISTCheckerDriver(wb.regs, "sata_bist")
wb.open()
regs = wb.regs
###

if len(sys.argv) < 2:
	print("Need trigger condition!")
	sys.exit(0)

conditions = {}
conditions["wr_cmd"] = {
	"sata_command_tx_sink_stb"			: 1,
	"sata_command_tx_sink_payload_write"	: 1,
}
conditions["wr_dma_activate"] = {
	"sata_command_rx_source_stb"			: 1,
	"sata_command_rx_source_payload_write"	: 1,
}
conditions["rd_cmd"] = {
	"sata_command_tx_sink_stb"			: 1,
	"sata_command_tx_sink_payload_read"	: 1,
}
conditions["rd_data"] = {
	"sata_command_rx_source_stb"			: 1,
	"sata_command_rx_source_payload_read"	: 1,
}
conditions["id_cmd"] = {
	"sata_command_tx_sink_stb"				: 1,
	"sata_command_tx_sink_payload_identify"	: 1,
}
conditions["id_pio_setup"] = {
	"source_source_payload_data" : primitives["X_RDY"],
}

mila.prog_term(port=0, cond=conditions[sys.argv[1]])
mila.prog_sum("term")

# Trigger / wait / receive
mila.trigger(offset=512, length=2000)

#identify.run()
generator.run(0, 2, 1, 0)
#checker.run(0, 2, 1, 0)
mila.wait_done()

mila.read()
mila.export("dump.vcd")
###
wb.close()

f = open("dump_link.txt", "w")
data = link_trace(mila,
	tx_data_name="sink_sink_payload_data",
	rx_data_name="source_source_payload_data"
)
f.write(data)
f.close()
