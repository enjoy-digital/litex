from config import *
import time

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

wb.open()
regs = wb.regs
###
regs.stim_enable.write(1)
regs.stim_tx_primitive.write(primitives["SYNC"])
for i in range(16):
	rx = regs.stim_rx_primitive.read()
	print("rx: %08x %s" %(rx, decode_primitive(rx)))
	time.sleep(0.1)
regs.stim_tx_primitive.write(primitives["R_RDY"])
for i in range(16):
	rx = regs.stim_rx_primitive.read()
	print("rx: %08x %s" %(rx, decode_primitive(rx)))
	time.sleep(0.1)
###
wb.close()
