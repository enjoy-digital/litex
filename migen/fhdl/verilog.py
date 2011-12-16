from functools import partial

from migen.fhdl.structure import *
from migen.fhdl.convtools import *

def _printsig(ns, s):
	if s.bv.signed:
		n = "signed "
	else:
		n = ""
	if s.bv.width > 1:
		n += "[" + str(s.bv.width-1) + ":0] "
	n += ns.get_name(s)
	return n

def _printexpr(ns, node):
	if isinstance(node, Constant):
		if node.n >= 0:
			return str(node.bv) + str(node.n)
		else:
			return "-" + str(node.bv) + str(-self.n)
	elif isinstance(node, Signal):
		return ns.get_name(node)
	elif isinstance(node, Operator):
		arity = len(node.operands)
		if arity == 1:
			r = node.op + _printexpr(ns, node.operands[0])
		elif arity == 2:
			r = _printexpr(ns, node.operands[0]) + " " + node.op + " " + _printexpr(ns, node.operands[1])
		else:
			raise TypeError
		return "(" + r + ")"
	elif isinstance(node, Slice):
		if node.start + 1 == node.stop:
			sr = "[" + str(node.start) + "]"
		else:
			sr = "[" + str(node.stop-1) + ":" + str(node.start) + "]"
		return _printexpr(ns, node.value) + sr
	elif isinstance(node, Cat):
		l = list(map(partial(_printexpr, ns), node.l))
		l.reverse()
		return "{" + ", ".join(l) + "}"
	elif isinstance(node, Replicate):
		return "{" + str(node.n) + "{" + _printexpr(ns, node.v) + "}}"
	else:
		raise TypeError

def _printnode(ns, level, node):
	if isinstance(node, Assign):
		if is_variable(node.l):
			assignment = " = "
		else:
			assignment = " <= "
		return "\t"*level + _printexpr(ns, node.l) + assignment + _printexpr(ns, node.r) + ";\n"
	elif isinstance(node, StatementList):
		return "".join(list(map(partial(_printnode, ns, level), node.l)))
	elif isinstance(node, If):
		r = "\t"*level + "if (" + _printexpr(ns, node.cond) + ") begin\n"
		r += _printnode(ns, level + 1, node.t)
		if node.f.l:
			r += "\t"*level + "end else begin\n"
			r += _printnode(ns, level + 1, node.f)
		r += "\t"*level + "end\n"
		return r
	elif isinstance(node, Case):
		r = "\t"*level + "case (" + _printexpr(ns, node.test) + ")\n"
		for case in node.cases:
			r += "\t"*(level + 1) + _printexpr(ns, case[0]) + ": begin\n"
			r += _printnode(ns, level + 2, case[1])
			r += "\t"*(level + 1) + "end\n"
		if node.default.l:
			r += "\t"*(level + 1) + "default: begin\n"
			r += _printnode(ns, level + 2, node.default)
			r += "\t"*(level + 1) + "end\n"
		r += "\t"*level + "endcase\n"
		return r
	else:
		raise TypeError

def _printinstances(ns, i, clk, rst):
	r = ""
	for x in i:
		r += x.of + " "
		if x.parameters:
			r += "#(\n"
			firstp = True
			for p in x.parameters:
				if not firstp:
					r += ",\n"
				firstp = False
				r += "\t." + p[0] + "("
				if isinstance(p[1], int) or isinstance(p[1], Constant):
					r += str(p[1])
				elif isinstance(p[1], str):
					r += "\"" + p[1] + "\""
				else:
					raise TypeError
				r += ")"
			r += "\n) "
		r += ns.get_name(x) 
		if x.parameters: r += " "
		r += "(\n"
		ports = list(x.ins.items()) + list(x.outs.items())
		if x.clkport:
			ports.append((x.clkport, clk))
		if x.rstport:
			ports.append((x.rstport, rst))
		firstp = True
		for p in ports:
			if not firstp:
				r += ",\n"
			firstp = False
			r += "\t." + p[0] + "(" + ns.get_name(p[1]) + ")"
		if not firstp:
			r += "\n"
		r += ");\n\n"
	return r

def Convert(f, ios=set(), name="top", clkname="sys_clk", rstname="sys_rst", ns=None):
	if ns is None: ns = Namespace()

	clks = Signal(name=clkname)
	rsts = Signal(name=rstname)

	ios |= f.pads

	sigs = list_signals(f)
	targets = list_targets(f)
	instouts = list_inst_outs(f)
	
	r = "/* Machine-generated using Migen */\n"
	r += "module " + name + "(\n"
	r += "\tinput " + ns.get_name(clks) + ",\n"
	r += "\tinput " + ns.get_name(rsts)
	for sig in ios:
		if sig in targets:
			r += ",\n\toutput reg " + _printsig(ns, sig)
		elif sig in instouts:
			r += ",\n\toutput " + _printsig(ns, sig)
		else:
			r += ",\n\tinput " + _printsig(ns, sig)
	r += "\n);\n\n"
	for sig in sigs - ios:
		if sig in instouts:
			r += "wire " + _printsig(ns, sig) + ";\n"
		else:
			r += "reg " + _printsig(ns, sig) + ";\n"
	r += "\n"
	
	if f.comb.l:
		r += "always @(*) begin\n"
		r += _printnode(ns, 1, f.comb)
		r += "end\n\n"
	if f.sync.l:
		r += "always @(posedge " + ns.get_name(clks) + ") begin\n"
		r += _printnode(ns, 1, insert_reset(rsts, f.sync))
		r += "end\n\n"
	r += _printinstances(ns, f.instances, clks, rsts)
	
	r += "endmodule\n"
	
	return r