from itertools import combinations

from migen.fhdl.structure import *

class _StepNamer:
	def __init__(self):
		self.name_to_ids = {}
	
	def get_step_str(self, obj):
		if isinstance(obj, str):
			return obj
		else:
			n = obj.__class__.__name__.lower()
			try:
				l = self.name_to_ids[n]
			except KeyError:
				self.name_to_ids[n] = [id(obj)]
				return n + "0"
			else:
				try:
					idx = l.index(id(obj))
				except ValueError:
					idx = len(l)
					l.append(id(obj))
				return n + str(idx)

def _bin(sn, sig_iters):
	status = []
	for signal, it in sig_iters:
		step, last = next(it)
		status.append((signal, it, step, last))
	terminals = []
	bins = {}
	for signal, it, step, last in status:
		step_name = sn.get_step_str(step)
		if last:
			terminals.append((step_name, signal))
		else:
			if step_name not in bins:
				bins[step_name] = []
			bins[step_name].append((signal, it))
	return terminals, bins

def _sets_disjoint(l):
	for s1, s2 in combinations(l, 2):
		if not s1.isdisjoint(s2):
			return False
	return True
	
def _r_build_pnd(sn, sig_iters):
	terminals, bins = _bin(sn, sig_iters)
	bins_named = [(k, _r_build_pnd(sn, v)) for k, v in bins.items()]
	name_sets = [set(sub_pnd.values()) for prefix, sub_pnd in bins_named]
	r = {}
	if not _sets_disjoint(name_sets):
		for prefix, sub_pnd in bins_named:
			for s, n in sub_pnd.items():
				r[s] = prefix + "_" + n
	else:
		for prefix, sub_pnd in bins_named:
			r.update(sub_pnd)
	for n, s in terminals:
		r[s] = n
	return r

def last_flagged(seq):
	seq = iter(seq)
	a = next(seq)
	for b in seq:
		yield a, False
		a = b
	yield a, True

def build_namespace(signals):
	sig_iters = [(signal, last_flagged(signal.backtrace))
	  for signal in signals if signal.name_override is None]
	pnd = _r_build_pnd(_StepNamer(), sig_iters)
	ns = Namespace(pnd)
	# register signals with name_override
	for signal in signals:
		if signal.name_override is not None:
			ns.get_name(signal)
	return ns

class Namespace:
	def __init__(self, pnd):
		self.counts = {}
		self.sigs = {}
		self.pnd = pnd
	
	def get_name(self, sig):
		if isinstance(sig, Memory):
			sig_name = "mem"
		else:
			if sig.name_override is not None:
				sig_name = sig.name_override
			else:
				sig_name = self.pnd[sig]
		try:
			n = self.sigs[sig]
		except KeyError:
			try:
				n = self.counts[sig_name]
			except KeyError:
				n = 0
			self.sigs[sig] = n
			self.counts[sig_name] = n + 1
		if n:
			return sig_name + "_" + str(n)
		else:
			return sig_name
