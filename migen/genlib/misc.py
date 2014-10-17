from migen.fhdl.std import *
from migen.fhdl.structure import _Operator

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
		if n != 0:
			r.append(v[offset:offset+n])
		else:
			r.append(None)
		offset += n
	return tuple(r)

def displacer(signal, shift, output, n=None, reverse=False):
	if shift is None:
		return output.eq(signal)
	if n is None:
		n = 2**flen(shift)
	w = flen(signal)
	if reverse:
		r = reversed(range(n))
	else:
		r = range(n)
	l = [Replicate(shift == i, w) & signal for i in r]
	return output.eq(Cat(*l))

def chooser(signal, shift, output, n=None, reverse=False):
	if shift is None:
		return output.eq(signal)
	if n is None:
		n = 2**flen(shift)
	w = flen(output)
	cases = {}
	for i in range(n):
		if reverse:
			s = n - i - 1
		else:
			s = i
		cases[i] = [output.eq(signal[s*w:(s+1)*w])]
	return Case(shift, cases).makedefault()

def timeline(trigger, events):
	lastevent = max([e[0] for e in events])
	counter = Signal(max=lastevent+1)

	counterlogic = If(counter != 0,
		counter.eq(counter + 1)
	).Elif(trigger,
		counter.eq(1)
	)
	# insert counter reset if it doesn't naturally overflow
	# (test if lastevent+1 is a power of 2)
	if (lastevent & (lastevent + 1)) != 0:
		counterlogic = If(counter == lastevent,
			counter.eq(0)
		).Else(
			counterlogic
		)

	def get_cond(e):
		if e[0] == 0:
			return trigger & (counter == 0)
		else:
			return counter == e[0]
	sync = [If(get_cond(e), *e[1]) for e in events]
	sync.append(counterlogic)
	return sync
