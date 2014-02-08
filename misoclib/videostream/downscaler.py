from migen.fhdl.std import *
from migen.genlib.fsm import *
from migen.genlib.record import Record
from migen.genlib.misc import optree
from migen.sim.generic import run_simulation

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

class Compacter(Module):
	def __init__(self, base_layout, N):
		self.i = Record([("w"+str(i), base_layout) for i in range(N)])
		self.sel = Signal(N)

		self.o = Record([("w"+str(i), base_layout) for i in range(N)])
		self.count = Signal(max=N+1)

		###

		def set_word(wn, selstart):
			if wn >= N or selstart >= N:
				return
			r = None
			for i in reversed(range(selstart, N)):
				r = If(self.sel[i],
					getattr(self.o, "w"+str(wn)).eq(getattr(self.i, "w"+str(i))),
					set_word(wn+1, i+1)
				).Else(r)
			return r
		self.sync += set_word(0, 0)
		self.sync += self.count.eq(optree("+", [self.sel[i] for i in range(N)]))

class Packer(Module):
	def __init__(self, base_layout, N):
		assert(N & (N - 1) == 0) # only support powers of 2

		self.i = Record([("w"+str(i), base_layout) for i in range(N)])
		self.count = Signal(max=N+1)

		self.o = Record([("w"+str(i), base_layout) for i in range(N)])
		self.stb = Signal()

		###

		buf = Record([("w"+str(i), base_layout) for i in range(2*N)])
		
		wrp = Signal(max=2*N)
		wrp_next = Signal(max=2*N)
		self.comb += wrp_next.eq(wrp + self.count)
		self.sync += [
			wrp.eq(wrp_next), self.stb.eq(wrp_next[-1] ^ wrp[-1]),
			Case(wrp, {i: [getattr(buf, "w"+str(j + i & 2*N - 1)).eq(getattr(self.i, "w"+str(j))) for j in range(N)] for i in range(2*N)})
		]

		rdp = Signal()
		self.sync += If(self.stb, rdp.eq(~rdp))
		self.comb += If(rdp, 
				[getattr(self.o, "w"+str(i)).eq(getattr(buf, "w"+str(i+N))) for i in range(N)]
			).Else(
				[getattr(self.o, "w"+str(i)).eq(getattr(buf, "w"+str(i))) for i in range(N)]
			)

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

	def gen_simulation(self, selfp):
		dut = selfp.dut

		print("initializing chopper...")
		dut.init = 1
		dut.p = 320
		dut.q = 681
		yield
		dut.init = 0
		yield
		while not dut.ready:
			yield
		print("done")

		dut.next = 1
		yield
		ones = 0
		niter = 681
		for i in range(niter):
			#print("{:04b}".format(dut.chopper))
			ones += _count_ones(dut.chopper)
			yield
		print("Ones: {} (expected: {})".format(ones, dut.p*niter*4//dut.q))

class _CompacterPackerTB(Module):
	def __init__(self, input_it):
		self.input_it = input_it
		self.output = []
		self.end_cycle = -1

		self.submodules.compacter = Compacter(16, 4)
		self.submodules.packer = Packer(16, 4)
		self.comb += self.packer.i.eq(self.compacter.o), self.packer.count.eq(self.compacter.count)

	def do_simulation(self, selfp):
		if selfp.simulator.cycle_counter == self.end_cycle:
			raise StopSimulation

		# push values
		sel = 0
		for i in range(4):
			try:
				value, keep = next(self.input_it)
			except StopIteration:
				value, keep = 0, 0
				if self.end_cycle == -1:
					self.end_cycle = selfp.simulator.cycle_counter + 3
			sel |= int(keep) << i
			setattr(selfp.compacter.i, "w"+str(i), value)
		selfp.compacter.sel = sel

		# pull values
		if selfp.packer.stb:
			for i in range(4):
				self.output.append(getattr(selfp.packer.o, "w"+str(i)))


if __name__ == "__main__":
	print("*** Testing chopper ***")
	run_simulation(_ChopperTB())

	print("*** Testing compacter and packer ***")
	test_seq = [
		(42, 0), (32, 1), ( 4, 1), (21, 0),
		(43, 1), (11, 1), ( 5, 1), (18, 0),
		(71, 0), (70, 1), (30, 1), (12, 1),
		( 3, 1), (12, 1), (21, 1), (10, 0),
		( 1, 1), (87, 0), (72, 0), (12, 0)
	]
	tb = _CompacterPackerTB(iter(test_seq))
	run_simulation(tb)
	print("got:      " + str(tb.output))
	print("expected: " + str([value for value, keep in test_seq if keep]))
