from itertools import combinations
from collections import defaultdict

from migen.fhdl.structure import *
from migen.fhdl.tracer import index_id

def _bin(sig_iters):
	# advance by one in the trace of each signal
	status = []
	for signal, it in sig_iters:
		step, last = next(it)
		status.append((signal, it, step, last))
	
	# build bins accordingly
	bins = defaultdict(lambda: defaultdict(list))
	for signal, it, (stepname, stepidx), last in status:
		if last:
			it = None
		bins[stepname][stepidx].append((signal, it))

	r = []
	# merge bins when all step indices differ
	for stepname, stepname_d in bins.items():
		if all(len(content) == 1 for content in stepname_d.values()):
			r.append((stepname, [(stepidx, signal, it)
				for stepidx, stepidx_d in stepname_d.items()
				for signal, it in stepidx_d]))
		else:
			for stepidx, stepidx_d in stepname_d.items():
				r.append((stepname, [(stepidx, signal, it)
					for signal, it in stepidx_d]))
	
	#for stepname, content in r:
		#print("Bin: " + stepname)
		#for stepidx, signal, it in content:
			#print("   stepidx:" + str(stepidx) + " " + str(signal) + " " + str(it))
	#print("++++++++++")
	
	return r

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
	
	for stepname, next_steps in bins:
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
				subname = (prefix, subname)
				subnames[signal] = subname
				mentions[subname].append(signal)
	else:
		for prefix, sub_pnd in bins_named:
			for signal, subname in sub_pnd.items():
				subname = ("", subname)
				subnames[signal] = subname
				mentions[subname].append(signal)
	
	# Sort lists of mentions by step indices
	for v in mentions.values():
		v.sort(key=lambda x: stepindices[x])
	
	r = {}
	for stepname, next_steps in bins:
		for stepidx, signal, it in next_steps:
			if it is None:
				name = stepname
				prefix = ""
			else:
				prefix = subnames[signal][0]
				name = subnames[signal][1]
			mention = mentions[(prefix, name)]
			if prefix:
				if len(mention) > 1:
					r[signal] = prefix + str(index_id(mention, signal)) + "_" + name
				else:
					r[signal] = prefix + "_" + name
			else:
				if len(mention) > 1:
					r[signal] = name + str(index_id(mention, signal))
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
