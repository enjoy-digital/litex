import ast

from migen.flow.actor import *
from migen.actorlib.sim import *

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


def gen_io(compiler, model, to_model, from_model):
	print(model)
	for arg in to_model:
		print(ast.dump(arg))
	return [], []
