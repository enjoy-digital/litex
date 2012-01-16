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

def obj_name(obj):
	if isinstance(obj, str):
		return obj
	else:
		return obj.__class__.__name__.lower()

class TreeNode:
	def __init__(self, name):
		self.name = name
		self.ids = {}
		self.children = []
		self.include_context = False
		self.include_varname = False
	
def add_to_tree(root, backtrace):
	for step in backtrace:
		n = obj_name(step[0])
		found = list(filter(lambda x: x.name == n, root.children))
		if found:
			node = found[0]
		else:
			node = TreeNode(n)
			root.children.append(node)
		if not isinstance(step[0], str) and id(step[0]) not in node.ids:
			node.ids[id(step[0])] = len(node.ids)
		root = node

def build_tree(signals):
	t = TreeNode("root")
	for signal in signals:
		if signal.name_override is None:
			add_to_tree(t, signal.backtrace)
	return t

def name_backtrace(root, backtrace):
	parts = []
	for step in backtrace[:-1]:
		n = obj_name(step[0])
		found = list(filter(lambda x: x.name == n, root.children))
		node = found[0]
		if node.include_context:
			if len(node.ids) > 1:
				parts.append(node.name + str(node.ids[id(step[0])]))
			else:
				parts.append(node.name)
		if node.include_varname and step[1] is not None:
			parts.append(step[1])
		root = node
	last = backtrace[-1]
	if last[1] is not None:
		parts.append(last[1])
	else:
		parts.append(obj_name(last[0]))
	return "_".join(parts)

def _include_divergence(root, bt1, bt2):
	for step1, step2 in zip(bt1, bt2):
		n1, n2 = obj_name(step1[0]), obj_name(step2[0])
		node1 = list(filter(lambda x: x.name == n1, root.children))[0]
		node2 = list(filter(lambda x: x.name == n2, root.children))[0]
		if node1 != node2:
			node1.include_context = True
			node2.include_context = True
			return
		if not isinstance(step1[0], str) and not isinstance(step2[0], str) \
		  and id(step1[0]) != id(step2[0]):
			node1.include_context = True
			return
		if step1[1] is not None and step2[1] is not None \
		  and step1[1] != step2[1]:
			  node1.include_varname = True
			  return
		root = node1

def resolve_conflicts(root, signals):
	for s1, s2 in combinations(signals, 2):
		if name_backtrace(root, s1.backtrace) == name_backtrace(root, s2.backtrace):
			_include_divergence(root, s1.backtrace, s2.backtrace)

def build_tree_res(signals):
	t = build_tree(signals)
	resolve_conflicts(t, signals)
	return t

def signal_name(root, sig):
	if sig.name_override is not None:
		return sig.name_override
	else:
		return name_backtrace(root, sig.backtrace)

class Namespace:
	def __init__(self, tree):
		self.counts = {}
		self.sigs = {}
		self.tree = tree
	
	def get_name(self, sig):
		sig_name = signal_name(self.tree, sig)
		try:
			n = self.sigs[sig]
			if n:
				return sig_name + "_" + str(n)
			else:
				return sig_name
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
