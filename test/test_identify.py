import time
from config import *
from miscope.host.dump import *
from miscope.host.drivers import MiLaDriver

mila = MiLaDriver(wb.regs, "mila", use_rle=False)
wb.open()
regs = wb.regs
###
trigger0 = mila.sata_con_sink_stb_o*1
mask0 = mila.sata_con_sink_stb_m

mila.prog_term(port=0, trigger=trigger0, mask=mask0)
mila.prog_sum("term")

# Trigger / wait / receive
mila.trigger(offset=32, length=256)
regs.identify_requester_req.write(1)
regs.identify_requester_req.write(0)
mila.wait_done()
mila.read()
mila.export("dump.vcd")
mila.export("dump.csv")
mila.export("dump.py")
###
wb.close()

###

primitives = {
	"ALIGN"	:	0x7B4A4ABC,
	"CONT"	: 	0X9999AA7C,
	"SYNC"	:	0xB5B5957C,
	"R_RDY"	:	0x4A4A957C,
	"R_OK"	:	0x3535B57C,
	"R_ERR"	:	0x5656B57C,
	"R_IP"	:	0X5555B57C,
	"X_RDY"	:	0x5757B57C,
	"CONT"	:	0x9999AA7C,
	"WTRM"	:	0x5858B57C,
	"SOF"	:	0x3737B57C,
	"EOF"	:	0xD5D5B57C,
	"HOLD"	:	0xD5D5AA7C,
	"HOLDA"	: 	0X9595AA7C
}

def decode_primitive(dword):
	for k, v in primitives.items():
		if dword == v:
			return k
	return ""

dump = Dump()
dump.add_from_layout(mila.layout, mila.dat)

for var in dump.vars:
	if var.name == "sata_phy_sink_sink_payload_data":
		tx_data = var.values
	if var.name == "sata_phy_source_source_payload_data":
		rx_data = var.values

for i in range(len(tx_data)):
	tx = "%08x " %tx_data[i]
	tx += decode_primitive(tx_data[i])
	tx += " "*(16-len(tx))

	rx = "%08x " %rx_data[i]
	rx += decode_primitive(rx_data[i])
	rx += " "*(16-len(rx))

	print(tx + rx)
