import subprocess

cables = {
	"mixxeo":		"milkymist",
	"m1":			"milkymist",
	"papilio_pro":	"Flyswatter"
}

def load(platform_name, bitstream):
	cmds = """cable {cable}
detect
pld load {bitstream}
quit
""".format(cable=cables[platform_name], bitstream=bitstream)
	process = subprocess.Popen("jtag", stdin=subprocess.PIPE)
	process.stdin.write(cmds.encode("ASCII"))
	process.communicate()

def flash(bitstream):
	subprocess.call(["m1nor-ng", bitstream])
