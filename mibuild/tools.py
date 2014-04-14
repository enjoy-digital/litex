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

def write_to_file(filename, contents, force_unix=False):
	newline = None
	if force_unix:
		newline = "\n"
	f = open(filename, "w", newline=newline)
	f.write(contents)
	f.close()
