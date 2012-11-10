from migen.flow.actor import *

class Pytholite:
	def get_fragment(self):
		return self.fragment

class DFPytholite(Pytholite, Actor):
	pass

def make_io_object(dataflow=None):
	if dataflow is None:
		return Pytholite()
	else:
		return DFPytholite(dataflow)

