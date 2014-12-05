import random

from lib.sata.std import *

def seed_to_data(seed, random=True):
	if random:
		return (seed * 0x31415979 + 1) & 0xffffffff
	else:
		return seed

def check(ref, res):
	if isinstance(ref, int):
		return 0, 1, int(ref != res)
	else:
		shift = 0
		while((ref[0] != res[0]) and (len(res)>1)):
			res.pop(0)
			shift += 1
		length = min(len(ref), len(res))
		errors = 0
		for i in range(length):
			if ref.pop(0) != res.pop(0):
				errors += 1
		return shift, length, errors

def randn(max_n):
	return random.randint(0, max_n-1)

class AckRandomizer(Module):
	def __init__(self, description, level=0):
		self.level = level

		self.sink = Sink(description)
		self.source = Source(description)

		self.run = Signal()

		self.comb += \
			If(self.run,
				Record.connect(self.sink, self.source)
			).Else(
				self.source.stb.eq(0),
				self.sink.ack.eq(0),
			)

	def do_simulation(self, selfp):
		n = randn(100)
		if n < self.level:
			selfp.run = 0
		else:
			selfp.run = 1
