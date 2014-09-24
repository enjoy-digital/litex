from migen.fhdl.std import *
from migen.genlib.crc import CRC32
from migen.fhdl import verilog

class Example(Module):
	def __init__(self, width):
		crc32 = CRC32(width)
		self.submodules += crc32
		self.ios = {crc32.reset, crc32.ce,
					crc32.d, crc32.value, crc32.error}

example = Example(8)
print(verilog.convert(example, example.ios))
