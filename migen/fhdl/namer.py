from itertools import combinations
from collections import defaultdict

from migen.fhdl.structure import *
from migen.fhdl.tracer import index_id

def _bin(sig_iters):
	# advance by one in the trace of each signal
	status = []
	for signal, it in sig_iters:
		if it is not None:
			step, last = next(it)
			status.append((signal, it, step, last))
	
	# build bins accordingly
	bins = defaultdict(list)
	for signal, it, (stepname, stepidx), last in status:
		if last:
			it = None
		bins[stepname].append((stepidx, signal, it))
	return bins

def _sets_disjoint(l):
	for s1, s2 in combinations(l, 2):
		if not s1.isdisjoint(s2):
			return False
	return True

# sig_iters contains a list of tuples (signal, iterator on the current trace position)
def _r_build_pnd(sig_iters):
	bins = _bin(sig_iters)
	
	subnames = {}
	mentions = defaultdict(list)
	bins_named = []
	stepindices = {}
	
	for stepname, next_steps in bins.items():
		bin_content = []
		for stepidx, signal, it in next_steps:
			if it is None:
				mentions[stepname].append(signal)
			else:
				bin_content.append((signal, it))
			stepindices[signal] = stepidx
		if bin_content:
			bins_named.append((stepname, _r_build_pnd(bin_content)))
	
	name_sets = [set(sub_pnd.values()) for prefix, sub_pnd in bins_named]
	if not _sets_disjoint(name_sets):
		for prefix, sub_pnd in bins_named:
			for signal, subname in sub_pnd.items():
				subname = prefix + "_" + subname
				subnames[signal] = subname
				mentions[subname].append(signal)
	else:
		for prefix, sub_pnd in bins_named:
			for signal, subname in sub_pnd.items():
				subnames[signal] = subname
				mentions[subname].append(signal)
	
	# Sort lists of mentions by step indices
	for v in mentions.values():
		v.sort(key=lambda x: stepindices[x])
	
	r = {}
	for stepname, next_steps in bins.items():
		for stepidx, signal, it in next_steps:
			if it is None:
				name = stepname
			else:
				name = subnames[signal]
			if len(mentions[name]) > 1:
				r[signal] = name + str(index_id(mentions[name], signal))
			else:
				r[signal] = name
	
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
	pnd = _r_build_pnd(sig_iters)
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
