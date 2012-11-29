from functools import partial
from operator import itemgetter

from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign
from migen.fhdl.tools import *
from migen.fhdl.namer import Namespace, build_namespace
from migen.fhdl import verilog_mem_behavioral

def _printsig(ns, s):
	if s.signed:
		n = "signed "
	else:
		n = ""
	if len(s) > 1:
		n += "[" + str(len(s)-1) + ":0] "
	n += ns.get_name(s)
	return n

def _printintbool(node):
	if isinstance(node, bool):
		if node:
			return "1'd1", False
		else:
			return "1'd0", False
	elif isinstance(node, int):
		if node >= 0:
			return str(bits_for(node)) + "'d" + str(node), False
		else:
			return "-" + str(bits_for(node)) + "'sd" + str(-node), True
	else:
		raise TypeError

def _printexpr(ns, node):
	if isinstance(node, (int, bool)):
		return _printintbool(node)
	elif isinstance(node, Signal):
		return ns.get_name(node), node.signed
	elif isinstance(node, _Operator):
		arity = len(node.operands)
		r1, s1 = _printexpr(ns, node.operands[0])
		if arity == 1:
			if node.op == "-":
				if s1:
					r = node.op + r1
				else:
					r = "-$signed({1'd0, " + r1 + "})"
				s = True
			else:
				r = node.op + r1
				s = s1
		elif arity == 2:
			r2, s2 = _printexpr(ns, node.operands[1])
			if node.op in ["+", "-", "*", "&", "^", "|"]:
				if s2 and not s1:
					r1 = "$signed({1'd0, " + r1 + "})"
				if s1 and not s2:
					r2 = "$signed({1'd0, " + r2 + "})"
			r = r1 + " " + node.op + " " + r2
			s = s1 or s2
		else:
			raise TypeError
		return "(" + r + ")", s
	elif isinstance(node, _Slice):
		# Verilog does not like us slicing non-array signals...
		if isinstance(node.value, Signal) \
		  and len(node.value) == 1 \
		  and node.start == 0 and node.stop == 1:
			  return _printexpr(ns, node.value)

		if node.start + 1 == node.stop:
			sr = "[" + str(node.start) + "]"
		else:
			sr = "[" + str(node.stop-1) + ":" + str(node.start) + "]"
		r, s = _printexpr(ns, node.value)
		return r + sr, s
	elif isinstance(node, Cat):
		l = [_printexpr(ns, v)[0] for v in reversed(node.l)]
		return "{" + ", ".join(l) + "}", False
	elif isinstance(node, Replicate):
		return "{" + str(node.n) + "{" + _printexpr(ns, node.v)[0] + "}}", False
	else:
		raise TypeError

(_AT_BLOCKING, _AT_NONBLOCKING, _AT_SIGNAL) = range(3)

def _printnode(ns, at, level, node):
	if node is None:
		return ""
	elif isinstance(node, _Assign):
		if at == _AT_BLOCKING:
			assignment = " = "
		elif at == _AT_NONBLOCKING:
			assignment = " <= "
		elif is_variable(node.l):
			assignment = " = "
		else:
			assignment = " <= "
		return "\t"*level + _printexpr(ns, node.l)[0] + assignment + _printexpr(ns, node.r)[0] + ";\n"
	elif isinstance(node, list):
		return "".join(list(map(partial(_printnode, ns, at, level), node)))
	elif isinstance(node, If):
		r = "\t"*level + "if (" + _printexpr(ns, node.cond)[0] + ") begin\n"
		r += _printnode(ns, at, level + 1, node.t)
		if node.f:
			r += "\t"*level + "end else begin\n"
			r += _printnode(ns, at, level + 1, node.f)
		r += "\t"*level + "end\n"
		return r
	elif isinstance(node, Case):
		if node.cases:
			r = "\t"*level + "case (" + _printexpr(ns, node.test)[0] + ")\n"
			css = sorted([(k, v) for (k, v) in node.cases.items() if k != "default"], key=itemgetter(0))
			for choice, statements in css:
				r += "\t"*(level + 1) + _printexpr(ns, choice)[0] + ": begin\n"
				r += _printnode(ns, at, level + 2, statements)
				r += "\t"*(level + 1) + "end\n"
			if "default" in node.cases:
				r += "\t"*(level + 1) + "default: begin\n"
				r += _printnode(ns, at, level + 2, node.cases["default"])
				r += "\t"*(level + 1) + "end\n"
			r += "\t"*level + "endcase\n"
			return r
		else:
			return ""
	else:
		raise TypeError

def _list_comb_wires(f):
	r = set()
	groups = group_by_targets(f.comb)
	for g in groups:
		if len(g[1]) == 1 and isinstance(g[1][0], _Assign):
			r |= g[0]
	return r

def _printheader(f, ios, name, ns):
	sigs = list_signals(f) | list_inst_ios(f, True, True, True) | list_mem_ios(f, True, True)
	inst_mem_outs = list_inst_ios(f, False, True, False) | list_mem_ios(f, False, True)
	inouts = list_inst_ios(f, False, False, True)
	targets = list_targets(f) | inst_mem_outs
	wires = _list_comb_wires(f) | inst_mem_outs
	r = "module " + name + "(\n"
	firstp = True
	for sig in sorted(ios, key=lambda x: x.huid):
		if not firstp:
			r += ",\n"
		firstp = False
		if sig in inouts:
			r += "\tinout " + _printsig(ns, sig)
		elif sig in targets:
			if sig in wires:
				r += "\toutput " + _printsig(ns, sig)
			else:
				r += "\toutput reg " + _printsig(ns, sig)
		else:
			r += "\tinput " + _printsig(ns, sig)
	r += "\n);\n\n"
	for sig in sorted(sigs - ios, key=lambda x: x.huid):
		if sig in wires:
			r += "wire " + _printsig(ns, sig) + ";\n"
		else:
			r += "reg " + _printsig(ns, sig) + ";\n"
	r += "\n"
	return r

def _printcomb(f, ns, display_run):
	r = ""
	if f.comb:
		# Generate a dummy event to get the simulator
		# to run the combinatorial process once at the beginning.
		syn_off = "// synthesis translate off\n"
		syn_on = "// synthesis translate on\n"
		dummy_s = Signal(name_override="dummy_s")
		r += syn_off
		r += "reg " + _printsig(ns, dummy_s) + ";\n"
		r += "initial " + ns.get_name(dummy_s) + " <= 1'd0;\n"
		r += syn_on
		
		groups = group_by_targets(f.comb)
		
		for n, g in enumerate(groups):
			if len(g[1]) == 1 and isinstance(g[1][0], _Assign):
				r += "assign " + _printnode(ns, _AT_BLOCKING, 0, g[1][0])
			else:
				dummy_d = Signal(name_override="dummy_d")
				r += "\n" + syn_off
				r += "reg " + _printsig(ns, dummy_d) + ";\n"
				r += syn_on
				
				r += "always @(*) begin\n"
				if display_run:
					r += "\t$display(\"Running comb block #" + str(n) + "\");\n"
				for t in g[0]:
					r += "\t" + ns.get_name(t) + " <= " + _printexpr(ns, t.reset)[0] + ";\n"
				r += _printnode(ns, _AT_NONBLOCKING, 1, g[1])
				r += syn_off
				r += "\t" + ns.get_name(dummy_d) + " <= " + ns.get_name(dummy_s) + ";\n"
				r += syn_on
				r += "end\n"
	r += "\n"
	return r

def _printsync(f, ns, clock_domains):
	r = ""
	for k, v in sorted(f.sync.items(), key=itemgetter(0)):
		r += "always @(posedge " + ns.get_name(clock_domains[k].clk) + ") begin\n"
		r += _printnode(ns, _AT_SIGNAL, 1, insert_reset(clock_domains[k].rst, v))
		r += "end\n\n"
	return r

def _printinstances(f, ns, clock_domains):
	r = ""
	for x in f.instances:
		parameters = list(filter(lambda i: isinstance(i, Instance.Parameter), x.items))
		r += x.of + " "
		if parameters:
			r += "#(\n"
			firstp = True
			for p in parameters:
				if not firstp:
					r += ",\n"
				firstp = False
				r += "\t." + p.name + "("
				if isinstance(p.value, (int, bool)):
					r += _printintbool(p.value)[0]
				elif isinstance(p.value, float):
					r += str(p.value)
				elif isinstance(p.value, str):
					r += "\"" + p.value + "\""
				else:
					raise TypeError
				r += ")"
			r += "\n) "
		r += ns.get_name(x) 
		if parameters: r += " "
		r += "(\n"
		firstp = True
		for p in x.items:
			if isinstance(p, Instance._IO):
				name_inst = p.name
				name_design = _printexpr(ns, p.expr)[0]
			elif isinstance(p, Instance.ClockPort):
				name_inst = p.name_inst
				name_design = ns.get_name(clock_domains[p.domain].clk)
				if p.invert:
					name_design = "~" + name_design
			elif isinstance(p, Instance.ResetPort):
				name_inst = p.name_inst
				name_design = ns.get_name(clock_domains[p.domain].rst)
			else:
				continue
			if not firstp:
				r += ",\n"
			firstp = False
			r += "\t." + name_inst + "(" + name_design + ")"
		if not firstp:
			r += "\n"
		r += ");\n\n"
	return r

def _printmemories(f, ns, handler, clock_domains):
	r = ""
	for memory in f.memories:
		r += handler(memory, ns, clock_domains)
	return r

def _printinit(f, ios, ns):
	r = ""
	signals = list_signals(f) \
		- ios \
		- list_targets(f) \
		- list_inst_ios(f, False, True, False) \
		- list_mem_ios(f, False, True)
	if signals:
		r += "initial begin\n"
		for s in sorted(signals, key=lambda x: x.huid):
			r += "\t" + ns.get_name(s) + " <= " + _printexpr(ns, s.reset)[0] + ";\n"
		r += "end\n\n"
	return r

def convert(f, ios=set(), name="top",
  clock_domains=None,
  return_ns=False,
  memory_handler=verilog_mem_behavioral.handler,
  display_run=False):
	if clock_domains is None:
		clock_domains = dict()
		for d in f.get_clock_domains():
			cd = ClockDomain(d)
			clock_domains[d] = cd
			ios.add(cd.clk)
			ios.add(cd.rst)
		
	f = lower_arrays(f)

	ns = build_namespace(list_signals(f) \
		| list_inst_ios(f, True, True, True) \
		| list_mem_ios(f, True, True) \
		| ios)

	r = "/* Machine-generated using Migen */\n"
	r += _printheader(f, ios, name, ns)
	r += _printcomb(f, ns, display_run)
	r += _printsync(f, ns, clock_domains)
	r += _printinstances(f, ns, clock_domains)
	r += _printmemories(f, ns, memory_handler, clock_domains)
	r += _printinit(f, ios, ns)
	r += "endmodule\n"

	if return_ns:
		return r, ns
	else:
		return r
