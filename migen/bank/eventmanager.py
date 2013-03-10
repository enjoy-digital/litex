from migen.fhdl.structure import *
from migen.fhdl.module import Module
from migen.bank.description import *
from migen.genlib.misc import optree

class _EventSource(HUID):
	def __init__(self):
		HUID.__init__(self)
		self.trigger = Signal()
		self.pending = Signal()

class EventSourcePulse(_EventSource):
	pass

class EventSourceLevel(_EventSource):
	pass

class EventManager(Module, AutoReg):
	def __init__(self):
		self.irq = Signal()
	
	def do_finalize(self):
		sources_u = [v for v in self.__dict__.values() if isinstance(v, _EventSource)]
		sources = sorted(sources_u, key=lambda x: x.huid)
		n = len(sources)
		self.status = RegisterRaw("status", n)
		self.pending = RegisterRaw("pending", n)
		self.enable = RegisterFields("enable",
		  [Field("s" + str(i), access_bus=READ_WRITE, access_dev=READ_ONLY) for i in range(n)])

		# status
		for i, source in enumerate(sources):
			if isinstance(source, EventSourcePulse):
				self.comb += self.status.w[i].eq(0)
			elif isinstance(source, EventSourceLevel):
				self.comb += self.status.w[i].eq(source.trigger)
			else:
				raise TypeError
		
		# pending
		for i, source in enumerate(sources):
			# W1C
			self.sync += If(self.pending.re & self.pending.r[i], source.pending.eq(0))
			if isinstance(source, EventSourcePulse):
				# set on a positive trigger pulse
				self.sync += If(source.trigger, source.pending.eq(1))
			elif isinstance(source, EventSourceLevel):
				# set on the falling edge of the trigger
				old_trigger = Signal()
				self.sync += [
					old_trigger.eq(source.trigger),
					If(~source.trigger & old_trigger, source.pending.eq(1))
				]
			else:
				raise TypeError
			self.comb += self.pending.w[i].eq(source.pending)
		
		# IRQ
		irqs = [self.pending.w[i] & field.r for i, field in enumerate(self.enable.fields)]
		self.comb += self.irq.eq(optree("|", irqs))

	def __setattr__(self, name, value):
		if isinstance(value, _EventSource) and self.finalized:
			raise FinalizeError
		object.__setattr__(self, name, value)
