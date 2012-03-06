import subprocess
import os

def _str2file(filename, contents):
	f = open(filename, "w")
	f.write(contents)
	f.close()

class Runner:
	def __init__(self, extra_files=None, top_file="migensim_top.v", dut_file="migensim_dut.v", vvp_file=None, keep_files=False):
		if extra_files is None: extra_files = []
		if vvp_file is None: vvp_file = dut_file + "vp"
		self.extra_files = extra_files
		self.top_file = top_file
		self.dut_file = dut_file
		self.vvp_file = vvp_file
		self.keep_files = keep_files
	
	def start(self, c_top, c_dut):
		_str2file(self.top_file, c_top)
		_str2file(self.dut_file, c_dut)
		subprocess.check_call(["iverilog", "-o", self.vvp_file, self.top_file, self.dut_file] + self.extra_files)
		self.process = subprocess.Popen(["vvp", "-mmigensim", self.vvp_file])

	def __del__(self):
		if hasattr(self, "process"):
			self.process.wait()
		if not self.keep_files:
			for f in [self.top_file, self.dut_file, self.vvp_file]:
				try:
					os.remove(f)
				except OSError:
					pass
