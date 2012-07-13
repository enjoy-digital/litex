from migen.fhdl.structure import *
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
		r.append(v[offset:offset+n])
		offset += n
	return tuple(r)

def displacer(signal, shift, output, n=None, reverse=False):
	if n is None:
		n = 2**len(shift)
	w = len(signal)
	if reverse:
		r = reversed(range(n))
	else:
		r = range(n)
	l = [Replicate(shift == i, w) & signal for i in r]
	return output.eq(Cat(*l))

def chooser(signal, shift, output, n=None, reverse=False):
	if n is None:
		n = 2**len(shift)
	w = len(output)
	cases = []
	for i in range(n):
		if reverse:
			s = n - i - 1
		else:
			s = i
		cases.append([Constant(i, shift.bv), output.eq(signal[s*w:(s+1)*w])])
	cases[n-1][0] = Default()
	return Case(shift, *cases)

def timeline(trigger, events):
	lastevent = max([e[0] for e in events])
	counter = Signal(BV(bits_for(lastevent)))
	
	counterlogic = If(counter != Constant(0, counter.bv),
		counter.eq(counter + Constant(1, counter.bv))
	).Elif(trigger,
		counter.eq(Constant(1, counter.bv))
	)
	# insert counter reset if it doesn't naturally overflow
	# (test if lastevent+1 is a power of 2)
	if (lastevent & (lastevent + 1)) != 0:
		counterlogic = If(counter == lastevent,
			counter.eq(Constant(0, counter.bv))
		).Else(
			counterlogic
		)
	
	def get_cond(e):
		if e[0] == 0:
			return trigger & (counter == Constant(0, counter.bv))
		else:
			return counter == Constant(e[0], counter.bv)
	sync = [If(get_cond(e), *e[1]) for e in events]
	sync.append(counterlogic)
	return sync
