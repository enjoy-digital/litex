from migen.fhdl.std import *
from migen.flow.actor import EndpointDescription

eth_mtu = 1532
eth_preamble = 0xD555555555555555
buffer_depth = 2**log2_int(eth_mtu, need_pow2=False)

def eth_description(dw):
	layout = [
		("d", dw),
		("last_be", dw//8),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)
