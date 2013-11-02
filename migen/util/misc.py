def xdir(obj, return_values=False):
	for attr in dir(obj):
		if attr[:2] != "__" and attr[-2:] != "__":
			if return_values:
				yield attr, getattr(obj, attr)
			else:
				yield attr
