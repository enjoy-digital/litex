from migen.fhdl.std import *
from migen.genlib.fsm import *

class Chopper(Module):
	def __init__(self, N, frac_bits):
		self.init = Signal()
		self.ready = Signal()
		self.next = Signal()
		self.p = Signal(frac_bits)
		self.q = Signal(frac_bits)
		self.chopper = Signal(N)

		###

		# initialization counter
		ic = Signal(frac_bits)
		ic_overflow = Signal()
		ic_inc = Signal()
		self.sync += \
			If(self.init,
				ic.eq(0),
				ic_overflow.eq(1)
			).Elif(ic_inc,
				If(ic + self.p >= self.q,
					ic.eq(ic + self.p - self.q),
					ic_overflow.eq(1)
				).Else(
					ic.eq(ic + self.p),
					ic_overflow.eq(0)
				)
			)

		# computed N*p mod q
		Np = Signal(frac_bits)
		load_np = Signal()
		self.sync += If(load_np, Np.eq(ic))

		fsm = FSM()
		self.submodules += fsm
		fsm.act("IDLE",
			self.ready.eq(1),
			If(self.init, NextState(0))
		)

		prev_acc_r = Signal(frac_bits)
		prev_acc = prev_acc_r
		for i in range(N):
			acc = Signal(frac_bits)

			# pipeline stage 1: update accumulators
			load_init_acc = Signal()
			self.sync += \
				If(load_init_acc,
					acc.eq(ic)
				).Elif(self.next,
					If(acc + Np >= Cat(self.q, 0), # FIXME: workaround for imbecilic Verilog extension rules, needs to be put in Migen backend
						acc.eq(acc + Np - self.q),
					).Else(
						acc.eq(acc + Np)
					)
				)

			# pipeline stage 2: detect overflows and generate chopper signal
			load_init_chopper = Signal()
			self.sync += \
				If(load_init_chopper,
					self.chopper[i].eq(ic_overflow)
				).Elif(self.next,
					self.chopper[i].eq(prev_acc >= acc)
				)
			if i == N-1:
				self.sync += \
					If(load_init_chopper,
						prev_acc_r.eq(ic)	
					).Elif(self.next,
						prev_acc_r.eq(acc)
					)
			prev_acc = acc

			# initialize stage 2
			fsm.act(i, 
				load_init_chopper.eq(1),
				ic_inc.eq(1),
				NextState(i + 1)
			)
			# initialize stage 1
			fsm.act(N + i,
				load_init_acc.eq(1),
				ic_inc.eq(1),
				NextState(N + i + 1) if i < N-1 else NextState("IDLE")
			)
		# initialize Np
		fsm.act(N, load_np.eq(1))

def _count_ones(n):
	r = 0
	while n:
		if n & 1:
			r += 1
		n >>= 1
	return r

class _ChopperTB(Module):
	def __init__(self):
		self.submodules.dut = Chopper(4, 16)

	def gen_simulation(self, s):
		from migen.sim.generic import Proxy
		dut = Proxy(s, self.dut)

		dut.init = 1
		dut.p = 320
		dut.q = 681
		yield
		dut.init = 0
		yield
		while not dut.ready:
			print("waiting")
			yield
		print("done")

		dut.next = 1
		yield
		ones = 0
		niter = 681
		for i in range(niter):
			print("{:04b}".format(dut.chopper))
			ones += _count_ones(dut.chopper)
			yield
		print("Ones: {} (expected: {})".format(ones, dut.p*niter*4//dut.q))

if __name__ == "__main__":
	from migen.sim.generic import Simulator
	with Simulator(_ChopperTB()) as s:
		s.run(1000)
