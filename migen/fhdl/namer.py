from collections import OrderedDict
from itertools import combinations

from migen.fhdl.structure import *

class _Node:
	def __init__(self):
		self.use_name = False
		self.children = OrderedDict()

def _build_tree(signals):
	root = _Node()
	for signal in signals:
		current = root
		for name, number in signal.backtrace:
			try:
				current = current.children[name]
			except KeyError:
				new = _Node()
				current.children[name] = new
				current = new
	return root

def _set_use_name(node, node_name=""):
	if not node.children:
		node.use_name = True
		return {(node_name, )}
	else:
		cnames = [(k, _set_use_name(v, k)) for k, v in node.children.items()]
		for (c1_prefix, c1_names), (c2_prefix, c2_names) in combinations(cnames, 2):
			if not c1_names.isdisjoint(c2_names):
				node.children[c1_prefix].use_name = True
				node.children[c2_prefix].use_name = True
		r = set()
		for c_prefix, c_names in cnames:
			if node.children[c_prefix].use_name:
				for c_name in c_names:
					r.add((c_prefix, ) + c_name)
			else:
				r |= c_names
		return r

def _display_tree(tree):
	from migen.graph.treeviz import RenderNode
	
	def _to_render_node(name, node):
		children = [_to_render_node(k, v) for k, v in node.children.items()]
		if node.use_name:
			color = (0.8, 0.5, 0.9)
		else:
			color = (0.8, 0.8, 0.8)
		return RenderNode(name, children, color=color)

	top = _to_render_node("top", tree)
	top.to_svg("names.svg")

def _name_signal(tree, signal):
	elements = []
	treepos = tree
	for step_name, step_n in signal.backtrace:
		treepos = treepos.children[step_name]
		if treepos.use_name:
			elements.append(step_name)
	return "_".join(elements)

def _build_pnd(tree, signals):
	return dict((signal, _name_signal(tree, signal)) for signal in signals)
	
def build_namespace(signals):
	tree = _build_tree(signals)
	_set_use_name(tree)
	_display_tree(tree)
	pnd = _build_pnd(tree, signals)
	
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
