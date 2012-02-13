from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator

def multimux(sel, inputs, output):
	n = len(inputs)
	i = 0
	statements = []
	for osig in output:
		choices = [x[i] for x in inputs]
		cases = [[Constant(j, sel.bv), osig.eq(choices[j])] for j in range(n)]
		cases[n-1][0] = Default()
		statements.append(Case(sel, *cases))
		i += 1
	return statements

def optree(op, operands, lb=None, ub=None, default=None):
	if lb is None:
		lb = 0
	if ub is None:
		ub = len(operands)
	l = ub - lb
	if l == 0:
		if default is None:
			raise AttributeError
		else:
			return default
	elif l == 1:
		return operands[lb]
	else:
		s = lb + l//2
		return _Operator(op,
			[optree(op, operands, lb, s, default),
			optree(op, operands, s, ub, default)])

def split(v, *counts):
	r = []
	offset = 0
	for n in counts:
		r.append(v[offset:offset+n])
		offset += n
	return tuple(r)

def displacer(signal, shift, output, n=None):
	if n is None:
		n = 2**shift.bv.width
	w = signal.bv.width
	l = [Replicate(shift == i, w) & signal for i in range(n)]
	return output.eq(Cat(*l))

def chooser(signal, shift, output, n=None):
	if n is None:
		n = 2**shift.bv.width
	w = output.bv.width
	cases = [[Constant(i, shift.bv), output.eq(signal[i*w:(i+1)*w])] for i in range(n)]
	cases[n-1][0] = Default()
	return Case(shift, *cases)
