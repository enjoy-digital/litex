import subprocess
import os

class Programmer:
	def __init__(self, flash_proxy_basename=None):
		self.flash_proxy_basename = flash_proxy_basename
		self.flash_proxy_dirs = ["~/.mlabs", "/usr/local/share/mlabs", "/usr/share/mlabs"]

	def set_flash_proxy_dir(self, flash_proxy_dir):
		if flash_proxy_dir is not None:
			self.flash_proxy_dirs = [flash_proxy_dir]

	def find_flash_proxy(self):
		for d in self.flash_proxy_dirs:
			fulldir = os.path.abspath(os.path.expanduser(d))
			fullname = os.path.join(fulldir, self.flash_proxy_basename)
			if os.path.exists(fullname):
				return fullname
		raise OSError("Failed to find flash proxy bitstream")

def _run_urjtag(cmds):
	with subprocess.Popen("jtag", stdin=subprocess.PIPE) as process:
		process.stdin.write(cmds.encode("ASCII"))
		process.communicate()

class UrJTAG(Programmer):
	needs_bitreverse = True

	def load_bitstream(self, bitstream_file):
		cmds = """cable milkymist
detect
pld load {bitstream}
quit
""".format(bitstream=bitstream_file)
		_run_urjtag(cmds)

	def flash(self, address, data_file):
		flash_proxy = self.find_flash_proxy()
		cmds = """cable milkymist
detect
pld load "{flash_proxy}"
initbus fjmem opcode=000010
frequency 6000000
detectflash 0
endian big
flashmem "{address}" "{data_file}" noverify
""".format(flash_proxy=flash_proxy, address=address, data_file=data_file)
		_run_urjtag(cmds)

class XC3SProg(Programmer):
	needs_bitreverse = False

	def __init__(self, cable, flash_proxy_basename=None):
		Programmer.__init__(self, flash_proxy_basename)
		self.cable = cable

	def load_bitstream(self, bitstream_file):
		subprocess.call(["xc3sprog", "-v", "-c", self.cable, bitstream_file])

	def flash(self, address, data_file):
		flash_proxy = self.find_flash_proxy()
		subprocess.call(["xc3sprog", "-v", "-c", self.cable, "-I"+flash_proxy, "{}:w:0x{:x}:BIN".format(data_file, address)])

class USBBlaster(Programmer):
	needs_bitreverse = False

	def load_bitstream(self, bitstream_file, port=0):
		usb_port = "[USB-"+str(port)+"]"
		subprocess.call(["quartus_pgm", "-m", "jtag", "-c", "USB-Blaster"+usb_port, "-o", "p;"+bitstream_file])

	def flash(self, address, data_file):
		raise NotImplementedError
