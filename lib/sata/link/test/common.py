def seed_to_data(seed, random=True):
	if random:
		return (seed * 0x31415979 + 1) & 0xffffffff
	else:
		return seed

def check(ref, res):
	if isinstance(ref, int):
		return 0, 1, int(ref != res)
	else:
		shift = 0
		while((ref[0] != res[0]) and (len(res)>1)):
			res.pop(0)
			shift += 1
		length = min(len(ref), len(res))
		errors = 0
		for i in range(length):
			if ref.pop(0) != res.pop(0):
				errors += 1
		return shift, length, errors
