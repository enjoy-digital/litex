# Simple Processor Interface

from migen.fhdl.std import *
from migen.bank.description import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.flow import plumbing
from migen.actorlib import misc
from migen.bank.eventmanager import *

# layout is a list of tuples, either:
# - (name, nbits, [reset value], [alignment bits])
# - (name, sublayout)

def _convert_layout(layout):
	r = []
	for element in layout:
		if isinstance(element[1], list):
			r.append((element[0], _convert_layout(element[1])))
		else:
			r.append((element[0], element[1]))
	return r

(MODE_EXTERNAL, MODE_SINGLE_SHOT, MODE_CONTINUOUS) = range(3)

class SingleGenerator(Module, AutoCSR):
	def __init__(self, layout, mode):
		self.source = Source(_convert_layout(layout))
		self.busy = Signal()
		
		self.comb += self.busy.eq(self.source.stb)

		if mode == MODE_EXTERNAL:
			self.trigger = Signal()
			trigger = self.trigger
		elif mode == MODE_SINGLE_SHOT:
			self._r_shoot = CSR()
			trigger = self._r_shoot.re
		elif mode == MODE_CONTINUOUS:
			self._r_enable = CSRStorage()
			trigger = self._r_enable.storage
		else:
			raise ValueError
		self.sync += If(self.source.ack | ~self.source.stb, self.source.stb.eq(trigger))

		self._create_csrs(layout, self.source.payload, mode != MODE_SINGLE_SHOT)

	def _create_csrs(self, layout, target, atomic, prefix=""):
		for element in layout:
			if isinstance(element[1], list):
				self._create_csrs(element[1], atomic,
					getattr(target, element[0]),
					element[0] + "_")
			else:
				name = element[0]
				nbits = element[1]
				if len(element) > 2:
					reset = element[2]
				else:
					reset = 0
				if len(element) > 3:
					alignment = element[3]
				else:
					alignment = 0
				regname = prefix + name
				reg = CSRStorage(nbits + alignment, reset=reset, atomic_write=atomic,
					alignment_bits=alignment, name=regname)
				setattr(self, "r_"+regname, reg)
				self.sync += If(self.source.ack | ~self.source.stb,
					getattr(target, name).eq(reg.storage))

class Collector(Module, AutoCSR):
	def __init__(self, layout, depth=1024):
		self.sink = Sink(layout)
		self.busy = Signal()
		dw = sum(len(s) for s in self.sink.payload.flatten())

		self._r_wa = CSRStorage(bits_for(depth-1), write_from_dev=True)
		self._r_wc = CSRStorage(bits_for(depth), write_from_dev=True, atomic_write=True)
		self._r_ra = CSRStorage(bits_for(depth-1))
		self._r_rd = CSRStatus(dw)
		
		###
	
		mem = Memory(dw, depth)
		self.specials += mem
		wp = mem.get_port(write_capable=True)
		rp = mem.get_port()
		self.specials += wp, rp
		
		self.comb += [
			self.busy.eq(0),

			If(self._r_wc.r != 0,
				self.sink.ack.eq(1),
				If(self.sink.stb,
					self._r_wa.we.eq(1),
					self._r_wc.we.eq(1),
					wp.we.eq(1)
				)
			),
			self._r_wa.dat_w.eq(self._r_wa.storage + 1),
			self._r_wc.dat_w.eq(self._r_wc.storage - 1),
			
			wp.adr.eq(self._r_wa.storage),
			wp.dat_w.eq(self.sink.payload.raw_bits()),
			
			rp.adr.eq(self._r_ra.storage),
			self._r_rd.status.eq(rp.dat_r)
		]

class _DMAController(Module):
	def __init__(self, bus_accessor, bus_aw, bus_dw, mode, base_reset=0, length_reset=0, generate_irq=False):
		self.alignment_bits = bits_for(bus_dw//8) - 1
		layout = [
			("length", bus_aw + self.alignment_bits, length_reset, self.alignment_bits),
			("base", bus_aw + self.alignment_bits, base_reset, self.alignment_bits)
		]
		self.generator = SingleGenerator(layout, mode)
		self.r_busy = CSRStatus()

		self.length = self.generator.r_length.storage
		self.base = self.generator.r_base.storage
		if hasattr(self.generator, "trigger"):
			self.trigger = self.generator.trigger

		self.generate_irq = generate_irq
		if generate_irq:
			self.submodules.ev = EventManager()
			self.ev.done = EventSourcePulse()
			self.ev.finalize()

			r_busy_d = Signal()

			self.sync += r_busy_d.eq(self.r_busy.status)
			self.comb += self.ev.done.trigger.eq(~self.r_busy.status & r_busy_d)


	def get_csrs(self):
		csrs = self.generator.get_csrs() + [self.r_busy]
		if self.generate_irq:
			csrs += self.ev.get_csrs()
		return csrs

class DMAReadController(_DMAController):
	def __init__(self, bus_accessor, *args, **kwargs):
		bus_aw = flen(bus_accessor.address.payload.a)
		bus_dw = flen(bus_accessor.data.payload.d)
		_DMAController.__init__(self, bus_accessor, bus_aw, bus_dw, *args, **kwargs)
		
		g = DataFlowGraph()
		g.add_pipeline(self.generator,
			misc.IntSequence(bus_aw, bus_aw),
			AbstractActor(plumbing.Buffer),
			bus_accessor,
			AbstractActor(plumbing.Buffer))
		comp_actor = CompositeActor(g)
		self.submodules += comp_actor

		self.data = comp_actor.q
		self.busy = comp_actor.busy
		self.comb += self.r_busy.status.eq(self.busy)

class DMAWriteController(_DMAController):
	def __init__(self, bus_accessor, *args, **kwargs):
		bus_aw = flen(bus_accessor.address_data.payload.a)
		bus_dw = flen(bus_accessor.address_data.payload.d)
		_DMAController.__init__(self, bus_accessor, bus_aw, bus_dw, *args, **kwargs)
		
		g = DataFlowGraph()
		adr_buffer = AbstractActor(plumbing.Buffer)
		g.add_pipeline(self.generator,
			misc.IntSequence(bus_aw, bus_aw),
			adr_buffer)
		g.add_connection(adr_buffer, bus_accessor, sink_subr=["a"])
		g.add_connection(AbstractActor(plumbing.Buffer), bus_accessor, sink_subr=["d"])
		comp_actor = CompositeActor(g)
		self.submodules += comp_actor

		self.data = comp_actor.d
		self.busy = comp_actor.busy
		self.comb += self.r_busy.status.eq(self.busy)
