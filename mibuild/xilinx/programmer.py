import subprocess

from mibuild.generic_programmer import GenericProgrammer

def _run_urjtag(cmds):
	with subprocess.Popen("jtag", stdin=subprocess.PIPE) as process:
		process.stdin.write(cmds.encode("ASCII"))
		process.communicate()

class UrJTAG(GenericProgrammer):
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

class XC3SProg(GenericProgrammer):
	needs_bitreverse = False

	def __init__(self, cable, flash_proxy_basename=None):
		Programmer.__init__(self, flash_proxy_basename)
		self.cable = cable

	def load_bitstream(self, bitstream_file):
		subprocess.call(["xc3sprog", "-v", "-c", self.cable, bitstream_file])

	def flash(self, address, data_file):
		flash_proxy = self.find_flash_proxy()
		subprocess.call(["xc3sprog", "-v", "-c", self.cable, "-I"+flash_proxy, "{}:w:0x{:x}:BIN".format(data_file, address)])
