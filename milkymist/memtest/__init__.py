from migen.fhdl.std import *
from migen.genlib.misc import optree
from migen.bank.description import *
from migen.actorlib import dma_lasmi
from migen.actorlib.spi import MODE_SINGLE_SHOT, DMAReadController, DMAWriteController

class LFSR(Module):
	def __init__(self, n_out, n_state=31, taps=[27, 30]):
		self.ce = Signal()
		self.reset = Signal()
		self.o = Signal(n_out)

		###

		state = Signal(n_state)
		curval = [state[i] for i in range(n_state)]
		curval += [0]*(n_out - n_state)
		for i in range(n_out):
			nv = ~optree("^", [curval[tap] for tap in taps])
			curval.insert(0, nv)
			curval.pop()

		self.sync += If(self.reset,
				state.eq(0),
				self.o.eq(0)
			).Elif(self.ce,
				state.eq(Cat(*curval[:n_state])),
				self.o.eq(Cat(*curval))
			)

def _print_lfsr_code():
	from migen.fhdl import verilog
	dut = LFSR(3, 4, [3, 2])
	print(verilog.convert(dut, ios={dut.ce, dut.o}))

class _LFSRTB(Module):
	def __init__(self, *args, **kwargs):
		self.submodules.lfsr = LFSR(*args, **kwargs)
		self.comb += self.lfsr.ce.eq(1)

	def do_simulation(self, s):
		print(s.rd(self.lfsr.o))

def _sim_lfsr():
	from migen.sim.generic import Simulator
	tb = _LFSRTB(3, 4, [3, 2])
	sim = Simulator(tb)
	sim.run(20)

memtest_magic = 0x361f

class MemtestWriter(Module):
	def __init__(self, lasmim):
		self._r_magic = CSRStatus(16)
		self._r_reset = CSR()
		self.submodules._dma = DMAWriteController(dma_lasmi.Writer(lasmim), MODE_SINGLE_SHOT)

		###

		self.comb += self._r_magic.status.eq(memtest_magic)

		lfsr = LFSR(lasmim.dw)
		self.submodules += lfsr
		self.comb += lfsr.reset.eq(self._r_reset.re)

		self.comb += [
			self._dma.data.stb.eq(1),
			lfsr.ce.eq(self._dma.data.ack),
			self._dma.data.payload.d.eq(lfsr.o)
		]

	def get_csrs(self):
		return [self._r_magic, self._r_reset] + self._dma.get_csrs()

class MemtestReader(Module):
	def __init__(self, lasmim):
		self._r_magic = CSRStatus(16)
		self._r_reset = CSR()
		self._r_error_count = CSRStatus(lasmim.aw)
		self.submodules._dma = DMAReadController(dma_lasmi.Reader(lasmim), MODE_SINGLE_SHOT)

		###

		self.comb += self._r_magic.status.eq(memtest_magic)

		lfsr = LFSR(lasmim.dw)
		self.submodules += lfsr
		self.comb += lfsr.reset.eq(self._r_reset.re)

		self.comb += [
			lfsr.ce.eq(self._dma.data.stb),
			self._dma.data.ack.eq(1)
		]
		err_cnt = self._r_error_count.status
		self.sync += [
			If(self._r_reset.re,
				err_cnt.eq(0)
			).Elif(self._dma.data.stb,
				If(self._dma.data.payload.d != lfsr.o, err_cnt.eq(err_cnt + 1))
			)
		]

	def get_csrs(self):
		return [self._r_magic, self._r_reset, self._r_error_count] + self._dma.get_csrs()

if __name__ == "__main__":
	_print_lfsr_code()
	_sim_lfsr()
