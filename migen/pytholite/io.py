import ast

from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.actorlib.sim import *
from migen.pytholite.fsm import *

class Pytholite:
	def get_fragment(self):
		return self.fragment

class DFPytholite(Pytholite, Actor):
	pass

def make_io_object(dataflow=None):
	if dataflow is None:
		return Pytholite()
	else:
		return DFPytholite(*dataflow)

def gen_df_io(compiler, to_model, from_model):
	if len(to_model) == 1 or len(to_model) == 2:
		epname = ast.literal_eval(to_model[0])
		ep = compiler.ioo.endpoints[epname]
	else:
		raise TypeError("Token() takes 1 or 2 arguments")
	
	if len(to_model) == 1:
		# token pull from sink
		raise NotImplementedError # TODO
	else:
		# token push to source
		if from_model:
			raise TypeError("Attempted to read from pushed token")
		d = to_model[1]
		if not isinstance(d, ast.Dict):
			raise NotImplementedError
		state = []
		for akey, value in zip(d.keys, d.values):
			key = ast.literal_eval(akey)
			signal = getattr(ep.token, key)
			state.append(signal.eq(compiler.ec.visit_expr(value)))
		state += [
			ep.stb.eq(1),
			If(~ep.ack, AbstractNextState(state))
		]
		return [state], [state]

def gen_io(compiler, model, to_model, from_model):
	if model == Token:
		return gen_df_io(compiler, to_model, from_model)
	else:
		raise NotImplementedError
