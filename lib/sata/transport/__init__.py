from lib.sata.std import *
from lib.sata.transport.std import *

class SATATransportLayerTX(Module):
	def __init__(self):
		self.sink = Sink(transport_layout(32))

class SATATransportLayerRX(Module):
	def __init__(self):
		self.sink = Sink(transport_layout(32))

class SATATransportLayer(Module):
	def __init__(self):
		self.submodules.tx = SATATransportLayerTX()
		self.submodules.rx = SATATransportLayerRX()
