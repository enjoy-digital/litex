from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _ArrayProxy

# y <= y + a + b
#
# unroll_sync(sync, {b: [b1, b2], c: [c1, c2]}, {y: [y1, y2]})
#
# ==>
#
# v_y1 = y2 + a1 + b1
# v_y2 = v_y1 + a2 + b2
# y1 <= v_y1
# y2 <= v_y2

(_UNDETERMINED, _IN, _OUT) = range(3)

# TODO: arrays

def _replace_if_in(d, s):
	try:
		return d[s]
	except KeyError:
		return s

def _replace(node, rin, rout, mode=_UNDETERMINED):
	if isinstance(node, Constant):
		return node
	elif isinstance(node, Signal):
		if mode == _IN:
			return _replace_if_in(rin, node)
		elif mode == _OUT:
			return _replace_if_in(rout, node)
		else:
			raise ValueError
	elif isinstance(node, _Operator):
		rop = [_replace(op, rin, rout, mode) for op in node.operands]
		return _Operator(node.op, rop)
	elif isinstance(node, _Slice):
		return _Slice(_replace(node.value, rin, rout, mode), node.start, node.stop)
	elif isinstance(node, Cat):
		rcomp = [_replace(comp, rin, rout, mode) for comp in node.l]
		return Cat(*rcomp)
	elif isinstance(node, Replicate):
		return Replicate(_replace(node.v, rin, rout, mode), node.n)
	elif isinstance(node, _Assign):
		return _Assign(_replace(node.l, rin, rout, _OUT), _replace(node.r, rin, rout, _IN))
	elif isinstance(node, list):
		return [_replace(s, rin, rout) for s in node]
	elif isinstance(node, If):
		r = If(_replace(node.cond, rin, rout, _IN))
		r.t = _replace(node.t, rin, rout)
		r.f = _replace(node.f, rin, rout)
		return r
	elif isinstance(node, Case):
		r = Case(_replace(case.test, rin, rout, _IN))
		r.cases = [(c[0], _replace(c[1], rin, rout)) for c in node.cases]
		r.default = _replace(node.default, rin, rout)
		return r
	else:
		raise TypeError

def _list_step_dicts(d):
	iterdict = dict((k, iter(v)) for k, v in d.items())
	r = []
	try:
		while True:
			r.append(dict([(k, next(i)) for k, i in iterdict.items()]))
	except StopIteration:
		pass
	return r

def _variable_for(s, n):
	sn = s.backtrace[-1][0]
	if isinstance(sn, str):
		name = "v" + str(n) + "_" + sn
	else:
		name = "v"
	return Signal(s.bv, name=name, variable=True)

def unroll_sync(sync, inputs, outputs):
	sd_in = _list_step_dicts(inputs)
	sd_out = _list_step_dicts(outputs)
	
	do_var_old = sd_out[-1]
	r = []
	for n, (di, do) in enumerate(zip(sd_in, sd_out)):
		do_var = dict((k, _variable_for(v, n)) for k, v in do.items())
		di_plus_do_var_old = di.copy()
		di_plus_do_var_old.update(do_var_old)
		r += _replace(sync, di_plus_do_var_old, do_var)
		r += [v.eq(do_var[k]) for k, v in do.items()]
		do_var_old = do_var
	
	return r
