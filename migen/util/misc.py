import collections

def flat_iteration(l):
	for element in l:
		if isinstance(element, collections.Iterable):
			for element2 in flat_iteration(element):
				yield element2
		else:
			yield element

def xdir(obj, return_values=False):
	for attr in dir(obj):
		if attr[:2] != "__" and attr[-2:] != "__":
			if return_values:
				yield attr, getattr(obj, attr)
			else:
				yield attr

def autotype(s):
	if s == "True":
		return True
	elif s == "False":
		return False
	try:
		return int(s, 0)
	except ValueError:
		pass
	return s
