import subprocess

def _str2file(filename, contents):
	f = open(filename, "w")
	f.write(contents)
	f.close()

class Runner:
	def __init__(self, top_file="migensim_top.v", dut_file="migensim_dut.v", extra_files=None, vvp_file=None):
		if extra_files is None: extra_files = []
		if vvp_file is None: vvp_file = dut_file + "vp"
		self.top_file = top_file
		self.dut_file = dut_file
		self.extra_files = extra_files
		self.vvp_file = vvp_file
	
	def start(self, c_top, c_dut):
		_str2file(self.top_file, c_top)
		_str2file(self.dut_file, c_dut)
		subprocess.check_call(["iverilog", "-o", self.vvp_file, self.top_file, self.dut_file] + self.extra_files)
		subprocess.Popen(["vvp", "-mmigensim", self.vvp_file])
