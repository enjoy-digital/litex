from .structure import *
from .convtools import *
from functools import partial

def _printsig(ns, s):
	if s.bv.signed:
		n = "signed "
	else:
		n = ""
	if s.bv.width > 1:
		n += "[" + str(s.bv.width-1) + ":0] "
	n += ns.GetName(s)
	return n

def _printexpr(ns, node):
	if isinstance(node, Constant):
		if node.n >= 0:
			return str(node.bv) + str(node.n)
		else:
			return "-" + str(node.bv) + str(-self.n)
	elif isinstance(node, Signal):
		return ns.GetName(node)
	elif isinstance(node, Operator):
		arity = len(node.operands)
		if arity == 1:
			r = self.op + _printexpr(ns, node.operands[0])
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
	else:
		raise TypeError

def _printnode(ns, level, comb, node):
	if isinstance(node, Assign):
		if comb or IsVariable(node.l):
			assignment = " = "
		else:
			assignment = " <= "
		return "\t"*level + _printexpr(ns, node.l) + assignment + _printexpr(ns, node.r) + ";\n"
	elif isinstance(node, StatementList):
		return "".join(list(map(partial(_printnode, ns, level, comb), node.l)))
	elif isinstance(node, If):
		r = "\t"*level + "if (" + _printexpr(ns, node.cond) + ") begin\n"
		r += _printnode(ns, level + 1, comb, node.t)
		if node.f.l:
			r += "\t"*level + "end else begin\n"
			r += _printnode(ns, level + 1, comb, node.f)
		r += "\t"*level + "end\n"
		return r
	elif isinstance(node, Case):
		r = "\t"*level + "case (" + _printexpr(ns, node.test) + ")\n"
		for case in node.cases:
			r += "\t"*(level + 1) + _printexpr(ns, case[0]) + ": begin\n"
			r += _printnode(ns, level + 2, comb, case[1])
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
				if isinstance(p[1], int):
					r += str(p[1])
				elif isinstance(p[1], basestring):
					r += "\"" + p[1] + "\""
				else:
					raise TypeError
				r += ")"
			r += "\n) "
		r += ns.GetName(x) + "(\n"
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
			r += "\t." + p[0] + "(" + ns.GetName(p[1]) + ")"
		if not firstp:
			r += "\n"
		r += ");\n\n"
	return r

def Convert(f, ios=set(), name="top", clkname="sys_clk", rstname="sys_rst"):
	ns = Namespace()
	
	clks = Signal(name=clkname)
	rsts = Signal(name=rstname)

	sigs = ListSignals(f)
	targets = ListTargets(f)
	instouts = ListInstOuts(f)
	
	r = "/* Machine-generated using Migen */\n"
	r += "module " + name + "(\n"
	r += "\tinput " + ns.GetName(clks) + ",\n"
	r += "\tinput " + ns.GetName(rsts)
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
		r += _printnode(ns, 1, True, f.comb)
		r += "end\n\n"
	if f.sync.l:
		r += "always @(posedge " + ns.GetName(clks) + ") begin\n"
		r += _printnode(ns, 1, False, InsertReset(rsts, f.sync))
		r += "end\n\n"
	r += _printinstances(ns, f.instances, clks, rsts)
	
	r += "endmodule\n"
	
	return r