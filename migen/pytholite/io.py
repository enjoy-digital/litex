import ast

from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.actorlib.sim import *
from migen.pytholite.fsm import *
from migen.pytholite.expr import ExprCompiler

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

class _TokenPullExprCompiler(ExprCompiler):
	def __init__(self, symdict, modelname, ep):
		super().__init__(symdict)
		self.modelname = modelname
		self.ep = ep
	
	def visit_expr_subscript(self, node):
		# check that we are subscripting <modelname>.value
		if not isinstance(node.value, ast.Attribute) \
		  or node.value.attr != "value" \
		  or not isinstance(node.value.value, ast.Name) \
		  or node.value.value.id != self.modelname:
			raise NotImplementedError
		
		if not isinstance(node.slice, ast.Index):
			raise NotImplementedError
		field = ast.literal_eval(node.slice.value)
		signal = getattr(self.ep.token, field)
		
		return signal

def gen_df_io(compiler, modelname, to_model, from_model):
	if len(to_model) == 1 or len(to_model) == 2:
		epname = ast.literal_eval(to_model[0])
		ep = compiler.ioo.endpoints[epname]
	else:
		raise TypeError("Token() takes 1 or 2 arguments")
	
	if len(to_model) == 1:
		# token pull from sink
		if not isinstance(ep, Sink):
			raise TypeError("Attempted to pull from source")
		ec = _TokenPullExprCompiler(compiler.symdict, modelname, ep)
		state = []
		for target_regs, expr in from_model:
			cexpr = ec.visit_expr(expr)
			state += [reg.load(cexpr) for reg in target_regs]
		state += [
			ep.ack.eq(1),
			If(~ep.stb, AbstractNextState(state))
		]
		return [state], [state]
	else:
		# token push to source
		if not isinstance(ep, Source):
			raise TypeError("Attempted to push to sink")
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

def gen_io(compiler, modelname, model, to_model, from_model):
	if model == Token:
		return gen_df_io(compiler, modelname, to_model, from_model)
	else:
		raise NotImplementedError
