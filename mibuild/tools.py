import os

def mkdir_noerror(d):
	try:
		os.mkdir(d)
	except OSError:
		pass

def language_by_filename(name):
	extension = name.rsplit(".")[-1] 
	if extension in ["v", "vh", "vo"]:
		return "verilog"
	if extension in ["vhd", "vhdl", "vho"]:
		return "vhdl"
	return None

def write_to_file(filename, contents):
	f = open(filename, "w")
	f.write(contents)
	f.close()
