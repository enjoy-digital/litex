import inspect
import re
from itertools import combinations

class NoContext:
	pass

def trace_back(name=None):
	l = []
	frame = inspect.currentframe().f_back.f_back
	while frame is not None:
		try:
			obj = frame.f_locals["self"]
		except KeyError:
			obj = None
		if obj is None or isinstance(obj, NoContext):
			modules = frame.f_globals["__name__"]
			modules = modules.split(".")
			obj = modules[len(modules)-1]
		
		if name is None:
			line = inspect.getframeinfo(frame).code_context[0]
			m = re.match("[\t ]*([0-9A-Za-z_\.]+)[\t ]*=", line)
			if m is None:
				name = None
			else:
				names = m.group(1).split(".")
				name = names[len(names)-1]
		l.insert(0, (obj, name))
		name = None
		frame = frame.f_back
	return l

class _StepNamer():
	def __init__(self):
		self.name_to_ids = {}
	
	def basename(self, obj):
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

	def name(self, step):
		n = self.basename(step[0])
		if step[1] is not None:
			n += "_" + step[1]
		return n

def _bin(sn, sig_iters):
	terminals = []
	bins = {}
	for signal, it in sig_iters:
		try:
			step = it.__next__()
		except StopIteration:
			terminals.append(signal)
		else:
			step_name = sn.name(step)
			if step_name not in bins:
				bins[step_name] = []
			bins[step_name].append((signal, it))
	return terminals, bins

def _r_build_pnd(sn, sig_iters):
	terminals, bins = _bin(sn, sig_iters)
	bins_named = [(k, _r_build_pnd(sn, v)) for k, v in bins.items()]
	name_sets = [set(sub_pnd.values()) for prefix, sub_pnd in bins_named]
	if name_sets:
		intersection = set.intersection(*name_sets)
	else:
		intersection = set()
	r = {}
	if intersection:
		for prefix, sub_pnd in bins_named:
			for s, n in sub_pnd.items():
				if n:
					r[s] = prefix + "_" + n
				else:
					r[s] = prefix
	else:
		for prefix, sub_pnd in bins_named:
			r.update(sub_pnd)
	for t in terminals:
		r[t] = ""
	return r

def build_pnd(signals):
	sig_iters = [(signal, iter(signal.backtrace))
	  for signal in signals]
	return _r_build_pnd(_StepNamer(), sig_iters)

class Namespace:
	def __init__(self, pnd):
		self.counts = {}
		self.sigs = {}
		self.pnd = pnd
	
	def get_name(self, sig):
		if sig.name_override is not None:
			sig_name = sig.name_override
		else:
			sig_name = self.pnd[sig]
		if not sig_name:
			sig_name = "anonymous"
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
