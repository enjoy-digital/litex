from migen.fhdl.std import *
from migen.genlib.record import *

K28_5 = 0b1010000011

ALIGN_VAL   = 0x7B4A4ABC
CONT_VAL    = 0x9999AA7C
DMAT_VAL    = 0x3636B57C
EOF_VAL     = 0xD5D5B57C
HOLD_VAL    = 0xD5D5AA7C
HOLDA_VAL   = 0x9595AA7C
PMACK_VAL   = 0x9595957C
PMNAK_VAL   = 0xF5F5957C
PMREQ_P_VAL = 0x1717B57C
PMREQ_S_VAL = 0x7575957C
R_ERR_VAL   = 0x5656B57C
R_IP_VAL    = 0x5555B57C
R_OK_VAL    = 0x3535B57C
R_RDY_VAL   = 0x4A4A957C
SOF_VAL     = 0x3737B57C
SYNC_VAL    = 0xB5B5957C
WTRM_VAL    = 0x5858B57C
X_RDY_VAL   = 0x5757B57C

def ones(width):
	return 2**width-1

class DRPBus(Record):
	def __init__(self):
		layout = [
			("clk",  1, DIR_M_TO_S),
			("en",   1, DIR_M_TO_S),
			("rdy",  1, DIR_S_TO_M),
			("we",   1, DIR_M_TO_S),
			("addr", 8, DIR_M_TO_S),
			("di",  16, DIR_M_TO_S),
			("do",  16, DIR_S_TO_M)
		]
		Record.__init__(self, layout)
