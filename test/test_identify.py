import time
from config import *
from tools import *
from miscope.host.drivers import MiLaDriver

mila = MiLaDriver(wb.regs, "mila")
wb.open()
regs = wb.regs
###
#trigger0 = mila.sata_phy_source_source_payload_data_o*primitives["R_OK"]
#mask0 = mila.sata_phy_source_source_payload_data_m

trigger0 = mila.sata_con_sink_payload_identify_o*1
mask0 = mila.sata_con_sink_payload_identify_m

mila.prog_term(port=0, trigger=trigger0, mask=mask0)
mila.prog_sum("term")

# Trigger / wait / receive
mila.trigger(offset=32, length=512)
regs.command_generator_identify.write(1)
mila.wait_done()
mila.read()
mila.export("dump.vcd")
###
wb.close()

print_link_trace(mila,
	tx_data_name="sata_phy_sink_sink_payload_data",
	rx_data_name="sata_phy_source_source_payload_data"
)
