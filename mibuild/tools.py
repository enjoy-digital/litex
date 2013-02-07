import os

def mkdir_noerror(d):
	try:
		os.mkdir(d)
	except OSError:
		pass

def write_to_file(filename, contents):
	f = open(filename, "w")
	f.write(contents)
	f.close()
