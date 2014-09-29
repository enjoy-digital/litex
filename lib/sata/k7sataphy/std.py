from migen.fhdl.std import *
from migen.genlib.record import *

ALIGN_VAL   = 0x7B4A4ABC
SYNC_VAL    = 0xB5B5957C

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
