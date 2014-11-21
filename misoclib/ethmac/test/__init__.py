import random

from migen.fhdl.std import *
from migen.flow.actor import Sink, Source

from misoclib.ethmac.common import *

class PacketStreamer(Module):
	def __init__(self, data):
		self.source = Source(eth_description(8))
		self.data = data

	def gen_simulation(self, selfp):
		for n, data in enumerate(self.data):
			selfp.source.stb = 1
			selfp.source.sop = (n == 0)
			selfp.source.eop = (n == len(self.data)-1)
			selfp.source.payload.d = data
			yield
			while selfp.source.ack == 0:
				yield
			selfp.source.stb = 0
			while random.getrandbits(1):
				yield

class PacketLogger(Module):
	def __init__(self):
		self.sink = Sink(eth_description(8))
		self.data = []

	def do_simulation(self, selfp):
		selfp.sink.ack = bool(random.getrandbits(1))
		if selfp.sink.stb and selfp.sink.ack:
			self.data.append(selfp.sink.payload.d)

def print_results(s, l1, l2):
	def comp(l1, l2):
		r = True
		try:
			for i, val in enumerate(l1):
				if val != l2[i]:
					print(s + " : val : {:02X}, exp : {:02X}".format(val, l2[i]))
					r = False
		except:
			r = False
		return r

	c = comp(l1, l2)
	r = s + " "
	if c:
		r += "[OK]"
	else:
		r += "[KO]"
	print(r)
