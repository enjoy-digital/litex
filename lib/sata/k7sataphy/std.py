from migen.fhdl.std import *

K28_5 = 0b1010000011

def _ones(width):
	return 2**width-1

class DRPBus(Record):
	def __init__(self):
		layout = [
			("clk",  1, DIR_M_TO_S),
			("en",   1, DIR_M_TO_S),
			("rdy",  1, DIR_S_TO_M),
			("we",   1, DIR_M_TO_S)
			("addr", 8, DIR_M_TO_S),
			("di",  16, DIR_M_TO_S),
			("do",  16, DIR_S_TO_M)
		]
		Record.__init__(self, layout)
