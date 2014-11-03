from migen.fhdl.std import *

def phy_layout(dw):
	layout = [
		("p_packetized", True),
		("d", dw)
	]
	return layout
