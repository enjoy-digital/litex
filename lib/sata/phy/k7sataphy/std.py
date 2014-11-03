from migen.fhdl.std import *
from migen.genlib.record import *

ALIGN_VAL   = 0x7B4A4ABC
SYNC_VAL    = 0xB5B5957C

def ones(width):
	return 2**width-1
