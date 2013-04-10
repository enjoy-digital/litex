import ast
from itertools import zip_longest

from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.genlib.ioo import UnifiedIOObject
from migen.flow.actor import Source, Sink
from migen.flow.transactions import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.pytholite.fsm import *
from migen.pytholite.expr import ExprCompiler

class Pytholite(UnifiedIOObject):
	def __init__(self, dataflow=None, buses={}):
		UnifiedIOObject.__init__(self, dataflow, buses)
		if dataflow is not None:
			self.busy.reset = 1
		self.memory_ports = dict((mem, mem.get_port(write_capable=True, we_granularity=8))
			for mem in self.buses.values() if isinstance(mem, Memory))
	
	def get_fragment(self):
		return UnifiedIOObject.get_fragment(self) + self.fragment

class _TokenPullExprCompiler(ExprCompiler):
	def __init__(self, symdict, modelname, ep):
		ExprCompiler.__init__(self, symdict)
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
		signal = getattr(self.ep.payload, field)
		
		return signal

def _gen_df_io(compiler, modelname, to_model, from_model):
	epname = ast.literal_eval(to_model["endpoint"])
	values = to_model["value"]
	idle_wait = ast.literal_eval(to_model["idle_wait"])
	ep = getattr(compiler.ioo, epname)
	if idle_wait:
		state = [compiler.ioo.busy.eq(0)]
	else:
		state = []
	
	if isinstance(values, ast.Name) and values.id == "None":
		# token pull from sink
		if not isinstance(ep, Sink):
			raise TypeError("Attempted to pull from source")
		ec = _TokenPullExprCompiler(compiler.symdict, modelname, ep)
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
		if not isinstance(values, ast.Dict):
			raise NotImplementedError
		for akey, value in zip(values.keys, values.values):
			key = ast.literal_eval(akey)
			signal = getattr(ep.payload, key)
			state.append(signal.eq(compiler.ec.visit_expr(value)))
		state += [
			ep.stb.eq(1),
			If(~ep.ack, AbstractNextState(state))
		]
		return [state], [state]

class _BusReadExprCompiler(ExprCompiler):
	def __init__(self, symdict, modelname, data_signal):
		ExprCompiler.__init__(self, symdict)
		self.modelname = modelname
		self.data_signal = data_signal
	
	def visit_expr_attribute(self, node):
		# recognize <modelname>.data as the bus read signal, raise exception otherwise
		if not isinstance(node.value, ast.Name) \
		  or node.value.id != self.modelname \
		  or node.attr != "data":
			raise NotImplementedError
		return self.data_signal

def _gen_wishbone_io(compiler, modelname, model, to_model, from_model, bus):
	state = [
		bus.cyc.eq(1),
		bus.stb.eq(1),
		bus.adr.eq(compiler.ec.visit_expr(to_model["address"])),
	]
	
	if model == TWrite:
		if from_model:
			raise TypeError("Attempted to read from write transaction")
		state += [
			bus.we.eq(1),
			bus.dat_w.eq(compiler.ec.visit_expr(to_model["data"]))
		]
		sel = to_model["sel"]
		if isinstance(sel, ast.Name) and sel.id == "None":
			nbytes = (len(bus.dat_w) + 7)//8
			state.append(bus.sel.eq(2**nbytes-1))
		else:
			state.append(bus.sel.eq(compiler.ec.visit_expr(sel)))
	else:
		ec = _BusReadExprCompiler(compiler.symdict, modelname, bus.dat_r)
		for target_regs, expr in from_model:
			cexpr = ec.visit_expr(expr)
			state += [reg.load(cexpr) for reg in target_regs]
	state.append(If(~bus.ack, AbstractNextState(state)))
	return [state], [state]

def _gen_memory_io(compiler, modelname, model, to_model, from_model, port):
	s1 = [port.adr.eq(compiler.ec.visit_expr(to_model["address"]))]
	if model == TWrite:
		if from_model:
			raise TypeError("Attempted to read from write transaction")
		s1.append(port.dat_w.eq(compiler.ec.visit_expr(to_model["data"])))
		sel = to_model["sel"]
		if isinstance(sel, ast.Name) and sel.id == "None":
			nbytes = (len(port.dat_w) + 7)//8
			s1.append(port.we.eq(2**nbytes-1))
		else:
			s1.append(port.we.eq(compiler.ec.visit_expr(sel)))
		return [s1], [s1]
	else:
		s2 = []
		s1.append(AbstractNextState(s2))
		ec = _BusReadExprCompiler(compiler.symdict, modelname, port.dat_r)
		for target_regs, expr in from_model:
			cexpr = ec.visit_expr(expr)
			s2 += [reg.load(cexpr) for reg in target_regs]
		return [s1, s2], [s2]

def _gen_bus_io(compiler, modelname, model, to_model, from_model):
	busname = ast.literal_eval(to_model["busname"])
	if busname is None:
		if len(compiler.ioo.buses) != 1:
			raise TypeError("Bus name not specified")
		bus = list(compiler.ioo.buses.values())[0]
	else:
		bus = compiler.ioo.buses[busname]
	if isinstance(bus, wishbone.Interface):
		return _gen_wishbone_io(compiler, modelname, model, to_model, from_model, bus)
	elif isinstance(bus, Memory):
		port = compiler.ioo.memory_ports[bus]
		return _gen_memory_io(compiler, modelname, model, to_model, from_model, port)
	else:
		raise NotImplementedError("Unsupported bus")

def _decode_args(desc, args, args_kw):
	d = {}
	argnames = set()
	for param, value in zip_longest(desc, args):
		if param is None:
			raise TypeError("Too many arguments")
		if isinstance(param, tuple):
			name, default = param
		else:
			name, default = param, None
		
		# build the set of argument names at the same time
		argnames.add(name)
		
		if value is None:
			if default is None:
				raise TypeError("No default value for parameter " + name)
			else:
				d[name] = default
		else:
			d[name] = value
	for akw in args_kw:
		if akw.arg not in argnames:
			raise TypeError("Parameter " + akw.arg + " does not exist")
		d[akw.arg] = akw.value
	return d

def gen_io(compiler, modelname, model, to_model, to_model_kw, from_model):
	if model == Token:
		desc = [
			"endpoint",
			("value", ast.Name("None", ast.Load())),
			("idle_wait", ast.Name("False", ast.Load()))
		]
		args = _decode_args(desc, to_model, to_model_kw)
		return _gen_df_io(compiler, modelname, args, from_model)
	elif model == TRead or model == TWrite:
		desc = [
			"address",
			("data", ast.Num(0)),
			("sel", ast.Name("None", ast.Load())),
			("busname", ast.Name("None", ast.Load()))
		]
		args = _decode_args(desc, to_model, to_model_kw)
		return _gen_bus_io(compiler, modelname, model, args, from_model)
	else:
		raise NotImplementedError
