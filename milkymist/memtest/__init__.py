from migen.fhdl.std import *
from migen.genlib.misc import optree
from migen.fhdl import verilog

class LFSR(Module):
	def __init__(self, n_out, n_state=31, taps=[27, 30]):
		self.ce = Signal()
		self.o = Signal(n_out)

		###

		state = Signal(n_state)
		curval = [state[i] for i in range(n_state)]
		curval += [0]*(n_out - n_state)
		for i in range(n_out):
			nv = optree("^", [curval[tap] for tap in taps])
			curval.insert(0, nv)
			curval.pop()

		self.sync += If(self.ce,
				state.eq(Cat(*curval[:n_state])),
				self.o.eq(Cat(*curval))
			)

def _printcode():
	dut = LFSR(3, 4, [3, 2])
	print(verilog.convert(dut, ios={dut.ce, dut.o}))

if __name__ == "__main__":
	_printcode()
