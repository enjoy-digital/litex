from collections import OrderedDict

from migen.fhdl.std import *
from migen.fhdl.std import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.record import *
from migen.genlib.fsm import FSM, NextState
from migen.flow.actor import EndpointDescription
from migen.flow.actor import Sink, Source
from migen.actorlib.structuring import Converter, Pipeline
from migen.actorlib.fifo import SyncFIFO, AsyncFIFO
from migen.bank.description import *

eth_mtu = 1532
eth_preamble = 0xD555555555555555
buffer_depth = 2**log2_int(eth_mtu, need_pow2=False)

def eth_phy_description(dw):
	layout = [
		("data", dw),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)

def eth_mac_description(dw):
	layout = [
		("data", dw),
		("last_be", dw//8),
		("error", dw//8)
	]
	return EndpointDescription(layout, packetized=True)
