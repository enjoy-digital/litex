import re

def get_macros(filename):
	f = open(filename, "r")
	r = {}
	for line in f:
		match = re.match("\w*#define\s+(\w+)\s+(.*)", line, re.IGNORECASE)
		if match:
			r[match.group(1)] = match.group(2)
	return r
