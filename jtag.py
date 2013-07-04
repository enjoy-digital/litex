import subprocess

def load(bitstream):
	cmds = """cable milkymist
detect
pld load {bitstream}
quit
""".format(bitstream=bitstream)
	process = subprocess.Popen("jtag", stdin=subprocess.PIPE)
	process.stdin.write(cmds.encode("ASCII"))
	process.communicate()

def flash(bitstream):
	subprocess.call(["m1nor-ng", bitstream])
