from migen.fhdl.std import *

ALIGN_VAL   = 0x7B4A4ABC
SYNC_VAL    = 0xB5B5957C
R_RDY_VAL   = 0x4A4A957C
R_OK_VAL    = 0x3535B57C
R_ERR_VAL   = 0x5656B57C
R_IP_VAL    = 0X5555B57C
X_RDY_VAL   = 0x5757B57C
CONT_VAL    = 0x9999AA7C
WTRM_VAL    = 0x5858B57C
SOF_VAL     = 0x3737B57C
EOF_VAL     = 0xD5D5B57C
HOLD_VAL    = 0xD5D5AA7C
HOLD_ACK    = 0X9595AA7C

def phy_layout(dw):
	layout = [
		("p_packetized", True),
		("d", dw)
	]
	return layout

def link_layout(dw):
	layout = [
		("p_packetized", True),
		("d", dw)
	]
	return layout
